import time, threading, hashlib
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt6.QtCore import QThread, pyqtSignal
from core.utils import AUDIO_EXT, UNKNOWN, extract_tags, canonical_artist, should_auto_blacklist, translate_if_needed, album_lyrics_status, compute_hash, get_duration, HashSidecar, Notifier, PausableMixin

class ScannerThread(QThread, PausableMixin):
    progress       = pyqtSignal(int,int,int,int,float,str)
    result_ready   = pyqtSignal(dict)
    hash_progress  = pyqtSignal(int,int)
    hash_result    = pyqtSignal(dict,list,list)
    auto_bl        = pyqtSignal(list)
    status_message = pyqtSignal(str)

    def __init__(self, folders, ds):
        super().__init__()
        self._init_pause()
        self.folders=folders; self.ds=ds
        self._done=0; self._lk=threading.Lock(); self._start=0.0

    def run(self):
        self._start=time.monotonic()
        self.status_message.emit("Collecting audio files…")
        all_files=[]
        for folder in self.folders:
            try:
                all_files.extend(p for p in Path(folder).rglob("*")
                                 if p.is_file() and p.suffix.lower() in AUDIO_EXT
                                 and not p.name.startswith("."))
            except Exception as e:
                self.status_message.emit(f"Error in {folder}: {e}")
        total=len(all_files)
        if not total:
            self.status_message.emit("No audio files found.")
            self.result_ready.emit({}); return

        workers=max(1,self.ds.settings.get("scan_workers",4))
        name_map:dict={}
        album_files:dict=defaultdict(list)
        album_data:dict={}
        lib_lk=threading.Lock()
        art_set:set=set(); alb_set:set=set()

        def scan_one(fp:Path):
            if self._stop_flag: return None
            self._pause_evt.wait()
            return extract_tags(fp)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures={pool.submit(scan_one,fp):fp for fp in all_files}
            for fut in as_completed(futures):
                if self._stop_flag:
                    for f in futures: f.cancel()
                    break
                try: tags=fut.result()
                except Exception: tags=None
                with self._lk:
                    self._done+=1; done=self._done
                if tags:
                    raw_a=tags["artist"]; low_a=raw_a.lower()
                    album=tags["album"]; year=tags["year"]
                    genre=tags.get("genre","")
                    mbid=tags.get("mbid","") # NEW: Extract MBID here
                    with lib_lk:
                        name_map[low_a]=(canonical_artist(name_map[low_a],raw_a)
                                         if low_a in name_map else raw_a)
                        key=(low_a,album.lower())
                        album_files[key].append(str(futures[fut]))
                        if key not in album_data:
                            album_data[key]=(album,year,genre,mbid) # Store MBID
                        elif genre and not album_data[key][2]:
                            album_data[key]=(album,year,genre,mbid)
                        elif mbid and not album_data[key][3]:
                            album_data[key]=(album,year,genre,mbid)
                        art_set.add(low_a); alb_set.add(key)
                elapsed=max(0.001,time.monotonic()-self._start)
                self.progress.emit(done,total,len(art_set),len(alb_set),
                                   done/elapsed,futures[fut].name[:40])

        if not self._stop_flag:
            e=max(0.001,time.monotonic()-self._start)
            self.progress.emit(total,total,len(art_set),len(alb_set),total/e,"")

        library:dict=defaultdict(list)
        for (low_a,alb_low),(disp_alb,year,genre,mbid) in album_data.items(): # Pull MBID out here
            canonical=name_map.get(low_a,low_a)
            files=album_files[(low_a,alb_low)]
            lyr=album_lyrics_status(files)
            if self.ds.settings.get("translate_titles"):
                disp_alb=translate_if_needed(disp_alb)
            library[canonical].append({
                "album":disp_alb,"year":year,"type":"","mbid":mbid, # Use the MBID variable
                "genre":genre,"files":files,"lyr_status":lyr,
            })

        if self._stop_flag:
            self.status_message.emit("Scan stopped.")
            self.result_ready.emit(dict(library)); return

        new_bl=[n for n in library
                if n!=UNKNOWN and should_auto_blacklist(n)
                and n not in self.ds.blacklist]
        if new_bl:
            for n in new_bl: self.ds.blacklist.add(n)
            self.ds.save_lists(); self.auto_bl.emit(new_bl)

        self.ds.library=dict(library); self.ds.save_library()
        self.result_ready.emit(dict(library))

        if self.ds.settings.get("hash_enabled"):
            self._run_hashing(all_files,dict(library))

        elapsed_total = time.monotonic() - self._start
        fps_final = total / max(elapsed_total, 0.001)
        self.ds.le.record_scan(self.ds.settings.get('scan_workers', 4), fps_final)
        self.ds.le.save()

        self.status_message.emit(
            f"Scan complete — {total:,} files · {len(art_set):,} artists · "
            f"{len(alb_set):,} albums · {time.strftime('%H:%M:%S', time.gmtime(elapsed_total))} elapsed.")
        Notifier.notify("MusicWatcher",
                        f"Scan complete: {len(art_set):,} artists, "
                        f"{len(alb_set):,} albums")

        cands = self.ds.le.suggest_blacklist(
            [a for a in library if a not in self.ds.blacklist])
        if cands:
            self.auto_bl.emit(cands[:20])

    def _run_hashing(self, all_files, library):
        self.status_message.emit("Hashing audio files…")
        audio_only=self.ds.settings.get("hash_audio_only",True)
        hash_map:dict=defaultdict(list)
        changed:list=[]; rows:list=[]
        workers=max(2,self.ds.settings.get("scan_workers",4)//2)

        path_type:dict={}
        for releases in library.values():
            for r in releases:
                is_single=(r.get("type","")=="Single")
                for p in r.get("files",[]):
                    path_type[p]=("Single" if is_single else "Album")

        def hash_one(fp):
            if self._stop_flag: return None
            self._pause_evt.wait()
            if HashSidecar.is_current(fp):
                h,dur=HashSidecar.read(fp)
                if h: return fp,h,dur or 0.0,"cached"
            old_h,_=HashSidecar.read(fp)
            h=compute_hash(fp,audio_only); dur=get_duration(fp)
            if h:
                HashSidecar.write(fp,h,dur)
                return fp,h,dur,"changed" if(old_h and old_h!=h) else "ok"
            return None

        done=0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for result in pool.map(hash_one,all_files):
                if self._stop_flag: break
                done+=1; self.hash_progress.emit(done,len(all_files))
                if result:
                    fp,h,dur,status=result
                    hash_map[h].append(str(fp))
                    if status=="changed": changed.append(str(fp))
                    rows.append({"path":str(fp),"hash":h,
                                 "duration_sec":f"{dur:.1f}","status":status,
                                 "is_single":path_type.get(str(fp),"Unknown")})

        dups={h:ps for h,ps in hash_map.items() if len(ps)>1}
        for row in rows:
            if row["hash"] in dups: row["status"]="duplicate"
        self.ds.save_hashes(rows)
        self.hash_result.emit(dups,changed,rows)
