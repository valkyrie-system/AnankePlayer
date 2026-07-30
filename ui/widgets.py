import re, time, os, threading, requests, hashlib
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog,
    QListWidget, QListWidgetItem, QLineEdit, QProgressBar, QFrame, QSplitter,
    QScrollArea, QStackedWidget, QSizePolicy, QSlider, QMenu, QLayout, QDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QObject, QUrl, QPoint, QRect, QSize, pyqtSignal, pyqtSlot, pyqtProperty, QThread
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap, QShortcut, QKeySequence, QIcon

try:
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    HAS_MULTIMEDIA = True
except ImportError:
    HAS_MULTIMEDIA = False

from core.utils import APP_NAME, extract_tags, lyrics_status, lyrics_emoji, fmt_n, fmt_dur, elapsed_s, CAA_BASE
from services.artwork import ArtworkLoader
from mutagen import File as MutagenFile

# ─────────────────────────────────────────────────────────────────────────────
# Progress widget
# ─────────────────────────────────────────────────────────────────────────────

class ProgressWidget(QWidget):
    pause_toggled = pyqtSignal(bool)
    stopped       = pyqtSignal()

    def __init__(self,label="",parent=None):
        super().__init__(parent)
        self._label=label; self._start_t=None; self._total=1; self._paused=False
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,2); layout.setSpacing(2)
        self.bar=QProgressBar(); self.bar.setObjectName("bigBar")
        self.bar.setFixedHeight(30); self.bar.setTextVisible(False)
        layout.addWidget(self.bar)
        row=QHBoxLayout()
        self.elapsed_lbl=QLabel("00:00"); self.elapsed_lbl.setObjectName("elapsedLabel")
        self.elapsed_lbl.setFixedWidth(54)
        self.info=QLabel("Idle"); self.info.setObjectName("progressInfo")
        self.info.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred)
        self.pause_btn=QPushButton("⏸  Pause"); self.pause_btn.setObjectName("pauseBtn")
        self.pause_btn.setFixedHeight(26); self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._toggle)
        self.stop_btn=QPushButton("■  Stop"); self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setFixedHeight(26); self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stopped.emit)
        row.addWidget(self.elapsed_lbl); row.addWidget(self.info,stretch=1)
        row.addWidget(self.pause_btn); row.addWidget(self.stop_btn)
        layout.addLayout(row)
        self._timer=QTimer(self); self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def begin(self,total:int):
        self._start_t=time.monotonic(); self._total=max(total,1); self._paused=False
        self.bar.setMaximum(self._total); self.bar.setValue(0)
        self.pause_btn.setEnabled(True); self.pause_btn.setText("⏸  Pause")
        self.stop_btn.setEnabled(True); self.elapsed_lbl.setText("00:00")
        self._timer.start(); self.show()

    def update_progress(self,done:int,artists:int=0,albums:int=0,fps:float=0,extra:str=""):
        self.bar.setValue(min(done,self._total))
        eta="—"
        if self._start_t and done>0:
            el=time.monotonic()-self._start_t; rate=done/el
            if rate>0 and self._total>done: eta=fmt_dur(int((self._total-done)/rate))
        pct=int(done*100/self._total) if self._total else 0
        parts=[f"{done:,} / {self._total:,}  ({pct}%)"]
        if artists: parts.append(f"{artists:,} artists")
        if albums:  parts.append(f"{albums:,} albums")
        if fps>0:   parts.append(f"{fps:.0f}/s")
        parts.append(f"ETA {eta}")
        if extra: parts.append(extra)
        self.info.setText("  "+self._label+"   "+"  ·  ".join(parts))

    def finish(self,msg=""):
        self._timer.stop(); self.bar.setValue(self._total)
        self.pause_btn.setEnabled(False); self.stop_btn.setEnabled(False)
        if msg: self.info.setText(f"  ✔  {msg}")

    def _tick(self):
        if self._start_t: self.elapsed_lbl.setText(elapsed_s(self._start_t))

    def _toggle(self):
        self._paused=not self._paused
        self.pause_btn.setText("▶  Resume" if self._paused else "⏸  Pause")
        self._timer.stop() if self._paused else self._timer.start()
        self.pause_toggled.emit(self._paused)

