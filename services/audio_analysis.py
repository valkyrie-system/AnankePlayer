import time
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from core.utils import Notifier, PausableMixin, MutagenFile

try:
    import librosa
    import numpy as np
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False

MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
PITCH_CLASSES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

def estimate_mood(y, sr) -> str:
    rms = librosa.feature.rms(y=y).mean()
    cent = librosa.feature.spectral_centroid(y=y, sr=sr).mean()
    zcr = librosa.feature.zero_crossing_rate(y).mean()
    if rms > 0.08 and cent > 3000 and zcr > 0.15: return "Angry"
    elif rms > 0.05 and cent > 2000: return "Energetic"
    elif rms < 0.03 and cent < 2000: return "Acoustic"
    elif rms < 0.05: return "Chill"
    else: return "Dark"

def detect_fake_flac(file_path: str) -> bool:
    """Analyzes spectral rolloff. Lossy transcodes usually cut off below 18kHz."""
    if not file_path.lower().endswith('.flac'): return False
    try:
        # sr=None preserves the native sample rate (crucial for high-freq detection)
        y, sr = librosa.load(file_path, sr=None, mono=True, duration=30.0)
        # 0.99 rolloff finds the frequency below which 99% of the audio energy lies
        rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.99)[0]
        max_freq = rolloff.mean()
        # True lossless 44.1kHz audio easily goes above 20kHz.
        # MP3 320 cuts off around 20kHz, MP3 192/128 cuts off around 16-18kHz.
        return max_freq < 18000
    except Exception:
        return False

def analyze_track(file_path: str) -> tuple:
    if not HAS_LIBROSA: return None, None, None
    try:
        y, sr = librosa.load(file_path, sr=22050, mono=True, duration=30.0)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(tempo) if not isinstance(tempo, np.ndarray) else float(tempo[0])

        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_mean = np.mean(chroma, axis=1)

        best_score = -np.inf
        best_key = "Unknown"
        for i in range(12):
            major_corr = np.correlate(chroma_mean, np.roll(MAJOR_PROFILE, i))
            minor_corr = np.correlate(chroma_mean, np.roll(MINOR_PROFILE, i))
            if major_corr > best_score:
                best_score = major_corr
                best_key = f"{PITCH_CLASSES[i]} Major"
            if minor_corr > best_score:
                best_score = minor_corr
                best_key = f"{PITCH_CLASSES[i]} Minor"

        mood = estimate_mood(y, sr)
        return int(round(bpm)), best_key, mood
    except Exception:
        return None, None, None

class AudioAnalysisThread(QThread, PausableMixin):
    progress = pyqtSignal(int, int, str)
    status_message = pyqtSignal(str)
    finished_all = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, ds):
        super().__init__()
        self._init_pause()
        self.ds = ds

    def run(self):
        if not HAS_LIBROSA:
            self.error.emit("librosa is not installed. Please run: pip install librosa")
            return

        releases_to_analyze = []
        for artist, rels in self.ds.library.items():
            for r in rels:
                if r.get("files") and not r.get("bpm"):
                    releases_to_analyze.append((artist, r.get("album", ""), r["files"][0]))

        total = len(releases_to_analyze)
        if total == 0:
            self.status_message.emit("No new releases to analyze.")
            self.finished_all.emit()
            return

        self.status_message.emit(f"Analyzing audio features for {total} releases...")
        done = 0
        c = self.ds.db.cursor()

        for artist, album, file_path in releases_to_analyze:
            if not self._wait(): break

            bpm, key, mood = analyze_track(file_path)
            is_fake = detect_fake_flac(file_path) # Run the Fake FLAC check!

            if bpm and key and mood:
                c.execute("UPDATE releases SET bpm=?, key=?, mood=?, is_fake_flac=? WHERE artist=? AND album=?",
                          (bpm, key, mood, is_fake, artist, album))
                self.ds.db.commit()

                # Update in-memory library
                for r in self.ds.library.get(artist, []):
                    if r.get("album") == album:
                        r["bpm"] = bpm
                        r["key"] = key
                        r["mood"] = mood
                        r["is_fake_flac"] = is_fake

                try:
                    audio = MutagenFile(file_path, easy=True)
                    if audio is not None:
                        updated = False
                        if mood:
                            audio["mood"] = mood
                            updated = True
                        if not audio.get("genre"):
                            audio["genre"] = mood
                            updated = True
                        if updated: audio.save()
                except Exception:
                    pass

            done += 1
            self.progress.emit(done, total, f"{artist} - {album}")
            time.sleep(0.05)

        self.status_message.emit(f"Audio analysis complete. {done} releases analyzed.")
        Notifier.notify("MusicWatcher", f"Audio analysis complete: {done} releases analyzed.")
        self.finished_all.emit()
