***

# 🎵 MusicWatcher

![MusicWatcher Logo](MusicWatcher.png)

**MusicWatcher** is a comprehensive, self-improving desktop music library manager built with PyQt6. It scans your local audio collection, enriches it with metadata from MusicBrainz, Last.fm, and ListenBrainz, fetches synced lyrics, downloads album artwork, detects duplicates by audio-content hashing, and provides a beautiful, adaptive UI for exploring your collection.

> Python 3.10+ · Linux / Windows

---

## 🚀 Core Features

### 📚 Library Management
- **Parallel multi-threaded scanner** with hardware-adaptive worker counts.
- Supports **MP3, FLAC, OGG, Opus, M4A, AAC, MP4, WMA, WAV, AIFF**.
- **Tree and Grid views** with true wrapping `FlowLayout`.
- **Watch folders** mode — auto-rescans on file changes (3-second debounce).
- **System tray icon** with minimize-to-tray support.

### 🎤 Lyrics & Artwork
- Fetches **synced (.lrc)** and **plain (.txt)** lyrics from [lrclib.net](https://lrclib.net).
- **Genius lyrics viewer** integration for full lyric pages.
- **Cover Art Archive** integration for release-group covers.
- **Embedded artwork extraction** (MP3 `APIC`, FLAC pictures, M4A `covr`).
- **LRU memory cache** + disk cache for instant UI rendering.

### 📊 Popularity & Metadata
- Aggregates listener counts from **ListenBrainz** and **Last.fm**.
- **Blended popularity score** with adaptive weighting.
- **Global & geo rankings** from Last.fm charts.
- **MusicBrainz caching** (7-day TTL) with rate limiting (~1 req/sec).

### 🆕 New Release Detection
- Queries **MusicBrainz release-groups** for artists in your library.
- **Auto-translation** of non-Latin album titles.
- Right-click to **Auto-Download** missing releases via Soulseek (`slskd`).

### 🗑️ Duplicate Detection
- **SHA-256 audio-content hashing** (metadata ignored to avoid false positives).
- **mmap-optimized hashing** for large files.
- Learning-driven auto-selection of singles to delete when albums exist.

### 🎧 Built-in Audio Player
- Full **local audio playback** with queue management.
- **Synced lyrics display** that follows playback position.
- **MPRIS2 integration** on Linux (media keys, desktop controls).
- **Last.fm scrobbling** & **ListenBrainz submitting**.

---

## 📦 Installation & Running

### 1. Prerequisites
Install the required Python libraries:
```bash
pip install PyQt6 mutagen requests plyer deep-translator librosa numpy
```
*(Optional: `psutil` for better hardware detection, `PyQt6-Qt6-DBus` for Linux MPRIS media keys, `PyQt6-Qt6-Multimedia` for audio playback/previews).*

### 2. Launch the App
Navigate to the `musicwatcher` folder and run:
```bash
python main.py
```

On first launch, MusicWatcher will detect your hardware, optimize FFmpeg/VAAPI environment variables, and create `~/.musicwatcher/` with default settings.

---

## 🦑 Setting up Soulseek Auto-Download

To use the right-click "Auto-Download" feature, you need [slskd](https://github.com/slskd/slskd) running.

1. **Download slskd** and run it once to generate `~/.local/share/slskd/slskd.yml`.
2. **Configure `slskd.yml`**:
   * Set your Soulseek `username` and `password`.
   * Set the `downloads` directory to match MusicWatcher's Watch Folder.
   * Generate an API key under the `web.api_keys` section.
3. **Start slskd**: `./slskd`
4. **Link to MusicWatcher**: Open MusicWatcher → ⚙ Settings → External Services. Enter the `slskd` URL (`http://localhost:5030`) and your API Key.

---

## 📁 Project Structure

```text
musicwatcher/
├── main.py                  # Entry point
├── core/                    # DataStore, SQLite, LearningEngine, Hardware
├── services/                # External APIs (MusicBrainz, Last.fm, Soulseek, Lyrics)
├── threads/                 # QThread workers (Scanner, Popularity, Artwork)
└── ui/                      # PyQt6 UI components, Dialogs, Main Window
```

### Data Directory
All user data is safely stored in `~/.musicwatcher/`:
```text
~/.musicwatcher/
├── musicwatcher.db          # SQLite database (library, caches, lists)
├── settings.json            # User preferences
├── artwork/                 # Cached cover art
├── learning/
│   └── model.json           # Adaptive learning model state
├── backups/                 # Timestamped auto-backups (last 5 kept)
└── error.log                # Unhandled exception log
```

---

## 🛠️ Packaging & Distribution

MusicWatcher includes a PyInstaller spec file to easily build standalone executables.

### Build Native Executable
```bash
pip install pyinstaller
pyinstaller musicwatcher.spec
```
*Output: `dist/MusicWatcher/MusicWatcher` (or `.exe` on Windows).*

### Build Linux AppImage
Use the included `appimagetool` to wrap the PyInstaller output into a portable AppImage:
```bash
mkdir -p MusicWatcher.AppDir/usr/bin
cp -r dist/MusicWatcher/* MusicWatcher.AppDir/usr/bin/
printf '#!/bin/sh\nHERE="$(dirname "$(readlink -f "${0}")")"\nexec "${HERE}/usr/bin/MusicWatcher" "$@"\n' > MusicWatcher.AppDir/AppRun
chmod +x MusicWatcher.AppDir/AppRun
./appimagetool-x86_64.AppImage MusicWatcher.AppDir MusicWatcher.AppImage
```

---

## ⚙️ Configuration

Access via the **⚙ Settings** dialog. Key options include:

| Section | Feature | Description |
|---------|---------|-------------|
| **External APIs** | Last.fm API Key/Secret | Required for scrobbling & popularity data. |
| | ListenBrainz Token | Required for submitting listens. |
| | Slskd URL / API Key | Required for Soulseek auto-downloading. |
| **Performance** | Scan/Lyrics Workers | Parallel tag-reading / lyric-downloading threads. |
| | SHA-256 Hashing | Duplicate + change detection (audio content only). |
| **Metadata** | Auto-translate titles | Translate non-Latin album titles to English. |
| | Audio Analysis | Extract BPM and Key locally via `librosa`. |

---

## 🙏 Credits & Acknowledgements

Built with [PyQt6](https://www.riverbankcomputing.com/software/pyqt/), [Mutagen](https://mutagen.readthedocs.io/), [Librosa](https://librosa.org/), and the wonderful open music APIs (MusicBrainz, ListenBrainz, Last.fm, lrclib.net, Cover Art Archive). Soulseek integration via [slskd](https://github.com/slskd/slskd).

Released under the **MIT License**.

> “Where words fail, music speaks.” — Hans Christian Andersen