# ─────────────────────────────────────────────────────────────────────────────
# Folder panel
# ─────────────────────────────────────────────────────────────────────────────

class FolderPanel(QFrame):
    folders_changed=pyqtSignal(list)

    def __init__(self,parent=None):
        super().__init__(parent); self.setObjectName("folderPanel")
        layout=QVBoxLayout(self); layout.setContentsMargins(6,8,6,8); layout.setSpacing(6)
        hdr=QLabel("Music Folders"); hdr.setObjectName("panelHeader"); layout.addWidget(hdr)
        self.lw=QListWidget(); self.lw.setObjectName("folderList")
        self.lw.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.lw,stretch=1)
        row=QHBoxLayout()
        self.add_btn=QPushButton("+  Add"); self.add_btn.setObjectName("addBtn")
        self.add_btn.setFixedHeight(30); self.add_btn.clicked.connect(self._add)
        self.rem_btn=QPushButton("−  Remove"); self.rem_btn.setObjectName("removeBtn")
        self.rem_btn.setFixedHeight(30); self.rem_btn.setEnabled(False)
        self.rem_btn.clicked.connect(self._remove)
        row.addWidget(self.add_btn); row.addWidget(self.rem_btn); layout.addLayout(row)
        self.lw.itemSelectionChanged.connect(lambda:self.rem_btn.setEnabled(bool(self.lw.selectedItems())))

    def _add(self):
        folder=QFileDialog.getExistingDirectory(self,"Add Music Folder", os.path.expanduser("~"))
        if not folder: return
        if any(self.lw.item(i).data(Qt.ItemDataRole.UserRole)==folder for i in range(self.lw.count())):
            QMessageBox.information(self,"Already added",f'"{folder}" already in list.')
            return
        self._append(folder); self.folders_changed.emit(self.get())

    def _append(self,folder:str):
        parts=Path(folder).parts
        label=os.path.join(*parts[-2:]) if len(parts)>=2 else folder
        item=QListWidgetItem(label); item.setData(Qt.ItemDataRole.UserRole,folder)
        item.setToolTip(folder); self.lw.addItem(item)

    def _remove(self):
        for it in self.lw.selectedItems(): self.lw.takeItem(self.lw.row(it))
        self.folders_changed.emit(self.get())

    def get(self)->list:
        return[self.lw.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.lw.count())]

    def load(self,folders:list):
        self.lw.clear()
        for f in folders:
            if os.path.isdir(f): self._append(f)

# ─────────────────────────────────────────────────────────────────────────────
# Preview URL lookup (iTunes + Deezer)
# ─────────────────────────────────────────────────────────────────────────────

class PreviewLookup(QThread):
    found    = pyqtSignal(str, str, str)
    not_found = pyqtSignal(str, str)

    def __init__(self, artist: str, title: str):
        super().__init__()
        self.artist = artist
        self.title  = title

    def run(self):
        url = self._try_itunes() or self._try_deezer()
        if url: self.found.emit(self.artist, self.title, url)
        else:   self.not_found.emit(self.artist, self.title)

    def _try_itunes(self) -> str:
        try:
            q = f"{self.artist} {self.title}"
            r = requests.get("https://itunes.apple.com/search",
                params={"term": q, "media": "music", "entity": "album", "limit": 5},
                timeout=8, headers={"User-Agent": "MusicWatcher/5.1"})
            if r.status_code == 200:
                results = r.json().get("results", [])
                for res in results:
                    url = res.get("previewUrl", "")
                    if url: return url
        except Exception: pass
        return ""

    def _try_deezer(self) -> str:
        try:
            q = f'artist:"{self.artist}" album:"{self.title}"'
            r = requests.get("https://api.deezer.com/search",
                params={"q": q, "limit": 5},
                timeout=8, headers={"User-Agent": "MusicWatcher/5.1"})
            if r.status_code == 200:
                data = r.json().get("data", [])
                for track in data:
                    url = track.get("preview", "")
                    if url: return url
        except Exception: pass
        return ""

