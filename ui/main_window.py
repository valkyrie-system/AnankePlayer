import os, sys, re, time, json, threading, datetime, subprocess, webbrowser, hashlib, requests
from pathlib import Path
from collections import Counter
from ui.themes import THEMES
from ui.dialogs import (
    DuplicateManagerDialog, ListManagerDialog, TagEditorDialog,
    PlaylistGeneratorDialog, BackupManagerDialog, SettingsDialog, GeniusViewerDialog,
    LibraryOrganizerDialog, OrganizerThread
)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog,
    QTreeWidget, QTreeWidgetItem, QLineEdit, QProgressBar, QStatusBar, QListWidget,
    QListWidgetItem, QSplitter, QFrame, QMessageBox, QTabWidget, QSpinBox, QCheckBox,
    QDialog, QDialogButtonBox, QScrollArea, QStackedWidget, QSizePolicy, QAbstractItemView,
    QComboBox, QSlider, QMenu, QGroupBox, QTextBrowser, QSystemTrayIcon, QStyle, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings, QTimer, QObject, QUrl, QFileSystemWatcher, QPoint, QRect, QSize, pyqtSlot, pyqtProperty
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap, QClipboard, QDesktopServices, QIcon, QShortcut, QKeySequence

try:
    from PyQt6.QtDBus import QDBusConnection, QDBusAbstractAdaptor
    HAS_DBUS = True
except ImportError:
    HAS_DBUS = False

from core.utils import (
    APP_NAME, ORG_NAME, APP_VERSION, GITHUB_REPO, DATA_DIR, ART_DIR, UNKNOWN, GEO_COUNTRIES, check_squid_health,
    sort_key, fmt_n, stars, fmt_dur, lyrics_emoji, album_lyrics_status, extract_tags,
    should_auto_blacklist, canonical_artist, Notifier
)
from core.datastore import DataStore
from services.lastfm import LastFMScrobbler
from services.listenbrainz import ListenBrainzSubmitter
from services.soulseek import SoulSeekDownloadThread
from services.musicbrainz import NewReleaseChecker
from threads.scanner import ScannerThread
from threads.fetchers import PopularityFetcher, ArtworkFetcher
from services.lyrics import LyricsFetcher
from services.artwork import ArtworkLoader

from ui.widgets import (
    ProgressWidget, FolderPanel, PreviewPlayer, LocalPlayer, PlayerBar,
    FlowLayout, CommandPalette, GridWidget, ArtCard
)
from ui.dialogs import (
    DuplicateManagerDialog, ListManagerDialog, TagEditorDialog,
    PlaylistGeneratorDialog, BackupManagerDialog, SettingsDialog, GeniusViewerDialog
)

if HAS_DBUS:
    class MPRISAdaptor(QDBusAbstractAdaptor):
        def __init__(self, parent):
            super().__init__(parent)
            self.setAutoRelaySignals(True)
        @pyqtSlot()
        def Play(self): self.parent().mp_play()
        @pyqtSlot()
        def Pause(self): self.parent().mp_pause()
        @pyqtSlot()
        def PlayPause(self): self.parent().mp_playpause()
        @pyqtSlot()
        def Stop(self): self.parent().mp_stop()
        @pyqtProperty(str)
        def Identity(self): return "MusicWatcher"
        @pyqtProperty(bool)
        def CanPlay(self): return True
        @pyqtProperty(bool)
        def CanPause(self): return True
        @pyqtProperty(bool)
        def CanControl(self): return True

