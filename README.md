# Audio Splitter Pro — Android

Offline Android app to split audio files into equal-length WAV clips.
No internet needed to use it once installed.

## ⚠️ Important — realistic expectations

Mobile builds are genuinely harder to get right on the first try than
the Windows one was — audio decoding, storage permissions, and native
Android APIs behave differently across phone versions, and I can't
test this on a real device from here (unlike the Windows build, which
I fully verified in the cloud). **The first build may fail or the app
may crash on first run — that's expected, not unusual for mobile.**
If it does, send me:
- The GitHub Actions build log (if the build itself fails), or
- A screenshot of the error / a description of what happened on your phone

...and I'll fix it. Think of this as version 1 that we'll refine
together, same as we did with the Windows app's folder-path issue.

## What it supports
- **Input formats:** mp3, wav, m4a, ogg, flac
- **Output format:** always `.wav` (universal, no re-encoding quality
  loss, avoids needing a separate mp3 encoder on the phone)
- **Saves to:** `Music/AudioSplitterPro/` on your phone automatically
  (Android doesn't allow a simple "choose any folder" dialog without a
  lot of extra code, so it always saves here instead)

---

## How to build the APK (same GitHub method as before — no terminal)

1. Go to your GitHub account (or make a new repo, e.g. `audio-splitter-android`)
2. Upload **all files in this folder** — `main.py`, `buildozer.spec`,
   `README.md`, and the `.github` folder (remember: enable
   **"Hidden items"** in File Explorer's View tab to see `.github`)
3. Commit changes
4. Click the **Actions** tab — a build will start automatically
5. **This build takes 20–40 minutes** (Android builds compile a lot of
   native code — FFmpeg, Python, SDL2 — from scratch). Grab a coffee.
6. Once it finishes (green tick), scroll to **Artifacts** →
   download **`AudioSplitterPro-Android-APK`**
7. Unzip it — inside is your `.apk` file

## Installing the APK on your phone

1. Transfer the `.apk` file to your phone (via USB cable, WhatsApp to
   yourself, Google Drive, email — any way you like)
2. Tap the `.apk` file on your phone to install it
3. Android will likely warn **"Install blocked"** or **"Unknown
   source"** — this is normal for any app not from the Play Store.
   Tap **"Settings"** in that prompt → allow installs from that source
   → go back and tap the file again → **Install**
4. First time you open the app, it'll ask for storage permission —
   allow it (needed to read your audio files and save clips)

---

## If the build fails on GitHub

Open the failed run in the **Actions** tab, click the red ✕ step to
expand the error text, and send me a screenshot — buildozer error
logs are usually specific about what's missing (a version mismatch,
a missing package, etc.) and are normally fixable.

## If the app installs but crashes or misbehaves on your phone

Tell me exactly what happened — "closes immediately", "file picker
doesn't open", "export button does nothing" — and at what step. I'll
adjust the code and we rebuild (same GitHub process, just re-upload
the changed `main.py`).