class PreviewPlayer(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("previewPlayer")
        self.setFixedHeight(54)
        self._lookup = None
        self._current_url = ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4); layout.setSpacing(8)

        self.play_btn = QPushButton("▶")
        self.play_btn.setObjectName("previewPlayBtn")
        self.play_btn.setFixedSize(36, 36)
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self._toggle_play)
        layout.addWidget(self.play_btn)

        self.stop_btn = QPushButton("■")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setFixedSize(36, 36)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        layout.addWidget(self.stop_btn)

        self.track_label = QLabel("No preview loaded")
        self.track_label.setObjectName("previewLabel")
        self.track_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.track_label, stretch=1)

        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setObjectName("previewSeek")
        self.seek.setRange(0, 30000); self.seek.setFixedWidth(180); self.seek.setEnabled(False)
        self.seek.sliderMoved.connect(self._on_seek)
        layout.addWidget(self.seek)

        self.time_label = QLabel("0:00 / 0:30")
        self.time_label.setObjectName("elapsedLabel")
        self.time_label.setFixedWidth(78); layout.addWidget(self.time_label)

        vol_label = QLabel("🔊"); layout.addWidget(vol_label)
        self.vol = QSlider(Qt.Orientation.Horizontal)
        self.vol.setObjectName("previewSeek")
        self.vol.setRange(0, 100); self.vol.setValue(80); self.vol.setFixedWidth(80)
        self.vol.valueChanged.connect(self._on_volume); layout.addWidget(self.vol)

        self.source_label = QLabel("")
        self.source_label.setObjectName("noteLabel")
        self.source_label.setFixedWidth(70); layout.addWidget(self.source_label)

        if HAS_MULTIMEDIA:
            self._player = QMediaPlayer()
            self._audio  = QAudioOutput()
            self._player.setAudioOutput(self._audio)
            self._audio.setVolume(0.8)
            self._player.positionChanged.connect(self._on_position)
            self._player.durationChanged.connect(self._on_duration)
            self._player.playbackStateChanged.connect(self._on_state)
            self._player.errorOccurred.connect(self._on_error)
        else:
            self._player = None; self._audio  = None
            self.track_label.setText("Preview unavailable — install PyQt6-Qt6-Multimedia")
            self.play_btn.setEnabled(False)

        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._update_time)

    def preview(self, artist: str, release: str):
        if not HAS_MULTIMEDIA: return
        self._stop()
        self.track_label.setText(f"🔍 Searching preview for {artist} — {release}…")
        self.play_btn.setEnabled(False); self.seek.setEnabled(False); self.source_label.setText("")

        if self._lookup and self._lookup.isRunning(): self._lookup.terminate()

        self._lookup = PreviewLookup(artist, release)
        self._lookup.found.connect(self._on_preview_found)
        self._lookup.not_found.connect(self._on_preview_not_found)
        self._lookup.start()

    def _on_preview_found(self, artist: str, title: str, url: str):
        self._current_url = url
        source = "iTunes" if "apple.com" in url or "mzstatic.com" in url else "Deezer"
        self.source_label.setText(source)
        self.track_label.setText(f"▶  {artist} — {title}  ({source} 30-sec preview)")
        self.play_btn.setEnabled(True); self.seek.setEnabled(True)
        if self._player:
            self._player.setSource(QUrl(url))
            self._player.play()
            self._timer.start()

    def _on_preview_not_found(self, artist: str, title: str):
        self.track_label.setText(f"❌ No preview found for {artist} — {title}  (not on iTunes or Deezer)")
        self.play_btn.setEnabled(False); self.seek.setEnabled(False)

    def _toggle_play(self):
        if not self._player: return
        from PyQt6.QtMultimedia import QMediaPlayer as _QMP
        if self._player.playbackState() == _QMP.PlaybackState.PlayingState:
            self._player.pause(); self.play_btn.setText("▶"); self._timer.stop()
        else:
            self._player.play(); self.play_btn.setText("⏸"); self._timer.start()

    def _stop(self):
        if self._player: self._player.stop()
        self.play_btn.setText("▶")
        self.stop_btn.setEnabled(False); self.seek.setValue(0)
        self.time_label.setText("0:00 / 0:30"); self._timer.stop()

    def _on_seek(self, ms: int):
        if self._player: self._player.setPosition(ms)

    def _on_volume(self, val: int):
        if self._audio: self._audio.setVolume(val / 100.0)

    def _on_position(self, ms: int):
        self.seek.blockSignals(True); self.seek.setValue(ms); self.seek.blockSignals(False)

    def _on_duration(self, ms: int):
        self.seek.setMaximum(max(ms, 1))

    def _on_state(self, state):
        try:
            from PyQt6.QtMultimedia import QMediaPlayer as _QMP
            playing = (state == _QMP.PlaybackState.PlayingState)
            self.play_btn.setText("⏸" if playing else "▶")
            self.stop_btn.setEnabled(playing or state == _QMP.PlaybackState.PausedState)
            if state == _QMP.PlaybackState.StoppedState:
                self._timer.stop(); self.seek.setValue(0); self.time_label.setText("0:00 / 0:30")
        except Exception: pass

    def _on_error(self, error, error_string: str):
        self.track_label.setText(f"⚠ Playback error: {error_string}")

    def _update_time(self):
        if not self._player: return
        pos = self._player.position() // 1000
        dur = max(self._player.duration() // 1000, 30)
        self.time_label.setText(f"{pos//60}:{pos%60:02d} / {dur//60}:{dur%60:02d}")

# ─────────────────────────────────────────────────────────────────────────────
# Local Audio Player
# ─────────────────────────────────────────────────────────────────────────────

class LocalPlayer(QObject):
    state_changed = pyqtSignal(str)
    position_changed = pyqtSignal(int)
    duration_changed = pyqtSignal(int)
    track_changed = pyqtSignal(str, str)
    lyrics_line_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.player = QMediaPlayer()
        self.audio = QAudioOutput()
        self.player.setAudioOutput(self.audio)
        self.audio.setVolume(0.8)

        self.queue = []
        self.current_index = -1
        self.current_lrc = []

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self.duration_changed.emit)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status)

    def load_queue(self, files, start_index=0):
        if not files: return
        self.queue = files
        self.current_index = start_index - 1
        self.next()

    def play_file(self, file_path):
        if file_path.startswith("http"):
            self.player.setSource(QUrl(file_path))
        else:
            self.player.setSource(QUrl.fromLocalFile(file_path))
        self.player.play()

    def play(self): self.player.play()
    def pause(self): self.player.pause()

    def stop(self):
        self.player.stop()
        self.queue.clear()
        self.current_index = -1
        self.current_lrc.clear()
        self.track_changed.emit("", "")
        self.lyrics_line_changed.emit("")

    def next(self):
        if not self.queue: return
        self.current_index = (self.current_index + 1) % len(self.queue)
        self.play_file(self.queue[self.current_index])

    def prev(self):
        if not self.queue: return
        self.current_index = (self.current_index - 1) % len(self.queue)
        self.play_file(self.queue[self.current_index])

    def set_volume(self, val): self.audio.setVolume(val / 100.0)
    def seek(self, ms): self.player.setPosition(ms)

    def _on_position_changed(self, ms):
        self.position_changed.emit(ms)
        if self.current_lrc:
            current_line = ""
            for time, text in self.current_lrc:
                if ms >= time: current_line = text
                else: break
            self.lyrics_line_changed.emit(current_line)

    def _on_state_changed(self, state):
        from PyQt6.QtMultimedia import QMediaPlayer as _QMP
        if state == _QMP.PlaybackState.PlayingState: self.state_changed.emit("playing")
        elif state == _QMP.PlaybackState.PausedState: self.state_changed.emit("paused")
        else: self.state_changed.emit("stopped")

    def _on_media_status(self, status):
        from PyQt6.QtMultimedia import QMediaPlayer as _QMP
        if status == _QMP.MediaStatus.LoadedMedia:
            try:
                tags = extract_tags(Path(self.queue[self.current_index]))
                if tags:
                    self.track_changed.emit(tags.get("artist",""), tags.get("title",""))
                    self._load_lrc(Path(self.queue[self.current_index]))
            except: pass
        elif status == _QMP.MediaStatus.EndOfMedia:
            self.next()

    def _load_lrc(self, fp):
        self.current_lrc.clear()
        lrc_file = fp.with_suffix(".lrc")
        txt_file = fp.with_suffix(".txt")

        if lrc_file.exists():
            pattern = re.compile(r'\[(\d+):(\d+)(?:\.(\d+))?\](.*)')
            lines = []
            try:
                for line in lrc_file.read_text(encoding="utf-8").splitlines():
                    m = pattern.match(line)
                    if m:
                        mins = int(m.group(1)); secs = int(m.group(2))
                        ms = int(m.group(3) or 0) * 10
                        time = mins * 60000 + secs * 1000 + ms
                        text = m.group(4).strip()
                        if text: lines.append((time, text))
                lines.sort(key=lambda x: x[0])
                self.current_lrc = lines
            except: pass
        elif txt_file.exists():
            # Fallback: If only plain text exists, show the whole thing at time 0
            try:
                plain_lyrics = txt_file.read_text(encoding="utf-8").strip()
                if plain_lyrics:
                    self.current_lrc = [(0, plain_lyrics)]
            except: pass
        else:
            self.lyrics_line_changed.emit("")

