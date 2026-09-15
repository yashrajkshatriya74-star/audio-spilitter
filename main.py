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

from pydub import AudioSegment

# ---------------------------------------------------------------------
# Locate a bundled FFmpeg binary on Android (compiled in by the
# python-for-android "ffmpeg" recipe). Falls back to system ffmpeg
# when testing on desktop.
# ---------------------------------------------------------------------
def find_ffmpeg():
    if platform == "android":
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity
            native_lib_dir = activity.getApplicationInfo().nativeLibraryDir
            candidates = [
                os.path.join(native_lib_dir, "libffmpeg.so"),
                os.path.join(native_lib_dir, "ffmpeg"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    return c
        except Exception:
            pass
    return "ffmpeg"  # rely on PATH (desktop testing)


_FFMPEG = find_ffmpeg()
AudioSegment.converter = _FFMPEG

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
        self.audio_segment = None
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
        try:
            self.audio_segment = AudioSegment.from_file(path)
        except Exception as e:
            self.show_popup(
                "Could not load audio",
                f"{e}\n\nMake sure the file isn't corrupted."
            )
            return

        self.audio_path = path
        self.ids.file_label.text = os.path.basename(path)
        self.ids.play_btn.disabled = False
        self.ids.ok_btn.disabled = False
        self.ids.export_btn.disabled = False

        if self.sound:
            self.sound.unload()
        self.sound = SoundLoader.load(path)

        # Build waveform envelope
        raw = self.audio_segment.get_array_of_samples()
        if self.audio_segment.channels > 1:
            raw = raw[::self.audio_segment.channels]
        n_bars = 120
        chunk = max(1, len(raw) // n_bars)
        peak = max(1, max(abs(x) for x in raw[:chunk * n_bars:chunk]) or 1)
        envelope = []
        for i in range(0, min(len(raw), chunk * n_bars), chunk):
            seg = raw[i:i + chunk]
            avg = sum(abs(x) for x in seg) / len(seg) if seg else 0
            envelope.append(min(1.0, avg / peak))
        self.ids.waveform.samples = envelope

        self.preview_split()

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
        if not self.audio_segment:
            return
        total_sec = len(self.audio_segment) / 1000
        n_clips = math.ceil(total_sec / self.split_seconds)
        self.ids.preview_label.text = (
            f"Length: {self.fmt(total_sec)}  ->  "
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
        if not self.audio_segment:
            return
        out_dir = self.get_output_dir()
        base_name = os.path.splitext(os.path.basename(self.audio_path))[0]
        chunk_ms = self.split_seconds * 1000
        total_ms = len(self.audio_segment)
        n_clips = math.ceil(total_ms / chunk_ms)

        self.ids.progress.opacity = 1
        self.ids.progress.max = n_clips
        self.ids.progress.value = 0

        try:
            for i in range(n_clips):
                start = i * chunk_ms
                end = min(start + chunk_ms, total_ms)
                clip = self.audio_segment[start:end]
                out_path = os.path.join(out_dir, f"{base_name}_part{i+1:03d}.wav")
                clip.export(out_path, format="wav")
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
