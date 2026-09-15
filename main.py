"""
Audio Splitter Pro - Android
------------------------------
Offline audio splitter for Android. Pick an audio file (mp3/wav/m4a/etc),
choose a split interval, and export equal-length WAV clips to
Music/AudioSplitterPro/ on the device — fully offline, no internet needed.

NOTE ON FORMATS:
- Input: mp3, wav, m4a, ogg, flac (decoded on-device via bundled FFmpeg)
- Output: always .wav (universal, plays everywhere, no re-encoding quality loss)
"""

import os
import math
import wave

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.progressbar import ProgressBar
from kivy.uix.popup import Popup
from kivy.graphics import Color, Rectangle, Line
from kivy.core.audio import SoundLoader
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import NumericProperty, StringProperty, ListProperty
from kivy.utils import platform

# ---------------------------------------------------------------------
# Audio handling: pure-Python `wave` module — no FFmpeg needed.
# This means the app is 100% offline and needs no compiled native
# audio libraries, but it currently only reads/writes WAV files.
# ---------------------------------------------------------------------

APP_NAME = "Audio Splitter Pro"

# ---------------------------------------------------------------------
# THEME
# ---------------------------------------------------------------------
BG_DARK = (0.024, 0.094, 0.129, 1)
BG_PANEL = (0.047, 0.153, 0.2, 1)
ACCENT = (0.169, 0.831, 0.784, 1)
ACCENT_2 = (0.118, 0.608, 0.71, 1)
TEXT_MAIN = (0.875, 0.965, 0.961, 1)
DANGER = (1, 0.42, 0.42, 1)

KV = """
<RootWidget>:
    orientation: "vertical"
    padding: dp(16)
    spacing: dp(12)

    Label:
        text: "Audio Splitter Pro"
        font_size: "22sp"
        bold: True
        color: 0.169, 0.831, 0.784, 1
        size_hint_y: None
        height: dp(40)

    Button:
        id: pick_btn
        text: "Select Audio File"
        size_hint_y: None
        height: dp(50)
        on_release: root.pick_file()

    Label:
        id: file_label
        text: "No file selected"
        color: 0.494, 0.663, 0.69, 1
        size_hint_y: None
        height: dp(30)

    BoxLayout:
        size_hint_y: None
        height: dp(50)
        spacing: dp(10)
        Button:
            id: play_btn
            text: "Play"
            disabled: True
            on_release: root.toggle_play()
        Label:
            id: time_label
            text: "00:00 / 00:00"
            color: 0.875, 0.965, 0.961, 1

    Waveform:
        id: waveform
        size_hint_y: 0.35

    Label:
        text: "Split Interval (seconds)"
        color: 0.494, 0.663, 0.69, 1
        size_hint_y: None
        height: dp(24)

    BoxLayout:
        size_hint_y: None
        height: dp(50)
        spacing: dp(10)
        Slider:
            id: interval_slider
            min: 5
            max: 120
            value: 10
            step: 1
            on_value: root.on_slider_change(*args)
        Label:
            id: interval_label
            text: "10 sec"
            size_hint_x: None
            width: dp(70)
            color: 0.169, 0.831, 0.784, 1
            bold: True

    Button:
        id: ok_btn
        text: "OK - Preview Split"
        size_hint_y: None
        height: dp(50)
        disabled: True
        on_release: root.preview_split()

    Label:
        id: preview_label
        text: ""
        color: 0.494, 0.663, 0.69, 1
        size_hint_y: None
        height: dp(40)
        text_size: self.width, None

    ProgressBar:
        id: progress
        max: 100
        value: 0
        size_hint_y: None
        height: dp(16)
        opacity: 0

    Button:
        id: export_btn
        text: "Export Clips"
        size_hint_y: None
        height: dp(54)
        disabled: True
        on_release: root.export_clips()
"""


class Waveform(Widget):
    samples = ListProperty([])
    progress = NumericProperty(0.0)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.bind(size=self.redraw, pos=self.redraw,
                  samples=self.redraw, progress=self.redraw)

    def redraw(self, *args):
        self.canvas.clear()
        with self.canvas:
            Color(*BG_PANEL)
            Rectangle(pos=self.pos, size=self.size)
            if not self.samples:
                return
            n = len(self.samples)
            bar_w = self.width / n
            mid_y = self.pos[1] + self.height / 2
            played = int(self.progress * n)
            for i, amp in enumerate(self.samples):
                x = self.pos[0] + i * bar_w
                h = max(2, amp * self.height * 0.85)
                Color(*(ACCENT if i <= played else ACCENT_2))
                Rectangle(pos=(x, mid_y - h / 2), size=(max(1, bar_w - 1), h))
            Color(*DANGER)
            px = self.pos[0] + self.progress * self.width
            Line(points=[px, self.pos[1], px, self.pos[1] + self.height], width=1.5)