class PlayerBar(QFrame):
    def __init__(self, player: LocalPlayer, parent=None):
        super().__init__(parent)
        self.player = player
        self.setObjectName("previewPlayer")
        self.setFixedHeight(100) # <--- CHANGED THIS to prevent expanding!

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4); layout.setSpacing(2)

        self.lyrics_label = QLabel("♪ ♫")
        self.lyrics_label.setObjectName("previewLabel")
        self.lyrics_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lyrics_label.setWordWrap(False) # prevent vertical expanding
        layout.addWidget(self.lyrics_label)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)

        self.prev_btn = QPushButton("⏮")
        self.prev_btn.setFixedSize(32, 32)
        self.prev_btn.clicked.connect(self.player.prev)
        ctrl_row.addWidget(self.prev_btn)

        self.play_btn = QPushButton("▶")
        self.play_btn.setObjectName("previewPlayBtn")
        self.play_btn.setFixedSize(36, 36)
        self.play_btn.clicked.connect(self._toggle_play)
        ctrl_row.addWidget(self.play_btn)

        self.stop_btn = QPushButton("■")
        self.stop_btn.setFixedSize(32, 32)
        self.stop_btn.clicked.connect(self.player.stop)
        ctrl_row.addWidget(self.stop_btn)

        self.next_btn = QPushButton("⏭")
        self.next_btn.setFixedSize(32, 32)
        self.next_btn.clicked.connect(self.player.next)
        ctrl_row.addWidget(self.next_btn)

        self.track_label = QLabel("No track loaded")
        self.track_label.setObjectName("previewLabel")
        self.track_label.setWordWrap(False)
        self.track_label.setMinimumWidth(200) # Prevent cutoff
        self.track_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        ctrl_row.addWidget(self.track_label, stretch=1)

        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setObjectName("previewSeek")
        self.seek.setFixedWidth(200)
        self.seek.sliderMoved.connect(self.player.seek)
        ctrl_row.addWidget(self.seek)

        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setObjectName("elapsedLabel")
        self.time_label.setFixedWidth(80)
        ctrl_row.addWidget(self.time_label)

        vol_label = QLabel("🔊"); ctrl_row.addWidget(vol_label)
        self.vol = QSlider(Qt.Orientation.Horizontal)
        self.vol.setObjectName("previewSeek")
        self.vol.setRange(0, 100); self.vol.setValue(80); self.vol.setFixedWidth(80)
        self.vol.valueChanged.connect(self.player.set_volume)
        ctrl_row.addWidget(self.vol)

        layout.addLayout(ctrl_row)

        self.player.state_changed.connect(self._on_state)
        self.player.position_changed.connect(self._on_position)
        self.player.duration_changed.connect(self._on_duration)
        self.player.track_changed.connect(self._on_track)
        self.player.lyrics_line_changed.connect(self.lyrics_label.setText)

    def _toggle_play(self):
        from PyQt6.QtMultimedia import QMediaPlayer as _QMP
        if self.player.player.playbackState() == _QMP.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_state(self, state):
        self.play_btn.setText("⏸" if state == "playing" else "▶")

    def _on_position(self, ms):
        self.seek.blockSignals(True)
        self.seek.setValue(ms)
        self.seek.blockSignals(False)
        self._update_time()

    def _on_duration(self, ms):
        self.seek.setMaximum(max(ms, 1))
        self._update_time()

    def _on_track(self, artist, title):
        self.track_label.setText(f"▶  {artist} — {title}" if title else "No track loaded")

    def _update_time(self):
        pos = self.player.player.position() // 1000
        dur = max(self.player.player.duration() // 1000, 0)
        self.time_label.setText(f"{pos//60}:{pos%60:02d} / {dur//60}:{dur%60:02d}")

# ─────────────────────────────────────────────────────────────────────────────
# Flow Layout
# ─────────────────────────────────────────────────────────────────────────────

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=10):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items = []

    def addItem(self, item): self._items.append(item)
    def count(self): return len(self._items)
    def itemAt(self, index):
        if 0 <= index < len(self._items): return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items): return self._items.pop(index)
        return None

    def expandingDirections(self): return Qt.Orientation(0)
    def hasHeightForWidth(self): return True
    def heightForWidth(self, width): return self._doLayout(QRect(0, 0, width, 0), False)
    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._doLayout(rect, True)

    def sizeHint(self): return self.minimumSize()
    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _doLayout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0
        for item in self._items:
            wid = item.widget()
            if wid is None: continue
            hint = wid.sizeHint()
            next_x = x + hint.width() + self.spacing()
            if next_x - self.spacing() > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + self.spacing()
                next_x = x + hint.width() + self.spacing()
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y()

