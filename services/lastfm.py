import hashlib, requests
from core.utils import LASTFM_BASE

class LastFMScrobbler:
    def __init__(self, ds):
        self.ds = ds

    def _sign(self, params: dict):
        secret = self.ds.settings.get("lastfm_secret", "")
        signable = {k: v for k, v in params.items() if k not in ("format", "api_sig")}
        sig_str = "".join(f"{k}{v}" for k, v in sorted(signable.items())) + secret
        return hashlib.md5(sig_str.encode()).hexdigest()

    def scrobble(self, artist: str, track: str, album: str, timestamp: int):
        sk = self.ds.settings.get("lastfm_session_key", "")
        key = self.ds.settings.get("lastfm_key", "")
        if not sk or not key: return False

        params = {
            "method": "track.scrobble", "api_key": key, "sk": sk,
            "artist": artist, "track": track, "album": album,
            "timestamp": str(timestamp), "format": "json"
        }
        params["api_sig"] = self._sign(params)

        try:
            r = requests.post(LASTFM_BASE, data=params, timeout=10)
            return r.status_code == 200
        except: return False

    def update_now_playing(self, artist: str, track: str, album: str):
        sk = self.ds.settings.get("lastfm_session_key", "")
        key = self.ds.settings.get("lastfm_key", "")
        if not sk or not key: return False

        params = {
            "method": "track.updatenowplaying", "api_key": key, "sk": sk,
            "artist": artist, "track": track, "album": album, "format": "json"
        }
        params["api_sig"] = self._sign(params)

        try:
            r = requests.post(LASTFM_BASE, data=params, timeout=10)
            return r.status_code == 200
        except: return False

class LastFM:
    def __init__(self, key: str):
        self.key = key.strip()

    def _get(self, method: str, extra: dict | None = None, raise_exc: bool = False) -> dict:
        if not self.key: return {}
        params = {"method": method, "api_key": self.key, "format": "json"}
        if extra: params.update(extra)
        try:
            r = requests.get(LASTFM_BASE, params=params, timeout=10)
            r.raise_for_status()
            d = r.json()
            if "error" in d:
                if raise_exc: raise ValueError(f"LFM {d['error']}: {d.get('message','')}")
                return {}
            return d
        except Exception:
            if raise_exc: raise
            return {}

    def test_key(self) -> tuple[bool, str]:
        try:
            self._get("chart.getTopArtists", {"limit":1}, raise_exc=True)
            return (True, "Key valid ✓")
        except Exception as e:
            return (False, str(e))

    def artist_info(self, name: str) -> dict:
        return self._get("artist.getinfo", {"artist": name}).get("artist", {})

    def artist_tags(self, name: str, limit: int = 5) -> list:
        d = self._get("artist.gettoptags", {"artist": name})
        return [t["name"] for t in d.get("toptags",{}).get("tag",[])[:limit] if isinstance(t,dict)]

    def artist_similar(self, name: str, limit: int = 5) -> list:
        d = self._get("artist.getsimilar", {"artist": name, "limit": limit})
        return [a.get("name","") for a in d.get("similarartists",{}).get("artist",[]) if a.get("name")]

    def album_info(self, artist: str, album: str) -> dict:
        return self._get("album.getinfo",{"artist":artist,"album":album}).get("album",{})

    def chart_top_artists(self, limit: int = 200) -> list:
        return self._get("chart.gettopartists",{"limit":limit}).get("artists",{}).get("artist",[])

    def geo_top_artists(self, country: str, limit: int = 100) -> list:
        return self._get("geo.gettopartists",{"country":country,"limit":limit}).get("topartists",{}).get("artist",[])

    def listeners(self, info: dict) -> int:
        try: return int(info.get("stats",{}).get("listeners",0))
        except: return 0

    def playcount(self, info: dict) -> int:
        try: return int(info.get("stats",{}).get("playcount",0))
        except: return 0
