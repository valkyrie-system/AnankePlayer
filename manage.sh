#!/bin/bash
# MusicWatcher Unified Management Script

APP_NAME="MusicWatcher"
INSTALL_DIR="/opt/$APP_NAME"
BIN_LINK="/usr/local/bin/musicwatcher"
MANAGE_LINK="/usr/local/bin/musicwatcher-manage"
DESKTOP_FILE="/usr/share/applications/musicwatcher.desktop"
ICON_DIR="/usr/share/icons/hicolor/256x256/apps"

# Function to print the menu
show_menu() {
    clear
    echo "========================================"
    echo "  🎵 MusicWatcher Management Script"
    echo "========================================"
    echo "  1. 🚀 Install MusicWatcher (System-wide)"
    echo "  2. 🔄 Update MusicWatcher (System-wide)"
    echo "  3. 🧹 Uninstall MusicWatcher (System-wide)"
    echo "  4. 🛠️  Build Release (Developers Only)"
    echo "  5. Exit"
    echo "========================================"
}

# Function to check for root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo "❌ Error: This option requires root privileges."
        echo "   Please run this script as root: sudo bash manage.sh"
        echo ""
        read -p "Press Enter to return to the menu..."
        return 1
    fi
    return 0
}

# 1. Install Function
do_install() {
    check_root || return

    if [ ! -f "./$APP_NAME" ]; then
        echo "❌ Error: $APP_NAME executable not found in the current directory."
        echo "   Please run this script inside the extracted $APP_NAME folder."
        read -p "Press Enter to return to the menu..."
        return
    fi

    echo "========================================"
    echo "  🚀 Installing $APP_NAME to System"
    echo "========================================"

    echo -e "\n📁 1. Copying files to $INSTALL_DIR..."
    rm -rf "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
    cp -r ./* "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/$APP_NAME"

    if [ -f "$INSTALL_DIR/manage.sh" ]; then
        chmod +x "$INSTALL_DIR/manage.sh"
    fi

    echo -e "\n🔗 2. Creating executable links..."
    rm -f "$BIN_LINK"
    ln -s "$INSTALL_DIR/$APP_NAME" "$BIN_LINK"

    rm -f "$MANAGE_LINK"
    if [ -f "$INSTALL_DIR/manage.sh" ]; then
        ln -s "$INSTALL_DIR/manage.sh" "$MANAGE_LINK"
        echo "   -> Created 'musicwatcher-manage' command."
    fi

    echo -e "\n🎨 3. Installing icon..."
    mkdir -p "$ICON_DIR"
    if [ -f "./musicwatcher.png" ]; then
        cp "./musicwatcher.png" "$ICON_DIR/musicwatcher.png"
    elif [ -f "$INSTALL_DIR/musicwatcher.png" ]; then
        cp "$INSTALL_DIR/musicwatcher.png" "$ICON_DIR/musicwatcher.png"
    else
        echo "   ⚠️ Warning: musicwatcher.png not found. App will use a default system icon."
    fi

    echo -e "\n⚙️ 4. Creating application menu entry..."
    cat <<EOF > "$DESKTOP_FILE"
[Desktop Entry]
Name=MusicWatcher
Exec=musicwatcher
Icon=musicwatcher
Terminal=false
Type=Application
Categories=AudioVideo;Audio;
EOF

    echo -e "\n🔄 5. Updating system desktop database..."
    update-desktop-database -q 2>/dev/null || true

    echo -e "\n========================================"
    echo "  ✅ INSTALLATION COMPLETE!"
    echo "========================================"
    echo "You can now launch MusicWatcher from your application menu."
    echo "Or, run it from any terminal by typing: musicwatcher"
    echo "To manage the installation, type: sudo musicwatcher-manage"
    echo ""
    read -p "Press Enter to return to the menu..."
}

# 2. Update Function
do_update() {
    check_root || return

    if [ ! -f "./$APP_NAME" ]; then
        echo "❌ Error: $APP_NAME executable not found in the current directory."
        echo "   Please run this script inside the newly extracted $APP_NAME folder."
        read -p "Press Enter to return to the menu..."
        return
    fi

    if [ ! -d "$INSTALL_DIR" ]; then
        echo "❌ Error: MusicWatcher is not installed on this system."
        echo "   Please run Option 1 (Install) first."
        read -p "Press Enter to return to the menu..."
        return
    fi

    if [ "$(pwd)" == "$INSTALL_DIR" ]; then
        echo "❌ Error: Do not run this script from inside $INSTALL_DIR."
        echo "   Extract the new download to your Downloads folder and run it from there."
        read -p "Press Enter to return to the menu..."
        return
    fi

    echo "========================================"
    echo "  🔄 Updating $APP_NAME System Files"
    echo "========================================"

    echo -e "\n🧹 1. Removing old binary files..."
    rm -rf "$INSTALL_DIR"/*

    echo -e "\n📁 2. Copying new files to $INSTALL_DIR..."
    cp -r ./* "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/$APP_NAME"

    if [ -f "$INSTALL_DIR/manage.sh" ]; then
        chmod +x "$INSTALL_DIR/manage.sh"
    fi

    if [ -f "./musicwatcher.png" ]; then
        echo -e "\n🎨 3. Updating icon..."
        mkdir -p "$ICON_DIR"
        cp "./musicwatcher.png" "$ICON_DIR/musicwatcher.png"
    else
        echo -e "\n🎨 3. Skipping icon update (not found in folder)."
    fi

    echo -e "\n⚙️ 4. Verifying application menu entry..."
    cat <<EOF > "$DESKTOP_FILE"
[Desktop Entry]
Name=MusicWatcher
Exec=musicwatcher
Icon=musicwatcher
Terminal=false
Type=Application
Categories=AudioVideo;Audio;
EOF

    echo -e "\n🔄 5. Updating system desktop database..."
    update-desktop-database -q 2>/dev/null || true

    echo -e "\n========================================"
    echo "  ✅ UPDATE COMPLETE!"
    echo "========================================"
    echo "MusicWatcher has been successfully updated."
    echo "Your library data and settings (~/.musicwatcher) are untouched."
    echo ""
    read -p "Press Enter to return to the menu..."
}

# 3. Uninstall Function
do_uninstall() {
    check_root || return

    echo "🧹 Uninstalling MusicWatcher..."

    rm -rf "$INSTALL_DIR"
    rm -f "$BIN_LINK"
    rm -f "$MANAGE_LINK"
    rm -f "$DESKTOP_FILE"
    rm -f "$ICON_DIR/musicwatcher.png"

    update-desktop-database -q 2>/dev/null || true

    echo "✅ Uninstallation complete!"
    echo ""
    read -p "Press Enter to return to the menu..."
}

# 4. Build Function
do_build() {
    echo "========================================"
    echo "  ⚠️  DEVELOPER WARNING ⚠️"
    echo "========================================"
    echo "This build option is for development/convenience only."
    echo "It contains hardcoded paths specific to the developer's machine."
    echo "If you are an end-user, do NOT use this option."
    echo ""
    read -p "Are you sure you want to continue? (y/N): " confirm
    if [[ "$confirm" != [yY] && "$confirm" != [yY][eE][sS] ]]; then
        echo "Build cancelled."
        read -p "Press Enter to return to the menu..."
        return
    fi

    # Paths hardcoded for developer convenience
    SRC_DIR="/home/valkyrie-sys/Tools/Unfinished-Projects/musicwatcher"
    OUT_DIR="/home/valkyrie-sys/Tools/Finished Projects"
    BUILD_DIR="/home/valkyrie-sys/Tools/BuildFiles"
    SHIPPING_DIR="$OUT_DIR/Projects-Shipping"
    RELEASE_BASE_DIR="$SHIPPING_DIR/MusicWatcher-Release"
    TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
    RELEASE_DIR="$RELEASE_BASE_DIR/$TIMESTAMP"
    SPEC_FILE="musicwatcher.spec"
    APPIMAGE_TOOL="appimagetool-x86_64.AppImage"

    echo "========================================"
    echo "  🎵 Building $APP_NAME Release"
    echo "  📅 Timestamp: $TIMESTAMP"
    echo "========================================"

    cd "$SRC_DIR" || { echo "❌ Source directory not found!"; read -p "Press Enter..."; return; }

    # Robustly check for PyInstaller in system PATH and common directories
    PYINSTALLER_BIN=""
    if command -v pyinstaller &> /dev/null; then
        PYINSTALLER_BIN="pyinstaller"
    elif [ -x "/usr/bin/pyinstaller" ]; then
        PYINSTALLER_BIN="/usr/bin/pyinstaller"
    elif [ -x "/usr/local/bin/pyinstaller" ]; then
        PYINSTALLER_BIN="/usr/local/bin/pyinstaller"
    elif [ -x "$HOME/.local/bin/pyinstaller" ]; then
        PYINSTALLER_BIN="$HOME/.local/bin/pyinstaller"
    else
        echo "❌ Error: PyInstaller is not installed or not in PATH."
        echo "   Please install it via AUR (yay -S pyinstaller) or pip (pip install pyinstaller)"
        read -p "Press Enter to return to the menu..."
        return
    fi

    if [ ! -f "$APPIMAGE_TOOL" ]; then
        echo "❌ Error: $APPIMAGE_TOOL not found in $SRC_DIR."
        read -p "Press Enter to return to the menu..."
        return
    fi

    mkdir -p "$RELEASE_DIR"
    mkdir -p "$BUILD_DIR"

    echo -e "\n🧹 Cleaning up Projects-Shipping directory..."
    for item in "$SHIPPING_DIR"/*; do
        if [ "$item" == "$RELEASE_BASE_DIR" ]; then continue; fi
        if [ -e "$item" ]; then
            echo "   🚚 Moving $(basename "$item") into $RELEASE_BASE_DIR/"
            mv "$item" "$RELEASE_BASE_DIR/"
        fi
    done

    echo -e "\n🐍 1. Copying Python source files..."
    PY_DEST="$RELEASE_DIR/Musicwatcher-Python"
    rm -rf "$PY_DEST"
    mkdir -p "$PY_DEST"
    cp "main.py" "$PY_DEST/"
    cp "$SPEC_FILE" "$PY_DEST/"
    cp -r "core" "$PY_DEST/"
    cp -r "threads" "$PY_DEST/"
    cp -r "ui" "$PY_DEST/"
    cp -r "services" "$PY_DEST/"
    for f in requirements.txt README.md manage.sh MusicWatcher.png; do
        [ -f "$f" ] && cp "$f" "$PY_DEST/"
    done

    echo -e "\n📦 2. Zipping Python source code..."
    rm -f "$RELEASE_DIR/Musicwatcher-Python.zip"
    python3 -c "import shutil; shutil.make_archive('$RELEASE_DIR/Musicwatcher-Python', 'zip', '$RELEASE_DIR', 'Musicwatcher-Python')"

    echo -e "\n🛠️  3. Compiling native binary with PyInstaller..."
    "$PYINSTALLER_BIN" "$SPEC_FILE" --noconfirm

    echo -e "\n📁 4. Moving build artifacts to $BUILD_DIR..."
    if [ -d "build" ]; then
        rm -rf "$BUILD_DIR/build"
        mv build "$BUILD_DIR/"
    fi

    echo -e "\n🚚 5. Moving native binary to $RELEASE_DIR..."
    BIN_DEST="$RELEASE_DIR/MusicWatcher"
    rm -rf "$BIN_DEST"
    mv "dist/$APP_NAME" "$BIN_DEST"
    rm -rf dist

    echo -e "\n📜 6. Copying manage.sh to binary folder..."
    # Only copy manage.sh, no longer copying install.sh, uninstall.sh, or update.sh
    if [ -f "manage.sh" ]; then
        cp "manage.sh" "$BIN_DEST/"
        chmod +x "$BIN_DEST/manage.sh"
    else
        echo "   ⚠️ Warning: manage.sh not found in $SRC_DIR."
    fi

    echo -e "\n📦 7. Zipping native binary..."
    rm -f "$RELEASE_DIR/MusicWatcher-linux.zip"
    python3 -c "import shutil; shutil.make_archive('$RELEASE_DIR/MusicWatcher-linux', 'zip', '$RELEASE_DIR', 'MusicWatcher')"

    echo -e "\n🚀 8. Generating final AppImage in $RELEASE_DIR..."
    APPDIR="$SRC_DIR/MusicWatcher.AppDir"
    rm -rf "$APPDIR"
    mkdir -p "$APPDIR/usr/bin"
    mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
    cp -r "$BIN_DEST/"* "$APPDIR/usr/bin/"

    if [ -f "resources/$APP_NAME.png" ]; then
        cp "resources/$APP_NAME.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/musicwatcher.png"
        cp "resources/$APP_NAME.png" "$APPDIR/musicwatcher.png"
    elif [ -f "$APP_NAME.png" ]; then
        cp "$APP_NAME.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/musicwatcher.png"
        cp "$APP_NAME.png" "$APPDIR/musicwatcher.png"
    else
        echo "   ⚠️ Warning: $APP_NAME.png not found."
    fi

    printf '[Desktop Entry]\nName=MusicWatcher\nExec=MusicWatcher\nIcon=musicwatcher\nTerminal=false\nType=Application\nCategories=AudioVideo;Audio;\n' > "$APPDIR/musicwatcher.desktop"
    printf '#!/bin/sh\nHERE="$(dirname "$(readlink -f "${0}")")"\nexec "${HERE}/usr/bin/MusicWatcher" "$@"\n' > "$APPDIR/AppRun"
    chmod +x "$APPDIR/AppRun"

    FINAL_APPIMAGE="$RELEASE_DIR/MusicWatcher.AppImage"
    rm -f "$FINAL_APPIMAGE"
    chmod +x "$APPIMAGE_TOOL"
    "./$APPIMAGE_TOOL" "$APPDIR" "$FINAL_APPIMAGE"
    chmod +x "$FINAL_APPIMAGE"

    echo -e "\n🧹 9. Cleaning up temporary files..."
    rm -rf "$APPDIR"

    echo -e "\n🗄️ 10. Pruning old releases (keeping 3 newest)..."
    # Find all timestamped directories, sort newest first, skip first 3, delete the rest
    find "$RELEASE_BASE_DIR" -maxdepth 1 -mindepth 1 -type d | sort -r | tail -n +4 | while read -r old_dir; do
        echo "   🗑️ Removing old release: $(basename "$old_dir")"
        rm -rf "$old_dir"
    done

    echo -e "\n========================================"
    echo "  ✅ RELEASE BUILD COMPLETE!"
    echo "========================================"
    echo "👉 Release Folder:    $RELEASE_DIR"
    echo "👉 Python Source Zip: $RELEASE_DIR/Musicwatcher-Python.zip"
    echo "👉 Native Binary Zip: $RELEASE_DIR/MusicWatcher-linux.zip"
    echo "👉 Portable AppImage: $RELEASE_DIR/MusicWatcher.AppImage"
    echo ""
    read -p "Press Enter to return to the menu..."
}

# Main Loop
while true; do
    show_menu
    read -p "Select an option (1-5): " choice
    case $choice in
        1) do_install ;;
        2) do_update ;;
        3) do_uninstall ;;
        4) do_build ;;
        5) echo "Goodbye!"; exit 0 ;;
        *) echo "Invalid option. Please try again."; sleep 1 ;;
    esac
done
