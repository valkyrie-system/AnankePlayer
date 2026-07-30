import sys, os, re, time, json, hashlib, threading, unicodedata, mmap
from pathlib import Path
from collections import defaultdict
import requests

try:
    from mutagen import File as MutagenFile
except ImportError:
    print("ERROR: pip install mutagen"); sys.exit(1)

try:
    from deep_translator import GoogleTranslator; HAS_TRANSLATE = True
except ImportError:
    HAS_TRANSLATE = False

APP_NAME = "MusicWatcher"
ORG_NAME = "MusicWatcher"
DATA_DIR = Path.home() / ".musicwatcher"
ART_DIR  = DATA_DIR / "artwork"
AUDIO_EXT = {".mp3",".flac",".ogg",".opus",".m4a",".aac",".mp4",".wma",".wav",".aif",".aiff"}
SIDECAR_EXT = ".mwhash"
UNKNOWN = "Unknown"
MB_BASE = "https://musicbrainz.org/ws/2"
LB_BASE = "https://api.listenbrainz.org/1"
LRCLIB_BASE = "https://lrclib.net/api"
CAA_BASE = "https://coverartarchive.org"
LASTFM_BASE = "https://ws.audioscrobbler.com/2.0"
MB_RATE_DELAY = 1.15
MB_CACHE_TTL = 7 * 86400
STAR_THRESH = [5_000_000, 1_000_000, 200_000, 50_000, 0]

BAD_SECONDARY = {"Compilation","Live","Remix","Soundtrack","Demo","Mixtape/Street","Interview","Spokenword","Tribute"}
AUTO_BL_PATTERNS = [
    re.compile(r'^.+\s+(?:ft\.?|feat\.?|featuring)\s+\S.+$', re.IGNORECASE),
    re.compile(r'^(?:unknown|various\s*artists?|va|v\.a\.|various|assorted|soundtrack|ost|original\s+soundtrack)$', re.IGNORECASE),
]
TITLE_FEAT_RE = re.compile(r'\bfeat(?:uring|\.?)\.?\s+\S', re.IGNORECASE)
AUTO_BL_PUBLISHERS = {
    "nintendo", "game freak", "game chops", "soundcloud", "sega", "square enix",
    "squaresoft", "konami", "capcom", "namco", "bandai", "activision", "ubisoft",
    "game music", "video game music", "anime song", "anime soundtrack", "ost official",
}

LYR_SYNCED = "🎵"; LYR_PLAIN = "📝"; LYR_NONE = "❌"; LYR_MIXED = "🎵📝"
GEO_COUNTRIES = [
    "United States","Canada","Brazil","Mexico","Argentina","Chile","Colombia","United Kingdom",
    "Germany","France","Sweden","Netherlands","Norway","Denmark","Finland","Spain","Italy",
    "Poland","Belgium","Austria","Switzerland","Portugal","Czech Republic","Hungary","Romania",
    "Greece","Ukraine","Japan","South Korea","Australia","China","India","Taiwan","Thailand",
    "Philippines","Indonesia","Singapore","New Zealand","Hong Kong",
    "Turkey","Israel","South Africa","Egypt","Nigeria","Russia","Iceland",
]

_mb_lock     = threading.Lock()
_mb_last_req = 0.0

# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def mb_get(path: str, params: dict, timeout: int = 14) -> dict:
    global _mb_last_req
    with _mb_lock:
        wait = MB_RATE_DELAY - (time.monotonic() - _mb_last_req)
        if wait > 0: time.sleep(wait)
        _mb_last_req = time.monotonic()
    params["fmt"] = "json"
    r = requests.get(f"{MB_BASE}/{path}", params=params,
                     headers={"User-Agent": "MusicWatcher/5.1"}, timeout=timeout)
    r.raise_for_status()
    return r.json()

def should_auto_blacklist(name: str) -> bool:
    low = name.lower().strip()
    if low in AUTO_BL_PUBLISHERS: return True
    return any(p.search(name) for p in AUTO_BL_PATTERNS)

def normalise(s: str) -> str:
    return re.sub(r'\s+', ' ', s.strip())

