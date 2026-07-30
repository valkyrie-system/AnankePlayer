import os, json, re, csv, hashlib, zipfile, shutil, webbrowser, requests, random
from pathlib import Path
from ui.themes import THEMES
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog, QTreeWidget,
    QTreeWidgetItem, QLineEdit, QCheckBox, QDialogButtonBox, QSpinBox, QComboBox,
    QGroupBox, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QListWidget, QListWidgetItem, QFrame, QSlider, QTextBrowser, QWidget, QTabWidget # <--- ADD QTabWidget HERE
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QColor

from core.utils import DATA_DIR, ART_DIR, SIDECAR_EXT, LYR_SYNCED, LYR_PLAIN, LYR_NONE, GEO_COUNTRIES, HashSidecar, fmt_dur, mb_get, extract_tags
from services.lastfm import LastFM
from services.lyrics import GeniusFetchThread

try:
    from mutagen import File as MutagenFile
except ImportError:
    pass

# ─────────────────────────────────────────────────────────────────────────────
# Duplicate manager dialog
# ─────────────────────────────────────────────────────────────────────────────

class DuplicateManagerDialog(QDialog):
    def __init__(self, duplicates: dict, music_roots: list, ds=None, parent=None):
        super().__init__(parent)
        self._ds = ds
        self.setWindowTitle("Duplicate File Manager")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(900,600)
        self._roots=[Path(r) for r in music_roots]
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Groups of files with identical audio content (metadata ignored). "
            "Select files to delete. Parent directories will be removed if empty "
            "after deletion (music root folders are protected)."))

        self.tree=QTreeWidget()
        self.tree.setHeaderLabels(["File path","Type","Duration","Hash (10)","Size"])
        self.tree.setColumnWidth(0,460); self.tree.setColumnWidth(1,65)
        self.tree.setColumnWidth(2,70); self.tree.setColumnWidth(3,85)
        self.tree.setColumnWidth(4,80)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        layout.addWidget(self.tree,stretch=1)

        self._populate(duplicates)

        btn_row=QHBoxLayout()
        self.del_btn=QPushButton("🗑  Delete Selected Files")
        self.del_btn.setObjectName("removeBtn"); self.del_btn.setFixedHeight(34)
        self.del_btn.clicked.connect(self._delete_selected)
        close_btn=QPushButton("Close"); close_btn.setFixedHeight(34)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.del_btn); btn_row.addStretch(); btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _populate(self, duplicates: dict):
        self.tree.clear()
        singles_set:set=set(); album_set:set=set()

        if hasattr(self._ds, 'db'):
            try:
                c = self._ds.db.cursor()
                c.execute("SELECT path, is_single FROM hashes")
                for row in c.fetchall():
                    p = row["path"]
                    t = row["is_single"]
                    if t == "Single": singles_set.add(p)
                    elif t == "Album": album_set.add(p)
            except Exception: pass

        for h,paths in sorted(duplicates.items()):
            _,dur=HashSidecar.read(Path(paths[0]))
            dur_str=fmt_dur(dur) if dur else "—"
            has_album=any(p in album_set for p in paths)
            has_single=any(p in singles_set for p in paths)
            lbl=(f"Group — {len(paths)} identical files" +
                 ("  ⚠ album+single — singles pre-selected" if has_album and has_single else ""))
            group=QTreeWidgetItem([lbl, "","",h[:10],""])
            f=group.font(0); f.setBold(True); group.setFont(0,f)
            group.setForeground(0,QColor("#ff9966"))
            self.tree.addTopLevelItem(group)
            for path in sorted(paths):
                fp=Path(path)
                try: size=f"{fp.stat().st_size//1024} KB"
                except Exception: size="?"
                is_s=path in singles_set; is_a=path in album_set
                ptype="Single" if is_s else("Album" if is_a else "?")
                lrc=fp.with_suffix(".lrc"); txt=fp.with_suffix(".txt")
                lyr_str=LYR_SYNCED if lrc.exists() else(LYR_PLAIN if txt.exists() else LYR_NONE)

                auto = has_album and is_s
                if auto and self._ds:
                    auto = self._ds.le.should_auto_check_single()

                child=QTreeWidgetItem([str(fp),ptype,dur_str,"",size])
                child.setFlags(child.flags()|Qt.ItemFlag.ItemIsUserCheckable)
                child.setCheckState(0,Qt.CheckState.Checked if auto else Qt.CheckState.Unchecked)
                child.setData(0,Qt.ItemDataRole.UserRole,path)
                child.setForeground(0,QColor("#ff8866") if auto else QColor("#ccbbaa"))
                child.setToolTip(0,f"{path}  {lyr_str}")
                group.addChild(child)
            group.setExpanded(True)

    def _delete_selected(self):
        to_delete=[]
        for i in range(self.tree.topLevelItemCount()):
            group=self.tree.topLevelItem(i)
            for j in range(group.childCount()):
                child=group.child(j)
                if child.checkState(0)==Qt.CheckState.Checked:
                    to_delete.append(child.data(0,Qt.ItemDataRole.UserRole))

        if not to_delete:
            QMessageBox.information(self,"Nothing selected",
                "Check files to delete by clicking the checkbox."); return

        if self._ds:
            for i in range(self.tree.topLevelItemCount()):
                group = self.tree.topLevelItem(i)
                kept_types = set()
                deleted_types = set()
                for j in range(group.childCount()):
                    child = group.child(j)
                    ptype = child.text(1)
                    if child.checkState(0) == Qt.CheckState.Checked:
                        deleted_types.add(ptype)
                    else:
                        kept_types.add(ptype)
                for d_t in deleted_types:
                    for k_t in kept_types:
                        self._ds.le.record_dup_decision(d_t, k_t)
            self._ds.le.save()

        reply=QMessageBox.warning(self,"Confirm deletion",
            f"Permanently delete {len(to_delete)} file(s)?\n\n"
            + "\n".join(to_delete[:5])
            + ("\n…" if len(to_delete)>5 else ""),
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel)
        if reply!=QMessageBox.StandardButton.Yes: return

        deleted=0; errors=[]
        dirs_to_check=set()
        for path in to_delete:
            fp=Path(path)
            try:
                fp.unlink(); deleted+=1
                for ext in (SIDECAR_EXT,".lrc",".txt"):
                    sidecar=fp.with_suffix(fp.suffix+ext if ext==SIDECAR_EXT else ext)
                    if sidecar.exists(): sidecar.unlink(missing_ok=True)
                dirs_to_check.add(fp.parent)
            except Exception as e:
                errors.append(f"{fp.name}: {e}")

        scrubbed=0
        for d in sorted(dirs_to_check,key=lambda p:len(p.parts),reverse=True):
            if d in self._roots: continue
            if any(d==r or d.is_relative_to(r) and d==r for r in self._roots): continue
            try:
                if d.exists() and not any(d.iterdir()):
                    d.rmdir(); scrubbed+=1
            except Exception: pass

        msg=f"Deleted {deleted} file(s)."
        if scrubbed: msg+=f" Removed {scrubbed} empty folder(s)."
        if errors: msg+=f"\nErrors: {'; '.join(errors[:3])}"
        QMessageBox.information(self,"Done",msg)
        self.tree.clear()
        QMessageBox.information(self,"Refresh","Rescan the library to update the view.")

