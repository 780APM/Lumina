# Lumina

Lumina is a local desktop audio player with a Spotify-like layout and reactive visualizer.

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

Build a one-folder executable with PyInstaller:

```bash
pyinstaller lumina.spec
```

The app uses CustomTkinter, Tk, matplotlib, miniaudio, mutagen, Pillow, and numpy. If a platform-specific build misses a runtime asset, rebuild from the activated environment where those packages are installed.
