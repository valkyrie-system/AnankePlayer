import threading, requests, hashlib
from pathlib import Path
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtCore import QObject, pyqtSignal
from core.utils import ART_DIR, MB_BASE, CAA_BASE
from mutagen import File as MutagenFile

class _ArtSig(QObject):
    loaded = pyqtSignal(str, bytes)

class ArtworkLoader:
    _inst = None
    def __init__(self):
        ART_DIR.mkdir(parents=True, exist_ok=True)
        self._sig   = _ArtSig()
        self.loaded = self._sig.loaded
        self._pool  = ThreadPoolExecutor(max_workers=4, thread_name_prefix="art")
        self._pend: set = set()
        self._lk = threading.Lock()
        self._mem_cache = OrderedDict()
        self._mem_cache_limit = 200

    @classmethod
    def instance(cls):
        if cls._inst is None: cls._inst = cls()
        return cls._inst

    def _cache_to_mem(self, mbid: str, data: bytes):
        with self._lk:
            if mbid in self._mem_cache:
                self._mem_cache.move_to_end(mbid)
            else:
                self._mem_cache[mbid] = data
                if len(self._mem_cache) > self._mem_cache_limit:
                    self._mem_cache.popitem(last=False)

    def request(self, mbid: str, url: str):
        with self._lk:
            if mbid in self._pend: return
            self._pend.add(mbid)

        if mbid in self._mem_cache:
            self._sig.loaded.emit(mbid, self._mem_cache[mbid])
            with self._lk: self._pend.discard(mbid)
            return

        cache = ART_DIR / f"{mbid}.jpg"
        if cache.exists():
            try:
                data = cache.read_bytes()
                self._cache_to_mem(mbid, data)
                self._sig.loaded.emit(mbid, data)
                with self._lk: self._pend.discard(mbid)
                return
            except Exception: pass
        self._pool.submit(self._fetch, mbid, url, cache)

    def _fetch(self, mbid, url, cache):
        try:
            r = requests.get(url, timeout=12, allow_redirects=True,
                             headers={"User-Agent":"MusicWatcher/5.1"})
            if r.status_code == 200 and r.content:
                cache.write_bytes(r.content)
                self._cache_to_mem(mbid, r.content)
                self._sig.loaded.emit(mbid, r.content)
        except Exception: pass
        finally:
            with self._lk: self._pend.discard(mbid)

    def get_artist_art(self, artist: str, mbid: str):
        cache_key = f"artist_{mbid}"
        with self._lk:
            if cache_key in self._pend: return
            self._pend.add(cache_key)

        if cache_key in self._mem_cache:
            self._sig.loaded.emit(cache_key, self._mem_cache[cache_key])
            with self._lk: self._pend.discard(cache_key)
            return

        cache = ART_DIR / f"{cache_key}.jpg"
        if cache.exists():
            try:
                data = cache.read_bytes()
                self._cache_to_mem(cache_key, data)
                self._sig.loaded.emit(cache_key, data)
                return
            except Exception: pass
        self._pool.submit(self._fetch_artist, artist, mbid, cache)

    def get_embedded_art(self, path: str, cache_key: str):
        with self._lk:
            if cache_key in self._pend: return
            self._pend.add(cache_key)

        if cache_key in self._mem_cache:
            self._sig.loaded.emit(cache_key, self._mem_cache[cache_key])
            with self._lk: self._pend.discard(cache_key)
            return

        cache = ART_DIR / f"{cache_key}.jpg"
        if cache.exists():
            try:
                data = cache.read_bytes()
                self._cache_to_mem(cache_key, data)
                self._sig.loaded.emit(cache_key, data)
                return
            except Exception: pass

        self._pool.submit(self._fetch_embedded, path, cache_key, cache)

    def _fetch_embedded(self, path: str, cache_key: str, cache: Path):
        try:
            audio = MutagenFile(path)
            if audio:
                pics = []
                if hasattr(audio, 'pictures'):
                    pics = audio.pictures
                elif 'APIC:' in audio:
                    pics = [audio['APIC:']]
                elif 'covr' in audio:
                    covr = audio['covr']
                    if not isinstance(covr, list): covr = [covr]
                    for c in covr:
                        class FakePic: pass
                        p = FakePic()
                        p.data = c.data if hasattr(c, 'data') else c
                        pics.append(p)

                if pics:
                    data = pics[0].data
                    cache.write_bytes(data)
                    self._cache_to_mem(cache_key, data)
                    self._sig.loaded.emit(cache_key, data)
        except Exception: pass
        finally:
            with self._lk: self._pend.discard(cache_key)

    def _fetch_artist(self, artist, mbid, cache):
        try:
            r = requests.get(f"{MB_BASE}/artist/{mbid}",
                             params={"inc":"url-rels","fmt":"json"},
                             headers={"User-Agent":"MusicWatcher/5.1"},timeout=10)
            if r.status_code == 200:
                data = r.json()
                rels = data.get("relations",[])
                for rel in rels:
                    url = rel.get("url",{}).get("resource","")
                    if "commons.wikimedia.org" in url or "wikipedia.org" in url:
                        break
        except Exception: pass
        try:
            r2 = requests.get(f"{MB_BASE}/release",
                              params={"artist":mbid,"limit":1,"fmt":"json"},
                              headers={"User-Agent":"MusicWatcher/5.1"},timeout=10)
            if r2.status_code == 200:
                rels = r2.json().get("releases",[])
                if rels:
                    rid = rels[0].get("id","")
                    if rid:
                        self._fetch(f"artist_{mbid}",
                                    f"{CAA_BASE}/release/{rid}/front-250", cache)
        except Exception: pass
        finally:
            with self._lk: self._pend.discard(f"artist_{mbid}")
