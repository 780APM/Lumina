# Lumina

Lumina is a local desktop audio player with a Spotify-like layout and reactive visualizer.

![Lumina — Your music. Offline.](branding/launch-banner.png)

## Development

Create an environment and install the app in editable mode:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Run the app:

```bash
lumina
```

After installation, the package can also be run with:

```bash
python -m Lumina
```

From this source folder without installing, use:

```bash
python __main__.py
```

## Packaging

Build a portable single-file executable with PyInstaller:

```bash
python -m pip install -e ".[build]"
pyinstaller --clean lumina.spec
```

The resulting `dist/Lumina.exe` is self-contained. Code-sign the release and
publish its checksum before distributing it; unsigned one-file executables can
trigger Windows reputation warnings.

The app uses CustomTkinter, Tk, matplotlib, miniaudio, mutagen, Pillow, and numpy. If a platform-specific build misses a runtime asset, rebuild from the activated environment where those packages are installed.

The Lumen icon is applied to the executable and running window. Source PNG/ICO
files live in `assets/`. The [brand kit](branding/README.md) includes launch and
social artwork, copy, and an offline visual guide.

## Settings

Lumina stores validated settings in the platform config directory, such as
`%APPDATA%\Lumina` on Windows. A package-level `settings.json` from older
versions is read as a migration fallback.

## Tests

Run the standard-library test suite from the repository root:

```bash
python -m unittest discover -v
```

Playback is streamed from disk. Lumina keeps only a short PCM window for the
visualizer, so memory use does not grow with track duration.

2D and circular visualizers update persistent native Tk Canvas shapes at a
30 FPS budget, preserving peaks, reflections, and custom accents. Visualization
is suspended while minimized; optional 3D rendering still uses Matplotlib.

Lumina preloads nearby tracks' lightweight decoder metadata into a bounded
cache to make next/previous navigation responsive. When embedded artwork is unavailable, it checks for
common sidecar files such as `cover.jpg` and then generates identity artwork
from the inferred artist and title.

## License

Lumina is available under the [MIT License](LICENSE).