class MusicWatcher(QMainWindow):
    def __init__(self, hw: dict = None):
        super().__init__()
        self.setWindowTitle(APP_NAME); self.resize(1260,860)
        self._hw = hw if hw else {"cpu": 4, "ram_gb": 8, "workers": 8, "lyrics_workers": 16, "gpu_vendor": "unknown", "gpu_name": ""}
        self.ds = DataStore(self._hw)
        self._qs = QSettings(ORG_NAME, APP_NAME)
        self._library: dict = self.ds.library.copy()
        self._popularity: dict = {}
        self._new_releases: dict = {}
        self._new_pop: dict = {}
        self._duplicates: dict = {}
        self._changed: list = []
        self._scan_folders: list = []
        check_squid_health(self.ds)
        self._lists_dialog = None
        self._scanner = self._checker = self._pop_lib = self._pop_new = self._lyrfetch = self._artfetch = None

        self._watcher = QFileSystemWatcher()
        self._watcher.directoryChanged.connect(self._on_watch_dir_changed)
        self._watch_timer = QTimer(self)
        self._watch_timer.setSingleShot(True)
        self._watch_timer.setInterval(3000)
        self._watch_timer.timeout.connect(self._auto_scan)
        self._auto_scanning = False

        self.local_player = LocalPlayer()
        self.scrobbler = LastFMScrobbler(self.ds)
        self.lb_submitter = ListenBrainzSubmitter(self.ds)
        self._soulseek_thread = None
        self._current_scrobble_artist = ""
        self._current_scrobble_track = ""
        self._current_scrobble_album = ""
        self._scrobble_start_time = 0

        self.local_player.track_changed.connect(self._on_player_track_changed)
        self.local_player.state_changed.connect(self._on_player_state_changed)

        self._build_ui(); self._apply_theme(); self._restore_session()
        self._restore_ui_state()

        self._tray = QSystemTrayIcon(self)
        self._tray.setToolTip(APP_NAME)
        tray_menu = QMenu(self)
        show_action = tray_menu.addAction("Show Window")
        show_action.triggered.connect(self.showNormal)
        quit_action = tray_menu.addAction("Quit MusicWatcher")
        quit_action.triggered.connect(self._real_quit)
        self._tray.setContextMenu(tray_menu)
        self._load_tray_icon()
        self._tray.show()

        self._palette_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self._palette_shortcut.activated.connect(self._open_palette)

        # --- New Music Friday Radar ---
        self._radar_timer = QTimer(self)
        self._radar_timer.setInterval(6 * 3600 * 1000) # Check every 6 hours
        self._radar_timer.timeout.connect(self._check_new_music_radar)
        self._radar_timer.start()

        # Fire it once 10 seconds after startup so it doesn't block the UI drawing
        QTimer.singleShot(10000, self._check_new_music_radar)

    def _check_new_music_radar(self):
        """Background check for brand new releases from Favorite artists."""
        if not self.ds.favorites:
            return  # Don't run if user has no favorites

        today = datetime.datetime.now().date()
        yesterday = today - datetime.timedelta(days=2)  # Give a 2-day buffer for different timezones

        # reuse the NewReleaseChecker thread
        self._radar_checker = NewReleaseChecker(
            list(self.ds.favorites),
            self.ds,
            yesterday.year,
            today.year,
            self._library
        )

        def _on_radar_done(artist, releases):
            # Filter strictly for releases that came out today or yesterday
            brand_new = []
            for r in releases:
                try:
                    rel_date = datetime.datetime.strptime(r.get("year", "1900"), "%Y-%m-%d").date()
                    if yesterday <= rel_date <= today:
                        brand_new.append(r)
                except Exception:
                    pass  # If date parsing fails, ignore

            if brand_new:
                title = f"New Music Alert: {artist}"
                msg = f"New release out today!\n{', '.join(r['title'] for r in brand_new)}"
                Notifier.notify(title, msg)
                if hasattr(self, '_tray') and self._tray.isVisible():
                    self._tray.showMessage(title, msg, QSystemTrayIcon.MessageSeverity.Information, 10000)

        self._radar_checker.artist_done.connect(_on_radar_done)
        self._radar_checker.start()

        if self._library:
            self._populate_lib_tree(self._library); self._update_btns()
            self.status_bar.showMessage(f"Library loaded from cache — {len(self._library):,} artists.  Data: {DATA_DIR}")

        self._dbus_conn = None
        self._mpris = None
        if HAS_DBUS and sys.platform.startswith("linux"):
            self._dbus_conn = QDBusConnection.sessionBus()
            if self._dbus_conn.isConnected():
                self._dbus_conn.registerService("org.mpris.MediaPlayer2.MusicWatcher")
                self._dbus_conn.registerObject("/org/mpris/MediaPlayer2", self)
                self._mpris = MPRISAdaptor(self)

        # NEW: Check for GitHub updates 15 seconds after startup
        QTimer.singleShot(15000, lambda: self._check_for_updates(silent=True))

    def _build_ui(self):
        central=QWidget(); self.setCentralWidget(central)
        root=QVBoxLayout(central); root.setContentsMargins(8,8,8,4); root.setSpacing(6)

        tb=QHBoxLayout(); tb.setSpacing(6)
        self.theme_btn=QPushButton("☀  Light"); self.theme_btn.setObjectName("toolBtn")
        self.theme_btn.setFixedHeight(30); self.theme_btn.clicked.connect(self._toggle_theme)
        # Add this line to make the button text dynamic:
        self.theme_btn.setText("☀  Light" if self.ds.settings.get("theme_name", "Dark") == "Dark" else "🌙  Dark")
        self.view_btn=QPushButton("⊞  Grid"); self.view_btn.setObjectName("toolBtn")
        self.view_btn.setFixedHeight(30); self.view_btn.clicked.connect(self._toggle_view)
        fup=QPushButton("A+"); fup.setObjectName("toolBtn"); fup.setFixedSize(34,30)
        fup.clicked.connect(lambda:self._chg_font(1))
        fdn=QPushButton("A−"); fdn.setObjectName("toolBtn"); fdn.setFixedSize(34,30)
        fdn.clicked.connect(lambda:self._chg_font(-1))
        self.sort_combo=QComboBox(); self.sort_combo.setObjectName("sortCombo")
        self.sort_combo.setFixedHeight(30)
        self.sort_combo.addItems(["Sort: 0→#→A→Ω","Sort: Z→A","Sort: Listeners ↓"])
        self.sort_combo.currentIndexChanged.connect(self._apply_lib_filter)
        lists_btn=QPushButton("◉  Black/Whitelist"); lists_btn.setObjectName("toolBtn")
        lists_btn.setFixedHeight(30); lists_btn.clicked.connect(self._open_lists)
        settings_btn=QPushButton("⚙  Settings"); settings_btn.setObjectName("toolBtn")
        settings_btn.setFixedHeight(30); settings_btn.clicked.connect(self._open_settings)
        data_btn=QPushButton("📁  Data Dir"); data_btn.setObjectName("toolBtn")
        data_btn.setFixedHeight(30); data_btn.clicked.connect(self._open_data_dir)
        for w in(self.theme_btn,self.view_btn,fup,fdn,self.sort_combo): tb.addWidget(w)
        tb.addStretch()
        for w in(lists_btn,settings_btn,data_btn): tb.addWidget(w)
        root.addLayout(tb)

        sp=QSplitter(Qt.Orientation.Horizontal)
        self.sp = sp
        sp.setObjectName("mainSplitter"); sp.setHandleWidth(2)
        self.folder_panel=FolderPanel()
        self.folder_panel.setMinimumWidth(168); self.folder_panel.setMaximumWidth(262)
        self.folder_panel.folders_changed.connect(self._on_folders_changed)
        sp.addWidget(self.folder_panel)

        right=QWidget(); rl=QVBoxLayout(right)
        rl.setContentsMargins(6,0,0,0); rl.setSpacing(6)
        self.tabs=QTabWidget(); self.tabs.setObjectName("mainTabs")
        rl.addWidget(self.tabs)

        # ── Library tab ────────────────────────────────────────────────
        lt=QWidget(); ll=QVBoxLayout(lt)
        ll.setContentsMargins(0,6,0,0); ll.setSpacing(5)

        sr=QHBoxLayout()
        self.scan_btn=QPushButton("▶  Scan All Folders")
        self.scan_btn.setObjectName("primaryBtn"); self.scan_btn.setFixedHeight(36)
        self.scan_btn.setEnabled(False); self.scan_btn.clicked.connect(self._start_scan)
        self.search_box=QLineEdit(); self.search_box.setPlaceholderText("Filter library…")
        self.search_box.setObjectName("searchBox"); self.search_box.setFixedHeight(36)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._apply_lib_filter)
        self.search_box.textChanged.connect(lambda: self._search_timer.start())
        self.hash_chk=QCheckBox("SHA-256 hashing"); self.hash_chk.setObjectName("hashChk")
        self.hash_chk.stateChanged.connect(lambda v:self.ds.settings.update({"hash_enabled":bool(v)}))
        self.watch_chk=QCheckBox("👁 Watch"); self.watch_chk.setObjectName("hashChk")
        self.watch_chk.setChecked(self.ds.settings.get("watch_folders",False))
        self.watch_chk.stateChanged.connect(lambda v:(self.ds.settings.update({"watch_folders":bool(v)}), self._update_watcher()))
        sr.addWidget(self.scan_btn); sr.addWidget(self.search_box,stretch=1)
        sr.addWidget(self.hash_chk); sr.addWidget(self.watch_chk); ll.addLayout(sr)

        af=QHBoxLayout(); af.addWidget(QLabel("Filter artist:"))
        self.lib_af=QLineEdit(); self.lib_af.setPlaceholderText("Type artist name…")
        self.lib_af.setObjectName("searchBox"); self.lib_af.setFixedHeight(28)
        self.lib_af.textChanged.connect(self._apply_lib_filter)
        af.addWidget(self.lib_af,stretch=1)
        self.lib_pop_btn=QPushButton("📊  Fetch Popularity")
        self.lib_pop_btn.setObjectName("secondaryBtn"); self.lib_pop_btn.setFixedHeight(28)
        self.lib_pop_btn.setEnabled(False); self.lib_pop_btn.clicked.connect(self._start_lib_pop)
        af.addWidget(self.lib_pop_btn)

        self.lib_art_btn=QPushButton("🎨  Fetch Art")
        self.lib_art_btn.setObjectName("secondaryBtn"); self.lib_art_btn.setFixedHeight(28)
        self.lib_art_btn.setEnabled(False); self.lib_art_btn.clicked.connect(self._start_lib_art)
        af.addWidget(self.lib_art_btn); af.addWidget(QLabel("Min listeners:"))
        self.lib_min=QSpinBox(); self.lib_min.setRange(0,100_000_000)
        self.lib_min.setSingleStep(10_000); self.lib_min.setFixedWidth(108)
        self.lib_min.valueChanged.connect(self._apply_lib_filter)
        af.addWidget(self.lib_min)

        # NEW: Library List Filter Dropdown
        af.addWidget(QLabel("Show:"))
        self.lib_list_filter = QComboBox()
        self.lib_list_filter.addItems(["All", "Favorites", "Whitelist", "Blacklist"])
        self.lib_list_filter.currentIndexChanged.connect(self._apply_lib_filter)
        af.addWidget(self.lib_list_filter)

        ll.addLayout(af)

        self.scan_prog=ProgressWidget("Scan")
        self.scan_prog.pause_toggled.connect(self._on_scan_pause)
        self.scan_prog.stopped.connect(self._stop_scan); ll.addWidget(self.scan_prog)
        self.hash_prog=ProgressWidget("Hashing"); ll.addWidget(self.hash_prog)

        self.stack=QStackedWidget()
        self.tree=QTreeWidget(); self.tree.setObjectName("musicTree")
        self.tree.setHeaderLabels(["Artist / Release","Year","Type","Genre","Lyrics","Listeners","Stars"])
        self.tree.setColumnWidth(0,310); self.tree.setColumnWidth(1,48)
        self.tree.setColumnWidth(2,58); self.tree.setColumnWidth(3,110)
        self.tree.setColumnWidth(4,54); self.tree.setColumnWidth(5,78)
        self.tree.setColumnWidth(6,88)
        self.tree.setAlternatingRowColors(True); self.tree.setSortingEnabled(True)
        self.tree.setAnimated(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_context_menu)
        self.grid_view=GridWidget(); self.grid_view.artist_clicked.connect(lambda _:None)
        self.stack.addWidget(self.tree); self.stack.addWidget(self.grid_view)
        ll.addWidget(self.stack)

        lyr_row=QHBoxLayout()
        self.lyrics_btn=QPushButton("🎵  Fetch Lyrics (lrclib.net)")
        self.lyrics_btn.setObjectName("secondaryBtn"); self.lyrics_btn.setFixedHeight(28)
        self.lyrics_btn.setEnabled(False); self.lyrics_btn.clicked.connect(self._start_lyrics)
        lyr_row.addWidget(self.lyrics_btn); lyr_row.addStretch(); ll.addLayout(lyr_row)
        self.lyrics_prog=ProgressWidget("Lyrics fetch")
        self.lyrics_prog.pause_toggled.connect(self._on_lyrics_pause)
        self.lyrics_prog.stopped.connect(self._stop_lyrics)
        ll.addWidget(self.lyrics_prog)
        self.tabs.addTab(lt,"Library")

        # ── New Releases tab ───────────────────────────────────────────
        nt=QWidget(); nl=QVBoxLayout(nt)
        nl.setContentsMargins(0,6,0,0); nl.setSpacing(5)

        cr=QHBoxLayout()
        self.check_btn=QPushButton("🔍  Check New Releases")
        self.check_btn.setObjectName("primaryBtn"); self.check_btn.setFixedHeight(36)
        self.check_btn.setEnabled(False); self.check_btn.clicked.connect(self._start_check)
        cr.addWidget(self.check_btn)

        # NEW: Gap Radar Button
        self.gap_btn=QPushButton("📉 Find Missing Albums")
        self.gap_btn.setObjectName("secondaryBtn"); self.gap_btn.setFixedHeight(36)
        self.gap_btn.setEnabled(False); self.gap_btn.clicked.connect(self._start_gap_radar)
        cr.addWidget(self.gap_btn)

        cr.addWidget(QLabel("Years:"))
        cur=datetime.datetime.now().year
        self.year_from=QSpinBox(); self.year_from.setRange(1900,2100)
        self.year_from.setValue(cur-1); self.year_from.setFixedWidth(74)
        self.year_to=QSpinBox(); self.year_to.setRange(1900,2100)
        self.year_to.setValue(cur+1); self.year_to.setFixedWidth(74)
        cr.addWidget(self.year_from); cr.addWidget(QLabel("to")); cr.addWidget(self.year_to)
        cr.addStretch()
        cr.addWidget(QLabel("Show:"))
        self.rt_album=QCheckBox("Albums");   self.rt_album.setChecked(True)
        self.rt_ep   =QCheckBox("EPs");      self.rt_ep.setChecked(True)
        self.rt_single=QCheckBox("Singles"); self.rt_single.setChecked(True)
        for cb in(self.rt_album,self.rt_ep,self.rt_single):
            cb.stateChanged.connect(self._apply_new_filter); cr.addWidget(cb)

        # NEW: Filter by List dropdown
        cr.addWidget(QLabel("Filter:"))
        self.new_list_filter = QComboBox()
        self.new_list_filter.addItems(["All", "Favorites Only", "Whitelist Only"])
        self.new_list_filter.currentIndexChanged.connect(self._apply_new_filter)
        cr.addWidget(self.new_list_filter)

        nl.addLayout(cr)

        naf=QHBoxLayout(); naf.addWidget(QLabel("Filter artist:"))
        self.new_af=QLineEdit(); self.new_af.setPlaceholderText("Type artist name…")
        self.new_af.setObjectName("searchBox"); self.new_af.setFixedHeight(28)
        self.new_af.textChanged.connect(self._apply_new_filter)
        naf.addWidget(self.new_af,stretch=1)
        self.new_pop_btn=QPushButton("📊  Fetch Popularity")
        self.new_pop_btn.setObjectName("secondaryBtn"); self.new_pop_btn.setFixedHeight(28)
        self.new_pop_btn.setEnabled(False); self.new_pop_btn.clicked.connect(self._start_new_pop)
        naf.addWidget(self.new_pop_btn); naf.addWidget(QLabel("Min listeners:"))
        self.new_min=QSpinBox(); self.new_min.setRange(0,100_000_000)
        self.new_min.setSingleStep(10_000); self.new_min.setFixedWidth(108)
        self.new_min.valueChanged.connect(self._apply_new_filter)
        naf.addWidget(self.new_min); nl.addLayout(naf)

        self.check_prog=ProgressWidget("MusicBrainz check")
        self.check_prog.pause_toggled.connect(self._on_check_pause)
        self.check_prog.stopped.connect(self._stop_check); nl.addWidget(self.check_prog)

        self.new_tree=QTreeWidget(); self.new_tree.setObjectName("newTree")
        self.new_tree.setHeaderLabels(["Artist / Release","Year","Type","Genre","LB Listeners","LFM Listeners","Stars","Region","Global Rank"])
        self.new_tree.setColumnWidth(0,270); self.new_tree.setColumnWidth(1,46)
        self.new_tree.setColumnWidth(2,54); self.new_tree.setColumnWidth(3,90)
        self.new_tree.setColumnWidth(4,88); self.new_tree.setColumnWidth(5,95)
        self.new_tree.setColumnWidth(6,86); self.new_tree.setColumnWidth(7,95)
        self.new_tree.setColumnWidth(8,88)
        self.new_tree.setAlternatingRowColors(True); self.new_tree.setSortingEnabled(True)
        self.new_tree.setAnimated(True)
        self.new_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.new_tree.customContextMenuRequested.connect(self._new_tree_context_menu)

        self.new_stack = QStackedWidget()
        self.new_grid = GridWidget(); self.new_grid.artist_clicked.connect(lambda _:None)
        self.new_stack.addWidget(self.new_tree)
        self.new_stack.addWidget(self.new_grid)
        nl.addWidget(self.new_stack)
        nl.addWidget(QLabel(f"MusicBrainz ~1 req/sec · 7-day cache · saved to {DATA_DIR}/new_releases.csv"))


        self.tabs.addTab(nt,"New Releases")

        # ── Popularity tab ─────────────────────────────────────────────
        pt=QWidget(); pl=QVBoxLayout(pt); pl.setContentsMargins(0,6,0,0)
        pl.addWidget(QLabel("Artist Popularity  (LB = ListenBrainz · LFM = Last.fm · source and countries configurable in Settings)"))
        self.pop_tree=QTreeWidget(); self.pop_tree.setObjectName("musicTree")
        self.pop_tree.setHeaderLabels(["Artist","LB Listeners","LFM Listeners","Stars","Origin","% of Top","Global Rank","Geo Ranks","Genre Tags","Similar Artists", "Blended", "Norm%"])
        for i,w in enumerate([220,88,95,100,115,72,85,140,160,200, 80, 60]):
            self.pop_tree.setColumnWidth(i,w)
        self.pop_tree.setAlternatingRowColors(True); self.pop_tree.setSortingEnabled(True)

        self.pop_stack = QStackedWidget()
        self.pop_grid = GridWidget(); self.pop_grid.artist_clicked.connect(lambda _:None)
        self.pop_stack.addWidget(self.pop_tree)
        self.pop_stack.addWidget(self.pop_grid)
        pl.addWidget(self.pop_stack)
        pl.addWidget(QLabel(f"⚠ Geo/Global ranks reflect Last.fm listener data, not official chart positions.  Popularity data saved to {DATA_DIR}/popularity.csv"))
        self.tabs.addTab(pt,"Popularity")

        # ── Recommendations tab ────────────────────────────────────────
        rt=QWidget(); rtl=QVBoxLayout(rt); rtl.setContentsMargins(0,6,0,0)
        rtl.addWidget(QLabel("Artist Recommendations (Based on similar artists in your library)"))
        rec_btn_row = QHBoxLayout()
        self.build_recs_btn = QPushButton("✨ Build Recommendations")
        self.build_recs_btn.setObjectName("primaryBtn"); self.build_recs_btn.setFixedHeight(36)
        self.build_recs_btn.clicked.connect(self._build_recs)
        rec_btn_row.addWidget(self.build_recs_btn); rec_btn_row.addStretch()
        rtl.addLayout(rec_btn_row)

        self.recs_stack = QStackedWidget()
        self.recs_tree = QTreeWidget(); self.recs_tree.setObjectName("musicTree")
        self.recs_tree.setHeaderLabels(["Artist","Match Count","Popularity","Norm%","Stars","Tags"])
        for i,w in enumerate([220,100,90,60,80,200]): self.recs_tree.setColumnWidth(i,w)
        self.recs_tree.setAlternatingRowColors(True); self.recs_tree.setSortingEnabled(True)
        self.recs_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.recs_tree.customContextMenuRequested.connect(self._recs_ctx)

        self.recs_grid = GridWidget(); self.recs_grid.artist_clicked.connect(lambda _:None)
        self.recs_stack.addWidget(self.recs_tree)
        self.recs_stack.addWidget(self.recs_grid)
        rtl.addWidget(self.recs_stack)
        self.tabs.addTab(rt,"Recs ♥")

        # ── Stats Dashboard tab ───────────────────────────────────────
        st_tab = QWidget(); stl = QVBoxLayout(st_tab)
        stl.setContentsMargins(0,6,0,0)

        stats_header = QLabel("📊 Library Statistics & Insights")
        stats_header.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        stl.addWidget(stats_header)

        self.stats_browser = QTextBrowser()
        self.stats_browser.setObjectName("musicTree")
        self.stats_browser.setOpenExternalLinks(True)
        stl.addWidget(self.stats_browser, stretch=1)

        pl_row = QHBoxLayout()
        pl_row.addStretch()

        self.export_btn = QPushButton("📥 Export Library")
        self.export_btn.setObjectName("secondaryBtn")
        self.export_btn.setFixedHeight(34)
        self.export_btn.clicked.connect(self._open_exporter)
        pl_row.addWidget(self.export_btn)

        self.organizer_btn = QPushButton("🤖 Library Organizer")
        self.organizer_btn.setObjectName("secondaryBtn")
        self.organizer_btn.setFixedHeight(34)
        self.organizer_btn.clicked.connect(self._open_organizer)
        pl_row.addWidget(self.organizer_btn)

        self.gen_playlist_btn = QPushButton("✨ Smart Playlist")
        self.gen_playlist_btn.setObjectName("secondaryBtn")
        self.gen_playlist_btn.setFixedHeight(34)
        self.gen_playlist_btn.clicked.connect(self._open_playlist_gen)
        pl_row.addWidget(self.gen_playlist_btn)
        stl.addLayout(pl_row)
        self.tabs.addTab(st_tab, "📊 Stats")

        # ── Hash Analysis tab ──────────────────────────────────────────
        hw_tab=QWidget(); htl=QVBoxLayout(hw_tab); htl.setContentsMargins(0,6,0,0)
        htl.addWidget(QLabel(f"Duplicates (audio-content hash; metadata ignored).  Manifest: {DATA_DIR}/hashes.csv"))
        dup_top=QHBoxLayout()
        self.open_dup_btn=QPushButton("🗑  Manage Duplicate Files")
        self.open_dup_btn.setObjectName("removeBtn"); self.open_dup_btn.setFixedHeight(30)
        self.open_dup_btn.setEnabled(False); self.open_dup_btn.clicked.connect(self._open_dup_manager)
        dup_top.addWidget(self.open_dup_btn); dup_top.addStretch(); htl.addLayout(dup_top)
        self.dup_tree=QTreeWidget(); self.dup_tree.setObjectName("dupTree")
        self.dup_tree.setHeaderLabels(["File path","Type","Duration","Hash (10)","Size"])
        self.dup_tree.setColumnWidth(0,450); self.dup_tree.setColumnWidth(1,65)
        self.dup_tree.setColumnWidth(2,68); self.dup_tree.setColumnWidth(3,85)
        self.dup_tree.setColumnWidth(4,75)
        self.dup_tree.setAlternatingRowColors(True); self.dup_tree.setAnimated(True)
        htl.addWidget(self.dup_tree,stretch=1)
        htl.addWidget(QLabel("Changed files (hash differs from previous scan):"))
        self.changed_tree=QTreeWidget(); self.changed_tree.setObjectName("changedTree")
        self.changed_tree.setHeaderLabels(["File path"])
        self.changed_tree.setAlternatingRowColors(True)
        htl.addWidget(self.changed_tree,stretch=1)
        self.tabs.addTab(hw_tab,"Hash Analysis")

        sp.addWidget(right); sp.setStretchFactor(0,0); sp.setStretchFactor(1,1)
        root.addWidget(sp)

        self.main_player_bar = PlayerBar(self.local_player, self)
        root.addWidget(self.main_player_bar)

        self.status_bar=QStatusBar(); self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(f"Welcome to MusicWatcher  ·  Data: {DATA_DIR}")

    def _open_organizer(self):
        dlg = LibraryOrganizerDialog(self)
        dlg.exec()

    def _open_exporter(self):
        from ui.dialogs import LibraryExporterDialog
        dlg = LibraryExporterDialog(self.ds, self)
        dlg.exec()

    def _apply_theme(self):
        # Default to "Dark" if the setting doesn't exist yet
        current_theme = self.ds.settings.get("theme_name", "Dark")
        css = THEMES.get(current_theme, THEMES["Dark"])
        self.setStyleSheet(css)
        f = QApplication.instance().font()
        f.setPointSize(self.ds.settings.get("font_size", 13))
        QApplication.instance().setFont(f)

    def _css(self, dark: bool) -> str:
        if dark:
            return("QMainWindow,QWidget{background:#1a1a2e;color:#e0e0f0;font-family:'Segoe UI','SF Pro Display',sans-serif;}"
                   "QTabWidget::pane{border:none;}"
                   "QTabBar::tab{background:#22223a;color:#8888bb;padding:7px 18px;border-radius:4px 4px 0 0;margin-right:2px;font-weight:600;}"
                   "QTabBar::tab:selected{background:#1a1a2e;color:#d0b0ff;}"
                   "QTabBar::tab:hover{background:#2a2a4a;}"
                   "#folderPanel{background:#12122a;border-right:1px solid #2a2a50;padding:8px;}"
                   "#panelHeader{font-size:11px;font-weight:700;letter-spacing:1px;color:#7766aa;}"
                   "#folderList,#managerList{background:#1a1a38;border:1px solid #2a2a50;border-radius:5px;color:#c0c0e0;}"
                   "#folderList::item,#managerList::item{padding:5px 6px;}"
                   "#folderList::item:selected,#managerList::item:selected{background:#3a2a6a;color:#fff;}"
                   "#addBtn{background:#2a3a2a;color:#88cc88;border:1px solid #335533;border-radius:4px;font-weight:600;}"
                   "#removeBtn{background:#3a2020;color:#cc8888;border:1px solid #553333;border-radius:4px;font-weight:600;}"
                   "#removeBtn:disabled{color:#555;background:#222;border-color:#333;}"
                   "#primaryBtn{background:#3a2a6a;color:#d0b0ff;border:1px solid #5544aa;border-radius:5px;padding:4px 18px;font-weight:700;}"
                   "#primaryBtn:disabled{color:#555580;background:#22223a;border-color:#333;}"
                   "#secondaryBtn{background:#1a2a3a;color:#88bbdd;border:1px solid #2a4a66;border-radius:4px;font-weight:600;}"
                   "#toolBtn{background:#22223a;color:#aabbcc;border:1px solid #333358;border-radius:4px;font-weight:600;}"
                   "#pauseBtn{background:#2a2a50;color:#aabbee;border:1px solid #3a3a70;border-radius:5px;padding:2px 12px;font-weight:600;}"
                   "#stopBtn{background:#3a1a1a;color:#ff8888;border:1px solid #662222;border-radius:5px;padding:2px 12px;font-weight:700;}"
                   "#searchBox{background:#12122a;border:1px solid #333358;border-radius:5px;color:#e0e0f0;padding:2px 10px;}"
                   "#musicTree,#newTree,#dupTree,#changedTree{background:#12122a;alternate-background-color:#1a1a38;border:1px solid #2a2a50;border-radius:6px;outline:none;}"
                   "#musicTree::item:selected,#newTree::item:selected,#dupTree::item:selected,#changedTree::item:selected{background:#3a2a6a;color:#fff;}"
                   "QHeaderView::section{background:#22223a;color:#8888bb;border:none;border-bottom:1px solid #333358;padding:6px 8px;font-weight:700;font-size:11px;}"
                   "#bigBar{background:#22223a;border-radius:5px;}"
                   "#bigBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #5533aa,stop:1 #9944cc);border-radius:5px;}"
                   "QStatusBar{background:#12122a;color:#6666aa;font-size:11px;}"
                   "QScrollBar:vertical{background:#12122a;width:10px;border-radius:5px;}"
                   "QScrollBar::handle:vertical{background:#333368;border-radius:5px;}"
                   "#artistCard{background:#1e1e3a;border:1px solid #2a2a50;border-radius:8px;}"
                   "#previewPlayBtn{background:#3a2a6a;color:#d0b0ff;border:1px solid #5544aa;border-radius:18px;font-weight:700;font-size:16px;}"
                   )
        else:
            return("QMainWindow,QWidget{background:#f0f0f8;color:#1a1a2e;font-family:'Segoe UI','SF Pro Display',sans-serif;}"
                   "QTabWidget::pane{border:none;}"
                   "QTabBar::tab{background:#dcdcec;color:#444488;padding:7px 18px;border-radius:4px 4px 0 0;margin-right:2px;font-weight:600;}"
                   "QTabBar::tab:selected{background:#f0f0f8;color:#5533aa;}"
                   "#folderPanel{background:#e8e8f5;border-right:1px solid #c0c0d8;padding:8px;}"
                   "#folderList,#managerList{background:#fff;border:1px solid #c0c0d8;border-radius:5px;color:#1a1a2e;}"
                   "#folderList::item:selected,#managerList::item:selected{background:#c8b8ff;color:#000;}"
                   "#addBtn{background:#d8f0d8;color:#226622;border:1px solid #88cc88;border-radius:4px;font-weight:600;}"
                   "#removeBtn{background:#f0d8d8;color:#882222;border:1px solid #cc8888;border-radius:4px;font-weight:600;}"
                   "#primaryBtn{background:#5533aa;color:#fff;border:1px solid #3322aa;border-radius:5px;padding:4px 18px;font-weight:700;}"
                   "#secondaryBtn{background:#d8eaf8;color:#224466;border:1px solid #88aacc;border-radius:4px;font-weight:600;}"
                   "#toolBtn{background:#e0e0ee;color:#333366;border:1px solid #aaaacc;border-radius:4px;font-weight:600;}"
                   "#searchBox{background:#fff;border:1px solid #c0c0d8;border-radius:5px;color:#1a1a2e;padding:2px 10px;}"
                   "#musicTree,#newTree,#dupTree,#changedTree{background:#fff;alternate-background-color:#f5f5ff;border:1px solid #c0c0d8;border-radius:6px;outline:none;}"
                   "#musicTree::item:selected,#newTree::item:selected,#dupTree::item:selected,#changedTree::item:selected{background:#c8b8ff;color:#000;}"
                   "QHeaderView::section{background:#dcdcec;color:#444488;border:none;border-bottom:1px solid #c0c0d8;padding:6px 8px;font-weight:700;font-size:11px;}"
                   "#bigBar{background:#dcdcec;border-radius:5px;}"
                   "#bigBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #7755cc,stop:1 #aa77ff);border-radius:5px;}"
                   "QStatusBar{background:#e8e8f5;color:#555577;font-size:11px;}"
                   "#artistCard{background:#fff;border:1px solid #c0c0d8;border-radius:8px;}"
                   "#previewPlayBtn{background:#5533aa;color:#fff;border:1px solid #3322aa;border-radius:18px;font-weight:700;font-size:16px;}"
                   )

    def _toggle_theme(self):
        # Simple toggle between Dark and Light for the toolbar button
        current = self.ds.settings.get("theme_name", "Dark")
        new_theme = "Light" if current == "Dark" else "Dark"
        self.ds.settings["theme_name"] = new_theme
        self.ds.save_settings()
        self._apply_theme()

    def _chg_font(self,d:int):
        sz=max(10,min(22,self.ds.settings.get("font_size",13)+d))
        self.ds.settings["font_size"]=sz
        f=QApplication.instance().font(); f.setPointSize(sz)
        QApplication.instance().setFont(f); self.ds.save_settings()

    def _toggle_view(self):
        is_list = self.stack.currentIndex() == 0
        idx = 1 if is_list else 0
        self.stack.setCurrentIndex(idx)
        self.new_stack.setCurrentIndex(idx)
        self.pop_stack.setCurrentIndex(idx)
        self.recs_stack.setCurrentIndex(idx)
        self.view_btn.setText("☰  List" if is_list else "⊞  Grid")
        self._apply_lib_filter()
        self._apply_new_filter()
        self._refresh_pop_tab()
        if hasattr(self, 'recs_tree'): self._build_recs()

    def _sort_fn(self):
        idx=self.sort_combo.currentIndex()
        if idx==0: return sort_key
        if idx==1:
            def rev(n): k=sort_key(n); return(k[0],k[1][::-1],k[2])
            return rev
        return lambda n:-(self._popularity.get(n,{}).get("listeners") or 0)

    def _restore_session(self):
        folders=self._qs.value("folders",[])
        if isinstance(folders,str): folders=[folders]
        if folders: self.folder_panel.load(folders); self._scan_folders=list(folders)
        self.hash_chk.setChecked(self.ds.settings.get("hash_enabled",False))
        self._update_btns()
        self._update_watcher()
                # NEW: Make sure hash_prog is visible if hashing is enabled
        if self.ds.settings.get("hash_enabled", False):
            self.hash_prog.show()

    def _open_palette(self):
        dlg = CommandPalette(self._library, self)
        dlg.search.setFocus()
        dlg.exec()

    def _play_album(self, artist, album):
        releases = self._library.get(artist, [])
        target_files = []
        for r in releases:
            if r.get("album", "") == album:
                target_files = r.get("files", [])
                break
        if not target_files:
            QMessageBox.information(self, "No Files", "Could not find local audio files for this album.")
            return
        self.local_player.load_queue(target_files, 0)
        self.status_bar.showMessage(f"Playing: {artist} - {album}")

    def _start_preview_lookup(self, artist: str, release: str):
        """Searches iTunes/Deezer and plays the 30-sec preview in the main player."""
        if not HAS_MULTIMEDIA:
            QMessageBox.warning(self, "Multimedia Missing", "PyQt6-Multimedia is not installed.")
            return

        self.status_bar.showMessage(f"🔍 Searching preview for {artist} - {release}...")
        self.local_player.pause()

        self._preview_lookup = PreviewLookup(artist, release)
        self._preview_lookup.found.connect(self._on_preview_found)
        self._preview_lookup.not_found.connect(lambda a, t: self.status_bar.showMessage(f"❌ No preview found for {a} - {t}"))
        self._preview_lookup.start()

    def _on_preview_found(self, artist: str, title: str, url: str):
        self.status_bar.showMessage(f"▶ Playing 30-sec preview: {artist} - {title}")
        self.local_player.queue = [url]  # Put the URL in the queue
        self.local_player.current_index = 0
        self.local_player.play_file(url)

    def _send_to_player(self, files: list):
        if not files:
            QMessageBox.information(self, "No Files", "Could not find local audio files for this album.")
            return

        player = self.ds.settings.get("external_player", "strawberry").strip()
        if not player:
            QMessageBox.warning(self, "No Player Set", "Please set your external player executable (e.g., strawberry, vlc) in Settings.")
            return

        import tempfile
        tmp_m3u = Path(tempfile.gettempdir()) / "musicwatcher_ext_player.m3u"
        try:
            with open(tmp_m3u, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for p in files:
                    f.write(f"{p}\n")

            subprocess.Popen([player, str(tmp_m3u)])
            self.status_bar.showMessage(f"Sent to {player}...")
        except FileNotFoundError:
            QMessageBox.warning(self, "Player Not Found", f"Could not find '{player}' in your system PATH. Is it installed?")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to launch {player}: {e}")

    def _open_in_picard(self, files: list):
        if not files:
            QMessageBox.information(self, "No Files", "Could not find local audio files for this album.")
            return
        try:
            # Picard accepts a list of files/directories as arguments
            subprocess.Popen(['picard'] + files)
            self.status_bar.showMessage("Opening files in MusicBrainz Picard...")
        except FileNotFoundError:
            QMessageBox.warning(self, "Picard Not Found", "Could not find 'picard' in your system PATH. Is it installed?")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to launch Picard: {e}")

    def _open_tag_editor(self, artist, album):
        releases = self._library.get(artist, [])
        target_files = []
        for r in releases:
            if r.get("album", "") == album:
                target_files = r.get("files", [])
                break
        if not target_files:
            QMessageBox.information(self, "No Files", "Could not find local audio files for this album.")
            return
        dlg = TagEditorDialog(target_files, self.ds, self)
        dlg.exec()

    def _on_player_track_changed(self, artist, title):
        self._current_scrobble_artist = artist
        self._current_scrobble_track = title
        self._scrobble_start_time = int(time.time())
        self._current_scrobble_album = ""
        for rel in self._library.get(artist, []):
            if self.local_player.queue:
                fp = Path(self.local_player.queue[self.local_player.current_index])
                if str(fp) in rel.get("files", []):
                    self._current_scrobble_album = rel.get("album", "")
                    break

        # Submit to ListenBrainz in background
        if artist and title:
            threading.Thread(
                target=self.lb_submitter.submit_listen,
                args=(artist, title, self._current_scrobble_album),
                daemon=True
            ).start()

        if self._current_scrobble_artist and self._current_scrobble_track:
            self.scrobbler.update_now_playing(self._current_scrobble_artist, self._current_scrobble_track, self._current_scrobble_album)

    def _on_player_state_changed(self, state):
        if state == "stopped" or state == "paused":
            if self._current_scrobble_track and self._scrobble_start_time:
                elapsed = int(time.time()) - self._scrobble_start_time
                if elapsed >= 240 or (self.local_player.player.duration() > 0 and elapsed >= (self.local_player.player.duration() / 1000) / 2):
                    self.scrobbler.scrobble(self._current_scrobble_artist, self._current_scrobble_track, self._current_scrobble_album, self._scrobble_start_time)
                    self._scrobble_start_time = 0

    def mp_play(self):
        if hasattr(self, 'local_player'): self.local_player.play()
    def mp_pause(self):
        if hasattr(self, 'local_player'): self.local_player.pause()
    def mp_playpause(self):
        if hasattr(self, 'local_player'):
            from PyQt6.QtMultimedia import QMediaPlayer as _QMP
            if self.local_player.player.playbackState() == _QMP.PlaybackState.PlayingState:
                self.local_player.pause()
            else:
                self.local_player.play()
    def mp_stop(self):
        if hasattr(self, 'local_player'): self.local_player.stop()

    def _open_playlist_gen(self):
        dlg = PlaylistGeneratorDialog(self.ds, self)
        dlg.exec()

    def _load_tray_icon(self):
        path = self.ds.settings.get("tray_icon_path", "")
        if path and os.path.exists(path):
            icon = QIcon(path)
            if not icon.isNull():
                self._tray.setIcon(icon)
                self.setWindowIcon(icon)
                return
        default_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        self._tray.setIcon(default_icon)
        self.setWindowIcon(default_icon)

    def _update_stats(self):
        total_artists = len(self._library)
        total_releases = sum(len(v) for v in self._library.values())
        types = Counter()
        decade_counter = Counter()
        genre_counter = Counter()

        for artist, releases in self._library.items():
            for r in releases:
                r_type = r.get("type", "Album") or "Album"
                types[r_type] += 1
                year_str = r.get("year", "")
                if year_str and year_str != UNKNOWN:
                    try:
                        decade = (int(year_str[:4]) // 10) * 10
                        decade_counter[f"{decade}s"] += 1
                    except: pass
                # FIXED!
                genre = r.get("genre", "")
                if genre:
                    for g in re.split(r'[/,;|]', genre):
                        g = g.strip()
                        if g: genre_counter[g] += 1

        for artist, pop in self._popularity.items():
            for tag in pop.get("tags", []):
                genre_counter[tag] += 1

        html = "<div style='font-family: sans-serif; color: #e0e0f0;'>"
        html += "<h2>🎵 Library Overview</h2>"
        html += f"<b>Total Artists:</b> {total_artists:,}<br>"
        html += f"<b>Total Releases:</b> {total_releases:,}<br><br>"

        html += "<h3>💿 Release Types</h3>"
        if types:
            max_t = max(types.values()) or 1
            for t, c in types.most_common():
                html += f"{t}: {c} <span style='color:#666;'>({c/total_releases*100:.1f}%)</span><br>"
            html += "<br>"
        else:
            html += "<i>No data yet. Scan your library.</i><br><br>"

        html += "<h3>🗓️ Releases by Decade</h3>"
        if decade_counter:
            max_d = max(decade_counter.values()) or 1
            for d, c in sorted(decade_counter.items()):
                bar = "█" * int((c / max_d) * 30)
                html += f"{d}: {c} <span style='color:#7755cc;'>{bar}</span><br>"
            html += "<br>"

        html += "<h3>🎸 Top Genres & Tags</h3>"
        if genre_counter:
            top_genres = genre_counter.most_common(20)
            max_g = top_genres[0][1] or 1
            for g, c in top_genres:
                bar = "█" * int((c / max_g) * 20)
                html += f"{g}: {c} <span style='color:#9944cc;'>{bar}</span><br>"
        else:
            html += "<i>Run 'Fetch Popularity' to aggregate genre tags.</i><br>"

        html += "</div>"

        if not self.ds.settings.get("theme","dark")=="dark":
            html = html.replace("#e0e0f0", "#1a1a2e").replace("#666", "#888").replace("#7755cc", "#5533aa").replace("#9944cc", "#5533aa")

        self.stats_browser.setHtml(html)

    def _restore_ui_state(self):
        if self._qs.contains("geometry"):
            self.restoreGeometry(self._qs.value("geometry"))
        if self._qs.contains("windowState"):
            self.restoreState(self._qs.value("windowState"))
        if self._qs.contains("splitter"):
            self.sp.restoreState(self._qs.value("splitter"))
        if self._qs.contains("active_tab"):
            idx = int(self._qs.value("active_tab"))
            if 0 <= idx < self.tabs.count():
                self.tabs.setCurrentIndex(idx)
        self._update_stats()

    def _save_session(self):
        self._qs.setValue("folders",self.folder_panel.get()); self.ds.save_settings()

    def _real_quit(self):
        self._is_quitting = True
        self.close()
        QApplication.quit()

    def closeEvent(self,event):
        if not getattr(self, "_is_quitting", False) and self._tray.isVisible():
            event.ignore()
            self.hide()
            self._tray.showMessage(APP_NAME, "Running in the background. Right-click tray icon to quit.")
            return

        self._save_session()
        self._qs.setValue("geometry", self.saveGeometry())
        self._qs.setValue("windowState", self.saveState())
        if hasattr(self, 'sp'): self._qs.setValue("splitter", self.sp.saveState())
        if hasattr(self, 'tabs'): self._qs.setValue("active_tab", self.tabs.currentIndex())
        try:
            if hasattr(self,'preview_player') and self.preview_player._player:
                self.preview_player._player.stop()
        except Exception: pass
        for t in(self._scanner,self._checker,self._pop_lib,self._pop_new,self._lyrfetch,self._artfetch):
            if t and t.isRunning(): t.stop(); t.wait(2000)
        self.ds.save_all()
        self.ds.le.save()
        super().closeEvent(event)

    def _on_folders_changed(self,folders):
        self._scan_folders=folders; self._save_session(); self._update_btns()
        self._update_watcher()

    def _update_watcher(self):
        if not self.ds.settings.get("watch_folders", False):
            if self._watcher.directories():
                self._watcher.removePaths(self._watcher.directories())
            return
        if self._watcher.directories():
            self._watcher.removePaths(self._watcher.directories())
        for f in self._scan_folders:
            if os.path.isdir(f): self._watcher.addPath(f)

    def _on_watch_dir_changed(self, path):
        if self.ds.settings.get("watch_folders", False):
            self._watch_timer.start()

    def _auto_scan(self):
        if not self.ds.settings.get("watch_folders", False): return
        if self._scanner and self._scanner.isRunning():
            self._watch_timer.start()
            return
        if not self._scan_folders:
            return

        self._auto_scanning = True

        # If Auto-Organize is enabled, run the Organizer first, THEN scan
        if self.ds.settings.get("auto_organize", False):
            self.status_bar.showMessage("🤖 Auto-organizing watch folder...")
            # Organize files into the first watch folder (in-place)
            self._watch_organizer = OrganizerThread(self._scan_folders[0], self._scan_folders[0], move_files=True)

            def _on_organize_done(moved, errors):
                self.status_bar.showMessage(f"Organized {moved} files. Starting scan...", 3000)
                self._start_scan()

            def _on_organize_error(err):
                QMessageBox.warning(self, "Organizer Error", err)
                self._start_scan() # Scan anyway

            self._watch_organizer.finished.connect(_on_organize_done)
            self._watch_organizer.start()
        else:
            self._start_scan()

    def _update_btns(self):
        has_f=bool(self.folder_panel.get()); has_l=bool(self._library)
        has_n=bool(self._new_releases); has_d=bool(self._duplicates)
        self.scan_btn.setEnabled(has_f); self.check_btn.setEnabled(has_l)
        self.gap_btn.setEnabled(has_l)  # NEW
        self.lib_pop_btn.setEnabled(has_l); self.new_pop_btn.setEnabled(has_n)
        self.lyrics_btn.setEnabled(has_l and self.ds.settings.get("lyrics_enabled",False))
        self.open_dup_btn.setEnabled(has_d)
        self.lib_art_btn.setEnabled(has_l)

    def _open_settings(self):
        dlg=SettingsDialog(self.ds,self._hw,self)
        dlg.reset_requested.connect(self._reset_database)
        dlg.exec()
        self.ds.save_settings()
        self._update_btns()
        self._apply_theme()
        self._load_tray_icon()

    def _reset_database(self):
        import shutil
        for t in(self._scanner,self._checker,self._pop_lib,self._pop_new,self._lyrfetch,self._artfetch):
            if t and t.isRunning(): t.stop(); t.wait(2000)

        self._library.clear()
        self._popularity.clear()
        self._new_releases.clear()
        self._new_pop.clear()
        self._duplicates.clear()
        self._changed.clear()

        try:
            self.ds.db.close()
            for f in DATA_DIR.glob("*.csv"): f.unlink(missing_ok=True)
            for f in DATA_DIR.glob("*.json"): f.unlink(missing_ok=True)
            if (DATA_DIR / "musicwatcher.db").exists():
                (DATA_DIR / "musicwatcher.db").unlink()
            if (DATA_DIR / "learning").exists():
                shutil.rmtree(DATA_DIR / "learning")
            if ART_DIR.exists():
                shutil.rmtree(ART_DIR)
                ART_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QMessageBox.warning(self, "Reset Error", f"Could not delete some files: {e}")

        self.ds = DataStore(self._hw)
        self._populate_lib_tree({})
        self._populate_new_tree({})
        self._refresh_pop_tab()
        self._populate_dup_tree()
        self._populate_changed_tree()
        self._update_btns()
        self.status_bar.showMessage("Database reset complete. Please rescan your folders.")
        self.tabs.setCurrentIndex(0)

    def _open_lists(self):
        if self._lists_dialog and not self._lists_dialog.isHidden():
            self._lists_dialog.raise_(); return
        self._lists_dialog=ListManagerDialog(
            sorted(self._library.keys(),key=str.lower),
            self.ds.blacklist,self.ds.whitelist,ds=self.ds,parent=self)
        self._lists_dialog.lists_updated.connect(self._on_lists_updated)
        self._lists_dialog.show()

    def _on_lists_updated(self,bl,wl):
        self.ds.blacklist=bl; self.ds.whitelist=wl; self.ds.save_lists()

    def _open_data_dir(self):
        if sys.platform=="win32": os.startfile(str(DATA_DIR))
        else: subprocess.Popen(["xdg-open",str(DATA_DIR)])

    def _open_dup_manager(self):
        if not self._duplicates: return
        dlg=DuplicateManagerDialog(self._duplicates,self._scan_folders,ds=self.ds,parent=self)
        dlg.exec()

    def _toggle_favorite(self,artist:str):
        if artist in self.ds.favorites: self.ds.favorites.discard(artist)
        else: self.ds.favorites.add(artist)
        self.ds.save_lists(); self._apply_lib_filter(); self._apply_new_filter()

    def _open_genius(self, artist: str, title: str):
        api_key = self.ds.settings.get("genius_api_key", "").strip()
        if not api_key:
            QMessageBox.warning(self, "No API Key", "Please set your Genius API key in Settings to use this feature.")
            return
        dlg = GeniusViewerDialog(artist, title, api_key, self)
        dlg.exec()

    def _fav_label(self,artist:str)->str:
        return("★ Remove from Favorites" if artist in self.ds.favorites
               else "☆ Add to Favorites")

    def _tree_context_menu(self,pos):
        item=self.tree.itemAt(pos)
        if not item: return
        menu=QMenu(self)
        if item.parent():
            artist=item.parent().text(0).lstrip("★☆ ")
            album=item.text(0).strip()

            # Find the files for this album
            target_files = []
            for r in self._library.get(artist, []):
                if r.get("album", "") == album:
                    target_files = r.get("files", [])
                    break

            play_action = menu.addAction("▶ Play Album")
            play_action.triggered.connect(lambda: self._play_album(artist, album))
            menu.addSeparator()

            # NEW: Send to External Player
            ext_player_action = menu.addAction("🎧 Send to External Player")
            ext_player_action.triggered.connect(lambda: self._send_to_player(target_files))

            # NEW: Open in Picard
            picard_action = menu.addAction("🧩 Open in MusicBrainz Picard")
            picard_action.triggered.connect(lambda: self._open_in_picard(target_files))

            menu.addSeparator()
            edit_action = menu.addAction("✏️ Edit Tags")
            edit_action.triggered.connect(lambda: self._open_tag_editor(artist, album))
            menu.addSeparator()
            self._add_search_actions(menu,artist,album)
            menu.addAction("📜 View Lyrics on Genius", lambda: self._open_genius(artist, album))
            urls=self.ds.mb_cache.get(artist,{}).get("urls",{})
            self._add_url_actions(menu,artist,urls)
        else:
            artist=item.text(0).lstrip("★☆ ")
            menu.addAction(self._fav_label(artist),lambda:self._toggle_favorite(artist))
            menu.addSeparator()
            urls=self.ds.mb_cache.get(artist,{}).get("urls",{})
            self._add_url_actions(menu,artist,urls)
        menu.exec(self.tree.mapToGlobal(pos))

    def _new_tree_context_menu(self,pos):
        item=self.new_tree.itemAt(pos)
        if not item: return
        menu=QMenu(self)
        if item.parent():
            artist=item.parent().text(0).lstrip("★☆✓ ")
            release=item.text(0).strip()
            rtype = item.text(2).strip()

            # NEW: Soulseek Auto-Download Action
            slsk_action = menu.addAction("🦑 Auto-Download (Soulseek)")
            slsk_action.triggered.connect(lambda: self._start_soulseek_download(artist, release))

            menu.addSeparator()

            # Preview Button (Pauses main player first!)
            if HAS_MULTIMEDIA:
                # Route 30-sec preview to the main bottom PlayerBar
                pa=menu.addAction("▶  Preview (30-sec)",
                    lambda: self._start_preview_lookup(artist, release))
                menu.addSeparator()

            self._add_search_actions(menu,artist,release, rtype)
            menu.addAction("📜 View Lyrics on Genius", lambda: self._open_genius(artist, release))
            urls=self.ds.mb_cache.get(artist,{}).get("urls",{})
            self._add_url_actions(menu,artist,urls)
        else:
            artist=item.text(0).lstrip("★☆✓ ")
            menu.addAction(self._fav_label(artist),lambda:self._toggle_favorite(artist))
            menu.addSeparator()
            urls=self.ds.mb_cache.get(artist,{}).get("urls",{})
            self._add_url_actions(menu,artist,urls)
        menu.exec(self.new_tree.mapToGlobal(pos))

    def _add_search_actions(self,menu:QMenu,artist:str,release:str, rtype: str = ""):
        q_raw=requests.utils.quote(f"{artist} {release}")
        q_sl =f'{artist} "{release}" flac'

        fb   =self.ds.settings.get("squid_fallback","")
        q_qob=(f"https://qobuz.squid.wtf/?q={q_raw}"
               if not fb
               else f"https://lucida.to/?q={q_raw}&cs=qobuz")
        q_tid=(f"https://tidal.squid.wtf/?q={q_raw}"
               if not fb
               else f"https://lucida.to/?q={q_raw}&cs=tidal")

        if rtype:
            self.ds.le.record_release_action(rtype, "search")
            self.ds.le.save()

        nicotine_url = QUrl(f"nicotine+://search/{requests.utils.quote(q_sl)}")
        menu.addAction("🦑 Search Nicotine+ (Auto)",
            lambda: QDesktopServices.openUrl(nicotine_url))

        menu.addAction("📋 Copy Soulseek Query",
            lambda:QApplication.clipboard().setText(q_sl))

        menu.addAction("📋 Qobuz (squid.wtf)" if not fb else "📋 Qobuz (lucida.to)",lambda:(QApplication.clipboard().setText(q_qob),webbrowser.open(q_qob)))
        menu.addAction("📋 Tidal (squid.wtf)" if not fb else "📋 Tidal (lucida.to)",lambda:(QApplication.clipboard().setText(q_tid),webbrowser.open(q_tid)))
        menu.addSeparator()

    def _add_url_actions(self,menu:QMenu,artist:str,urls:dict):
        PRIORITY_TYPES=["bandcamp","official homepage","myspace","soundcloud",
                        "youtube","instagram","twitter","facebook","spotify",
                        "apple music","tidal","amazon music","deezer","last.fm",
                        "discogs","allmusic","wikidata","wikipedia"]
        added=0
        for utype in PRIORITY_TYPES:
            url=urls.get(utype,"")
            if url:
                icon={"bandcamp":"🎵","official homepage":"🌐","youtube":"▶","spotify":"🎧","last.fm":"📻","instagram":"📸","twitter":"🐦"}.get(utype,"🔗")
                label=f"{icon} {utype.title()} — {url[:48]}{'…' if len(url)>48 else ''}"
                menu.addAction(label,lambda u=url:webbrowser.open(u))
                added+=1
        if not added:
            lfm_url=self.ds.pop_cache.get(artist,{}).get("lfm_url","")
            if lfm_url:
                menu.addAction(f"📻 Last.fm — {artist}",lambda u=lfm_url:webbrowser.open(u))

    def _start_scan(self):
        folders=self.folder_panel.get()
        if not folders: return
        missing=[f for f in folders if not os.path.isdir(f)]
        if missing:
            QMessageBox.warning(self,"Missing folders","Skipping:\n"+"\n".join(missing))
            folders=[f for f in folders if f not in missing]
            if not folders: return
        self._scan_folders=folders
        self.tree.clear(); self.search_box.clear()
        self._library.clear(); self._popularity.clear()
        self.scan_btn.setEnabled(False)
        self.scan_prog.begin(1); self.scan_prog.info.setText("  Collecting files…")
        self._scanner=ScannerThread(folders,self.ds)
        self._scanner.progress.connect(self._on_scan_prog)
        self._scanner.result_ready.connect(self._on_scan_done)
        self._scanner.hash_progress.connect(self._on_hash_prog)
        self._scanner.hash_result.connect(self._on_hash_done)
        self._scanner.auto_bl.connect(self._on_auto_bl)
        self._scanner.status_message.connect(self.status_bar.showMessage)
        self._scanner.start()

    def _on_scan_pause(self,p):
        if self._scanner: (self._scanner.pause if p else self._scanner.resume)()

    def _stop_scan(self):
        if self._scanner: self._scanner.stop()
        self.scan_prog.finish("Stopped."); self._update_btns()

    def _on_scan_prog(self,done,total,artists,albums,fps,fname):
        if self.scan_prog.bar.maximum()!=total:
            self.scan_prog.bar.setMaximum(max(total,1)); self.scan_prog._total=max(total,1)
        self.scan_prog.update_progress(done,artists,albums,fps,fname)

    def _on_scan_done(self,library):
        self._library=library
        self.scan_prog.finish(f"{len(library):,} artists · {sum(len(v) for v in library.values()):,} albums")
        self._apply_lib_filter(); self._update_btns()
        self._update_stats()
        if self._auto_scanning:
            self._auto_scanning = False
            self.status_bar.showMessage("Auto-scan complete.", 3000)
        self._new_releases.clear(); self.new_tree.clear()
        if self.ds.settings.get("hash_enabled"):
            self.hash_prog.begin(100); self.hash_prog.info.setText("  Hashing…")

    def _on_hash_prog(self,done,total):
        if self.hash_prog.bar.maximum()!=total:
            self.hash_prog.bar.setMaximum(max(total,1)); self.hash_prog._total=max(total,1)
        self.hash_prog.update_progress(done)

    def _on_hash_done(self,dups,changed,rows):
        self._duplicates=dups; self._changed=changed
        self.hash_prog.finish(f"{sum(len(v) for v in dups.values())} dup files · {len(changed)} changed")
        self._populate_dup_tree(); self._populate_changed_tree()
        self._update_btns()
        if dups or changed: self.tabs.setCurrentIndex(5)

    def _on_auto_bl(self,artists):
        msg="\n".join(artists[:20])
        if len(artists)>20: msg+=f"\n…and {len(artists)-20} more"
        QMessageBox.information(self,"Auto-blacklisted",
            f"{len(artists)} artist(s) auto-blacklisted "
            f"(explicit feat/unknown/publisher patterns or learned):\n\n{msg}")

    def _start_lyrics(self):
        if not self._scan_folders:
            QMessageBox.information(self,"No folders","Scan your library first."); return

        audio_files=[p for f in self._scan_folders for p in Path(f).rglob("*") if p.is_file() and p.suffix.lower() in {".mp3",".flac",".ogg",".opus",".m4a",".aac",".mp4",".wma",".wav",".aif",".aiff"}]
        total=len(audio_files)
        existing_lrc=[p for p in audio_files if p.with_suffix(".lrc").exists()]
        existing_txt=[p for p in audio_files if p.with_suffix(".txt").exists()]
        has_plain_only=[p for p in existing_txt if not p.with_suffix(".lrc").exists()]

        summary_parts=[]
        if existing_lrc: summary_parts.append(f"{len(existing_lrc)} files already have synced .lrc lyrics")
        if has_plain_only: summary_parts.append(f"{len(has_plain_only)} files have plain .txt lyrics")
        no_lyrics=total-len(existing_lrc)-len(has_plain_only)
        if no_lyrics>0: summary_parts.append(f"{no_lyrics} files have no lyrics yet")
        summary="\n".join(summary_parts) if summary_parts else f"{total} files to process"

        overwrite_lrc=False
        if existing_lrc:
            msg=(f"{summary}\n\nOverwrite all {len(existing_lrc)} existing .lrc (synced) files with fresh lyrics?\n\nYes = re-fetch and overwrite all .lrc files\nNo  = skip files that already have .lrc")
            reply=QMessageBox.question(self,"Overwrite existing synced lyrics?",msg,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
            overwrite_lrc=(reply==QMessageBox.StandardButton.Yes)
        else:
            if total==0:
                QMessageBox.information(self,"No audio files","No audio files found in the scanned folders.")
                return
            QMessageBox.information(self,"Starting lyrics fetch",summary)

        self.lyrics_btn.setEnabled(False)
        self.lyrics_prog.begin(max(total,1))
        self._lyrfetch=LyricsFetcher(self._scan_folders,self.ds,overwrite_lrc=overwrite_lrc)
        self._lyrfetch.progress.connect(lambda d,t,name:(self.lyrics_prog.bar.setMaximum(max(t,1)), setattr(self.lyrics_prog,"_total",max(t,1)), self.lyrics_prog.update_progress(d,extra=name)))
        self._lyrfetch.finished.connect(self._on_lyrics_done)
        self._lyrfetch.status_message.connect(self.status_bar.showMessage)
        self._lyrfetch.start()

    def _on_lyrics_pause(self,p):
        if self._lyrfetch: (self._lyrfetch.pause if p else self._lyrfetch.resume)()

    def _stop_lyrics(self):
        if self._lyrfetch: self._lyrfetch.stop()
        self.lyrics_prog.finish("Stopped."); self._update_btns()

    def _on_lyrics_done(self,synced,plain):
        self.lyrics_prog.finish(f"{synced} synced 🎵 + {plain} plain 📝 saved")
        self._update_btns()
        self._apply_lib_filter()
        self._update_stats()

    def _start_check(self):
        af=self.new_af.text().strip().lower()
        artists=[a for a in self._library if a!=UNKNOWN and (not af or af in a.lower()) and not (a in self.ds.blacklist and a not in self.ds.whitelist)]
        if not artists:
            QMessageBox.information(self,"No artists","No artists match filter."); return
        self.new_tree.clear(); self._new_releases.clear(); self._new_pop.clear()
        self.check_btn.setEnabled(False)
        self.check_prog.begin(len(artists)); self.tabs.setCurrentIndex(1)
        self._checker=NewReleaseChecker(artists,self.ds,self.year_from.value(),self.year_to.value(),self._library)
        self._checker.progress.connect(self._on_check_prog)
        self._checker.artist_done.connect(self._on_artist_done)
        self._checker.finished_all.connect(self._on_check_done)
        self._checker.status_message.connect(self.status_bar.showMessage)
        self._checker.error.connect(lambda m:self.status_bar.showMessage(f"⚠ {m}"))
        self._checker.start()

    def _start_gap_radar(self):
        af=self.new_af.text().strip().lower()
        artists=[a for a in self._library if a!=UNKNOWN and (not af or af in a.lower()) and not (a in self.ds.blacklist and a not in self.ds.whitelist)]
        if not artists:
            QMessageBox.information(self,"No artists","No artists match filter."); return
        self.new_tree.clear(); self._new_releases.clear(); self._new_pop.clear()
        self.check_btn.setEnabled(False)
        self.gap_btn.setEnabled(False)
        self.check_prog.begin(len(artists)); self.tabs.setCurrentIndex(1)

        # Set year range to 1900 -> current_year + 1 to catch everything
        cur_year = datetime.datetime.now().year
        self._checker=NewReleaseChecker(artists, self.ds, 1900, cur_year + 1, self._library)
        self._checker.progress.connect(self._on_check_prog)
        self._checker.artist_done.connect(self._on_artist_done)
        self._checker.finished_all.connect(self._on_check_done)
        self._checker.status_message.connect(self.status_bar.showMessage)
        self._checker.error.connect(lambda m:self.status_bar.showMessage(f"⚠ {m}"))
        self._checker.start()

    def _on_check_pause(self,p):
        if self._checker: (self._checker.pause if p else self._checker.resume)()

    def _stop_check(self):
        if self._checker: self._checker.stop()
        self.check_prog.finish("Stopped."); self._update_btns()

    def _on_check_prog(self,done,total,artist):
        self.check_prog.update_progress(done,extra=artist[:38])

    def _on_artist_done(self,artist,releases):
        self._new_releases[artist]=releases; self._apply_new_filter()

    def _on_check_done(self,total_new):
        self.ds.save_new_releases(self._new_releases)
        self.check_prog.finish(f"{total_new:,} new release(s) · saved to {DATA_DIR}/new_releases.csv")
        self._update_btns()

    def _make_fetcher(self, artists: list, target: dict, is_lib: bool = True) -> PopularityFetcher:
        f = PopularityFetcher(artists, self.ds)
        self._pop_dirty = False
        def _on_artist(a: str, pop: dict):
            target[a] = pop
            if is_lib: self._popularity.setdefault(a, pop)
            self._pop_dirty = True
        def _flush():
            if self._pop_dirty:
                self._pop_dirty = False
                if is_lib: self._apply_lib_filter()
                else: self._apply_new_filter()
                self._refresh_pop_tab()
        self._pop_flush_timer = QTimer(self)
        self._pop_flush_timer.setInterval(2000)
        self._pop_flush_timer.timeout.connect(_flush)
        self._pop_flush_timer.start()
        f.artist_done.connect(_on_artist)
        f.status_message.connect(self.status_bar.showMessage)
        f.error.connect(lambda m: self.status_bar.showMessage(f"⚠ {m}"))
        return f

    def _start_lib_art(self):
        artists = [a for a in self._library if a != UNKNOWN]
        if not artists: return
        self.lib_art_btn.setEnabled(False)
        self.scan_prog.begin(len(artists)); self.scan_prog.info.setText("  Fetching missing artwork…")
        self._artfetch = ArtworkFetcher(self.ds)
        self._artfetch.progress.connect(self._on_art_prog)
        self._artfetch.finished.connect(self._on_art_done)
        self._artfetch.status_message.connect(self.status_bar.showMessage)
        self._artfetch.start()

    def _on_art_prog(self, done, total, artist):
        self.scan_prog.update_progress(done, extra=artist[:38])

    def _on_art_done(self):
        self.scan_prog.finish("Artwork fetch complete.")
        self.lib_art_btn.setEnabled(True)
        self._apply_lib_filter()
        self._update_stats()

    def _start_lib_pop(self):
        artists = [a for a in self._library if a != UNKNOWN]
        if not artists: return

        for a in artists:
            if a in self.ds.pop_cache: del self.ds.pop_cache[a]
            if a in self._popularity: del self._popularity[a]

        self.lib_pop_btn.setEnabled(False)
        self.scan_prog.begin(len(artists))
        self.scan_prog.info.setText("  Fetching popularity…")

        def _done():
            self._pop_flush_timer.stop()
            self._apply_lib_filter(); self._refresh_pop_tab()
            self.lib_pop_btn.setEnabled(True)
            self.scan_prog.finish("Popularity fetch complete.")
            if not self._popularity or all(v.get("listeners",0)==0 for v in self._popularity.values()):
                self.status_bar.showMessage("⚠ No popularity data fetched. Check Last.fm API key or network connection.")
            else:
                self.status_bar.showMessage(f"Popularity loaded for {len(self._popularity)} artists. Saved to {DATA_DIR}/popularity.csv")

        self._pop_lib = self._make_fetcher(artists, self._popularity, is_lib=True)
        self._pop_lib.progress.connect(self._on_pop_prog)
        self._pop_lib.finished_all.connect(_done)
        self._pop_lib.start()

    def _on_pop_prog(self, done, total, artist):
        self.scan_prog.update_progress(done, extra=artist[:38])

    def _start_new_pop(self):
        artists = list(self._new_releases.keys())
        if not artists: return
        self.new_pop_btn.setEnabled(False)
        def _done():
            self._pop_flush_timer.stop()
            self._apply_new_filter(); self._refresh_pop_tab()
            self.new_pop_btn.setEnabled(True)
            self.status_bar.showMessage(f"Popularity loaded for {len(self._new_pop)} artists.")
        self._pop_new = self._make_fetcher(artists, self._new_pop, is_lib=False)
        self._pop_new.finished_all.connect(_done)
        self._pop_new.start()

    def _refresh_pop_tab(self):
        self.pop_tree.clear(); self.pop_tree.setSortingEnabled(False)
        if not self._popularity: return
        max_l=max((v.get("listeners",0) or 0 for v in self._popularity.values()),default=1) or 1
        for artist,pop in sorted(self._popularity.items(), key=lambda x:-(x[1].get("listeners") or 0)):
            lb=pop.get("listeners",0) or 0
            lfm=pop.get("lfm_listeners",0) or 0
            rank=pop.get("global_rank",0)
            geo_d=pop.get("geo_ranks",{})
            geo_str=", ".join(f"{c}:#{r}" for c,r in sorted(geo_d.items(),key=lambda x:x[1]))
            item=QTreeWidgetItem([
                artist,fmt_n(lb),fmt_n(lfm) if lfm else "—",
                stars(max(lb,lfm)),pop.get("area","—"),
                f"{lb*100/max_l:.1f}%", f"#{rank}" if rank else "—",
                geo_str or "—", ", ".join(pop.get("tags",[])), ", ".join(pop.get("similar",[])),
                fmt_n(pop.get("blended", 0)), f"{pop.get('normalised', 0)*100:.1f}%"
            ])
            item.setData(1,Qt.ItemDataRole.UserRole,lb)
            item.setForeground(0,QColor("#bb99ff")); item.setForeground(3,QColor("#ffcc44"))
            self.pop_tree.addTopLevelItem(item)
        self.pop_tree.setSortingEnabled(True)

        grid_lib = {a: self._library.get(a, []) for a in self._popularity}
        self.pop_grid.set_data(grid_lib, self._popularity, self._sort_fn(), self.ds)
        if self.pop_stack.currentIndex() == 1:
            (self.pop_grid.show_albums(self.pop_grid._current)
                 if self.pop_grid._current else self.pop_grid.show_artists())

    def _apply_lib_filter(self):
        query=self.search_box.text().lower().strip()
        af=self.lib_af.text().lower().strip()
        min_l=self.lib_min.value()
        filter_mode = self.lib_list_filter.currentText() if hasattr(self, "lib_list_filter") else "All"

        filtered={}
        for artist,releases in self._library.items():
            if af and af not in artist.lower(): continue

            # NEW: Apply List Filter
            if filter_mode == "Favorites":
                if artist not in self.ds.favorites: continue
            elif filter_mode == "Whitelist":
                if artist not in self.ds.whitelist: continue
            elif filter_mode == "Blacklist":
                if artist not in self.ds.blacklist: continue

            pop=self._popularity.get(artist,{})
            l=pop.get("listeners")
            if l is not None and l<min_l: continue
            if query:
                if query in artist.lower(): filtered[artist]=releases
                else:
                    m=[r for r in releases if query in r.get("album","").lower() or query in r.get("year","")]
                    if m: filtered[artist]=m
            else: filtered[artist]=releases
        if self.stack.currentIndex()==0: self._populate_lib_tree(filtered)
        else:
            self.grid_view.set_data(filtered,self._popularity,self._sort_fn(),self.ds)
        (self.grid_view.show_albums(self.grid_view._current) if self.grid_view._current else self.grid_view.show_artists())

    def _populate_lib_tree(self,library:dict):
        self.tree.clear(); self.tree.setSortingEnabled(False)
        sf=self._sort_fn()
        for artist in sorted(library.keys(),key=sf):
            releases=library[artist]
            pop=self._popularity.get(artist,{})
            listeners=pop.get("listeners")
            genre=", ".join(pop.get("tags",[])) or next((r.get("genre","") for r in releases if r.get("genre")),"")
            fav_star="★ " if artist in self.ds.favorites else ""
            a_item=QTreeWidgetItem([fav_star+artist,"","",genre,"",fmt_n(listeners),stars(listeners)])
            a_item.setData(5,Qt.ItemDataRole.UserRole,listeners if listeners is not None else -1)
            f=a_item.font(0); f.setBold(True); f.setPointSize(f.pointSize()+1)
            a_item.setFont(0,f); a_item.setForeground(0,QColor("#bb99ff"))
            a_item.setForeground(5,QColor("#66aacc")); a_item.setForeground(6,QColor("#ffcc44"))
            a_item.setToolTip(0,f"{len(releases)} releases")
            for r in sorted(releases,key=lambda x:(x.get("year",""),x.get("album",""))):
                lyr_e=lyrics_emoji(r.get("lyr_status","none"))
                files=r.get("files",[])
                if files: lyr_e=lyrics_emoji(album_lyrics_status(files))

                # NEW: Fake FLAC Warning Prefix
                album_text = f"  {r.get('album',UNKNOWN)}"
                if r.get("is_fake_flac"):
                    album_text = f"  ⚠️ FAKE FLAC: {r.get('album',UNKNOWN)}"

                child=QTreeWidgetItem([album_text,r.get("year",UNKNOWN),r.get("type",""),r.get("genre",""),lyr_e,"",""])
                child.setForeground(0,QColor("#ff5555") if r.get("is_fake_flac") else QColor("#ccccee"))
                child.setForeground(1,QColor("#8899bb"))
                child.setForeground(2,QColor("#778899")); child.setForeground(3,QColor("#667788"))
                child.setForeground(4,QColor("#aabb88" if lyr_e=="🎵" else "#aa8855" if lyr_e=="📝" else "#886666"))
                a_item.addChild(child)
            self.tree.addTopLevelItem(a_item)
        self.tree.expandAll(); self.tree.setSortingEnabled(True)

    def _apply_new_filter(self):
        af=self.new_af.text().strip().lower()
        min_l=self.new_min.value()
        filter_mode = self.new_list_filter.currentText() if hasattr(self, "new_list_filter") else "All"

        allowed=set()
        if hasattr(self,"rt_album") and self.rt_album.isChecked(): allowed.add("Album")
        if hasattr(self,"rt_ep") and self.rt_ep.isChecked():       allowed.add("EP")
        if hasattr(self,"rt_single") and self.rt_single.isChecked(): allowed.add("Single")
        if not allowed: allowed={"Album","EP","Single"}

        filtered={}
        for artist,releases in self._new_releases.items():
            if af and af not in artist.lower(): continue

            # Apply List Filter
            if filter_mode == "Favorites Only":
                if artist not in self.ds.favorites: continue
            elif filter_mode == "Whitelist Only":
                if artist not in self.ds.whitelist: continue
            else: # "All"
                if artist in self.ds.blacklist and artist not in self.ds.whitelist: continue

            pop=self._new_pop.get(artist,{})
            l=pop.get("listeners")
            if l is not None and l<min_l: continue
            typed=[r for r in releases if not r.get("type") or r.get("type","") in allowed]
            typed.sort(key=lambda r: self.ds.le.release_sort_key(r.get("type","")))
            if typed: filtered[artist]=typed

        favs  ={a:v for a,v in filtered.items() if a in self.ds.favorites}
        others={a:v for a,v in filtered.items() if a not in self.ds.favorites}
        data = {**favs,**others}
        if self.new_stack.currentIndex() == 0:
            self._populate_new_tree(data)
        else:
            grid_data = {a: [{"album": r.get("title",""), "year": r.get("year",""), "type": r.get("type",""), "mbid": r.get("mbid","")} for r in v] for a, v in data.items()}
            self.new_grid.set_data(grid_data, self._new_pop, self._sort_fn(), self.ds)
            self.new_grid.show_artists()

    def _populate_new_tree(self,data:dict):
        self.new_tree.clear(); self.new_tree.setSortingEnabled(False)
        sf=self._sort_fn()
        for artist in sorted(data.keys(),key=sf):
            releases=data[artist]
            pop=self._new_pop.get(artist,{})
            lb=pop.get("listeners"); lfm=pop.get("lfm_listeners")
            genre=", ".join(pop.get("tags",[])) or next((r.get("genre","") for r in self._library.get(artist,[]) if r.get("genre")),"")
            rank=pop.get("global_rank",0)
            is_wl =artist in self.ds.whitelist
            is_fav=artist in self.ds.favorites
            prefix="★ " if is_fav else("✓ " if is_wl else "")
            a_item=QTreeWidgetItem([prefix+artist,"","",genre,fmt_n(lb),fmt_n(lfm) if lfm else "—",stars(max(lb or 0,lfm or 0)),pop.get("area","—"),f"#{rank}" if rank else "—"])
            a_item.setData(4,Qt.ItemDataRole.UserRole,lb if lb is not None else -1)
            f=a_item.font(0); f.setBold(True); a_item.setFont(0,f)
            a_item.setForeground(0,(QColor("#ffcc44") if is_fav else QColor("#88dd88") if is_wl else QColor("#ffbb55")))
            a_item.setForeground(4,QColor("#66aacc")); a_item.setForeground(6,QColor("#ffcc44"))
            urls=self.ds.mb_cache.get(artist,{}).get("urls",{})
            if urls: a_item.setToolTip(0," | ".join(f"{k}: {v}" for k,v in list(urls.items())[:3]))
            for r in sorted(releases,key=lambda x:(x.get("year",UNKNOWN),x.get("title",""))):
                child=QTreeWidgetItem([f"  {r['title']}",r.get("year",UNKNOWN),r.get("type",""),"","","","","",""])
                child.setForeground(0,QColor("#ffddaa")); child.setForeground(1,QColor("#8899bb"))
                a_item.addChild(child)
            self.new_tree.addTopLevelItem(a_item); a_item.setExpanded(True)
        self.new_tree.setSortingEnabled(True)

    def _build_recs(self):
        if not self.ds.pop_cache:
            QMessageBox.information(self, "No Data", "Please run 'Fetch Popularity' on the Library or New Releases tab first to generate recommendations.")
            return

        self.recs_tree.clear(); self.recs_tree.setSortingEnabled(False)
        recs = Counter()
        for artist, pop in self.ds.pop_cache.items():
            # NEW: Only build recommendations based on Favorites or Whitelisted artists
            if artist not in self.ds.favorites and artist not in self.ds.whitelist:
                continue

            for sim in pop.get("similar", []):
                if sim and sim not in self._library and sim not in self.ds.blacklist:
                    recs[sim] += 1

        for artist, count in recs.most_common():
            pop = self.ds.pop_cache.get(artist, {})
            lb = pop.get("listeners", 0)
            lfm = pop.get("lfm_listeners", 0)
            blended = pop.get("blended", 0)
            norm = pop.get("normalised", 0.0)
            tags = ", ".join(pop.get("tags", []))
            item = QTreeWidgetItem([
                artist, str(count), fmt_n(max(lb, lfm)),
                f"{norm*100:.1f}%", stars(blended), tags
            ])
            item.setData(1, Qt.ItemDataRole.UserRole, count)
            item.setForeground(0, QColor("#ffddaa"))
            self.recs_tree.addTopLevelItem(item)
        self.recs_tree.setSortingEnabled(True)

        grid_recs = {a: [] for a in recs}
        self.recs_grid.set_data(grid_recs, self.ds.pop_cache, sort_key, self.ds)
        if self.recs_stack.currentIndex() == 1:
            (self.recs_grid.show_albums(self.recs_grid._current)
                 if self.recs_grid._current else self.recs_grid.show_artists())

    def _recs_ctx(self, pos):
        item = self.recs_tree.itemAt(pos)
        if not item: return
        artist = item.text(0)
        menu = QMenu(self)
        menu.addAction(self._fav_label(artist), lambda: self._toggle_favorite(artist))
        menu.addAction("⬅ Add to Whitelist", lambda: (self.ds.whitelist.add(artist), self.ds.save_lists()))
        menu.addAction("🚫 Add to Blacklist", lambda: (self.ds.blacklist.add(artist), self.ds.save_lists()))
        menu.addSeparator()
        self._add_search_actions(menu, artist, "", "")
        urls = self.ds.mb_cache.get(artist, {}).get("urls", {})
        self._add_url_actions(menu, artist, urls)
        menu.exec(self.recs_tree.mapToGlobal(pos))

    def _populate_dup_tree(self):
        self.dup_tree.clear()
        for h,paths in sorted(self._duplicates.items()):
            _,dur=HashSidecar.read(Path(paths[0]))
            group=QTreeWidgetItem([f"Group ({len(paths)} files)","",fmt_dur(dur) if dur else "—",h[:10],""])
            f=group.font(0); f.setBold(True); group.setFont(0,f)
            group.setForeground(0,QColor("#ff9966"))
            for p in sorted(paths):
                fp=Path(p)
                try: size=f"{fp.stat().st_size//1024} KB"
                except Exception: size="?"
                child=QTreeWidgetItem([p,"?","",h[:10],size])
                child.setForeground(0,QColor("#ccbbaa")); child.setToolTip(0,p)
                group.addChild(child)
            self.dup_tree.addTopLevelItem(group); group.setExpanded(True)

    def _populate_changed_tree(self):
        self.changed_tree.clear()
        for p in sorted(self._changed):
            item=QTreeWidgetItem([p]); item.setForeground(0,QColor("#ffdd55"))
            item.setToolTip(0,p); self.changed_tree.addTopLevelItem(item)

    def _check_for_updates(self, silent=True):
        """Checks GitHub for a new release. If silent=True, it only alerts if an update exists."""
        def _fetch():
            try:
                r = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                                 timeout=5, headers={"User-Agent": "MusicWatcher-Updater"})
                r.raise_for_status()
                data = r.json()
                latest_version = data.get("tag_name", "").lstrip("v")
                release_url = data.get("html_url", "")

                if latest_version:
                    try:
                        cur_tup = tuple(map(int, APP_VERSION.split(".")))
                        new_tup = tuple(map(int, latest_version.split(".")))
                        is_newer = new_tup > cur_tup
                    except:
                        is_newer = False

                    if is_newer:
                        QTimer.singleShot(0, lambda: self._show_update_dialog(latest_version, release_url))
                    elif not silent:
                        QTimer.singleShot(0, lambda: QMessageBox.information(self, "Up to Date", f"You are running the latest version ({APP_VERSION})."))
            except Exception:
                if not silent:
                    QTimer.singleShot(0, lambda: QMessageBox.warning(self, "Update Check Failed", "Could not connect to GitHub to check for updates."))

        threading.Thread(target=_fetch, daemon=True).start()

    def _show_update_dialog(self, latest_version, release_url):
        msg = f"A new version of MusicWatcher is available!\n\n"
        msg += f"Current Version: {APP_VERSION}\n"
        msg += f"Latest Version:  {latest_version}\n\n"
        msg += "Would you like to open the download page in your browser?"
        reply = QMessageBox.question(self, "Update Available", msg,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.Yes)
        if reply == QMessageBox.StandardButton.Yes:
            webbrowser.open(release_url)

    def _start_soulseek_download(self, artist: str, release: str):
        """Initiates the slskd search and download process."""
        api_url = self.ds.settings.get("slskd_url", "http://localhost:5030")
        api_key = self.ds.settings.get("slskd_key", "")

        self._soulseek_thread = SoulSeekDownloadThread(artist, release, api_url, api_key)
        self._soulseek_thread.status_message.connect(self.status_bar.showMessage)
        self._soulseek_thread.error.connect(lambda m: QMessageBox.warning(self, "Soulseek Error", m))
        self._soulseek_thread.start()