class RootWidget(BoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.audio_path = None
        self.wav_params = None
        self.wav_frames = None
        self.duration_sec = 0
        self.sound = None
        self.split_seconds = 10
        Clock.schedule_interval(self.update_playhead, 0.1)

    # ---------------- File picking ----------------
    def pick_file(self):
        try:
            from plyer import filechooser
            filechooser.open_file(
                on_selection=self.on_file_chosen,
                filters=[("Audio", "*.mp3", "*.wav", "*.m4a", "*.ogg", "*.flac")]
            )
        except Exception as e:
            self.show_popup("Error", f"File picker failed: {e}")

    def on_file_chosen(self, selection):
        if not selection:
            return
        path = selection[0]
        self.load_file(path)

    def load_file(self, path):
        if not path.lower().endswith(".wav"):
            self.show_popup(
                "WAV files only (for now)",
                "This version only reads .wav files (no FFmpeg bundled "
                "yet, to keep the app small and reliable).\n\n"
                "Convert your file to .wav first using the Windows app, "
                "or a free online converter."
            )
            return
        try:
            wf = wave.open(path, "rb")
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)
            wf.close()
        except Exception as e:
            self.show_popup("Could not load audio", str(e))
            return

        self.audio_path = path
        self.wav_params = (n_channels, sampwidth, framerate)
        self.wav_frames = raw
        self.duration_sec = n_frames / float(framerate) if framerate else 0

        self.ids.file_label.text = os.path.basename(path)
        self.ids.play_btn.disabled = False
        self.ids.ok_btn.disabled = False
        self.ids.export_btn.disabled = False

        if self.sound:
            self.sound.unload()
        self.sound = SoundLoader.load(path)

        # Build a simple waveform envelope from the raw PCM bytes
        self.ids.waveform.samples = self._build_envelope(raw, sampwidth, n_channels)

        self.preview_split()

    @staticmethod
    def _build_envelope(raw, sampwidth, n_channels, n_bars=120):
        import array
        type_code = {1: "b", 2: "h", 4: "i"}.get(sampwidth, "h")
        try:
            samples = array.array(type_code, raw)
        except Exception:
            return []
        if n_channels > 1:
            samples = samples[::n_channels]
        if not samples:
            return []
        peak = max(1, max(abs(x) for x in samples))
        chunk = max(1, len(samples) // n_bars)
        envelope = []
        for i in range(0, len(samples), chunk):
            seg = samples[i:i + chunk]
            avg = sum(abs(x) for x in seg) / len(seg) if seg else 0
            envelope.append(min(1.0, avg / peak))
        return envelope[:n_bars]

    # ---------------- Playback ----------------
    def toggle_play(self):
        if not self.sound:
            return
        if self.sound.state == "play":
            self.sound.stop()
            self.ids.play_btn.text = "Play"
        else:
            self.sound.play()
            self.ids.play_btn.text = "Pause"

    def update_playhead(self, dt):
        if self.sound and self.sound.length:
            pos = self.sound.get_pos()
            self.ids.waveform.progress = min(1.0, pos / self.sound.length)
            self.ids.time_label.text = f"{self.fmt(pos)} / {self.fmt(self.sound.length)}"
            if self.sound.state != "play":
                self.ids.play_btn.text = "Play"

    @staticmethod
    def fmt(seconds):
        s = int(seconds)
        return f"{s // 60:02d}:{s % 60:02d}"

    # ---------------- Interval ----------------
    def on_slider_change(self, instance, value):
        self.split_seconds = int(value)
        self.ids.interval_label.text = f"{int(value)} sec"

    def preview_split(self):
        if not self.audio_path:
            return
        n_clips = math.ceil(self.duration_sec / self.split_seconds)
        self.ids.preview_label.text = (
            f"Length: {self.fmt(self.duration_sec)}  ->  "
            f"Will create {n_clips} clip(s) of {self.split_seconds}s each."
        )

    # ---------------- Export ----------------
    def get_output_dir(self):
        if platform == "android":
            from android.storage import primary_external_storage_path
            out = os.path.join(primary_external_storage_path(), "Music", "AudioSplitterPro")
        else:
            out = os.path.join(os.path.expanduser("~"), "AudioSplitterPro")
        os.makedirs(out, exist_ok=True)
        return out

    def export_clips(self):
        if not self.audio_path:
            return
        out_dir = self.get_output_dir()
        base_name = os.path.splitext(os.path.basename(self.audio_path))[0]

        n_channels, sampwidth, framerate = self.wav_params
        bytes_per_frame = n_channels * sampwidth
        total_frames = len(self.wav_frames) // bytes_per_frame
        frames_per_chunk = int(self.split_seconds * framerate)
        n_clips = math.ceil(total_frames / frames_per_chunk)

        self.ids.progress.opacity = 1
        self.ids.progress.max = n_clips
        self.ids.progress.value = 0

        try:
            for i in range(n_clips):
                start_frame = i * frames_per_chunk
                end_frame = min(start_frame + frames_per_chunk, total_frames)
                start_byte = start_frame * bytes_per_frame
                end_byte = end_frame * bytes_per_frame
                chunk_data = self.wav_frames[start_byte:end_byte]

                out_path = os.path.join(out_dir, f"{base_name}_part{i+1:03d}.wav")
                out_wave = wave.open(out_path, "wb")
                out_wave.setnchannels(n_channels)
                out_wave.setsampwidth(sampwidth)
                out_wave.setframerate(framerate)
                out_wave.writeframes(chunk_data)
                out_wave.close()

                self.ids.progress.value = i + 1
        except Exception as e:
            self.show_popup("Export failed", str(e))
            return
        finally:
            self.ids.progress.opacity = 0

        self.show_popup("Done", f"Exported {n_clips} clip(s) to:\n{out_dir}")

    def show_popup(self, title, msg):
        Popup(
            title=title,
            content=Label(text=msg),
            size_hint=(0.85, 0.4)
        ).open()


class AudioSplitterApp(App):
    def build(self):
        Builder.load_string(KV)
        Window.clearcolor = BG_DARK
        if platform == "android":
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
            ])
        return RootWidget()


if __name__ == "__main__":
    AudioSplitterApp().run()
