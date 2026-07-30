# musicwatcher.spec
import sys
from PyInstaller.utils.hooks import collect_all

# Collect all PyQt6 data, binaries, and hidden imports
datas, binaries, hiddenimports = collect_all('PyQt6')

# Ensure specific multimedia and DBus modules are caught
hiddenimports += [
    'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidget',
    'PyQt6.QtDBus', 'mutagen', 'requests', 'plyer'
]

# Explicitly tell PyInstaller to include our local packages
hiddenimports += [
    'core', 'core.utils', 'core.datastore', 'core.hardware', 'core.learning',
    'services', 'services.artwork', 'services.lastfm', 'services.listenbrainz', 'services.lyrics', 'services.musicbrainz', 'services.soulseek',
    'threads', 'threads.scanner', 'threads.fetchers',
    'ui', 'ui.main_window', 'ui.widgets', 'ui.dialogs'
]

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'], # <--- Added this so PyInstaller looks in the current directory
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MusicWatcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MusicWatcher',
)
