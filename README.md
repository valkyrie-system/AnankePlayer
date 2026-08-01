
***

# 🎵 Anankê Player

![Ananke Player Logo](AnankePlayer.png)

**Anankê Player** is a comprehensive, self-improving desktop music library manager built with PyQt6. It scans your local audio collection, enriches it with metadata from MusicBrainz, Last.fm, and ListenBrainz, fetches synced lyrics, downloads album artwork, detects duplicates by audio-content hashing, and provides a beautiful, adaptive UI for exploring your collection.

> Python 3.10+ · Linux / Windows / macOS

---

## 🚀 Core Features

### 📚 Library Management
- **Parallel multi-threaded scanner** with hardware-adaptive worker counts.
- Supports **MP3, FLAC, OGG, Opus, M4A, AAC, MP4, WMA, WAV, AIFF**.
- **Tree and Grid views** with true wrapping `FlowLayout` and embedded artwork extraction.
- **Watch folders** mode — auto-rescans on file changes, with optional auto-organize.
- **List Filters**: Instantly filter your Library and New Releases tabs by Favorites, Whitelist, or Blacklist.

### 🎤 Lyrics & Artwork
- Fetches **synced (.lrc)** and **plain (.txt)** lyrics from [lrclib.net](https://lrclib.net).
- **Genius lyrics viewer** integration for full lyric pages.
- **Cover Art Archive** integration for release-group covers.
- **Local Artwork Saving**: Automatically saves `cover.jpg` and `artist.jpg` to album folders for Plex/Jellyfin.

### 📊 Popularity & Metadata
- Aggregates listener counts from **ListenBrainz** and **Last.fm**.
- **Blended popularity score** with adaptive weighting.
- **Global & geo rankings** from Last.fm charts.
- **MusicBrainz caching** (7-day TTL) with rate limiting (~1 req/sec).

### 🆕 New Release Detection & Radar
- Queries **MusicBrainz release-groups** for artists in your library.
- **New Music Friday Radar**: Background timer that alerts you when favorited artists drop new music.
- **Auto-translation** of non-Latin album titles.

### 🗑️ Duplicate Detection
- **SHA-256 audio-content hashing** (metadata ignored to avoid false positives).
- **mmap-optimized hashing** for large files.
- Learning-driven auto-selection of singles to delete when albums exist.

### 🎧 Built-in Audio Player
- Full **local audio playback** with queue management.
- **Synced lyrics display** that follows playback position.
- **MPRIS2 integration** on Linux (media keys, desktop controls).
- **Last.fm scrobbling** & **ListenBrainz submitting**.
- **30-sec Previews**: Search and play 30-second iTunes/Deezer previews directly in the unified player bar.

---

## 📦 Installation & Running

### 1. Prerequisites
Install the required Python libraries:
```bash
pip install PyQt6 mutagen requests plyer deep-translator librosa numpy
```
*(Optional: `psutil` for better hardware detection, `PyQt6-Qt6-DBus` for Linux MPRIS media keys, `PyQt6-Qt6-Multimedia` for audio playback/previews).*

### 2. Launch the App
Navigate to the `musicwatche` folder and run:
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
3. **Start slskd**: You can run it directly via `./slskd`, or set it up to run permanently in the background as a **systemd service**:

   Create the service file:
   ```bash
   mkdir -p ~/.config/systemd/user
   nano ~/.config/systemd/user/slskd.service
   ```

   Paste the following configuration (make sure to update the `ExecStart` path to match where you unzipped `slskd`):
   ```ini
   [Unit]
   Description=slskd (Soulseek Daemon)
   After=network.target

   [Service]
   Type=simple
   WorkingDirectory=/path/to/slskd/folder
   ExecStart=/path/to/slskd/folder/slskd
   Restart=on-failure
   RestartSec=5

   [Install]
   WantedBy=default.target
   ```

   Enable and start the service:
   ```bash
   systemctl --user daemon-reload
   systemctl --user enable slskd.service
   systemctl --user start slskd.service
   ```

4. **Link to MusicWatcher**: Open MusicWatcher → ⚙ Settings → External Services. Enter the `slskd` URL (`http://localhost:5030`) and your API Key.

---

## 📁 Project Structure

```text
musicwatcher/
├── main.py                  # Entry point
├── core/                    # DataStore, SQLite, LearningEngine, Hardware
├── services/                # External APIs (MusicBrainz, Last.fm, Soulseek, Lyrics)
├── threads/                 # QThread workers (Scanner, Popularity, Artwork, Analysis)
└── ui/                      # PyQt6 UI components, Dialogs, Themes, Main Window
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
| | External Player | Set executable (e.g., `strawberry`, `vlc`) for right-click sending. |
| **Performance** | Scan/Lyrics Workers | Parallel tag-reading / lyric-downloading threads. |
| | SHA-256 Hashing | Duplicate + change detection (audio content only). |
| | Auto-Organize | Physically reorganize files dropped into the Watch Folder. |
| **Metadata** | Auto-translate titles | Translate non-Latin album titles to English. |
| | Audio Analysis | Extract BPM, Key, and Mood locally via `librosa`. |

---

## 🔮 Roadmap

Here are the upcoming features planned for future releases:

### 1. 🏷️ Write Audio Analysis to File Tags (Quick Win)
Right now, the BPM, Key, and Mood are saved in the database, but not written to the actual audio files. We can add a button (or make it automatic) that uses `mutagen` to write `BPM`, `INITIALKEY`, and `MOOD` tags directly to the FLAC/MP3 files. This means DJ software like Rekordbox, Serato, or Mixxx will instantly read that data!

### 2. ⚙️ Customizable Library Organizer Format
Right now, the Auto-Organizer forces the `Artist/Album/Track - Title.flac` structure. We could add a Settings text field where you can define your own format string (e.g., `[Year] Album/Track - Title` or `Artist - Album/Track. Title`), giving you total control over how your folders are structured.

### 3. 🪟 Floating "Now Playing" Desktop Widget
We can spawn a small, borderless, always-on-top window (frameless `QWidget`) that sits in the corner of your screen. It would display the current album art, track name, and a scrolling synced lyrics line, acting like a mini Spotify-style overlay while you work.

### 4. 🧹 One-Click "Auto-Fix Missing Tags"
If you have albums showing up as "Unknown Artist" or "Unknown Album", we can add a right-click menu option: **"🧠 Auto-Fix Tags from MusicBrainz"**. It would take the files, use the existing MBID (or do an acoustic fingerprint lookup), fetch the correct Artist/Album/Tracklist, and automatically write the tags in the background without needing to open the Picard window.

### 5. 📱 Web / Mobile Companion (Advanced)
We could spin up a tiny local Flask/FastAPI server inside MusicWatcher. This would expose an API on your local network (e.g., `http://192.168.1.x:5000`). You could open a browser on your phone, see your library, and hit "Play" to remotely control the MusicWatcher desktop player.

---

## 🙏 Credits & Acknowledgements

Built with [PyQt6](https://www.riverbankcomputing.com/software/pyqt/), [Mutagen](https://mutagen.readthedocs.io/), [Librosa](https://librosa.org/), and the wonderful open music APIs (MusicBrainz, ListenBrainz, Last.fm, lrclib.net, Cover Art Archive). Soulseek integration via [slskd](https://github.com/slskd/slskd). Most importantly! tranxuanthang  for their work on [LRCGET](https://github.com/tranxuanthang/lrcget) !

Released under the **MIT License**.

> “Where words fail, music speaks.” — Hans Christian Andersen
