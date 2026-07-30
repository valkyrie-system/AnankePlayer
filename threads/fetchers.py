import time, requests, threading
from PyQt6.QtCore import QThread, pyqtSignal
from core.utils import mb_get, GEO_COUNTRIES, ART_DIR, CAA_BASE, PausableMixin
from services.lastfm import LastFM

class PopularityFetcher(QThread, PausableMixin):
    progress     = pyqtSignal(int,int,str)
    artist_done  = pyqtSignal(str,dict)
    finished_all = pyqtSignal()
    status_message = pyqtSignal(str)
    error          = pyqtSignal(str)

    LB_BATCH=25

    def __init__(self, artists, ds):
        super().__init__()
        self._init_pause()
        self.artists=artists; self.ds=ds

    def run(self):
        total    = len(self.artists)
        lfm_key  = self.ds.settings.get("lastfm_key", "").strip()
        lfm      = LastFM(lfm_key)
        pop_src  = self.ds.settings.get("pop_source", "both")
        use_lb   = pop_src in ("lb", "both")
        use_lfm  = pop_src in ("lfm", "both") and bool(lfm_key)

        mbid_map:   dict = {}
        need_fetch: list = []

        for i, artist in enumerate(self.artists, 1):
            if not self._wait(): return
            self.progress.emit(i, total, artist)
            if self.ds.pop_cache_valid(artist):
                self.artist_done.emit(artist, self.ds.pop_cache[artist])
                continue
            cached_mb = self.ds.mb_cache.get(artist, {})
            mbid = cached_mb.get("mbid", "")
            area = cached_mb.get("area", "")
            if not mbid and use_lb:
                self.status_message.emit(f"Resolving MusicBrainz ID for {artist}…")
                try:
                    data = mb_get("artist", {"query": f'artist:"{artist}"', "limit": 3})
                    arts = data.get("artists", [])
                    if arts:
                        best = next((a for a in arts if a.get("name","").lower() == artist.lower()), arts[0])
                        mbid = best.get("id", "")
                        if not area:
                            a_d = (best.get("area") or best.get("begin-area") or {})
                            area = (a_d.get("name","") if isinstance(a_d, dict) else "")
                except Exception: pass
            if mbid: mbid_map[artist] = (mbid, area)
            need_fetch.append(artist)

        if not need_fetch:
            self.ds.save_pop_cache(); self.ds.save_popularity()
            self.finished_all.emit(); return

        global_ranks: dict = {}
        geo_chart:    dict = {}

        if use_lfm:
            self.status_message.emit("Fetching Last.fm global chart…")
            try:
                chart = lfm.chart_top_artists(limit=200)
                global_ranks = {a.get("name","").lower(): idx for idx, a in enumerate(chart, 1) if a.get("name")}
            except Exception as e:
                self.error.emit(f"LFM global chart: {e}")

            for country in self.ds.settings.get("geo_countries", GEO_COUNTRIES[:3]):
                if not self._wait(): return
                self.status_message.emit(f"Fetching Last.fm geo: {country}…")
                try:
                    geo = lfm.geo_top_artists(country, limit=100)
                    geo_chart[country] = {a.get("name","").lower(): idx for idx, a in enumerate(geo, 1) if a.get("name")}
                except Exception as e:
                    self.error.emit(f"LFM geo {country}: {e}")
                time.sleep(0.25)

        lb_results: dict = {}
        if use_lb and mbid_map:
            inv   = {mbid_map[a][0]: a for a in need_fetch if a in mbid_map}
            mbids = list(inv.keys())
            self.status_message.emit(f"Querying ListenBrainz for {len(mbids)} artists…")
            for start in range(0, len(mbids), self.LB_BATCH):
                if not self._wait(): return
                batch = mbids[start: start + self.LB_BATCH]
                try:
                    resp = requests.post("https://api.listenbrainz.org/1/popularity/artist", json={"artist_mbids": batch},
                                         headers={"User-Agent": "MusicWatcher/5.1"}, timeout=15)
                    if resp.status_code == 404: pass
                    elif resp.ok:
                        data  = resp.json()
                        items = (data if isinstance(data, list) else data.get("payload", []))
                        for item in items:
                            m  = item.get("artist_mbid", "")
                            lc = (item.get("total_listen_count") or item.get("listeners") or item.get("listen_count") or 0)
                            a  = inv.get(m)
                            if a and isinstance(lc, int): lb_results[a] = lc
                    else:
                        self.error.emit(f"LB HTTP {resp.status_code} (batch {start//self.LB_BATCH+1})")
                except Exception as exc:
                    self.error.emit(f"LB batch error: {exc}")
                time.sleep(0.5)

        lfm_results: dict = {}; lfm_tags: dict = {}; lfm_similar: dict = {}; lfm_urls: dict = {}

        if use_lfm:
            self.status_message.emit(f"Fetching Last.fm info for {len(need_fetch)} artists…")
            for artist in need_fetch:
                if not self._wait(): return
                try:
                    info = lfm.artist_info(artist)
                    if info:
                        lfm_results[artist] = lfm.listeners(info)
                        raw_tags = (info.get("tags") or {}).get("tag", [])
                        lfm_tags[artist] = [t["name"] for t in raw_tags[:5] if isinstance(t, dict) and t.get("name")]
                        raw_sim = (info.get("similar") or {}).get("artist", [])
                        lfm_similar[artist] = [s.get("name","") for s in raw_sim[:5] if s.get("name")]
                        lfm_urls[artist] = info.get("url", "")
                except Exception: pass
                time.sleep(0.2)

        for artist in need_fetch:
            if not self._wait(): return
            mbid, area = mbid_map.get(artist, ("", ""))
            lb_l  = lb_results.get(artist, 0)
            lfm_l = lfm_results.get(artist, 0)
            rank  = global_ranks.get(artist.lower(), 0)
            geo_r = {c: geo_chart[c][artist.lower()] for c in geo_chart if artist.lower() in geo_chart[c]}

            self.ds.le.update_max_listeners(max(lb_l, lfm_l))
            self.ds.le.record_source_hit("lb",  lb_l  > 0)
            self.ds.le.record_source_hit("lfm", lfm_l > 0)
            blended = self.ds.le.blend(lb_l, lfm_l)
            normalised = round(self.ds.le.normalise(blended), 4)

            pop = {
                "listeners":     lb_l,
                "lfm_listeners": lfm_l,
                "area":          area,
                "global_rank":   rank,
                "geo_ranks":     geo_r,
                "tags":          lfm_tags.get(artist, []),
                "similar":       lfm_similar.get(artist, []),
                "lfm_url":       lfm_urls.get(artist, ""),
                "blended":       blended,
                "normalised":    normalised,
                "ts":            time.time(),
            }
            self.ds.pop_cache[artist] = pop
            self.artist_done.emit(artist, pop)

        self.ds.save_pop_cache()
        self.ds.save_popularity()
        self.finished_all.emit()

