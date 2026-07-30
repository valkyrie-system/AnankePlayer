import json, time, re
from pathlib import Path
from core.utils import DATA_DIR

class LearningEngine:
    """
    Lightweight self-improving model stored in ~/.musicwatcher/learning/model.json
    """
    LEARN_DIR  = DATA_DIR / "learning"
    MODEL_FILE = DATA_DIR / "learning" / "model.json"

    _DEFAULTS: dict = {
        "bl_patterns":  {},
        "bl_suffixes":  {},
        "bl_history":   [],
        "rt_clicks":    {"Album": 0, "EP": 0, "Single": 0},
        "rt_searches":  {"Album": 0, "EP": 0, "Single": 0},
        "dup_kept_album":  0,
        "dup_kept_single": 0,
        "dup_kept_ep":     0,
        "lb_has_data":   0.5,
        "lfm_has_data":  0.5,
        "pop_blend_w":   0.5,
        "max_listeners": 0,
        "lrc_attempts":  {"get": 0, "search": 0},
        "lrc_successes": {"get": 0, "search": 0},
        "perf_history":  [],
        "best_workers":  None,
        "scan_count":    0,
        "version": 1,
    }

    def __init__(self):
        self.LEARN_DIR.mkdir(parents=True, exist_ok=True)
        self._m = {k: (v.copy() if isinstance(v, dict) else
                       list(v)  if isinstance(v, list) else v)
                   for k, v in self._DEFAULTS.items()}
        self._load()

    def _load(self):
        try:
            if self.MODEL_FILE.exists():
                data = json.loads(self.MODEL_FILE.read_text())
                for k, v in data.items():
                    if k not in self._m: continue
                    if isinstance(self._m[k], dict) and isinstance(v, dict):
                        self._m[k].update(v)
                    else:
                        self._m[k] = v
        except Exception: pass

    def save(self):
        try: self.MODEL_FILE.write_text(json.dumps(self._m, indent=2))
        except Exception: pass

    def learn_blacklist(self, artist: str):
        words = re.findall(r"[a-z]{3,}", artist.lower())
        for w in words:
            self._m["bl_patterns"][w] = self._m["bl_patterns"].get(w, 0) + 1
        if words:
            last = words[-1]
            self._m["bl_suffixes"][last] = self._m["bl_suffixes"].get(last, 0) + 1
        hist = self._m["bl_history"]
        hist.append({"artist": artist, "ts": time.time()})
        self._m["bl_history"] = hist[-500:]

    def suggest_blacklist(self, candidates: list) -> list:
        strong = {p for p, c in self._m["bl_patterns"].items() if c >= 3}
        strong_sfx = {s for s, c in self._m["bl_suffixes"].items() if c >= 3}
        if not strong and not strong_sfx: return []
        out = []
        for artist in candidates:
            words = set(re.findall(r"[a-z]{3,}", artist.lower()))
            score = (sum(self._m["bl_patterns"].get(w, 0) for w in words & strong) +
                     sum(self._m["bl_suffixes"].get(w, 0) for w in words & strong_sfx))
            if score > 0: out.append((artist, score))
        return [a for a, _ in sorted(out, key=lambda x: -x[1])]

    def record_release_action(self, release_type: str, action: str = "search"):
        key = "rt_searches" if action == "search" else "rt_clicks"
        self._m[key][release_type] = self._m[key].get(release_type, 0) + 1

    def release_sort_key(self, release_type: str) -> float:
        clicks   = self._m["rt_clicks"]
        searches = self._m["rt_searches"]
        total_ev = sum(clicks.values()) + sum(searches.values())
        if total_ev < 10:
            return {"Album": 0.0, "EP": 0.5, "Single": 1.0}.get(release_type, 0.5)
        score = clicks.get(release_type, 0) * 2 + searches.get(release_type, 0)
        max_s = max(clicks.get(t, 0) * 2 + searches.get(t, 0) for t in ["Album", "EP", "Single"]) or 1
        return 1.0 - (score / max_s)

    def record_dup_decision(self, deleted_type: str, kept_type: str):
        if deleted_type == "Single" and kept_type in ("Album", "EP"):
            self._m["dup_kept_album"] += 1
        elif deleted_type in ("Album", "EP") and kept_type == "Single":
            self._m["dup_kept_single"] += 1
        elif deleted_type == "Single" and kept_type == "EP":
            self._m["dup_kept_ep"] += 1

    def should_auto_check_single(self) -> bool:
        ka = self._m["dup_kept_album"]
        ks = self._m["dup_kept_single"]
        if ka + ks < 5: return True
        return ka >= ks

    def auto_check_confidence(self) -> float:
        ka = self._m["dup_kept_album"]
        total = ka + self._m["dup_kept_single"]
        return ka / total if total else 0.8

    def update_max_listeners(self, n: int):
        if n > self._m["max_listeners"]: self._m["max_listeners"] = n

    def normalise(self, n) -> float:
        if n is None or n <= 0: return 0.0
        mx = self._m["max_listeners"] or 1
        return min(1.0, n / mx)

    def blend(self, lb: int, lfm: int) -> int:
        w = self._m["pop_blend_w"]
        return int(lb * (1.0 - w) + lfm * w)

    def record_source_hit(self, source: str, had_data: bool):
        alpha = 0.08
        key   = "lb_has_data" if source == "lb" else "lfm_has_data"
        self._m[key] = self._m[key] * (1 - alpha) + (1.0 if had_data else 0.0) * alpha
        lb_acc  = self._m["lb_has_data"]  or 0.5
        lfm_acc = self._m["lfm_has_data"] or 0.5
        total   = lb_acc + lfm_acc
        self._m["pop_blend_w"] = lfm_acc / total if total else 0.5

    def record_lyrics(self, source: str, success: bool):
        self._m["lrc_attempts"][source]  = self._m["lrc_attempts"].get(source, 0) + 1
        if success:
            self._m["lrc_successes"][source] = self._m["lrc_successes"].get(source, 0) + 1

    def lyric_success_rate(self, source: str) -> float:
        a = self._m["lrc_attempts"].get(source, 0)
        s = self._m["lrc_successes"].get(source, 0)
        return s / a if a > 0 else 0.5

    def lyric_source_order(self) -> list:
        sources = ["get", "search"]
        return sorted(sources, key=lambda s: -self.lyric_success_rate(s))

    def record_scan(self, workers: int, fps: float):
        h = self._m["perf_history"]
        prev_best = max((e["fps"] for e in h), default=0)
        h.append({"workers": workers, "fps": fps, "ts": time.time()})
        self._m["perf_history"] = h[-30:]
        self._m["scan_count"]  += 1
        if self._m["best_workers"] is None or fps >= prev_best:
            self._m["best_workers"] = workers

    def best_worker_count(self):
        if self._m["scan_count"] >= 3: return self._m["best_workers"]
        return None

    def summary(self) -> dict:
        return {
            "scan_count":    self._m["scan_count"],
            "best_workers":  self._m["best_workers"],
            "max_listeners": self._m["max_listeners"],
            "pop_blend_w":   round(self._m["pop_blend_w"], 3),
            "lrc_get_rate":  round(self.lyric_success_rate("get"), 3),
            "lrc_srch_rate": round(self.lyric_success_rate("search"), 3),
            "bl_patterns":   len(self._m["bl_patterns"]),
            "auto_chk_conf": round(self.auto_check_confidence(), 2),
        }
