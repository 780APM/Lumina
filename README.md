<p align="center">
  <img src="assets/lumina-256.png" width="88" height="88" alt="Lumina Lumen icon">
</p>

<h1 align="center">Lumina</h1>

<p align="center"><strong>Your music. Offline.</strong></p>

<p align="center">
  A portable Windows music player for the tracks you already own.<br>
  Local files, album artwork, and reactive visuals. No streaming. No accounts.
</p>

<p align="center">
  <a href="#features">Features</a> ·
  <a href="#getting-started">Getting started</a> ·
  <a href="#development">Development</a> ·
  <a href="branding/README.md">Brand kit</a> ·
  <a href="LICENSE">MIT license</a>
</p>

![Lumina — Your music. Offline. Local files. Living sound.](branding/launch-banner.png)

## Features

- **Local listening.** Play MP3, FLAC, WAV, and OGG files from your computer.
- **Music with an identity.** View titles, artists, albums, and embedded artwork. Missing tags fall back to filenames; missing artwork uses sidecar covers or generated art.
- **Reactive visuals.** Choose a spectrum, circular visualizer, or optional rotatable 3D view. The 2D modes use lightweight native canvas rendering.
- **Familiar controls.** Seek through a track, shuffle, loop the playlist, mute, and adjust volume by dragging or scrolling the slider.
- **Make it yours.** Pick an accent color, with long titles scrolling inside a fixed track panel.
- **Portable playback.** The single-file Windows EXE bundles its runtime. Listeners do not need Python installed.

Playback streams from disk instead of loading complete tracks into memory. Visualization pauses while the window is minimized.

## Getting started

1. Open `Lumina.exe`.
2. Select **Add Files** and choose your local audio files.
3. Select a track and press **Play** or **Space**.
4. Open **Settings** to change the accent and visualizer mode.

To create the portable EXE yourself, follow [Building the Windows app](#building-the-windows-app). The [Windows build workflow](https://github.com/780APM/Lumina/actions/workflows/windows-release.yml) can also be run manually by a repository maintainer; successful runs provide a `Lumina-windows` artifact containing the EXE.

### Keyboard controls

| Key | Action |
| --- | --- |
| Space | Play / pause |
| ← / → | Previous / next track |
| ↑ / ↓ | Volume up / down |
| M | Mute / restore volume |
| S | Toggle shuffle |
| L | Toggle playlist looping |

Scroll over the volume slider to adjust it with the mouse wheel. Hover over the timeline to preview the seek position.

## Development

Requires **Python 3.11+**. From the repository folder, create an environment and install Lumina:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[build]"
.\.venv\Scripts\python.exe -m Lumina
```

On macOS/Linux, use `.venv/bin/python` instead of the Windows interpreter path. Playback backends support those platforms, but the distributed EXE and release workflow target Windows.

After installation, `lumina` and `python -m Lumina` are available. You can also run `python __main__.py` directly from this folder.

### Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

The suite covers playback, volume, settings, artwork, stable title layout, persistent visualizer shapes, mode switching, and icon assets. UI tests require a desktop display.

## Building the Windows app

Build on Windows from the environment above:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean lumina.spec
```

The portable executable is written to **`dist/Lumina.exe`**. Its Lumen icon and runtime artwork are bundled by the spec. `build/`, `dist/`, Python caches, and generated package metadata are excluded from Git.

GitHub Actions runs the tests and builds the same EXE on version tags or manual dispatch. Build artifacts are attached to the workflow run; pushing source changes alone does not publish a downloadable release.

## Project layout

| Location | Purpose |
| --- | --- |
| `ui/` | Player interface and native canvas visualizers |
| `streaming_audio_engine.py` | Streaming playback and volume control |
| `visualizer.py` | FFT spectrum analysis |
| `settings.py` | Validated per-user preferences |
| `branding.py`, `assets/` | Runtime logo, Windows identity, PNG/ICO assets |
| `branding/` | Promotional artwork, copy, and visual brand guide |
| `tests/` | Regression tests |
| `docs/` | Performance review and original icon concepts |

Settings are stored under `%APPDATA%\Lumina\settings.json` on Windows. Older package-local settings are supported as a migration fallback.

## Lumen brand kit

The curved green **Lumen** mark appears in the executable, running window, and sidebar. The kit includes the PNG logo, multi-resolution Windows ICO, wide launch banner, square social artwork, copy, and usage guidance.

<p align="center">
  <img src="branding/social-square.png" width="380" alt="Lumina social artwork — Your music. Offline. No streaming. No accounts.">
</p>

Explore the [brand kit and usage guide](branding/README.md). Open `branding/index.html` locally for the visual guide.

## License

Lumina is available under the [MIT License](LICENSE).