class ArtworkFetcher(QThread, PausableMixin):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal()
    status_message = pyqtSignal(str)

    def __init__(self, ds):
        super().__init__()
        self._init_pause()
        self.ds = ds

    def run(self):
        from services.artwork import ArtworkLoader
        mb_artists = list(self.ds.mb_cache.keys())
        lib_artists = list(self.ds.library.keys())
        all_artists = sorted(list(set(mb_artists + lib_artists)))

        total = len(all_artists)
        loader = ArtworkLoader.instance()
        done = 0

        for artist in all_artists:
            if not self._wait(): break
            done += 1
            self.progress.emit(done, total, artist)

            mbid = self.ds.mb_cache.get(artist, {}).get("mbid", "")
            if mbid:
                cache_file = ART_DIR / f"artist_{mbid}.jpg"
                if not cache_file.exists():
                    loader.get_artist_art(artist, mbid)
                    time.sleep(0.1)

            for r in self.ds.library.get(artist, []):
                if not self._wait(): break
                r_mbid = r.get("mbid", "")
                files = r.get("files", [])
                if r_mbid:
                    r_cache = ART_DIR / f"{r_mbid}.jpg"
                    if not r_cache.exists():
                        loader.request(r_mbid, f"{CAA_BASE}/release-group/{r_mbid}/front-250")
                        time.sleep(0.1)
                elif files:
                    import hashlib
                    cache_key = f"embed_{hashlib.md5(files[0].encode()).hexdigest()}"
                    r_cache = ART_DIR / f"{cache_key}.jpg"
                    if not r_cache.exists():
                        loader.get_embedded_art(files[0], cache_key)
                        time.sleep(0.05)

        self.finished.emit()
