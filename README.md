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

## Settings

Lumina stores validated settings in the platform config directory, such as
`%APPDATA%\Lumina` on Windows. A package-level `settings.json` from older
versions is read as a migration fallback.

## Tests

Run the standard-library test suite from the repository root:

```bash
python -m unittest discover -v
```

The decoder currently loads each selected track into memory, so very large
files use memory proportional to their decoded PCM size.

## License

Lumina is available under the [MIT License](LICENSE).
