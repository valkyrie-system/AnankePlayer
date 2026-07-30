#!/usr/bin/env python3
import sys
import os
import signal # <--- Add this
from PyQt6.QtWidgets import QApplication
from core.hardware import setup_hardware_env, setup_logging
from ui.main_window import MusicWatcher

def main():
    setup_logging()
    hw_info = setup_hardware_env()

    app = QApplication(sys.argv)
    app.setApplicationName("MusicWatcher")
    app.setOrganizationName("MusicWatcher")
    app.setStyle("Fusion")

    # Tell Python to use the default OS handler for Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    w = MusicWatcher(hw=hw_info)
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
