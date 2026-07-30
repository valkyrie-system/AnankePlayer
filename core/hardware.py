import os
import sys
import multiprocessing
import subprocess
import logging
from pathlib import Path

def setup_logging():
    log_file = Path.home() / ".musicwatcher" / "error.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_file),
        level=logging.ERROR,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

   # sys.excepthook = handle_exception

def setup_hardware_env() -> dict:
    os.environ["QT_LOGGING_RULES"] = (
        "qt.multimedia.ffmpeg=false;"
        "qt.multimedia.video=false;"
        "qt.multimedia.player=false;"
        "qt.qpa.pipewire=false;"
        "kf.*=false"
    )

    gpu_vendor = "unknown"
    gpu_name = ""
    try:
        if sys.platform.startswith("linux"):
            out = subprocess.check_output(["lspci", "-mm"], stderr=subprocess.DEVNULL, timeout=3).decode(errors="replace")
            for line in out.splitlines():
                low = line.lower()
                if "vga" in low or "3d" in low or "display" in low:
                    if "amd" in low or "radeon" in low: gpu_vendor = "amd"
                    elif "nvidia" in low: gpu_vendor = "nvidia"
                    elif "intel" in low: gpu_vendor = "intel"
                    break
        elif sys.platform == "win32":
            out = subprocess.check_output(["wmic", "path", "win32_VideoController", "get", "Name", "/value"], stderr=subprocess.DEVNULL, timeout=5).decode(errors="replace")
            for line in out.splitlines():
                if "Name=" in line:
                    name = line.split("=",1)[1].strip()
                    low = name.lower()
                    if "amd" in low or "radeon" in low: gpu_vendor, gpu_name = "amd", name
                    elif "nvidia" in low: gpu_vendor, gpu_name = "nvidia", name
                    elif "intel" in low: gpu_vendor, gpu_name = "intel", name
                    break
    except Exception:
        pass

    if gpu_vendor == "amd": os.environ.setdefault("LIBVA_DRIVER_NAME", "radeonsi")
    elif gpu_vendor == "nvidia":
        os.environ.setdefault("LIBVA_DRIVER_NAME", "nvidia")
        os.environ.setdefault("VDPAU_DRIVER", "nvidia")
    elif gpu_vendor == "intel":
        os.environ.setdefault("LIBVA_DRIVER_NAME", "iHD")
        os.environ.setdefault("VDPAU_DRIVER", "va_gl")

    cpu = multiprocessing.cpu_count() or 4
    ram = 8.0
    try:
        import psutil; ram = psutil.virtual_memory().total / (1024**3)
    except Exception: pass

    workers = min(max(4, cpu * 2), 64)
    if ram < 4: workers = min(workers, 4)
    elif ram < 8: workers = min(workers, 16)
    elif ram < 16: workers = min(workers, 32)

    if ram >= 32: lyrics_workers = 64
    elif ram >= 16: lyrics_workers = 32
    elif ram >= 8: lyrics_workers = 16
    else: lyrics_workers = 8

    return {"cpu": cpu, "ram_gb": ram, "workers": workers, "lyrics_workers": lyrics_workers, "gpu_vendor": gpu_vendor, "gpu_name": gpu_name}
