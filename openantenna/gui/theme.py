"""Visual theme for the GUI.

One stylesheet, applied once at startup.  The goal is legibility and calm, not decoration: a dark
neutral palette, a single accent, consistent radii and spacing, and a monospace face for numbers so
tables of results line up.

Nothing here changes behaviour, so the GUI smoke tests and `--selftest` keep their meaning.
"""

from __future__ import annotations

ACCENT = "#4c8bf5"
BACKGROUND = "#1e1f22"
PANEL = "#2b2d31"
PANEL_ALT = "#313338"
BORDER = "#3a3d42"
TEXT = "#e6e6e6"
TEXT_MUTED = "#a8adb5"

STYLESHEET = f"""
QWidget {{
    background: {BACKGROUND};
    color: {TEXT};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 10pt;
}}
QMainWindow, QDialog {{ background: {BACKGROUND}; }}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    top: -1px;
    background: {PANEL};
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_MUTED};
    padding: 7px 16px;
    margin-right: 2px;
    border: 1px solid transparent;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
}}
QTabBar::tab:hover {{ color: {TEXT}; background: {PANEL_ALT}; }}
QTabBar::tab:selected {{
    color: {TEXT};
    background: {PANEL};
    border: 1px solid {BORDER};
    border-bottom-color: {PANEL};
}}

QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 14px;
    padding: 10px 10px 8px 10px;
    background: {PANEL};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 5px;
    color: {TEXT_MUTED};
    font-weight: 600;
}}

QPushButton {{
    background: {PANEL_ALT};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 14px;
    min-height: 18px;
}}
QPushButton:hover {{ border-color: {ACCENT}; color: #ffffff; }}
QPushButton:pressed {{ background: {BACKGROUND}; }}
QPushButton:disabled {{ color: #6b7078; border-color: #2f3237; background: #26282c; }}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {BACKGROUND};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px 8px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background: {PANEL};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
}}

QTableWidget, QTableView, QTreeWidget, QListWidget {{
    background: {PANEL};
    alternate-background-color: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QHeaderView::section {{
    background: {PANEL_ALT};
    color: {TEXT_MUTED};
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    padding: 6px 8px;
    font-weight: 600;
}}
QTableCornerButton::section {{ background: {PANEL_ALT}; border: none; }}

QProgressBar {{
    background: {BACKGROUND};
    border: 1px solid {BORDER};
    border-radius: 6px;
    text-align: center;
    color: {TEXT};
    height: 16px;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 5px; }}

QPlainTextEdit, QTextEdit {{
    background: {BACKGROUND};
    border: 1px solid {BORDER};
    border-radius: 8px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 9.5pt;
}}

QSplitter::handle {{ background: {BORDER}; }}
QDockWidget {{ titlebar-close-icon: none; color: {TEXT_MUTED}; }}
QDockWidget::title {{
    background: {PANEL_ALT};
    padding: 6px 8px;
    border-bottom: 1px solid {BORDER};
}}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #4a4f56; border-radius: 5px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #4a4f56; border-radius: 5px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}

QStatusBar {{ color: {TEXT_MUTED}; }}
QToolTip {{
    background: {PANEL_ALT};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px 6px;
}}
"""


def apply_theme(app) -> None:
    """Install the stylesheet and a consistent base style on a QApplication."""
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