# ─────────────────────────────────────────────────────────────────────────────
# Black/Whitelist dialog
# ─────────────────────────────────────────────────────────────────────────────

class ListManagerDialog(QDialog):
    lists_updated=pyqtSignal(set,set)

    def __init__(self, all_artists, blacklist, whitelist, ds=None, parent=None):
        super().__init__(parent)
        self._lds = ds
        self.setWindowTitle("Black / Whitelist Manager")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(940,590)
        self.blacklist=set(blacklist); self.whitelist=set(whitelist)
        self._all=sorted(all_artists,key=str.lower); self._show_listed=False
        outer=QVBoxLayout(self)
        opt=QHBoxLayout()
        chk=QCheckBox("Show already-listed artists in Library column")
        chk.stateChanged.connect(lambda v:(setattr(self,"_show_listed",bool(v)), self._refresh()))
        opt.addWidget(chk); opt.addStretch(); outer.addLayout(opt)
        cols=QHBoxLayout(); outer.addLayout(cols,stretch=1)

        def panel(title,col):
            f=QFrame(); f.setObjectName("listPanel"); vl=QVBoxLayout(f)
            lb=QLabel(title); lb.setStyleSheet(f"color:{col};font-weight:700;margin-bottom:4px;")
            vl.addWidget(lb)
            srch=QLineEdit(); srch.setPlaceholderText("Search…"); srch.setObjectName("searchBox")
            vl.addWidget(srch)
            lw=QListWidget(); lw.setObjectName("managerList")
            lw.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
            lw.setAutoScroll(False); vl.addWidget(lw)
            srch.textChanged.connect(lambda t,w=lw:
                [w.item(i).setHidden(t.lower() not in w.item(i).text().lower())
                 for i in range(w.count())])
            return f,lw

        lib_f,self.lib_lw=panel("Library Artists","#bb99ff")
        bl_f, self.bl_lw =panel("Blacklist  (hide new releases)","#ff8888")
        wl_f, self.wl_lw =panel("Whitelist  (always show)","#88cc88")

        def arrows(*pairs):
            c=QWidget(); vl=QVBoxLayout(c)
            vl.setAlignment(Qt.AlignmentFlag.AlignVCenter); vl.setSpacing(6)
            for lbl,fn in pairs:
                b=QPushButton(lbl); b.setFixedWidth(62); b.clicked.connect(fn)
                vl.addWidget(b)
            return c

        cols.addWidget(lib_f,2)
        cols.addWidget(arrows(
            ("→ BL",lambda:self._move(self.lib_lw,self.blacklist,self.bl_lw,self.whitelist)),
            ("→ WL",lambda:self._move(self.lib_lw,self.whitelist,self.wl_lw,self.blacklist)),
        ))
        cols.addWidget(bl_f,1)
        cols.addWidget(arrows(("← Rm",lambda:self._rm(self.bl_lw,self.blacklist))))
        cols.addWidget(wl_f,1)
        cols.addWidget(arrows(("← Rm",lambda:self._rm(self.wl_lw,self.whitelist))))

        bb=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._accept); bb.rejected.connect(self.reject)
        outer.addWidget(bb); self._refresh()

    def _fill(self,lw,items):
        pos=lw.verticalScrollBar().value(); lw.setUpdatesEnabled(False); lw.clear()
        for a in sorted(items,key=str.lower): lw.addItem(QListWidgetItem(a))
        lw.setUpdatesEnabled(True); lw.verticalScrollBar().setValue(pos)

    def _refresh(self):
        listed=self.blacklist|self.whitelist
        lib=self._all if self._show_listed else[a for a in self._all if a not in listed]
        self._fill(self.lib_lw,lib); self._fill(self.bl_lw,self.blacklist)
        self._fill(self.wl_lw,self.whitelist)

    def _move(self,src,dst,dst_lw,opp):
        for it in src.selectedItems():
            a=it.text()
            dst.add(a); opp.discard(a)
            if dst is self.blacklist and self._lds:
                self._lds.le.learn_blacklist(a)
        if self._lds:
            self._lds.le.save()
        self._refresh()

    def _rm(self,lw,the_set):
        for it in lw.selectedItems(): the_set.discard(it.text())
        self._refresh()

    def _accept(self):
        self.lists_updated.emit(self.blacklist,self.whitelist); self.accept()

# ─────────────────────────────────────────────────────────────────────────────
# Tag Editor
# ─────────────────────────────────────────────────────────────────────────────