# ─────────────────────────────────────────────────────────────────────────────
# Command Palette
# ─────────────────────────────────────────────────────────────────────────────

class CommandPalette(QDialog):
    def __init__(self, library, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Command Palette")
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.resize(450, 300)
        self._library = library
        self._parent_ref = parent

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search artists, tabs, or actions...")
        self.search.setObjectName("searchBox")
        self.search.textChanged.connect(self._filter)
        self.search.returnPressed.connect(self._execute)
        layout.addWidget(self.search)

        self.list = QListWidget()
        self.list.setObjectName("managerList")
        self.list.itemClicked.connect(self._execute)
        layout.addWidget(self.list)

        self._populate()

    def _populate(self):
        self.list.clear()
        actions = [
            ("➡ Go to Library", "tab:0"),
            ("➡ Go to New Releases", "tab:1"),
            ("➡ Go to Popularity", "tab:2"),
            ("➡ Go to Recommendations", "tab:3"),
            ("➡ Go to Stats", "tab:4"),
            ("➡ Go to Hash Analysis", "tab:5"),
            ("⚙ Open Settings", "settings"),
            ("⚙ Open Black/Whitelist", "lists"),
        ]
        for txt, data in actions:
            item = QListWidgetItem(txt)
            item.setData(Qt.ItemDataRole.UserRole, data)
            self.list.addItem(item)

        for artist in sorted(self._library.keys()):
            item = QListWidgetItem(f"🎵 {artist}")
            item.setData(Qt.ItemDataRole.UserRole, f"artist:{artist}")
            self.list.addItem(item)

        self.list.setCurrentRow(0)

    def _filter(self, text):
        text = text.lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(text not in item.text().lower())
        for i in range(self.list.count()):
            if not self.list.item(i).isHidden():
                self.list.setCurrentRow(i)
                break

    def _execute(self):
        item = self.list.currentItem()
        if not item: return
        data = item.data(Qt.ItemDataRole.UserRole)
        if data.startswith("tab:"):
            self._parent_ref.tabs.setCurrentIndex(int(data.split(":")[1]))
        elif data == "settings":
            self._parent_ref._open_settings()
        elif data == "lists":
            self._parent_ref._open_lists()
        elif data.startswith("artist:"):
            artist = data.split(":", 1)[1]
            self._parent_ref.tabs.setCurrentIndex(0)
            self._parent_ref._populate_lib_tree({artist: self._library[artist]})
        self.accept()

# ─────────────────────────────────────────────────────────────────────────────
# Artist / Album cards
# ─────────────────────────────────────────────────────────────────────────────

class ArtCard(QFrame):
    clicked_sig=pyqtSignal(str)

    def __init__(self,key,title,sub,color:QColor,art_mbid="",is_artist=True,files=None,parent=None):
        super().__init__(parent); self.setObjectName("artistCard")
        self.setFixedSize(200,220); self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._key=key; self._color=color; self._art_mbid=art_mbid; self._is_artist=is_artist
        self._files = files or []
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        self.art_lbl=QLabel(); self.art_lbl.setFixedSize(200,140)
        self.art_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.art_lbl.setObjectName("cardArt")
        self._set_placeholder(title[:2].upper() if title else "?")
        layout.addWidget(self.art_lbl)
        info_w=QWidget(); info_l=QVBoxLayout(info_w)
        info_l.setContentsMargins(8,6,8,6); info_l.setSpacing(2)
        nl=QLabel(title); nl.setObjectName("cardName"); nl.setWordWrap(True)
        sl=QLabel(sub);   sl.setObjectName("cardSub")
        info_l.addWidget(nl); info_l.addWidget(sl)
        layout.addWidget(info_w,stretch=1)

        loader=ArtworkLoader.instance()
        if art_mbid and not is_artist:
            loader.loaded.connect(self._on_art)
            loader.request(art_mbid,f"{CAA_BASE}/release-group/{art_mbid}/front-250")
        elif is_artist and art_mbid:
            loader.loaded.connect(self._on_art)
            loader.get_artist_art(key, art_mbid)
        elif not is_artist and self._files:
            self._load_embedded_art()

    def _set_placeholder(self,letters):
        px=QPixmap(200,140); px.fill(self._color)
        p=QPainter(px); p.setPen(QColor(255,255,255,200))
        f=p.font(); f.setPointSize(28); f.setBold(True); p.setFont(f)
        p.drawText(px.rect(),Qt.AlignmentFlag.AlignCenter,letters); p.end()
        self.art_lbl.setPixmap(px)

    def _load_embedded_art(self):
        import threading
        def _fetch():
            for fp_str in self._files:
                try:
                    fp = Path(fp_str)
                    a = MutagenFile(fp)
                    if a and hasattr(a, 'tags'):
                        if 'APIC:' in a.tags:
                            data = a.tags['APIC:'].data
                            QTimer.singleShot(0, lambda d=data: self._on_art("embedded", d))
                            return
                        if hasattr(a, 'pictures') and a.pictures:
                            data = a.pictures[0].data
                            QTimer.singleShot(0, lambda d=data: self._on_art("embedded", d))
                            return
                        if 'covr' in a.tags:
                            data = a.tags['covr'][0]
                            QTimer.singleShot(0, lambda d=data: self._on_art("embedded", d))
                            return
                except Exception:
                    pass
        threading.Thread(target=_fetch, daemon=True).start()

    def _on_art(self,mbid:str,data:bytes):
        expected=f"artist_{self._art_mbid}" if self._is_artist else self._art_mbid
        if mbid!=expected and mbid!="embedded": return
        px=QPixmap()
        if px.loadFromData(data):
            self.art_lbl.setPixmap(
                px.scaled(200,140,Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                          Qt.TransformationMode.SmoothTransformation).copy(0,0,200,140))

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton: self.clicked_sig.emit(self._key)
        super().mousePressEvent(event)

    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(0,0,self.width(),8,self._color); p.end()
        super().paintEvent(event)

class GridWidget(QWidget):
    artist_clicked=pyqtSignal(str)

    def __init__(self,parent=None):
        super().__init__(parent)
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,4); layout.setSpacing(4)
        nav=QHBoxLayout()
        self.back_btn=QPushButton("← Back to Artists")
        self.back_btn.setObjectName("toolBtn"); self.back_btn.setFixedHeight(28)
        self.back_btn.hide(); self.back_btn.clicked.connect(self.show_artists)
        self.breadcrumb=QLabel(""); self.breadcrumb.setObjectName("progressInfo")
        nav.addWidget(self.back_btn); nav.addWidget(self.breadcrumb); nav.addStretch()
        layout.addLayout(nav)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True)
        self._inner=QWidget()
        self._flow=FlowLayout(self._inner, spacing=10)
        self._flow.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self._inner); layout.addWidget(self.scroll)
        self._library:dict={}; self._popularity:dict={}
        self._ds_ref=None
        self._sort_fn=lambda n: (0, n.lower(), n); self._current:str|None=None; self._cards:list=[]

    def set_data(self,library,popularity,sort_fn,ds_ref=None):
        self._library=library; self._popularity=popularity; self._sort_fn=sort_fn
        if ds_ref is not None: self._ds_ref=ds_ref

    def show_artists(self):
        self._current=None; self.back_btn.hide(); self.breadcrumb.setText("")
        self._render_artists()

    def show_albums(self,artist:str):
        self._current=artist; self.back_btn.show()
        self.breadcrumb.setText(f"  Albums of:  {artist}"); self._render_albums(artist)

    def _clear(self):
        for c in self._cards: c.deleteLater()
        self._cards.clear()
        while self._flow.count():
            item=self._flow.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def _render_artists(self):
        self._clear()
        for artist in sorted(self._library.keys(),key=self._sort_fn):
            pop=self._popularity.get(artist,{}); hue=int(hashlib.md5(artist.encode()).hexdigest()[:4],16)%360
            mbid=self._get_mbid(artist)
            sub="  ".join(filter(None,[
                f"{len(self._library[artist])} releases",
                fmt_n(pop.get("listeners")), pop.get("stars",""), pop.get("area",""),
            ]))
            card=ArtCard(artist,artist,sub,QColor.fromHsl(hue,130,80),
                         art_mbid=mbid,is_artist=True)
            card.clicked_sig.connect(self._on_artist)
            self._cards.append(card)
            self._flow.addWidget(card)

    def _render_albums(self,artist:str):
        self._clear()
        for r in sorted(self._library.get(artist,[]),
                        key=lambda x:(x.get("year",""),x.get("album",""))):
            hue=int(hashlib.md5(r.get("album","").encode()).hexdigest()[:4],16)%360
            lyr=lyrics_emoji(r.get("lyr_status","none"))
            sub="  ".join(filter(None,[r.get("year",""),r.get("type",""),
                                       r.get("genre",""),lyr]))
            card=ArtCard(r.get("album",""),r.get("album",""),sub,
                         QColor.fromHsl(hue,100,90),
                         art_mbid=r.get("mbid",""),is_artist=False,
                         files=r.get("files",[]))
            self._cards.append(card)
            self._flow.addWidget(card)

    def _get_mbid(self,artist:str)->str:
        try: return self._ds_ref.mb_cache.get(artist,{}).get("mbid","")
        except Exception: return ""

    def _on_artist(self,key:str):
        if key in self._library: self.show_albums(key); self.artist_clicked.emit(key)

    def resizeEvent(self,event):
        super().resizeEvent(event); QTimer.singleShot(50,self._re_render)

    def _re_render(self):
        if self._current: self._render_albums(self._current)
        else:             self._render_artists()
