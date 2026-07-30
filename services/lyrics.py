import re, time, threading, requests, html as html_mod
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt6.QtCore import QThread, pyqtSignal
from core.utils import LRCLIB_BASE, extract_tags, Notifier, PausableMixin

class LyricsFetcher(QThread, PausableMixin):
    # ... rest of the file is exactly the same as what I sent ...
    progress       = pyqtSignal(int,int,str)
    file_done      = pyqtSignal(str,str)
    finished       = pyqtSignal(int,int)
    status_message = pyqtSignal(str)

    def __init__(self, folders: list, ds, overwrite_lrc: bool = False):
        super().__init__()
        self._init_pause()
        self.folders=folders; self.ds=ds
        self.overwrite_lrc=overwrite_lrc

    def run(self):
        files=[]
        for folder in self.folders:
            try:
                files.extend(p for p in Path(folder).rglob("*")
                             if p.is_file() and p.suffix.lower() in {".mp3",".flac",".ogg",".opus",".m4a",".aac",".mp4",".wma",".wav",".aif",".aiff"})
            except Exception: pass

        total=len(files); synced=plain=0
        done_count=0; done_lock=threading.Lock()
        import threading
        WORKERS = max(8, self.ds.settings.get("lyrics_workers", 32))

        def fetch_one(fp):
            if self._stop_flag: return str(fp),"skip"
            self._pause_evt.wait()
            if self._stop_flag: return str(fp),"skip"
            lrc=fp.with_suffix(".lrc")
            txt=fp.with_suffix(".txt")
            if lrc.exists() and not self.overwrite_lrc: return str(fp),"skip"
            tags=extract_tags(fp)
            if not tags: return str(fp),"skip"

            _src_order = self.ds.le.lyric_source_order()

            for source in _src_order:
                if self._stop_flag: return str(fp),"skip"
                if source == "get":
                    for attempt in range(2):
                        try:
                            r=requests.get(f"{LRCLIB_BASE}/get",params={
                                "artist_name":tags.get("artist",""),
                                "track_name": tags.get("title",""),
                                "album_name": tags.get("album",""),
                                "duration":   int(tags.get("duration",0)),
                            },timeout=10)
                            if r.status_code==200:
                                d=r.json()
                                if d.get("syncedLyrics"):
                                    lrc.write_text(d["syncedLyrics"],encoding="utf-8")
                                    txt.unlink(missing_ok=True)
                                    self.ds.le.record_lyrics("get", True)
                                    return str(fp),"synced"
                                elif d.get("plainLyrics"):
                                    if lrc.exists(): return str(fp),"skip"
                                    txt.write_text(d["plainLyrics"],encoding="utf-8")
                                    self.ds.le.record_lyrics("get", True)
                                    return str(fp),"plain"
                                self.ds.le.record_lyrics("get", False)
                                return str(fp),"none"
                            elif r.status_code==429 and attempt==0:
                                time.sleep(3); continue
                            break
                        except Exception: break
                elif source == "search":
                    if self.ds.settings.get("lyrics_alt_sources",True):
                        try:
                            r2=requests.get(f"{LRCLIB_BASE}/search",params={
                                "artist_name":tags.get("artist",""),
                                "track_name": tags.get("title",""),
                            },timeout=8)
                            if r2.status_code==200:
                                results=r2.json()
                                if isinstance(results,list) and results:
                                    best=results[0]
                                    if best.get("syncedLyrics"):
                                        fp.with_suffix(".lrc").write_text(best["syncedLyrics"],encoding="utf-8")
                                        fp.with_suffix(".txt").unlink(missing_ok=True)
                                        self.ds.le.record_lyrics("search", True)
                                        return str(fp),"synced"
                                    elif best.get("plainLyrics") and not fp.with_suffix(".lrc").exists():
                                        fp.with_suffix(".txt").write_text(best["plainLyrics"],encoding="utf-8")
                                        self.ds.le.record_lyrics("search", True)
                                        return str(fp),"plain"
                                self.ds.le.record_lyrics("search", False)
                        except Exception: pass
            return str(fp),"none"

        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=WORKERS,thread_name_prefix="lyr") as pool:
            futures={pool.submit(fetch_one,fp):fp for fp in files}
            for fut in as_completed(futures):
                if self._stop_flag:
                    for f in futures: f.cancel(); break
                with done_lock:
                    done_count+=1; done=done_count
                fp=futures[fut]
                self.progress.emit(done,total,fp.name[:42])
                try:
                    path,status=fut.result()
                    self.file_done.emit(path,status)
                    if status=="synced": synced+=1
                    elif status=="plain": plain+=1
                except Exception: pass

        self.finished.emit(synced,plain)
        self.status_message.emit(f"Lyrics: {synced} synced + {plain} plain saved.")
        Notifier.notify("MusicWatcher",f"Lyrics done: {synced} synced, {plain} plain.")

class GeniusFetchThread(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, artist, title, api_key):
        super().__init__()
        self.artist = artist
        self.title = title
        self.api_key = api_key

    def run(self):
        if not self.api_key:
            self.error.emit("No Genius API key set in Settings.")
            return
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            r = requests.get("https://api.genius.com/search",
                             params={"q": f"{self.artist} {self.title}"},
                             headers=headers, timeout=10)
            if r.status_code != 200:
                self.error.emit(f"Genius API error: {r.status_code}")
                return

            hits = r.json().get("response", {}).get("hits", [])
            if not hits:
                self.error.emit("No results found on Genius.")
                return

            path = hits[0]["result"]["path"]
            song_url = f"https://genius.com{path}"

            r2 = requests.get(song_url, headers={"User-Agent": "MusicWatcher/5.1"}, timeout=10)
            if r2.status_code != 200:
                self.error.emit(f"Failed to fetch Genius page: {r2.status_code}")
                return

            html = r2.text
            matches = re.findall(r'<div data-lyrics-container="true"[^>]*>(.*?)</div>', html, re.DOTALL)
            if matches:
                lyrics_html = "<br>".join(matches)
                lyrics = re.sub(r'<br>', '\n', lyrics_html)
                lyrics = re.sub(r'<[^>]+>', '', lyrics)
                lyrics = html_mod.unescape(lyrics)
                self.finished.emit(lyrics.strip())
            else:
                self.error.emit("Could not parse lyrics. The page might be missing or behind a paywall.")
        except Exception as e:
            self.error.emit(str(e))
