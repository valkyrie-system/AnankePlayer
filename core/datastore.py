import csv, json, sqlite3, time, shutil, datetime
from pathlib import Path
from collections import defaultdict
from core.utils import DATA_DIR, GEO_COUNTRIES
from core.learning import LearningEngine

class DataStore:
    def __init__(self, hw: dict):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(DATA_DIR / "musicwatcher.db", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._create_tables()

        self.library:   dict = {}
        self.mb_cache:  dict = {}
        self.pop_cache: dict = {}
        self.blacklist: set  = set()
        self.whitelist: set  = set()
        self.favorites: set  = set()
        self.settings:  dict = {
            "theme":"dark","font_size":13,
            "scan_workers":hw["workers"],
            "lyrics_workers":hw["lyrics_workers"],
            "hash_enabled":False,"hash_audio_only":True,
            "mb_fallback":False,"lastfm_key":"",
            "lyrics_enabled":False,"lastfm_country":"United States",
            "pop_source":"both",
            "geo_countries": GEO_COUNTRIES,
            "translate_titles":False,
            "show_mb_data":False,
            "release_types":["Album","EP","Single"],
            "squid_fallback":"",
            "data_dir":str(DATA_DIR),
            "genius_api_key":"",
            "lyrics_alt_sources":True,
            "tray_icon_path":"",
            "lastfm_secret":"",
            "lastfm_session_key":"",
            "listenbrainz_token":"",  # NEW
            "slskd_url":"http://localhost:5030", # NEW
            "slskd_key":"" # NEW
        }
        self._load()

    def _p(self,n): return DATA_DIR/n

    def _create_tables(self):
        c = self.db.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS artists (
            name TEXT PRIMARY KEY, blacklist BOOLEAN, whitelist BOOLEAN, favorite BOOLEAN)""")
        c.execute("""CREATE TABLE IF NOT EXISTS releases (
            id INTEGER PRIMARY KEY AUTOINCREMENT, artist TEXT, album TEXT, year TEXT, type TEXT,
            mbid TEXT, genre TEXT, files TEXT, lyr_status TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS mb_cache (
            artist TEXT PRIMARY KEY, data TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS pop_cache (
            artist TEXT PRIMARY KEY, data TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS hashes (
            path TEXT PRIMARY KEY, hash TEXT, duration_sec TEXT, status TEXT, is_single TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS new_releases (
            artist TEXT, title TEXT, year TEXT, type TEXT)""")
        self.db.commit()

    def _load(self):
        c = self.db.cursor()
        c.execute("SELECT COUNT(*) FROM releases")
        if c.fetchone()[0] == 0 and self._p("library.csv").exists():
            self._migrate_library_csv()

        p = self._p("settings.json")
        if p.exists():
            try: self.settings.update(json.loads(p.read_text()))
            except Exception: pass

        self.library = defaultdict(list)
        c.execute("SELECT artist, album, year, type, mbid, genre, files, lyr_status FROM releases")
        for row in c.fetchall():
            entry = {"album": row["album"], "year": row["year"], "type": row["type"],
                     "mbid": row["mbid"], "genre": row["genre"],
                     "files": json.loads(row["files"]) if row["files"] else [],
                     "lyr_status": row["lyr_status"]}
            self.library[row["artist"]].append(entry)
        self.library = dict(self.library)

        c.execute("SELECT artist, data FROM mb_cache")
        self.mb_cache = {row["artist"]: json.loads(row["data"]) for row in c.fetchall()}
        c.execute("SELECT artist, data FROM pop_cache")
        self.pop_cache = {row["artist"]: json.loads(row["data"]) for row in c.fetchall()}

        self.blacklist, self.whitelist, self.favorites = set(), set(), set()
        c.execute("SELECT name, blacklist, whitelist, favorite FROM artists")
        for row in c.fetchall():
            if row["blacklist"]: self.blacklist.add(row["name"])
            if row["whitelist"]: self.whitelist.add(row["name"])
            if row["favorite"]: self.favorites.add(row["name"])

        self.le = LearningEngine()
        self._make_backup()

    def _migrate_library_csv(self):
        c = self.db.cursor()
        p = self._p("library.csv")
        try:
            with open(p, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = []
                for row in reader:
                    files = row.get("files", "[]")
                    try: files = json.loads(files)
                    except: files = []
                    rows.append((
                        row.get("artist",""), row.get("album",""), row.get("year",""),
                        row.get("type",""), row.get("mbid",""), row.get("genre",""),
                        json.dumps(files), row.get("lyr_status","")
                    ))
                c.executemany("INSERT INTO releases (artist, album, year, type, mbid, genre, files, lyr_status) VALUES (?,?,?,?,?,?,?,?)", rows)
                self.db.commit()
            p.rename(self._p("library.csv.bak"))
        except Exception as e:
            print("Migration error:", e)

    def _make_backup(self):
        try:
            backup_root = DATA_DIR / "backups"; backup_root.mkdir(parents=True, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            dst = backup_root / ts; dst.mkdir(exist_ok=True)

            db_file = DATA_DIR / "musicwatcher.db"
            if db_file.exists(): shutil.copy2(db_file, dst / "musicwatcher.db")

            p = self._p("settings.json")
            if p.exists(): shutil.copy2(p, dst / "settings.json")

            for old in sorted(backup_root.iterdir(), key=lambda d: d.name)[:-5]:
                if old.is_dir(): shutil.rmtree(old, ignore_errors=True)
        except Exception: pass

    def mb_cache_valid(self, a):
        e = self.mb_cache.get(a); return bool(e and (time.time() - e.get("ts", 0)) < 7 * 86400)
    def pop_cache_valid(self, a):
        e = self.pop_cache.get(a); return bool(e and (time.time() - e.get("ts", 0)) < 7 * 86400)

    def save_library(self):
        c = self.db.cursor()
        c.execute("DELETE FROM releases")
        rows = []
        for artist, releases in self.library.items():
            for r in releases:
                rows.append((artist, r.get("album",""), r.get("year",""), r.get("type",""),
                             r.get("mbid",""), r.get("genre",""), json.dumps(r.get("files",[])),
                             r.get("lyr_status","")))
        c.executemany("INSERT INTO releases (artist, album, year, type, mbid, genre, files, lyr_status) VALUES (?,?,?,?,?,?,?,?)", rows)
        self.db.commit()

    def save_new_releases(self, nr: dict):
        c = self.db.cursor()
        c.execute("DELETE FROM new_releases")
        rows = []
        for artist, releases in nr.items():
            for r in releases:
                rows.append((artist, r.get("title",""), r.get("year",""), r.get("type","")))
        c.executemany("INSERT INTO new_releases (artist, title, year, type) VALUES (?,?,?,?)", rows)
        self.db.commit()

    def save_hashes(self, rows: list):
        c = self.db.cursor()
        c.execute("DELETE FROM hashes")
        data = [(r["path"], r["hash"], r["duration_sec"], r["status"], r["is_single"]) for r in rows]
        c.executemany("INSERT INTO hashes (path, hash, duration_sec, status, is_single) VALUES (?,?,?,?,?)", data)
        self.db.commit()

    def save_mb_cache(self):
        c = self.db.cursor()
        c.execute("DELETE FROM mb_cache")
        c.executemany("INSERT INTO mb_cache (artist, data) VALUES (?,?)",
                      [(k, json.dumps(v)) for k, v in self.mb_cache.items()])
        self.db.commit()

    def save_pop_cache(self):
        c = self.db.cursor()
        c.execute("DELETE FROM pop_cache")
        c.executemany("INSERT INTO pop_cache (artist, data) VALUES (?,?)",
                      [(k, json.dumps(v)) for k, v in self.pop_cache.items()])
        self.db.commit()

    def save_settings(self):
        self._p("settings.json").write_text(json.dumps(self.settings, indent=2))

    def save_lists(self):
        c = self.db.cursor()
        c.execute("DELETE FROM artists")
        all_artists = set(self.library.keys()) | self.blacklist | self.whitelist | self.favorites
        for a in all_artists:
            c.execute("INSERT INTO artists (name, blacklist, whitelist, favorite) VALUES (?,?,?,?)",
                      (a, a in self.blacklist, a in self.whitelist, a in self.favorites))
        self.db.commit()

    def save_all(self):
        self.save_library(); self.save_mb_cache(); self.save_pop_cache()
        self.save_settings(); self.save_lists()
        self.le.save()

    def save_popularity(self):
        # Alias to save_pop_cache to fix a missing method call in the original script
        self.save_pop_cache()
