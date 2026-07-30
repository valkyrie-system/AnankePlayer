# ui/themes.py

# ─── Handcrafted Base Themes ──────────────────────────────────────────────
THEMES = {
    "Dark": "QMainWindow,QWidget{background:#1a1a2e;color:#e0e0f0;font-family:'Segoe UI','SF Pro Display',sans-serif;}"
            "QTabWidget::pane{border:none;}"
            "QTabBar::tab{background:#22223a;color:#8888bb;padding:7px 18px;border-radius:4px 4px 0 0;margin-right:2px;font-weight:600;}"
            "QTabBar::tab:selected{background:#1a1a2e;color:#d0b0ff;}"
            "QTabBar::tab:hover{background:#2a2a4a;}"
            "#folderPanel{background:#12122a;border-right:1px solid #2a2a50;padding:8px;}"
            "#panelHeader{font-size:11px;font-weight:700;letter-spacing:1px;color:#7766aa;}"
            "#folderList,#managerList{background:#1a1a38;border:1px solid #2a2a50;border-radius:5px;color:#c0c0e0;}"
            "#folderList::item,#managerList::item{padding:5px 6px;}"
            "#folderList::item:selected,#managerList::item:selected{background:#3a2a6a;color:#fff;}"
            "#addBtn{background:#2a3a2a;color:#88cc88;border:1px solid #335533;border-radius:4px;font-weight:600;}"
            "#removeBtn{background:#3a2020;color:#cc8888;border:1px solid #553333;border-radius:4px;font-weight:600;}"
            "#removeBtn:disabled{color:#555;background:#222;border-color:#333;}"
            "#primaryBtn{background:#3a2a6a;color:#d0b0ff;border:1px solid #5544aa;border-radius:5px;padding:4px 18px;font-weight:700;}"
            "#primaryBtn:disabled{color:#555580;background:#22223a;border-color:#333;}"
            "#secondaryBtn{background:#1a2a3a;color:#88bbdd;border:1px solid #2a4a66;border-radius:4px;font-weight:600;}"
            "#toolBtn{background:#22223a;color:#aabbcc;border:1px solid #333358;border-radius:4px;font-weight:600;}"
            "#pauseBtn{background:#2a2a50;color:#aabbee;border:1px solid #3a3a70;border-radius:5px;padding:2px 12px;font-weight:600;}"
            "#stopBtn{background:#3a1a1a;color:#ff8888;border:1px solid #662222;border-radius:5px;padding:2px 12px;font-weight:700;}"
            "#searchBox{background:#12122a;border:1px solid #333358;border-radius:5px;color:#e0e0f0;padding:2px 10px;}"
            "#musicTree,#newTree,#dupTree,#changedTree{background:#12122a;alternate-background-color:#1a1a38;border:1px solid #2a2a50;border-radius:6px;outline:none;}"
            "#musicTree::item:selected,#newTree::item:selected,#dupTree::item:selected,#changedTree::item:selected{background:#3a2a6a;color:#fff;}"
            "QHeaderView::section{background:#22223a;color:#8888bb;border:none;border-bottom:1px solid #333358;padding:6px 8px;font-weight:700;font-size:11px;}"
            "#bigBar{background:#22223a;border-radius:5px;}"
            "#bigBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #5533aa,stop:1 #9944cc);border-radius:5px;}"
            "QStatusBar{background:#12122a;color:#6666aa;font-size:11px;}"
            "QScrollBar:vertical{background:#12122a;width:10px;border-radius:5px;}"
            "QScrollBar::handle:vertical{background:#333368;border-radius:5px;}"
            "#artistCard{background:#1e1e3a;border:1px solid #2a2a50;border-radius:8px;}"
            "#previewPlayBtn{background:#3a2a6a;color:#d0b0ff;border:1px solid #5544aa;border-radius:18px;font-weight:700;font-size:16px;}",

    "Light": "QMainWindow,QWidget{background:#f0f0f8;color:#1a1a2e;font-family:'Segoe UI','SF Pro Display',sans-serif;}"
             "QTabWidget::pane{border:none;}"
             "QTabBar::tab{background:#dcdcec;color:#444488;padding:7px 18px;border-radius:4px 4px 0 0;margin-right:2px;font-weight:600;}"
             "QTabBar::tab:selected{background:#f0f0f8;color:#5533aa;}"
             "#folderPanel{background:#e8e8f5;border-right:1px solid #c0c0d8;padding:8px;}"
             "#folderList,#managerList{background:#fff;border:1px solid #c0c0d8;border-radius:5px;color:#1a1a2e;}"
             "#folderList::item:selected,#managerList::item:selected{background:#c8b8ff;color:#000;}"
             "#addBtn{background:#d8f0d8;color:#226622;border:1px solid #88cc88;border-radius:4px;font-weight:600;}"
             "#removeBtn{background:#f0d8d8;color:#882222;border:1px solid #cc8888;border-radius:4px;font-weight:600;}"
             "#primaryBtn{background:#5533aa;color:#fff;border:1px solid #3322aa;border-radius:5px;padding:4px 18px;font-weight:700;}"
             "#secondaryBtn{background:#d8eaf8;color:#224466;border:1px solid #88aacc;border-radius:4px;font-weight:600;}"
             "#toolBtn{background:#e0e0ee;color:#333366;border:1px solid #aaaacc;border-radius:4px;font-weight:600;}"
             "#searchBox{background:#fff;border:1px solid #c0c0d8;border-radius:5px;color:#1a1a2e;padding:2px 10px;}"
             "#musicTree,#newTree,#dupTree,#changedTree{background:#fff;alternate-background-color:#f5f5ff;border:1px solid #c0c0d8;border-radius:6px;outline:none;}"
             "#musicTree::item:selected,#newTree::item:selected,#dupTree::item:selected,#changedTree::item:selected{background:#c8b8ff;color:#000;}"
             "QHeaderView::section{background:#dcdcec;color:#444488;border:none;border-bottom:1px solid #c0c0d8;padding:6px 8px;font-weight:700;font-size:11px;}"
             "#bigBar{background:#dcdcec;border-radius:5px;}"
             "#bigBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #7755cc,stop:1 #aa77ff);border-radius:5px;}"
             "QStatusBar{background:#e8e8f5;color:#555577;font-size:11px;}"
             "#artistCard{background:#fff;border:1px solid #c0c0d8;border-radius:8px;}"
             "#previewPlayBtn{background:#5533aa;color:#fff;border:1px solid #3322aa;border-radius:18px;font-weight:700;font-size:16px;}",

    "Dracula": "QMainWindow,QWidget{background:#282a36;color:#f8f8f2;font-family:'Segoe UI','SF Pro Display',sans-serif;}"
               "QTabWidget::pane{border:none;}"
               "QTabBar::tab{background:#44475a;color:#bd93f9;padding:7px 18px;border-radius:4px 4px 0 0;margin-right:2px;font-weight:600;}"
               "QTabBar::tab:selected{background:#282a36;color:#ff79c6;}"
               "#folderPanel{background:#21222c;border-right:1px solid #44475a;padding:8px;}"
               "#folderList,#managerList{background:#44475a;border:1px solid #6272a4;border-radius:5px;color:#f8f8f2;}"
               "#folderList::item:selected,#managerList::item:selected{background:#6272a4;color:#f8f8f2;}"
               "#addBtn{background:#50fa7b;color:#282a36;border:1px solid #50fa7b;border-radius:4px;font-weight:600;}"
               "#removeBtn{background:#ff5555;color:#f8f8f2;border:1px solid #ff5555;border-radius:4px;font-weight:600;}"
               "#primaryBtn{background:#bd93f9;color:#282a36;border:1px solid #bd93f9;border-radius:5px;padding:4px 18px;font-weight:700;}"
               "#secondaryBtn{background:#8be9fd;color:#282a36;border:1px solid #8be9fd;border-radius:4px;font-weight:600;}"
               "#toolBtn{background:#44475a;color:#f8f8f2;border:1px solid #6272a4;border-radius:4px;font-weight:600;}"
               "#searchBox{background:#21222c;border:1px solid #6272a4;border-radius:5px;color:#f8f8f2;padding:2px 10px;}"
               "#musicTree,#newTree,#dupTree,#changedTree{background:#21222c;alternate-background-color:#44475a;border:1px solid #6272a4;border-radius:6px;outline:none;}"
               "#musicTree::item:selected,#newTree::item:selected,#dupTree::item:selected,#changedTree::item:selected{background:#6272a4;color:#f8f8f2;}"
               "QHeaderView::section{background:#44475a;color:#bd93f9;border:none;border-bottom:1px solid #6272a4;padding:6px 8px;font-weight:700;font-size:11px;}"
               "#bigBar{background:#44475a;border-radius:5px;}"
               "#bigBar::chunk{background:#ff79c6;border-radius:5px;}"
               "QStatusBar{background:#21222c;color:#6272a4;font-size:11px;}"
               "QScrollBar:vertical{background:#21222c;width:10px;border-radius:5px;}"
               "QScrollBar::handle:vertical{background:#6272a4;border-radius:5px;}"
               "#artistCard{background:#44475a;border:1px solid #6272a4;border-radius:8px;}"
               "#previewPlayBtn{background:#bd93f9;color:#282a36;border:1px solid #bd93f9;border-radius:18px;font-weight:700;font-size:16px;}",

    "Nord": "QMainWindow,QWidget{background:#2e3440;color:#e5e9f0;font-family:'Segoe UI','SF Pro Display',sans-serif;}"
               "QTabWidget::pane{border:none;}"
               "QTabBar::tab{background:#3b4252;color:#88c0d0;padding:7px 18px;border-radius:4px 4px 0 0;margin-right:2px;font-weight:600;}"
               "QTabBar::tab:selected{background:#2e3440;color:#88c0d0;}"
               "#folderPanel{background:#292e39;border-right:1px solid #4c566a;padding:8px;}"
               "#folderList,#managerList{background:#3b4252;border:1px solid #4c566a;border-radius:5px;color:#e5e9f0;}"
               "#folderList::item:selected,#managerList::item:selected{background:#4c566a;color:#eceff4;}"
               "#addBtn{background:#a3be8c;color:#2e3440;border:1px solid #a3be8c;border-radius:4px;font-weight:600;}"
               "#removeBtn{background:#bf616a;color:#eceff4;border:1px solid #bf616a;border-radius:4px;font-weight:600;}"
               "#primaryBtn{background:#88c0d0;color:#2e3440;border:1px solid #88c0d0;border-radius:5px;padding:4px 18px;font-weight:700;}"
               "#secondaryBtn{background:#5e81ac;color:#eceff4;border:1px solid #5e81ac;border-radius:4px;font-weight:600;}"
               "#toolBtn{background:#4c566a;color:#e5e9f0;border:1px solid #5e81ac;border-radius:4px;font-weight:600;}"
               "#searchBox{background:#292e39;border:1px solid #4c566a;border-radius:5px;color:#e5e9f0;padding:2px 10px;}"
               "#musicTree,#newTree,#dupTree,#changedTree{background:#292e39;alternate-background-color:#3b4252;border:1px solid #4c566a;border-radius:6px;outline:none;}"
               "#musicTree::item:selected,#newTree::item:selected,#dupTree::item:selected,#changedTree::item:selected{background:#4c566a;color:#eceff4;}"
               "QHeaderView::section{background:#3b4252;color:#88c0d0;border:none;border-bottom:1px solid #4c566a;padding:6px 8px;font-weight:700;font-size:11px;}"
               "#bigBar{background:#3b4252;border-radius:5px;}"
               "#bigBar::chunk{background:#88c0d0;border-radius:5px;}"
               "QStatusBar{background:#292e39;color:#4c566a;font-size:11px;}"
               "QScrollBar:vertical{background:#292e39;width:10px;border-radius:5px;}"
               "QScrollBar::handle:vertical{background:#4c566a;border-radius:5px;}"
               "#artistCard{background:#3b4252;border:1px solid #4c566a;border-radius:8px;}"
               "#previewPlayBtn{background:#88c0d0;color:#2e3440;border:1px solid #88c0d0;border-radius:18px;font-weight:700;font-size:16px;}",

    "Solarized Dark": "QMainWindow,QWidget{background:#002b36;color:#93a1a1;font-family:'Segoe UI','SF Pro Display',sans-serif;}"
               "QTabWidget::pane{border:none;}"
               "QTabBar::tab{background:#073642;color:#268bd2;padding:7px 18px;border-radius:4px 4px 0 0;margin-right:2px;font-weight:600;}"
               "QTabBar::tab:selected{background:#002b36;color:#2aa198;}"
               "#folderPanel{background:#012b36;border-right:1px solid #586e75;padding:8px;}"
               "#folderList,#managerList{background:#073642;border:1px solid #586e75;border-radius:5px;color:#93a1a1;}"
               "#folderList::item:selected,#managerList::item:selected{background:#586e75;color:#eee8d5;}"
               "#addBtn{background:#859900;color:#002b36;border:1px solid #859900;border-radius:4px;font-weight:600;}"
               "#removeBtn{background:#dc322f;color:#eee8d5;border:1px solid #dc322f;border-radius:4px;font-weight:600;}"
               "#primaryBtn{background:#268bd2;color:#002b36;border:1px solid #268bd2;border-radius:5px;padding:4px 18px;font-weight:700;}"
               "#secondaryBtn{background:#2aa198;color:#002b36;border:1px solid #2aa198;border-radius:4px;font-weight:600;}"
               "#toolBtn{background:#073642;color:#93a1a1;border:1px solid #586e75;border-radius:4px;font-weight:600;}"
               "#searchBox{background:#012b36;border:1px solid #586e75;border-radius:5px;color:#93a1a1;padding:2px 10px;}"
               "#musicTree,#newTree,#dupTree,#changedTree{background:#012b36;alternate-background-color:#073642;border:1px solid #586e75;border-radius:6px;outline:none;}"
               "#musicTree::item:selected,#newTree::item:selected,#dupTree::item:selected,#changedTree::item:selected{background:#073642;color:#eee8d5;}"
               "QHeaderView::section{background:#073642;color:#268bd2;border:none;border-bottom:1px solid #586e75;padding:6px 8px;font-weight:700;font-size:11px;}"
               "#bigBar{background:#073642;border-radius:5px;}"
               "#bigBar::chunk{background:#b58900;border-radius:5px;}"
               "QStatusBar{background:#012b36;color:#586e75;font-size:11px;}"
               "QScrollBar:vertical{background:#012b36;width:10px;border-radius:5px;}"
               "QScrollBar::handle:vertical{background:#586e75;border-radius:5px;}"
               "#artistCard{background:#073642;border:1px solid #586e75;border-radius:8px;}"
               "#previewPlayBtn{background:#268bd2;color:#002b36;border:1px solid #268bd2;border-radius:18px;font-weight:700;font-size:16px;}",

    "Gruvbox": "QMainWindow,QWidget{background:#282828;color:#ebdbb2;font-family:'Segoe UI','SF Pro Display',sans-serif;}"
               "QTabWidget::pane{border:none;}"
               "QTabBar::tab{background:#3c3836;color:#d3869b;padding:7px 18px;border-radius:4px 4px 0 0;margin-right:2px;font-weight:600;}"
               "QTabBar::tab:selected{background:#282828;color:#fabd2f;}"
               "#folderPanel{background:#1d2021;border-right:1px solid #504945;padding:8px;}"
               "#folderList,#managerList{background:#3c3836;border:1px solid #504945;border-radius:5px;color:#ebdbb2;}"
               "#folderList::item:selected,#managerList::item:selected{background:#504945;color:#ebdbb2;}"
               "#addBtn{background:#b8bb26;color:#282828;border:1px solid #b8bb26;border-radius:4px;font-weight:600;}"
               "#removeBtn{background:#fb4934;color:#ebdbb2;border:1px solid #fb4934;border-radius:4px;font-weight:600;}"
               "#primaryBtn{background:#d3869b;color:#282828;border:1px solid #d3869b;border-radius:5px;padding:4px 18px;font-weight:700;}"
               "#secondaryBtn{background:#83a598;color:#282828;border:1px solid #83a598;border-radius:4px;font-weight:600;}"
               "#toolBtn{background:#3c3836;color:#ebdbb2;border:1px solid #504945;border-radius:4px;font-weight:600;}"
               "#searchBox{background:#1d2021;border:1px solid #504945;border-radius:5px;color:#ebdbb2;padding:2px 10px;}"
               "#musicTree,#newTree,#dupTree,#changedTree{background:#1d2021;alternate-background-color:#3c3836;border:1px solid #504945;border-radius:6px;outline:none;}"
               "#musicTree::item:selected,#newTree::item:selected,#dupTree::item:selected,#changedTree::item:selected{background:#504945;color:#ebdbb2;}"
               "QHeaderView::section{background:#3c3836;color:#fabd2f;border:none;border-bottom:1px solid #504945;padding:6px 8px;font-weight:700;font-size:11px;}"
               "#bigBar{background:#3c3836;border-radius:5px;}"
               "#bigBar::chunk{background:#fabd2f;border-radius:5px;}"
               "QStatusBar{background:#1d2021;color:#504945;font-size:11px;}"
               "QScrollBar:vertical{background:#1d2021;width:10px;border-radius:5px;}"
               "QScrollBar::handle:vertical{background:#504945;border-radius:5px;}"
               "#artistCard{background:#3c3836;border:1px solid #504945;border-radius:8px;}"
               "#previewPlayBtn{background:#d3869b;color:#282828;border:1px solid #d3869b;border-radius:18px;font-weight:700;font-size:16px;}",

    "Synthwave": "QMainWindow,QWidget{background:#1a1423;color:#f4f4f8;font-family:'Segoe UI','SF Pro Display',sans-serif;}"
               "QTabWidget::pane{border:none;}"
               "QTabBar::tab{background:#2d1b3d;color:#ff2a6d;padding:7px 18px;border-radius:4px 4px 0 0;margin-right:2px;font-weight:600;}"
               "QTabBar::tab:selected{background:#1a1423;color:#05d9e8;}"
               "#folderPanel{background:#130f1a;border-right:1px solid #ff2a6d;padding:8px;}"
               "#folderList,#managerList{background:#2d1b3d;border:1px solid #ff2a6d;border-radius:5px;color:#f4f4f8;}"
               "#folderList::item:selected,#managerList::item:selected{background:#ff2a6d;color:#ffffff;}"
               "#addBtn{background:#50fa7b;color:#130f1a;border:1px solid #50fa7b;border-radius:4px;font-weight:600;}"
               "#removeBtn{background:#ff5555;color:#f4f4f8;border:1px solid #ff5555;border-radius:4px;font-weight:600;}"
               "#primaryBtn{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #ff2a6d,stop:1 #05d9e8);color:#ffffff;border:1px solid #ff2a6d;border-radius:5px;padding:4px 18px;font-weight:700;}"
               "#secondaryBtn{background:#05d9e8;color:#130f1a;border:1px solid #05d9e8;border-radius:4px;font-weight:600;}"
               "#toolBtn{background:#2d1b3d;color:#f4f4f8;border:1px solid #ff2a6d;border-radius:4px;font-weight:600;}"
               "#searchBox{background:#130f1a;border:1px solid #ff2a6d;border-radius:5px;color:#f4f4f8;padding:2px 10px;}"
               "#musicTree,#newTree,#dupTree,#changedTree{background:#130f1a;alternate-background-color:#2d1b3d;border:1px solid #ff2a6d;border-radius:6px;outline:none;}"
               "#musicTree::item:selected,#newTree::item:selected,#dupTree::item:selected,#changedTree::item:selected{background:#ff2a6d;color:#ffffff;}"
               "QHeaderView::section{background:#2d1b3d;color:#05d9e8;border:none;border-bottom:1px solid #ff2a6d;padding:6px 8px;font-weight:700;font-size:11px;}"
               "#bigBar{background:#2d1b3d;border-radius:5px;}"
               "#bigBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #ff2a6d,stop:1 #05d9e8);border-radius:5px;}"
               "QStatusBar{background:#130f1a;color:#05d9e8;font-size:11px;}"
               "QScrollBar:vertical{background:#130f1a;width:10px;border-radius:5px;}"
               "QScrollBar::handle:vertical{background:#ff2a6d;border-radius:5px;}"
               "#artistCard{background:#2d1b3d;border:1px solid #ff2a6d;border-radius:8px;}"
               "#previewPlayBtn{background:#ff2a6d;color:#ffffff;border:1px solid #ff2a6d;border-radius:18px;font-weight:700;font-size:16px;}"
}

