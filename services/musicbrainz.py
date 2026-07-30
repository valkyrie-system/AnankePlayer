import time
from PyQt6.QtCore import QThread, pyqtSignal
from core.utils import mb_get, BAD_SECONDARY, TITLE_FEAT_RE, UNKNOWN, translate_if_needed, Notifier, PausableMixin

class NewReleaseChecker(QThread, PausableMixin):
    progress       = pyqtSignal(int,int,str)
    artist_done    = pyqtSignal(str,list)
    finished_all   = pyqtSignal(int)
    status_message = pyqtSignal(str)
    error          = pyqtSignal(str)

    def __init__(self, artists, ds, year_from, year_to, local_lib):
        super().__init__()
        self._init_pause()
        self.artists=artists; self.ds=ds
        self.year_from=year_from; self.year_to=year_to
        self.local_lib=local_lib

    def run(self):
        total=len(self.artists); new_total=0
        for i,artist in enumerate(self.artists,1):
            if not self._wait():
                self.status_message.emit("Check stopped."); return
            if artist in self.ds.blacklist and artist not in self.ds.whitelist:
                self.progress.emit(i,total,artist); continue
            self.progress.emit(i,total,artist)
            try:
                # Fetch ALL releases for the artist, cache the full list
                if self.ds.mb_cache_valid(artist):
                    all_releases=self.ds.mb_cache[artist].get("releases",[])
                else:
                    mbid=self._search_artist(artist)
                    if not mbid: continue
                    all_releases=self._get_releases(mbid)
                    area,urls=self._get_artist_extras(mbid)
                    self.ds.mb_cache[artist]={"mbid":mbid,"releases":all_releases,"area":area,"urls":urls,"ts":time.time()}
                    self.ds.save_mb_cache()

                local_set={e["album"].lower() for e in self.local_lib.get(artist,[]) if e.get("album") and e["album"]!=UNKNOWN}
                new=[]
                for r in all_releases:
                    if r["title"].lower() in local_set: continue
                    if TITLE_FEAT_RE.search(r["title"]): continue
                    # Filter by year AFTER caching
                    try:
                        y=int(r.get("year","0"))
                        if not(self.year_from<=y<=self.year_to): continue
                    except ValueError: pass
                    new.append(r)
                if new:
                    new_total+=len(new); self.artist_done.emit(artist,new)
            except Exception as exc:
                self.error.emit(f"'{artist}': {exc}")
        self.finished_all.emit(new_total)
        Notifier.notify("MusicWatcher",f"Release check done: {new_total} new releases found.")

    def _search_artist(self,name):
        data=mb_get("artist",{"query":f'artist:"{name}"',"limit":5})
        arts=data.get("artists",[])
        if not arts: return None
        for a in arts:
            if a.get("name","").lower()==name.lower(): return a["id"]
        return arts[0]["id"]

    def _get_releases(self,mbid):
        seen=set(); results=[]; offset,limit=0,100
        while True:
            data=mb_get("release-group",{"artist":mbid,"type":"album|single|ep","limit":limit,"offset":offset})
            for rg in data.get("release-groups",[]):
                if set(rg.get("secondary-types",[]))&BAD_SECONDARY: continue
                date_str=rg.get("first-release-date","")
                title=self._en_title(rg); year=date_str[:4] if date_str else UNKNOWN
                key=(title.lower().strip(),year)
                if key in seen: continue
                seen.add(key)
                results.append({"title":title,"year":year,"type":rg.get("primary-type",""),"mbid":rg.get("id","")})
            offset+=limit
            if offset>=data.get("release-group-count",0): break
        return results

    def _en_title(self,rg):
        for alias in rg.get("aliases",[]):
            if alias.get("locale","").startswith("en"):
                t=alias.get("name","")
                if t: return t
        title=rg.get("title",UNKNOWN)
        if self.ds.settings.get("translate_titles"):
            title=translate_if_needed(title)
        return title

    def _get_artist_extras(self, mbid: str) -> tuple:
        try:
            data = mb_get(f"artist/{mbid}", {"inc": "url-rels"})
            a_d  = data.get("area") or data.get("begin-area") or {}
            area = a_d.get("name","") if isinstance(a_d, dict) else ""
            urls: dict = {}
            for rel in data.get("relations", []):
                rtype = rel.get("type","")
                url   = rel.get("url", {}).get("resource","")
                if url and rtype: urls[rtype] = url
            return area, urls
        except Exception:
            return "", {}
