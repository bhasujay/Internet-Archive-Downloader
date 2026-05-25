# Internet Archive Downloader

A simple desktop GUI for browsing and downloading files from Internet Archive items.
Built in under one hour for an emergency requirement using AI assistance.

## Features

- Accepts an Internet Archive item URL or item ID.
- Fetches the directory listing and displays files with sizes.
- Search/filter the file list.
- Select all, deselect all, or pick individual files.
- Parallel downloads with progress, total bytes, and speed.
- Saves files into a folder named after the item title or ID.

## Requirements

- Python 3.10+ (uses modern type annotations)
- Tkinter support (bundled with most Python installs)

Dependencies are listed in [requirements.txt](requirements.txt):

- `customtkinter` for the GUI
- `requests` and `beautifulsoup4` for fetching/parsing listings
- `pillow` is optional but recommended for CustomTkinter assets

## Installation

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
```

On macOS/Linux, activate with:

```bash
source .venv/bin/activate
```

## Run the App

Run the module from the project root:

```bash
python -m src.main
```

## Usage

1. Paste an Internet Archive item URL or ID in the input field.
2. Click **Get Files** to load the directory listing.
3. Search or filter the file list as needed.
4. Select files and click **Download Selected**.
5. Choose a destination folder when prompted.

### Accepted Inputs

Examples that work:

- `https://archive.org/details/Invincible_michael_jackson_2001`
- `https://archive.org/download/Invincible_michael_jackson_2001`
- `Invincible_michael_jackson_2001`

The app extracts the item ID and builds the download URL automatically.

### Download Behavior

- Downloads run concurrently (up to 16 parallel files).
- A subfolder is created in the destination folder using the item title or ID.
- Filenames are sanitized to avoid invalid characters.
- Progress shows bytes downloaded, total bytes (when available), and speed.

## Project Structure

- [src/main.py](src/main.py) - Entry point that starts the GUI.
- [src/app.py](src/app.py) - App initialization and window setup.
- [src/gui.py](src/gui.py) - Main GUI and download workflow.
- [src/utils.py](src/utils.py) - URL parsing, listing parsing, helpers.
- [InternetArchiveDownloader.spec](InternetArchiveDownloader.spec) - PyInstaller build spec.

## Build a Desktop Executable (Windows)

This project includes a PyInstaller spec. Install PyInstaller and build:

```bash
python -m pip install pyinstaller
pyinstaller InternetArchiveDownloader.spec
```

The built executable will be placed under `dist/`.

## Troubleshooting

- **No files found**: The item may not have a public directory listing, or the listing format changed.
- **Network errors**: Check connectivity and try again. Some items may throttle requests.
- **GUI does not open**: Ensure Tkinter is available in your Python install.

## Notes and Limitations

- This tool does not handle authentication or restricted items.
- Use responsibly and respect Internet Archive terms of use.

## License

No license has been specified yet.