class TagEditorDialog(QDialog):
    def __init__(self, files: list, ds, parent=None):
        super().__init__(parent)
        self.files = files
        self.ds = ds
        self.setWindowTitle("✏️ Edit Tags")
        self.setMinimumWidth(550)
        layout = QVBoxLayout(self)

        info_group = QGroupBox("Album Info (Applies to all files)")
        info_layout = QVBoxLayout(info_group)

        def make_row(label_text):
            row = QHBoxLayout()
            row.addWidget(QLabel(label_text))
            ed = QLineEdit()
            ed.setObjectName("searchBox")
            row.addWidget(ed, stretch=1)
            info_layout.addLayout(row)
            return ed

        self.artist_ed = make_row("Artist:")
        self.album_ed = make_row("Album:")
        self.year_ed = make_row("Year:")
        self.genre_ed = make_row("Genre:")

        self.fetch_mb_btn = QPushButton("✨ Auto-Fix from MusicBrainz")
        self.fetch_mb_btn.setObjectName("secondaryBtn")
        self.fetch_mb_btn.clicked.connect(self._fetch_mb)
        info_layout.addWidget(self.fetch_mb_btn)

        layout.addWidget(info_group)

        layout.addWidget(QLabel("Track Titles (Edit individual tracks below):"))
        self.tracks_table = QTableWidget()
        self.tracks_table.setColumnCount(2)
        self.tracks_table.setHorizontalHeaderLabels(["Track #", "Title"])
        self.tracks_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tracks_table, stretch=1)

        save_btn = QPushButton("💾 Save Tags to Files")
        save_btn.setObjectName("primaryBtn")
        save_btn.setFixedHeight(36)
        save_btn.clicked.connect(self._save_tags)
        layout.addWidget(save_btn)

        self._load_tags()

    def _load_tags(self):
        if not self.files: return
        try:
            audio = MutagenFile(self.files[0], easy=True)
            if audio:
                self.artist_ed.setText(str(audio.get("artist", [""])[0]))
                self.album_ed.setText(str(audio.get("album", [""])[0]))
                self.year_ed.setText(str(audio.get("date", [""])[0]))
                self.genre_ed.setText(str(audio.get("genre", [""])[0]))
        except: pass

        self.tracks_table.setRowCount(len(self.files))
        for i, f in enumerate(self.files):
            try:
                a = MutagenFile(f, easy=True)
                tr_num = str(a.get("tracknumber", [""])[0]) if a else ""
                tr_title = str(a.get("title", [""])[0]) if a else Path(f).stem
                self.tracks_table.setItem(i, 0, QTableWidgetItem(tr_num))
                self.tracks_table.setItem(i, 1, QTableWidgetItem(tr_title))
            except:
                self.tracks_table.setItem(i, 0, QTableWidgetItem(""))
                self.tracks_table.setItem(i, 1, QTableWidgetItem(Path(f).stem))

    def _fetch_mb(self):
        artist = self.artist_ed.text().strip()
        album = self.album_ed.text().strip()
        mbid = ""
        for r in self.ds.library.get(artist, []):
            if r.get("album") == album:
                mbid = r.get("mbid", "")
                break

        if not mbid:
            QMessageBox.warning(self, "No MBID", "This album doesn't have a MusicBrainz ID in your database. Run 'Check New Releases' or scan first.")
            return

        try:
            data = mb_get(f"release-group/{mbid}", {"inc": "media+recordings"})

            title = data.get("title", "")
            if title: self.album_ed.setText(title)
            date_str = data.get("first-release-date", "")
            if date_str: self.year_ed.setText(date_str[:4])

            artist_credit = data.get("artist-credit", [])
            if artist_credit:
                a_name = artist_credit[0].get("name", "")
                if a_name: self.artist_ed.setText(a_name)

            media_list = data.get("media", [])
            if media_list:
                tracks = media_list[0].get("tracks", [])
                if tracks:
                    self.tracks_table.setRowCount(len(tracks))
                    for i, track in enumerate(tracks):
                        self.tracks_table.setItem(i, 0, QTableWidgetItem(str(track.get("number", i+1))))
                        self.tracks_table.setItem(i, 1, QTableWidgetItem(track.get("title", "")))

            QMessageBox.information(self, "Success", "Auto-filled tags from MusicBrainz. Click 'Save' to write them to files.")
        except Exception as e:
            QMessageBox.critical(self, "MusicBrainz Error", str(e))

    def _save_tags(self):
        reply = QMessageBox.warning(self, "Confirm Save",
            f"Permanently write these tags to {len(self.files)} file(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)

        if reply != QMessageBox.StandardButton.Yes: return

        artist = self.artist_ed.text().strip()
        album = self.album_ed.text().strip()
        year = self.year_ed.text().strip()
        genre = self.genre_ed.text().strip()

        errors = 0
        for i, f in enumerate(self.files):
            try:
                audio = MutagenFile(f, easy=True)
                if audio is None: continue

                audio["artist"] = artist
                audio["albumartist"] = artist
                audio["album"] = album
                audio["date"] = year
                if genre: audio["genre"] = genre

                item0 = self.tracks_table.item(i, 0)
                item1 = self.tracks_table.item(i, 1)
                if item0: audio["tracknumber"] = item0.text().strip()
                if item1: audio["title"] = item1.text().strip()

                audio.save()
            except Exception:
                errors += 1

        if errors:
            QMessageBox.warning(self, "Partial Success", f"Saved tags, but encountered errors on {errors} file(s).")
        else:
            QMessageBox.information(self, "Success", "Tags saved successfully! Please rescan your library to see the changes.")
        self.accept()

# ─────────────────────────────────────────────────────────────────────────────
# Smart Playlist Generator
# ─────────────────────────────────────────────────────────────────────────────

class PlaylistGeneratorDialog(QDialog):
    def __init__(self, ds, parent=None):
        super().__init__(parent)
        self.ds = ds
        self.setWindowTitle("✨ Smart Playlist Generator")
        self.setMinimumWidth(450)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Generate a smart playlist based on your library metrics:"))

        genre_row = QHBoxLayout()
        genre_row.addWidget(QLabel("Genre:"))
        self.genre_combo = QComboBox()
        self.genre_combo.addItems(["Any Genre"])
        genres = set()
        c = self.ds.db.cursor()
        c.execute("SELECT genre FROM releases")
        for row in c.fetchall():
            g_str = row["genre"]
            if g_str:
                for g in re.split(r'[/,;|]', g_str):
                    g = g.strip()
                    if g: genres.add(g)
        self.genre_combo.addItems(sorted(list(genres)))
        genre_row.addWidget(self.genre_combo, stretch=1)
        layout.addLayout(genre_row)

        decade_row = QHBoxLayout()
        decade_row.addWidget(QLabel("Decade:"))
        self.decade_combo = QComboBox()
        self.decade_combo.addItems(["Any Decade", "1960s", "1970s", "1980s", "1990s", "2000s", "2010s", "2020s"])
        decade_row.addWidget(self.decade_combo, stretch=1)
        layout.addLayout(decade_row)

        pop_row = QHBoxLayout()
        pop_row.addWidget(QLabel("Min Popularity (Norm %):"))
        self.pop_spin = QSpinBox()
        self.pop_spin.setRange(0, 100)
        self.pop_spin.setValue(10)
        pop_row.addWidget(self.pop_spin)
        pop_row.addStretch()
        layout.addLayout(pop_row)

        limit_row = QHBoxLayout()
        limit_row.addWidget(QLabel("Max Tracks:"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(10, 1000)
        self.limit_spin.setValue(50)
        limit_row.addWidget(self.limit_spin)
        limit_row.addStretch()
        layout.addLayout(limit_row)

        gen_btn = QPushButton("💾 Generate & Save .m3u")
        gen_btn.setObjectName("primaryBtn")
        gen_btn.setFixedHeight(36)
        gen_btn.clicked.connect(self._generate)
        layout.addWidget(gen_btn)

    def _generate(self):
        genre = self.genre_combo.currentText() if self.genre_combo.currentIndex() > 0 else None
        decade = self.decade_combo.currentText() if self.decade_combo.currentIndex() > 0 else None
        min_pop = self.pop_spin.value() / 100.0
        limit = self.limit_spin.value()

        c = self.ds.db.cursor()
        valid_artists = set()
        c.execute("SELECT artist, data FROM pop_cache")
        for row in c.fetchall():
            pop = json.loads(row["data"])
            norm = pop.get("normalised", 0.0)
            if norm >= min_pop:
                valid_artists.add(row["artist"])

        c.execute("SELECT artist, album, year, genre, files FROM releases")
        tracks = []
        for row in c.fetchall():
            if valid_artists and row["artist"] not in valid_artists: continue
            if decade:
                try:
                    y = int(row["year"][:4])
                    dec = (y // 10) * 10
                    if f"{dec}s" != decade: continue
                except: continue
            if genre:
                if not row["genre"] or genre.lower() not in row["genre"].lower(): continue

            try:
                files = json.loads(row["files"]) if row["files"] else []
                for f in files:
                    tracks.append(f)
            except: pass

        if not tracks:
            QMessageBox.information(self, "No Tracks", "No tracks found matching your criteria.")
            return

        random.shuffle(tracks)
        tracks = tracks[:limit]

        path, _ = QFileDialog.getSaveFileName(self, "Save Playlist", "musicwatcher_playlist.m3u", "Playlist Files (*.m3u)")
        if not path: return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for t in tracks:
                    f.write(f"#EXTINF:-1,{Path(t).stem}\n")
                    f.write(f"{t}\n")
            QMessageBox.information(self, "Success", f"Playlist saved with {len(tracks)} tracks to:\n{path}")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save playlist: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# Backup Manager Dialog
# ─────────────────────────────────────────────────────────────────────────────

class BackupManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🗄️ Backup Manager")
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Available backups (stored in ~/.musicwatcher/backups/):"))

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Timestamp", "Size", "Files"])
        self.tree.setColumnWidth(0, 180)
        self.tree.setColumnWidth(1, 80)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.tree)

        btn_row = QHBoxLayout()
        restore_btn = QPushButton("♻️ Restore Selected")
        restore_btn.setObjectName("secondaryBtn")
        restore_btn.clicked.connect(self._restore)
        btn_row.addWidget(restore_btn)

        delete_btn = QPushButton("🗑️ Delete Selected")
        delete_btn.setObjectName("removeBtn")
        delete_btn.clicked.connect(self._delete)
        btn_row.addWidget(delete_btn)

        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._populate()

    def _populate(self):
        self.tree.clear()
        backup_root = DATA_DIR / "backups"
        if not backup_root.exists(): return
        for d in sorted(backup_root.iterdir(), reverse=True):
            if d.is_dir():
                try:
                    size = sum(f.stat().st_size for f in d.glob('**/*') if f.is_file())
                    size_str = f"{size / 1024:.1f} KB"
                    file_count = len(list(d.glob('*')))
                    item = QTreeWidgetItem([d.name, size_str, str(file_count)])
                    item.setData(0, Qt.ItemDataRole.UserRole, str(d))
                    self.tree.addTopLevelItem(item)
                except Exception:
                    pass

    def _restore(self):
        item = self.tree.currentItem()
        if not item:
            QMessageBox.warning(self, "No Selection", "Please select a backup to restore.")
            return
        backup_dir = Path(item.data(0, Qt.ItemDataRole.UserRole))

        reply = QMessageBox.warning(self, "Confirm Restore",
            f"Restoring will overwrite your current library, caches, and settings with the backup from {backup_dir.name}.\n\n"
            "It is highly recommended to restart MusicWatcher afterwards.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)

        if reply == QMessageBox.StandardButton.Yes:
            try:
                for f in backup_dir.glob("*"):
                    dest = DATA_DIR / f.name
                    if dest.exists(): dest.unlink()
                    shutil.copy2(f, dest)
                QMessageBox.information(self, "Restore Complete", "Backup restored successfully. Please restart MusicWatcher to apply the changes.")
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to restore: {e}")

    def _delete(self):
        item = self.tree.currentItem()
        if not item: return
        backup_dir = Path(item.data(0, Qt.ItemDataRole.UserRole))

        reply = QMessageBox.warning(self, "Confirm Delete",
            f"Permanently delete the backup from {backup_dir.name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)

        if reply == QMessageBox.StandardButton.Yes:
            try:
                shutil.rmtree(backup_dir)
                self._populate()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# Settings dialog
# ─────────────────────────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    reset_requested = pyqtSignal()

    def __init__(self, ds, hw, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙  MusicWatcher Settings")
        self.setMinimumWidth(650)
        self.setMinimumHeight(550)
        self.ds=ds

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # Use a Tab Widget to organize settings
        tabs = QTabWidget()
        main_layout.addWidget(tabs)

        # ==========================================
        # Tab 1: General & Appearance
        # ==========================================
        general_tab = QWidget()
        gl = QVBoxLayout(general_tab)

        sys_group = QGroupBox("System & Maintenance")
        sys_layout = QVBoxLayout(sys_group)
        sys_layout.addWidget(QLabel(
            f"💻 Hardware: {hw['cpu']} CPUs · {hw.get('ram_gb', 0):.1f} GB RAM · "
            f"GPU: {hw.get('gpu_name', 'N/A')} ({hw.get('gpu_vendor', 'unknown')})"))

        summ = self.ds.le.summary()
        le_label = QLabel(
            f"🧠 Learning Engine Stats:\n"
            f"   Scans: {summ['scan_count']}   |   Best Workers: {summ['best_workers']}\n"
            f"   Pop. Blend Weight: {summ['pop_blend_w']}   |   Max Listeners: {summ['max_listeners']:,}\n"
            f"   LRC Success (Get/Search): {summ['lrc_get_rate']:.0%} / {summ['lrc_srch_rate']:.0%}\n"
            f"   BL Patterns Learned: {summ['bl_patterns']}   |   Auto-Del Confidence: {summ['auto_chk_conf']:.0%}"
        )
        le_label.setStyleSheet("background: rgba(127, 127, 127, 0.15); padding: 8px; border-radius: 4px; font-family: monospace;")
        sys_layout.addWidget(le_label)

        update_btn = QPushButton("🔄 Check for Updates")
        update_btn.setObjectName("secondaryBtn")
        update_btn.setFixedHeight(34)
        update_btn.clicked.connect(lambda: self.parent()._check_for_updates(silent=False))
        sys_layout.addWidget(update_btn)

        io_row = QHBoxLayout()
        export_btn = QPushButton("📦 Export Config")
        export_btn.setObjectName("secondaryBtn")
        export_btn.clicked.connect(self._export_config)
        io_row.addWidget(export_btn)

        import_btn = QPushButton("📥 Import Config")
        import_btn.setObjectName("secondaryBtn")
        import_btn.clicked.connect(self._import_config)
        io_row.addWidget(import_btn)

        backup_btn = QPushButton("🗄️  Backups")
        backup_btn.setObjectName("secondaryBtn")
        backup_btn.clicked.connect(self._open_backups)
        io_row.addWidget(backup_btn)
        sys_layout.addLayout(io_row)

        reset_btn = QPushButton("⚠  Reset App Database (Wipe All Data)")
        reset_btn.setObjectName("removeBtn")
        reset_btn.clicked.connect(self._trigger_reset)
        sys_layout.addWidget(reset_btn)
        gl.addWidget(sys_group)

        app_group = QGroupBox("Appearance")
        app_form = QVBoxLayout(app_group)
        theme_row = QHBoxLayout(); theme_row.addWidget(QLabel("UI Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(sorted(THEMES.keys()))
        self.theme_combo.setCurrentText(ds.settings.get("theme_name", "Dark"))
        self.theme_combo.currentTextChanged.connect(lambda t: ds.settings.update({"theme_name": t}))
        theme_row.addWidget(self.theme_combo, stretch=1)
        app_form.addLayout(theme_row)

        icon_row = QHBoxLayout(); icon_row.addWidget(QLabel("System tray icon:"))
        self._icon_ed = QLineEdit(ds.settings.get("tray_icon_path", ""))
        self._icon_ed.setObjectName("searchBox")
        self._icon_ed.setPlaceholderText("Default")
        icon_row.addWidget(self._icon_ed, stretch=1)
        icon_btn = QPushButton("Browse…")
        icon_btn.setObjectName("secondaryBtn")
        def _pick_icon():
            p, _ = QFileDialog.getOpenFileName(self, "Select Tray Icon", "", "Images (*.png *.jpg *.ico)")
            if p:
                self._icon_ed.setText(p)
                ds.settings.update({"tray_icon_path": p})
        icon_btn.clicked.connect(_pick_icon)
        icon_row.addWidget(icon_btn)
        app_form.addLayout(icon_row)

        fs_row=QHBoxLayout(); fs_row.addWidget(QLabel("Font size:"))
        sl=QSlider(Qt.Orientation.Horizontal); sl.setRange(10,22)
        sl.setValue(ds.settings.get("font_size",13))
        lbl2=QLabel(str(sl.value()))
        def on_font(v):
            lbl2.setText(str(v)); ds.settings["font_size"]=v
        sl.valueChanged.connect(on_font)
        fs_row.addWidget(sl); fs_row.addWidget(lbl2); app_form.addLayout(fs_row)
        gl.addWidget(app_group)
        gl.addStretch()
        tabs.addTab(general_tab, "General")

        # ==========================================
        # Tab 2: Library & Metadata
        # ==========================================
        lib_tab = QWidget()
        ll = QVBoxLayout(lib_tab)

        perf_group = QGroupBox("Performance & Metadata")
        perf_form = QVBoxLayout(perf_group)

        def spin(label,key,lo,hi):
            row=QHBoxLayout(); row.addWidget(QLabel(label))
            sb=QSpinBox(); sb.setRange(lo,hi); sb.setValue(ds.settings.get(key,lo))
            sb.valueChanged.connect(lambda v:ds.settings.update({key:v}))
            row.addWidget(sb); row.addStretch(); perf_form.addLayout(row)

        def chk(label,key,tip=""):
            cb=QCheckBox(label); cb.setChecked(ds.settings.get(key,False))
            if tip: cb.setToolTip(tip)
            cb.stateChanged.connect(lambda v:ds.settings.update({key:bool(v)}))
            perf_form.addWidget(cb); return cb

        spin("Scan workers (parallel tag reading):", "scan_workers", 1, 128)
        spin("Lyrics workers (parallel lrclib downloads):", "lyrics_workers", 4, 256)
        chk("Enable SHA-256 hashing (duplicate + change detection)", "hash_enabled")
        chk("Hash audio content only — skip metadata (fixes false positives)", "hash_audio_only")
        chk("MusicBrainz fallback for unknown artists (slow)", "mb_fallback")
        chk("Fetch lyrics from lrclib.net", "lyrics_enabled")
        chk("Try alternate lyrics sources if lrclib misses (NetEase)", "lyrics_alt_sources")
        chk("Show MusicBrainz hash & tag metadata in library", "show_mb_data")
        chk("Auto-organize files dropped into Watch Folder", "auto_organize")
        chk("Save cover.jpg/artist.jpg to folders (Plex/Jellyfin)", "save_art_to_folders")
        chk("Auto-translate non-Latin album titles to English", "translate_titles")

        ll.addWidget(perf_group)
        ll.addStretch()
        tabs.addTab(lib_tab, "Library")

        # ==========================================
        # Tab 3: Network & APIs
        # ==========================================
        net_tab = QWidget()
        nl = QVBoxLayout(net_tab)

        stor_group = QGroupBox("Data Directory")
        stor_layout = QVBoxLayout(stor_group)
        stor=QHBoxLayout(); stor.addWidget(QLabel("Path:"))
        self._stor_ed=QLineEdit(ds.settings.get("data_dir",str(DATA_DIR)))
        self._stor_ed.setObjectName("searchBox"); self._stor_ed.setReadOnly(True)
        sbtn=QPushButton("Browse…"); sbtn.setObjectName("secondaryBtn"); sbtn.setFixedHeight(26)
        def _pick():
            d=QFileDialog.getExistingDirectory(self,"Data directory",self._stor_ed.text())
            if d: self._stor_ed.setText(d); ds.settings["data_dir"]=d
        sbtn.clicked.connect(_pick)
        stor.addWidget(self._stor_ed,stretch=1); stor.addWidget(sbtn)
        stor_layout.addLayout(stor)
        nl.addWidget(stor_group)

        ext_group = QGroupBox("External Services && APIs")
        ext_form = QVBoxLayout(ext_group)

        lb_row=QHBoxLayout(); lb_row.addWidget(QLabel("ListenBrainz Token:"))
        lb_ed=QLineEdit(ds.settings.get("listenbrainz_token",""))
        lb_ed.setObjectName("searchBox"); lb_ed.setPlaceholderText("For submitting listens")
        lb_ed.textChanged.connect(lambda v:ds.settings.update({"listenbrainz_token":v}))
        lb_row.addWidget(lb_ed,stretch=1); ext_form.addLayout(lb_row)

        slsk_row=QHBoxLayout(); slsk_row.addWidget(QLabel("Slskd API URL:"))
        slsk_ed=QLineEdit(ds.settings.get("slskd_url","http://localhost:5030"))
        slsk_ed.setObjectName("searchBox")
        slsk_ed.textChanged.connect(lambda v:ds.settings.update({"slskd_url":v}))
        slsk_row.addWidget(slsk_ed,stretch=1); ext_form.addLayout(slsk_row)

        slsk_key_row=QHBoxLayout(); slsk_key_row.addWidget(QLabel("Slskd API Key:"))
        slsk_key_ed=QLineEdit(ds.settings.get("slskd_key",""))
        slsk_key_ed.setObjectName("searchBox"); slsk_key_ed.setEchoMode(QLineEdit.EchoMode.Password)
        slsk_key_ed.textChanged.connect(lambda v:ds.settings.update({"slskd_key":v}))
        slsk_key_row.addWidget(slsk_key_ed,stretch=1); ext_form.addLayout(slsk_key_row)

        ps_row=QHBoxLayout(); ps_row.addWidget(QLabel("Popularity source:"))
        self.ps_combo=QComboBox()
        self.ps_combo.addItems(["ListenBrainz only","Last.fm only","Both (LB + LFM)"])
        src=ds.settings.get("pop_source","both")
        self.ps_combo.setCurrentIndex({"lb":0,"lfm":1,"both":2}.get(src,2))
        self.ps_combo.currentIndexChanged.connect(
            lambda i:ds.settings.update({"pop_source":["lb","lfm","both"][i]}))
        ps_row.addWidget(self.ps_combo); ps_row.addStretch(); ext_form.addLayout(ps_row)

        for lbl,key,ph in [
            ("Last.fm API key:","lastfm_key","Enables richer data; register free at last.fm/api"),
            ("Last.fm API secret:","lastfm_secret","Required for scrobbling"),
            ("Last.fm country for geo charts:","lastfm_country","e.g. United States, Japan"),
        ]:
            row=QHBoxLayout(); row.addWidget(QLabel(lbl))
            ed=QLineEdit(ds.settings.get(key,"")); ed.setObjectName("searchBox")
            ed.setPlaceholderText(ph)
            if "secret" in key: ed.setEchoMode(QLineEdit.EchoMode.Password)
            ed.textChanged.connect(lambda v,k=key:ds.settings.update({k:v}))
            row.addWidget(ed,stretch=1); ext_form.addLayout(row)

        lfm_login_btn = QPushButton("🔗 Link Last.fm Account for Scrobbling")
        lfm_login_btn.setObjectName("secondaryBtn")
        def _link_lastfm():
            cid = ds.settings.get("lastfm_key", "").strip()
            secret = ds.settings.get("lastfm_secret", "").strip()
            if not cid or not secret:
                QMessageBox.warning(self, "Missing Info", "Please enter your Last.fm API Key and Secret first.")
                return
            sig_str = f"api_key{cid}methodauth.gettoken{secret}"
            api_sig = hashlib.md5(sig_str.encode()).hexdigest()
            try:
                r = requests.get("https://ws.audioscrobbler.com/2.0", params={
                    "method": "auth.gettoken", "api_key": cid, "api_sig": api_sig, "format": "json"
                }, timeout=10)
                token = r.json().get("token")
                if not token:
                    QMessageBox.critical(self, "Error", "Could not get Last.fm token.")
                    return
                webbrowser.open(f"https://www.last.fm/api/auth/?api_key={cid}&token={token}")
                QMessageBox.information(self, "Authorize MusicWatcher", "Your web browser has opened.\nPlease log into Last.fm and click 'Yes, allow access'.\n\nClick OK here when you are done.")
                sig_str2 = f"api_key{cid}methodauth.getsessiontoken{token}{secret}"
                api_sig2 = hashlib.md5(sig_str2.encode()).hexdigest()
                r2 = requests.get("https://ws.audioscrobbler.com/2.0", params={
                    "method": "auth.getsession", "api_key": cid, "token": token, "api_sig": api_sig2, "format": "json"
                }, timeout=10)
                sk = r2.json().get("session", {}).get("key")
                if sk:
                    ds.settings["lastfm_session_key"] = sk
                    QMessageBox.information(self, "Success", "Last.fm account linked successfully! Scrobbling is now enabled.")
                else:
                    QMessageBox.warning(self, "Failed", "Did not receive session key. Did you click 'Allow' in your browser?")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

        lfm_login_btn.clicked.connect(_link_lastfm)
        ext_form.addWidget(lfm_login_btn)

        test_btn=QPushButton("Test Last.fm Key"); test_btn.setObjectName("secondaryBtn")
        def _test_key():
            key=ds.settings.get("lastfm_key","").strip()
            if not key:
                QMessageBox.warning(self,"No key","Enter a Last.fm API key first."); return
            ok,msg=LastFM(key).test_key()
            (QMessageBox.information if ok else QMessageBox.warning)(self,"Last.fm Key Test",msg)
        test_btn.clicked.connect(_test_key)
        ext_form.addWidget(test_btn)

        geo_row=QHBoxLayout(); geo_row.addWidget(QLabel("Geo countries (comma-separated):"))
        geo_ed=QLineEdit(",".join(ds.settings.get("geo_countries",GEO_COUNTRIES[:3])))
        geo_ed.setObjectName("searchBox")
        geo_ed.textChanged.connect(
            lambda v:ds.settings.update({"geo_countries":[c.strip() for c in v.split(",") if c.strip()]}))
        geo_row.addWidget(geo_ed,stretch=1); ext_form.addLayout(geo_row)

        nl.addWidget(ext_group)
        nl.addStretch()
        tabs.addTab(net_tab, "Network && APIs")

        # ==========================================
        # Tab 4: External Apps
        # ==========================================
        apps_tab = QWidget()
        al = QVBoxLayout(apps_tab)

        apps_group = QGroupBox("External Applications")
        apps_form = QVBoxLayout(apps_group)

        ext_player_row = QHBoxLayout(); ext_player_row.addWidget(QLabel("External Player (e.g., strawberry, vlc):"))
        ext_player_ed = QLineEdit(ds.settings.get("external_player", "strawberry"))
        ext_player_ed.setObjectName("searchBox")
        ext_player_ed.textChanged.connect(lambda v: ds.settings.update({"external_player": v}))
        ext_player_row.addWidget(ext_player_ed, stretch=1)
        apps_form.addLayout(ext_player_row)

        gen=QHBoxLayout(); gen.addWidget(QLabel("Genius API key (optional):"))
        gen_ed=QLineEdit(ds.settings.get("genius_api_key",""))
        gen_ed.setObjectName("searchBox"); gen_ed.setPlaceholderText("For lyrics viewer")
        gen_ed.textChanged.connect(lambda v:ds.settings.update({"genius_api_key":v}))
        gen.addWidget(gen_ed,stretch=1); apps_form.addLayout(gen)

        al.addWidget(apps_group)
        al.addStretch()
        tabs.addTab(apps_tab, "External Apps")

        # Bottom OK button
        bb=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        bb.accepted.connect(self.accept)
        main_layout.addWidget(bb)
    def _trigger_reset(self):
        reply = QMessageBox.warning(self, "Confirm Reset",
            "Are you absolutely sure? This will delete your library, caches, blacklists, and learning model. It cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Yes:
            self.reset_requested.emit()
            self.accept()

    def _open_backups(self):
        dlg = BackupManagerDialog(self)
        dlg.exec()

    def _export_config(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Configuration", "musicwatcher_config.zip", "Zip Files (*.zip)")
        if not path: return
        try:
            with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for f in ["settings.json", "blacklist.json", "whitelist.json", "favorites.json"]:
                    p = DATA_DIR / f
                    if p.exists(): zf.write(p, f)
                model = DATA_DIR / "learning" / "model.json"
                if model.exists(): zf.write(model, "learning/model.json")
            QMessageBox.information(self, "Export Complete", f"Configuration exported to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export: {e}")

    def _import_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Configuration", "", "Zip Files (*.zip)")
        if not path: return
        reply = QMessageBox.warning(self, "Confirm Import",
            "This will overwrite your current settings, lists, and learning model. Restart required. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        if reply != QMessageBox.StandardButton.Yes: return
        try:
            with zipfile.ZipFile(path, 'r') as zf:
                zf.extractall(DATA_DIR)
            QMessageBox.information(self, "Import Complete", "Configuration imported. Please restart MusicWatcher.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to import: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# Genius Lyrics Viewer
# ─────────────────────────────────────────────────────────────────────────────

class GeniusViewerDialog(QDialog):
    def __init__(self, artist, title, api_key, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Genius Lyrics — {artist} - {title}")
        self.resize(600, 600)
        layout = QVBoxLayout(self)

        self.browser = QTextBrowser()
        self.browser.setPlaceholderText(f"Searching Genius for {artist} - {title}...")
        self.browser.setObjectName("lyricsBrowser")
        layout.addWidget(self.browser)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(34)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._thread = GeniusFetchThread(artist, title, api_key)
        self._thread.finished.connect(self._on_finished)
        self._thread.error.connect(self._on_error)
        self._thread.start()

    def _on_finished(self, lyrics):
        self.browser.setPlainText(lyrics)

    def _on_error(self, err):
        self.browser.setPlainText(f"⚠ Error: {err}")

# ─────────────────────────────────────────────────────────────────────────────
# Library Organizer Dialog
# ─────────────────────────────────────────────────────────────────────────────

class OrganizerThread(QThread):
    progress = pyqtSignal(int, int, str)
    status_message = pyqtSignal(str)
    finished = pyqtSignal(int, int)

    def __init__(self, source_dir, dest_dir, move_files=True):
        super().__init__()
        self.source_dir = Path(source_dir)
        self.dest_dir = Path(dest_dir)
        self.move_files = move_files
        self.stop_flag = False

    def run(self):
        from core.utils import AUDIO_EXT, extract_tags
        files = [p for p in self.source_dir.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXT]
        total = len(files)
        moved = 0
        errors = 0

        for i, fp in enumerate(files):
            if self.stop_flag: break

            tags = extract_tags(fp)
            if not tags or tags["artist"] == "Unknown" or tags["album"] == "Unknown":
                errors += 1
                continue

            artist = re.sub(r'[\\/:*?"<>|]', '_', tags["artist"])
            album = re.sub(r'[\\/:*?"<>|]', '_', tags["album"])
            title = re.sub(r'[\\/:*?"<>|]', '_', tags["title"])
            track_num = tags.get("tracknumber", "")

            if track_num and "/" in track_num:
                track_num = track_num.split("/")[0]
            if track_num and track_num.isdigit():
                track_num = f"{int(track_num):02d} - "
            else:
                track_num = ""

            dest_folder = self.dest_dir / artist / album
            dest_file = dest_folder / f"{track_num}{title}{fp.suffix.lower()}"

            # NEW: Skip if the file is already organized in the right place
            if fp == dest_file:
                continue

            try:
                if dest_file.exists():
                    errors += 1
                    continue

                dest_folder.mkdir(parents=True, exist_ok=True)
                if self.move_files:
                    shutil.move(str(fp), str(dest_file))
                else:
                    shutil.copy2(str(fp), str(dest_file))
                moved += 1
            except Exception:
                errors += 1

            self.progress.emit(i+1, total, f"{artist} - {title}")

        self.finished.emit(moved, errors)

    def stop(self):
        self.stop_flag = True

class LibraryOrganizerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🤖 Automated Library Organizer")
        self.setMinimumWidth(550)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Select a messy folder to scan (e.g., ~/Downloads):"))
        src_row = QHBoxLayout()
        self.src_ed = QLineEdit(); self.src_ed.setObjectName("searchBox")
        src_btn = QPushButton("Browse..."); src_btn.setObjectName("secondaryBtn")
        src_btn.clicked.connect(lambda: self._pick_dir(self.src_ed))
        src_row.addWidget(self.src_ed, stretch=1); src_row.addWidget(src_btn)
        layout.addLayout(src_row)

        layout.addWidget(QLabel("Select destination folder (e.g., ~/Music/Clean_Library):"))
        dest_row = QHBoxLayout()
        self.dest_ed = QLineEdit(); self.dest_ed.setObjectName("searchBox")
        dest_btn = QPushButton("Browse..."); dest_btn.setObjectName("secondaryBtn")
        dest_btn.clicked.connect(lambda: self._pick_dir(self.dest_ed))
        dest_row.addWidget(self.dest_ed, stretch=1); dest_row.addWidget(dest_btn)
        layout.addLayout(dest_row)

        opt_row = QHBoxLayout()
        self.move_chk = QCheckBox("Move files (uncheck to Copy instead)")
        self.move_chk.setChecked(True)
        opt_row.addWidget(self.move_chk); opt_row.addStretch()
        layout.addLayout(opt_row)

        self.run_btn = QPushButton("▶ Run Organizer")
        self.run_btn.setObjectName("primaryBtn")
        self.run_btn.setFixedHeight(36)
        self.run_btn.clicked.connect(self._run)
        layout.addWidget(self.run_btn)

        self.prog_bar = QProgressBar(); self.prog_bar.setFixedHeight(30)
        self.prog_bar.setVisible(False)
        layout.addWidget(self.prog_bar)

        self.log_lbl = QLabel("")
        self.log_lbl.setObjectName("progressInfo")
        layout.addWidget(self.log_lbl)

        self._thread = None

    def _pick_dir(self, ed):
        d = QFileDialog.getExistingDirectory(self, "Select Directory")
        if d: ed.setText(d)

    def _run(self):
        src = self.src_ed.text().strip()
        dest = self.dest_ed.text().strip()
        if not src or not dest:
            QMessageBox.warning(self, "Missing Info", "Please select both source and destination folders.")
            return

        self.run_btn.setEnabled(False)
        self.prog_bar.setVisible(True)
        self.log_lbl.setText("Scanning and organizing...")

        self._thread = OrganizerThread(src, dest, self.move_chk.isChecked())
        self._thread.progress.connect(self._on_prog)
        self._thread.finished.connect(self._on_done)
        self._thread.start()

    def _on_prog(self, done, total, name):
        self.prog_bar.setMaximum(max(total, 1))
        self.prog_bar.setValue(done)
        self.log_lbl.setText(f"Processing: {name}")

    def _on_done(self, moved, errors):
        self.run_btn.setEnabled(True)
        self.log_lbl.setText(f"✔ Organized {moved} files. Errors/Skipped: {errors}")
        QMessageBox.information(self, "Complete", f"Organized {moved} files successfully.\nErrors/Skipped: {errors}")

# ─────────────────────────────────────────────────────────────────────────────
# Library Exporter Dialog
# ─────────────────────────────────────────────────────────────────────────────
class LibraryExporterDialog(QDialog):
    def __init__(self, ds, parent=None):
        super().__init__(parent)
        self.ds = ds
        self.setWindowTitle("📊 Export Library")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Export your library data, stats, and popularity to a file."))

        btn_row = QHBoxLayout()
        csv_btn = QPushButton("📄 Export to CSV")
        csv_btn.setObjectName("secondaryBtn")
        csv_btn.clicked.connect(self._export_csv)
        btn_row.addWidget(csv_btn)

        html_btn = QPushButton("🌐 Export to HTML")
        html_btn.setObjectName("primaryBtn")
        html_btn.clicked.connect(self._export_html)
        btn_row.addWidget(html_btn)
        layout.addLayout(btn_row)

        self.log_lbl = QLabel("")
        self.log_lbl.setObjectName("progressInfo")
        layout.addWidget(self.log_lbl)

    def _get_data(self):
        c = self.ds.db.cursor()
        c.execute("SELECT artist, album, year, type, genre, lyr_status, bpm, key, mood FROM releases ORDER BY artist, year")
        return c.fetchall()

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "musicwatcher_library.csv", "CSV Files (*.csv)")
        if not path: return

        rows = self._get_data()
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Artist", "Album", "Year", "Type", "Genre", "Lyrics", "BPM", "Key", "Mood"])
                for r in rows:
                    w.writerow([r["artist"], r["album"], r["year"], r["type"], r["genre"], r["lyr_status"], r["bpm"], r["key"], r["mood"]])
            self.log_lbl.setText(f"✔ Exported {len(rows)} releases to CSV successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _export_html(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save HTML", "musicwatcher_library.html", "HTML Files (*.html)")
        if not path: return

        rows = self._get_data()
        try:
            html = "<html><head><style>body{font-family:sans-serif;background:#1a1a2e;color:#e0e0f0;}table{border-collapse:collapse;width:100%;}th,td{border:1px solid #444;padding:8px;text-align:left;}th{background:#3a2a6a;}</style></head><body>"
            html += "<h1>🎵 MusicWatcher Library Export</h1>"
            html += f"<p><b>Total Releases:</b> {len(rows)}</p>"
            html += "<table><tr><th>Artist</th><th>Album</th><th>Year</th><th>Type</th><th>Genre</th><th>BPM</th><th>Key</th><th>Mood</th></tr>"

            for r in rows:
                html += f"<tr><td>{r['artist']}</td><td>{r['album']}</td><td>{r['year']}</td><td>{r['type']}</td><td>{r['genre']}</td><td>{r['bpm'] or ''}</td><td>{r['key'] or ''}</td><td>{r['mood'] or ''}</td></tr>"

            html += "</table></body></html>"

            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            self.log_lbl.setText(f"✔ Exported {len(rows)} releases to HTML successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