# ─── Dynamic Color Palette Generator ───────────────────────────────────────
# Define color lists for various flags and identities.
# The generator will automatically create a readable, matching UI theme for each.
COLOR_PALETTES = {
    "Rainbow": ["#E50000", "#FF8D00", "#FFEE00", "#028121", "#004CFF", "#770088"],
    "Transgender": ["#55CDFD", "#F6AAB7", "#FFFFFF", "#F6AAB7", "#55CDFD"],
    "Nonbinary": ["#FCF431", "#FCFCFC", "#9D59D2", "#282828"],
    "Xenogender": ["#FF6692", "#FF9A98", "#FFB883", "#FBFFA8", "#85BCFF", "#9D85FF", "#A510FF"],
    "Agender": ["#000000", "#BABABA", "#FFFFFF", "#BAF484", "#FFFFFF", "#BABABA", "#000000"],
    "Queer": ["#B57FDD", "#FFFFFF", "#49821E"],
    "Genderfluid": ["#FE76A2", "#FFFFFF", "#BF12D7", "#000000", "#303CBE"],
    "Bisexual": ["#D60270", "#9B4F96", "#0038A8"],
    "Pansexual": ["#FF1C8D", "#FFD700", "#1AB3FF"],
    "Polysexual": ["#F714BA", "#01D66A", "#1594F6"],
    "Omnisexual": ["#FE9ACE", "#FF53BF", "#200044", "#6760FE", "#8EA6FF"],
    "Omniromantic": ["#FEC8E4", "#FDA1DB", "#89739A", "#ABA7FE", "#BFCEFF"],
    "Gay Men": ["#078D70", "#98E8C1", "#FFFFFF", "#7BADE2", "#3D1A78"],
    "Lesbian": ["#D62800", "#FF9B56", "#FFFFFF", "#D462A6", "#A40062"],
    "Abrosexual": ["#46D294", "#A3E9CA", "#FFFFFF", "#F78BB3", "#EE1766"],
    "Asexual": ["#000000", "#A4A4A4", "#FFFFFF", "#810081"],
    "Aromantic": ["#3BA740", "#A8D47A", "#FFFFFF", "#ABABAB", "#000000"],
    "Fictosexual": ["#000000", "#C4C4C4", "#A349A5", "#C4C4C4", "#000000"],
    "Aroace 1": ["#E28C00", "#ECCD00", "#FFFFFF", "#62AEDC", "#203856"],
    "Aroace 2": ["#000000", "#810081", "#A4A4A4", "#FFFFFF", "#A8D47A", "#3BA740"],
    "Aroace 3": ["#3BA740", "#A8D47A", "#FFFFFF", "#ABABAB", "#000000", "#A4A4A4", "#FFFFFF", "#810081"],
    "Demisexual": ["#000000", "#FFFFFF", "#6F0071", "#D3D3D3"],
    "Autosexual": ["#99D9EA", "#7F7F7F"],
    "Intergender": ["#900DC2", "#900DC2", "#FFE54F", "#900DC2", "#900DC2"],
    "Greygender": ["#B3B3B3", "#B3B3B3", "#FFFFFF", "#062383", "#062383", "#FFFFFF", "#535353", "#535353"],
    "Akiosexual": ["#F9485E", "#FEA06A", "#FEF44C", "#FFFFFF", "#000000"],
    "Bigender": ["#C479A2", "#EDA5CD", "#D6C7E8", "#FFFFFF", "#D6C7E8", "#9AC7E8", "#6D82D1"],
    "Demigender": ["#7F7F7F", "#C4C4C4", "#FBFF75", "#FFFFFF", "#FBFF75", "#C4C4C4", "#7F7F7F"],
    "Demiboy": ["#7F7F7F", "#C4C4C4", "#9DD7EA", "#FFFFFF", "#9DD7EA", "#C4C4C4", "#7F7F7F"],
    "Demigirl": ["#7F7F7F", "#C4C4C4", "#FDADC8", "#FFFFFF", "#FDADC8", "#C4C4C4", "#7F7F7F"],
    "Transmasculine": ["#FF8ABD", "#CDF5FE", "#9AEBFF", "#74DFFF", "#9AEBFF", "#CDF5FE", "#FF8ABD"],
    "Transfeminine": ["#73DEFF", "#FFE2EE", "#FFB5D6", "#FF8DC0", "#FFB5D6", "#FFE2EE", "#73DEFF"],
    "Genderfaun": ["#FCD689", "#FFF09B", "#FAF9CD", "#FFFFFF", "#8EDED9", "#8CACDE", "#9782EC"],
    "Demifaun": ["#7F7F7F", "#7F7F7F", "#C6C6C6", "#C6C6C6", "#FCC688", "#FFF19C", "#FFFFFF", "#8DE0D5", "#9682EC", "#C6C6C6", "#C6C6C6", "#7F7F7F", "#7F7F7F"],
    "Genderfae": ["#97C3A5", "#C3DEAE", "#F9FACD", "#FFFFFF", "#FCA2C4", "#DB8AE4", "#A97EDD"],
    "Demifae": ["#7F7F7F", "#7F7F7F", "#C5C5C5", "#C5C5C5", "#97C3A4", "#C4DEAE", "#FFFFFF", "#FCA2C5", "#AB7EDF", "#C5C5C5", "#C5C5C5", "#7F7F7F", "#7F7F7F"],
    "Neutrois": ["#FFFFFF", "#1F9F00", "#000000"],
    "Biromantic 1": ["#8869A5", "#D8A7D8", "#FFFFFF", "#FDB18D", "#151638"],
    "Biromantic 2": ["#740194", "#AEB1AA", "#FFFFFF", "#AEB1AA", "#740194"],
    "Autoromantic": ["#99D9EA", "#99D9EA", "#3DA542", "#7F7F7F", "#7F7F7F"],
    "Boyflux 2": ["#E48AE4", "#9A81B4", "#55BFAB", "#FFFFFF", "#A8A8A8", "#81D5EF", "#69ABE5", "#5276D4"],
    "Girlflux": ["#F9E6D7", "#F2526C", "#BF0311", "#E9C587", "#BF0311", "#F2526C", "#F9E6D7"],
    "Genderflux": ["#F47694", "#F2A2B9", "#CECECE", "#7CE0F7", "#3ECDF9", "#FFF48D"],
    "Nullflux": ["#0B0C0E", "#A28DB9", "#E1D4EF", "#F0E6DD", "#665858"],
    "Hypergender": ["#EFEFEF", "#FFFFFF", "#FBFF75", "#000000", "#FBFF75", "#FFFFFF", "#EFEFEF"],
    "Hyperboy": ["#EFEFEF", "#FFFFFF", "#74D7FE", "#000000", "#74D7FE", "#FFFFFF", "#EFEFEF"],
    "Hypergirl": ["#EFEFEF", "#FFFFFF", "#FC76D3", "#000000", "#FC76D3", "#FFFFFF", "#EFEFEF"],
    "Hyperandrogyne": ["#EFEFEF", "#FFFFFF", "#BB83FF", "#000000", "#BB83FF", "#FFFFFF", "#EFEFEF"],
    "Hyperneutrois": ["#EFEFEF", "#FFFFFF", "#BAFA74", "#000000", "#BAFA74", "#FFFFFF", "#EFEFEF"],
    "Finsexual": ["#B18EDF", "#D7B1E2", "#F7CDE9", "#F39FCE", "#EA7BB3"],
    "Unlabeled 1": ["#EAF8E4", "#FDFDFB", "#E1EFF7", "#F4E2C4"],
    "Unlabeled 2": ["#250548", "#FFFFFF", "#F7DCDA", "#EC9BEE", "#9541FA", "#7D2557"],
    "Pangender": ["#FFF798", "#FEDDCD", "#FFEBFB", "#FFFFFF", "#FFEBFB", "#FEDDCD", "#FFF798"],
    "Pangender Contrast": ["#FFE87F", "#FCBAA6", "#FBC9F3", "#FFFFFF", "#FBC9F3", "#FCBAA6", "#FFE87F"],
    "Gendernonconforming 1": ["#50284D", "#96467B", "#5C96F7", "#FFE6F7", "#5C96F7", "#96467B", "#50284D"],
    "Gendernonconforming 2": ["#50284D", "#96467B", "#5C96F7", "#FFE6F7", "#5C96F7", "#96467B", "#50284D"],
    "Femboy": ["#D260A5", "#E4AFCD", "#FEFEFE", "#57CEF8", "#FEFEFE", "#E4AFCD", "#D260A5"],
    "Tomboy": ["#2F3FB9", "#613A03", "#FEFEFE", "#F1A9B7", "#FEFEFE", "#613A03", "#2F3FB9"],
    "Gynesexual": ["#F4A9B7", "#903F2B", "#5B953B"],
    "Androsexual": ["#01CCFF", "#603524", "#B799DE"],
    "Gendervoid": ["#081149", "#4B484B", "#000000", "#4B484B", "#081149"],
    "Voidgirl": ["#180827", "#7A5A8B", "#E09BED", "#7A5A8B", "#180827"],
    "Voidboy": ["#0B130C", "#547655", "#66B969", "#547655", "#0B130C"],
    "Nonhuman Unity": ["#177B49", "#FFFFFF", "#593C90"],
    "Plural System": ["#2D0625", "#543475", "#7675C3", "#89C7B0", "#F3EDBD"],
    "Fraysexual": ["#226CB5", "#94E7DD", "#FFFFFF", "#636363"],
    "Bear": ["#623804", "#D56300", "#FEDD63", "#FEE6B8", "#FFFFFF", "#555555"],
    "Butch": ["#D72800", "#F17623", "#FF9C56", "#FFFDF6", "#FFCE89", "#FEAF02", "#A37000"],
    "Femme": ["#FF1A87", "#FF6AB1", "#FFFFFF", "#9A0731", "#51091D"],
    "Leather": ["#000000", "#252580", "#000000", "#252580", "#FFFFFF", "#252580", "#000000", "#252580", "#000000"],
    "Otter": ["#263881", "#5C9DC9", "#FFFFFF", "#3A291D", "#5C9DC9", "#263881"],
    "Twink": ["#FFB2FF", "#FFFFFF", "#FFFF81"],
    "Adipophilia": ["#000000", "#E16180", "#FFF9BE", "#603E41", "#000000"],
    "Kenochoric": ["#000000", "#2E1569", "#824DB7", "#C7A1D6"],
    "Veldian": ["#D182A8", "#FAF6E0", "#69ACBE", "#5D448F", "#3A113E"],
    "Solian": ["#FFF8ED", "#FFE7A8", "#F1B870", "#A56058", "#46281E"],
    "Lunian": ["#2F0E62", "#6F41B1", "#889FDF", "#7DDFD5", "#D2F2E2"],
    "Polyam": ["#FFFFFF", "#FCBF00", "#009FE3", "#E50051", "#340C46"],
    "Sapphic": ["#FD8BA8", "#FBF2FF", "#C76BC5", "#FDD768", "#C76BC5", "#FBF2FF", "#FD8BA8"],
    "Androgyne": ["#FE007F", "#9832FF", "#00B8E7"],
    "Interprogress": ["#FFD800", "#7902AA", "#FFFFFF", "#FFAFC8", "#74D7EE", "#613915", "#000000", "#E50000", "#FF8D00", "#FFEE00", "#028121", "#004CFF", "#770088"],
    "Progress": ["#FFFFFF", "#FFAFC8", "#74D7EE", "#613915", "#000000", "#E50000", "#FF8D00", "#FFEE00", "#028121", "#004CFF", "#770088"],
    "Intersex": ["#FFD800", "#FFD800", "#7902AA", "#FFD800", "#FFD800"],
    "Old Polyam": ["#0000FF", "#FF0000", "#FFFF00", "#FF0000", "#000000"],
    "Equal Rights": ["#0000FF", "#0000FF", "#FFFF00", "#0000FF", "#0000FF", "#FFFF00", "#0000FF", "#0000FF"],
    "Drag": ["#CC67FF", "#FFFFFF", "#FFA3E3", "#FFFFFF", "#3366FF"],
    "Pronounfluid": ["#FFB3F9", "#FFFFFF", "#D1FDCB", "#C7B0FF", "#000000", "#B8CCFF"],
    "Pronounflux": ["#FDB3F8", "#B6CCFA", "#18DDD3", "#64FF89", "#FF7690", "#FFFFFF"],
    "Exipronoun": ["#1C3D34", "#FFFFFF", "#321848", "#000000"],
    "Neopronoun": ["#BCEC64", "#FFFFFF", "#38077A"],
    "Neofluid": ["#FFECA0", "#FFFFFF", "#FFECA0", "#38087A", "#BCEC64"],
    "Genderqueer": ["#B57EDC", "#B57EDC", "#FFFFFF", "#FFFFFF", "#4A8123", "#4A8123"],
    "Cisgender": ["#D70270", "#0038A7"],
    "Baker": ["#F23D9E", "#F80A24", "#F78022", "#F9E81F", "#1E972E", "#1B86BC", "#243897", "#6F0A82"],
    "Caninekin": ["#2D2822", "#543D25", "#9C754D", "#E8DAC2", "#CFAD8C", "#B77B55", "#954E31"],
    "Libragender": ["#000000", "#808080", "#92D8E9", "#FFF544", "#FFB0CA", "#808080", "#000000"],
    "Librafeminine": ["#000000", "#A3A3A3", "#FFFFFF", "#C6568F", "#FFFFFF", "#A3A3A3", "#000000"],
    "Libramasculine": ["#000000", "#A3A3A3", "#FFFFFF", "#56C5C5", "#FFFFFF", "#A3A3A3", "#000000"],
    "Libraandrogyne": ["#000000", "#A3A3A3", "#FFFFFF", "#9186B1", "#FFFFFF", "#A3A3A3", "#000000"],
    "Libranonbinary": ["#000000", "#A3A3A3", "#FFFFFF", "#FFF987", "#FFFFFF", "#A3A3A3", "#000000"],
    "Fluidflux 1": ["#FF115F", "#A34AA3", "#00A4E7", "#FFDF00", "#000000", "#FFED71", "#85DAFF", "#DBADDA", "#FE8DB1"],
    "Fluidflux 2": ["#C6D1D2", "#F47B9D", "#F09F9B", "#E3F09E", "#75EEEA", "#52D2ED", "#C6D1D2"],
    "Transbian": ["#03A3E6", "#F8B4CD", "#FAFBF9", "#FA9C57", "#A80864"],
    "Autism": ["#C94A49", "#DE7554", "#DBB667", "#6FA35D", "#2E7574", "#232828"],
    "Cenelian": ["#FFE7B6", "#93554A", "#52203A", "#7E4A93", "#99AFD6"],
    "Transneutral": ["#74DFFF", "#FFFDB3", "#FFFC75", "#FFF200", "#FFFC75", "#FFFDB3", "#FE8CBF"],
    "Enbian": ["#261F4F", "#37296B", "#3C307C", "#5141A5", "#6551B5", "#8670D1", "#AB89DD"],
    "Paragender": ["#9C9C9C", "#FFFFFF", "#BDE4D7", "#63BFA1", "#F3EE94", "#63BFA1", "#BDE4D7", "#FFFFFF", "#9C9C9C"],
    "Paraboy": ["#9C9C9C", "#FFFFFF", "#E4CCEC", "#C48CD4", "#0809C3", "#C48CD4", "#E4CCEC", "#FFFFFF", "#9C9C9C"],
    "Paragirl": ["#9D9D9D", "#FFFFFF", "#FCCDBD", "#FC8D5C", "#FC1F4B", "#FC8D5C", "#FCCDBD", "#FFFFFF", "#9D9D9D"],
    "Paranonbinary": ["#9C9C9C", "#FCFCFC", "#FDE8BD", "#FCD25C", "#FB5A24", "#FCD25C", "#FDE8BD", "#FCFCFC", "#9C9C9C"],
    "Paragender Alt": ["#9E9E9E", "#FFFFFF", "#68CAB0", "#FFEBAD", "#68CAB0", "#FFFFFF", "#9E9E9E"],
    "Paraboy Alt": ["#9E9E9E", "#FFFFFF", "#D190E5", "#4F2ECA", "#D190E5", "#FFFFFF", "#9E9E9E"],
    "Paragirl Alt": ["#9E9E9E", "#FFFFFF", "#FFA07F", "#F43C3A", "#FFA07F", "#FFFFFF", "#9E9E9E"],
    "Paranonbinary Alt": ["#C9C9C9", "#F4F4F4", "#FFFCC0", "#FFB4EE", "#C267FF", "#8B4EFF"],
    "Cupiorose": ["#A0A0A0", "#C7BFE8", "#FFFFFF", "#B6C1DC"],
    "Cupioromantic": ["#FCAAA4", "#FDC6C1", "#FFFFFF", "#C9C0E7", "#A1A1A1"],
    "Cupiosexual": ["#A0A0A0", "#C7BFE8", "#FFFFFF", "#FFB3DA"],
    "Cow": ["#4FB7AC", "#FFFFFF", "#F6C0D0", "#EC758B", "#BC196A", "#520B45"],
    "Beiyang": ["#DF1B12", "#FFC600", "#01639D", "#FFFFFF", "#000000"],
    "Burger": ["#F3A26A", "#498701", "#FD1C13", "#7D3829", "#F3A26A"],
    "Throatlozenges": ["#2759DA", "#03940D", "#F5F100", "#F59B00", "#B71212"],
    "Band": ["#2670C0", "#F5BD00", "#DC0045", "#E0608E"],
    "Peter Griffin": ["#783717", "#FBB8A8", "#FFFFFF", "#29622F", "#462611"],
    "Rubber": ["#000000", "#FE0002", "#FFFF01", "#FE0002", "#000000", "#FE0002", "#000000"],
    "Haruhi": ["#613D2F", "#F5B422", "#613D2F", "#613D2F", "#57A4B8", "#F20205", "#57A4B8", "#57A4B8", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#57A4B8", "#57A4B8", "#F20205", "#57A4B8", "#613D2F", "#613D2F", "#F5B422", "#613D2F"],
    "Queer Villain": ["#662D91", "#8DC63F", "#F7941D", "#EC008C"],
    "Barlo": ["#A1399C", "#327FDB", "#6AC343"],
    "Disability": ["#595959", "#CE717F", "#EFDD77", "#E8E8E8", "#7AC3E0", "#3CB07D", "#595959"],
    "Unlabeled": ["#E7F9E4", "#FFFFFF", "#DEF0F7", "#FAE2C3"]
}

def _generate_theme_from_colors(colors: list) -> str:
    """Generates a complete Qt CSS stylesheet from a list of hex color strings."""
    # Ensure all colors start with '#'
    clean_colors = []
    for c in colors:
        if isinstance(c, str):
            if not c.startswith("#"):
                c = "#" + c
            clean_colors.append(c)

    if not clean_colors:
        return THEMES["Dark"]

    # Generate gradient stops
    n = len(clean_colors)
    stops = []
    for i, c in enumerate(clean_colors):
        pos = i / (n - 1) if n > 1 else 0
        stops.append(f"stop:{pos:.4f} {c}")
    grad = "qlineargradient(x1:0, y1:0, x2:1, y2:0, " + ", ".join(stops) + ")"

    # Use a dark base background for readability, and the middle color as the accent
    accent = clean_colors[len(clean_colors) // 2]
    bg = "#1a1a1a"
    text = "#ffffff"

    return (
        f"QMainWindow,QWidget{{background:{bg};color:{text};font-family:'Segoe UI','SF Pro Display',sans-serif;}}"
        f"QTabWidget::pane{{border:none;}}"
        f"QTabBar::tab{{background:#2a2a2a;color:#ffffff;padding:7px 18px;border-radius:4px 4px 0 0;margin-right:2px;font-weight:600;}}"
        f"QTabBar::tab:selected{{background:{bg};color:{accent};}}"
        f"#folderPanel{{background:#111111;border-right:1px solid {accent};padding:8px;}}"
        f"#folderList,#managerList{{background:#2a2a2a;border:1px solid {accent};border-radius:5px;color:#ffffff;}}"
        f"#folderList::item:selected,#managerList::item:selected{{background:{accent};color:#ffffff;}}"
        f"#addBtn{{background:#50fa7b;color:#111111;border:1px solid #50fa7b;border-radius:4px;font-weight:600;}}"
        f"#removeBtn{{background:#ff5555;color:#ffffff;border:1px solid #ff5555;border-radius:4px;font-weight:600;}}"
        f"#primaryBtn{{background:{grad};color:#ffffff;border:1px solid {accent};border-radius:5px;padding:4px 18px;font-weight:700;}}"
        f"#secondaryBtn{{background:{accent};color:#ffffff;border:1px solid {accent};border-radius:4px;font-weight:600;}}"
        f"#toolBtn{{background:#2a2a2a;color:#ffffff;border:1px solid #555555;border-radius:4px;font-weight:600;}}"
        f"#searchBox{{background:#111111;border:1px solid {accent};border-radius:5px;color:#ffffff;padding:2px 10px;}}"
        f"#musicTree,#newTree,#dupTree,#changedTree{{background:#111111;alternate-background-color:#1a1a1a;border:1px solid #444444;border-radius:6px;outline:none;}}"
        f"#musicTree::item:selected,#newTree::item:selected,#dupTree::item:selected,#changedTree::item:selected{{background:{accent};color:#ffffff;}}"
        f"QHeaderView::section{{background:#2a2a2a;color:{accent};border:none;border-bottom:1px solid #555555;padding:6px 8px;font-weight:700;font-size:11px;}}"
        f"#bigBar{{background:#2a2a2a;border-radius:5px;}}"
        f"#bigBar::chunk{{background:{grad};border-radius:5px;}}"
        f"QStatusBar{{background:#111111;color:{accent};font-size:11px;}}"
        f"QScrollBar:vertical{{background:#111111;width:10px;border-radius:5px;}}"
        f"QScrollBar::handle:vertical{{background:{accent};border-radius:5px;}}"
        f"#artistCard{{background:#2a2a2a;border:1px solid #555555;border-radius:8px;}}"
        f"#previewPlayBtn{{background:{accent};color:#ffffff;border:1px solid {accent};border-radius:18px;font-weight:700;font-size:16px;}}"
    )

# Dynamically generate and add all pride themes to the THEMES dictionary
for name, colors in COLOR_PALETTES.items():
    if isinstance(colors, list) and len(colors) > 0:
        THEMES[name] = _generate_theme_from_colors(colors)