def canonical_artist(a: str, b: str) -> str:
    def score(s):
        w = s.split()
        return sum(1 for x in w if x and x[0].isupper()) / max(len(w), 1)
    return a if score(a) >= score(b) else b

def sort_key(name: str) -> tuple:
    s = name.strip().lstrip("\"'★ ")
    if not s: return (3, "", name)
    c = s[0]
    if c.isdigit(): return (0, s.lower(), name)
    try: script = unicodedata.name(c).split()[0]
    except Exception: script = "UNKNOWN"
    return (1 if script == "LATIN" else 2, s.lower(), name)

def fmt_n(n) -> str:
    if n is None: return "—"
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n/1_000:.1f}K"
    return str(n)

def stars(n) -> str:
    if n is None: return "☆☆☆☆☆"
    for i, t in enumerate(STAR_THRESH):
        if n >= t:
            f = 5 - i
            return "★"*f + "☆"*(5-f)
    return "☆☆☆☆☆"

def fmt_dur(secs: float) -> str:
    secs = int(secs); h,r = divmod(secs,3600); m,s = divmod(r,60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def elapsed_s(start: float) -> str:
    return fmt_dur(time.monotonic() - start)

def translate_if_needed(text: str, target: str = "en") -> str:
    if not HAS_TRANSLATE or not text: return text
    try:
        if all(unicodedata.name(c, "").split()[0] == "LATIN" or not c.isalpha()
               for c in text if c.strip()):
            return text
        return GoogleTranslator(source="auto", target=target).translate(text) or text
    except Exception:
        return text

def lyrics_status(fp: Path) -> str:
    lrc = fp.with_suffix(".lrc")
    txt = fp.with_suffix(".txt")
    if lrc.exists(): return "synced"
    if txt.exists(): return "plain"
    return "none"

def lyrics_emoji(status: str) -> str:
    return {
        "synced": LYR_SYNCED,
        "plain":  LYR_PLAIN,
        "mixed":  LYR_MIXED,
        "none":   LYR_NONE,
    }.get(status, LYR_NONE)

def album_lyrics_status(file_paths: list) -> str:
    statuses = [lyrics_status(Path(p)) for p in file_paths if p]
    if not statuses: return "none"
    has_synced = any(s == "synced" for s in statuses)
    has_plain  = any(s == "plain"  for s in statuses)
    has_none   = any(s == "none"   for s in statuses)
    if has_synced and not has_plain and not has_none: return "synced"
    if (has_synced or has_plain) and has_none: return "mixed"
    if has_plain and not has_synced: return "plain"
    return "none"

# ─────────────────────────────────────────────────────────────────────────────
# Hash sidecar
# ─────────────────────────────────────────────────────────────────────────────

class HashSidecar:
    @staticmethod
    def path(ap: Path) -> Path:
        return ap.with_suffix(ap.suffix + SIDECAR_EXT)

    @staticmethod
    def read(ap: Path):
        try:
            parts = HashSidecar.path(ap).read_text().strip().split()
            return parts[0] if parts else None, \
                   float(parts[1]) if len(parts)>1 else None
        except Exception:
            return None, None

    @staticmethod
    def write(ap: Path, h: str, dur: float):
        try: HashSidecar.path(ap).write_text(f"{h} {dur:.2f}\n")
        except Exception: pass

    @staticmethod
    def is_current(ap: Path) -> bool:
        try:
            sp = HashSidecar.path(ap)
            return sp.exists() and sp.stat().st_mtime >= ap.stat().st_mtime
        except Exception:
            return False

def audio_offset(fp: Path) -> int:
    ext = fp.suffix.lower()
    try:
        with open(fp,"rb") as f: hdr = f.read(12)
        if ext==".mp3" and hdr[:3]==b"ID3" and len(hdr)>=10:
            return ((hdr[6]&0x7f)<<21|(hdr[7]&0x7f)<<14|
                    (hdr[8]&0x7f)<<7|(hdr[9]&0x7f))+10
        if ext==".flac" and hdr[:4]==b"fLaC":
            with open(fp,"rb") as f:
                f.seek(4)
                while True:
                    bh=f.read(4)
                    if len(bh)<4: break
                    is_last=bool(bh[0]&0x80); blen=(bh[1]<<16)|(bh[2]<<8)|bh[3]
                    if is_last: return f.tell()+blen
                    f.seek(blen,1)
        if ext in (".ogg",".opus"): return 4096
    except Exception: pass
    return 0

def compute_hash(fp: Path, audio_only: bool = True) -> str | None:
    h = hashlib.sha256()
    try:
        off = audio_offset(fp) if audio_only else 0
        size = fp.stat().st_size
        if size == 0: return None

        with open(fp, "rb") as f:
            if off: f.seek(off)
            if off < size and size - off > 65536:
                try:
                    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
                    if off: mm.seek(off)
                    while chunk := mm.read(131072): h.update(chunk)
                    mm.close()
                    return h.hexdigest()
                except Exception:
                    pass
            while chunk := f.read(131072): h.update(chunk)
        return h.hexdigest()
    except Exception: return None

def get_duration(fp: Path) -> float:
    try:
        a = MutagenFile(fp)
        if a and hasattr(a,"info") and hasattr(a.info,"length"):
            return float(a.info.length)
    except Exception: pass
    return 0.0

def extract_tags(fp: Path) -> dict | None:
    try: audio = MutagenFile(fp, easy=True)
    except Exception: return None
    if audio is None: return None

    def get(*keys):
        for k in keys:
            try:
                v = audio.get(k)
                if v:
                    s = normalise(str(v[0]))
                    if s: return s
            except Exception: pass
        return None

    artist  = get("albumartist","album_artist","artist") or UNKNOWN
    album   = get("album") or UNKNOWN
    title   = get("title") or fp.stem
    year_r  = get("date","year","originaldate")
    year    = year_r[:4] if year_r and len(year_r)>=4 else (year_r or UNKNOWN)
    genre   = get("genre") or ""
    return {"artist":artist,"album":album,"title":title,
            "year":year,"genre":genre,"duration":get_duration(fp),"path":str(fp)}

def check_squid_health(ds):
    def _check():
        _SQUID_STATUS = {"qobuz": True, "tidal": True}
        for svc,url in [("qobuz","https://qobuz.squid.wtf"),("tidal","https://tidal.squid.wtf")]:
            try:
                r=requests.get(url,timeout=5, headers={"User-Agent":"MusicWatcher/5.1"})
                _SQUID_STATUS[svc]=r.status_code<500
            except Exception:
                _SQUID_STATUS[svc]=False
        ds.settings["squid_fallback"]=("https://lucida.to" if not (_SQUID_STATUS["qobuz"] and _SQUID_STATUS["tidal"]) else "")
    threading.Thread(target=_check,daemon=True).start()

try:
    from plyer import notification as plyer_notify; HAS_PLYER = True
except ImportError:
    HAS_PLYER = False

class Notifier:
    @staticmethod
    def notify(title: str, message: str):
        from PyQt6.QtWidgets import QApplication
        QApplication.beep()
        if HAS_PLYER:
            try:
                plyer_notify.notify(title=title, message=message,
                                    app_name=APP_NAME, timeout=6); return
            except Exception: pass
        import subprocess, sys
        if sys.platform.startswith("linux"):
            try:
                subprocess.Popen(["notify-send","-a",APP_NAME,
                                  "-i","audio-headphones",title,message])
            except Exception: pass
        elif sys.platform == "win32":
            try:
                from win10toast import ToastNotifier
                ToastNotifier().show_toast(title, message, threaded=True)
            except Exception: pass

class PausableMixin:
    def _init_pause(self):
        self._pause_evt=threading.Event(); self._pause_evt.set()
        self._stop_flag=False
    def pause(self):  self._pause_evt.clear()
    def resume(self): self._pause_evt.set()
    def stop(self):   self._stop_flag=True; self._pause_evt.set()
    def _wait(self) -> bool:
        self._pause_evt.wait(); return not self._stop_flag
