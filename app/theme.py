"""Tema oscuro del estudio (QSS)."""

ACCENT = "#f5b942"  # amarillo racing

QSS = f"""
QWidget {{
    background: #0f1013;
    color: #e6e7ea;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}}
QMainWindow, QWidget#Root {{ background: #0f1013; }}
QFrame#Card {{
    background: #17181d;
    border: 1px solid #26272e;
    border-radius: 12px;
}}
QLabel#Title {{ font-size: 24px; font-weight: 600; }}
QLabel#Subtitle {{ color: #8b8d96; font-size: 14px; }}
QLabel#Section {{ font-size: 15px; font-weight: 600; color: #c8cad1; }}
QLabel#Muted {{ color: #8b8d96; }}
QLabel#StepActive {{ color: {ACCENT}; font-weight: 600; }}
QLabel#StepInactive {{ color: #6b6d76; }}
QLabel#StepDone {{ color: #7fbf7f; }}
QLabel#BigValue {{ font-size: 20px; font-weight: 600; color: {ACCENT}; }}

QPushButton {{
    background: #1e2027;
    border: 1px solid #2c2e37;
    border-radius: 8px;
    padding: 8px 18px;
    color: #e6e7ea;
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed {{ background: #262830; }}
QPushButton:disabled {{ color: #5a5c64; border-color: #22242b; }}
QPushButton#Primary {{
    background: {ACCENT};
    color: #0f1013;
    font-weight: 600;
    border: none;
}}
QPushButton#Primary:hover {{ background: #ffc95e; }}
QPushButton#Primary:disabled {{ background: #3a3527; color: #6b6d76; }}
QPushButton#Ghost {{ background: transparent; border: 1px solid #2c2e37; }}

QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{
    background: #1e2027;
    border: 1px solid #2c2e37;
    border-radius: 6px;
    padding: 5px 10px;
    color: #e6e7ea;
}}
QComboBox QAbstractItemView {{
    background: #1e2027;
    border: 1px solid #2c2e37;
    selection-background-color: {ACCENT};
    selection-color: #0f1013;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background: #262830; width: 18px; border: none;
}}

QTableWidget {{
    background: #17181d;
    alternate-background-color: #1a1b21;
    border: 1px solid #26272e;
    border-radius: 8px;
    gridline-color: #22242b;
}}
QHeaderView::section {{
    background: #1e2027;
    color: #8b8d96;
    border: none;
    padding: 7px;
    font-weight: 600;
}}
QTableWidget::item:selected {{ background: #2c2e37; }}

QProgressBar {{
    background: #1e2027;
    border: none;
    border-radius: 6px;
    text-align: center;
    height: 18px;
    color: #c8cad1;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 6px; }}

QRadioButton, QCheckBox {{ spacing: 8px; }}
QRadioButton::indicator, QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid #3a3c46; border-radius: 4px;
    background: #1e2027;
}}
QRadioButton::indicator:checked, QCheckBox::indicator:checked {{
    background: {ACCENT}; border-color: {ACCENT};
}}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2c2e37; border-radius: 5px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: #3a3c46; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #2c2e37; border-radius: 5px; min-width: 24px; }}

QStatusBar {{ background: #17181d; color: #8b8d96; }}
QMessageBox {{ background: #17181d; }}
QToolTip {{
    background: #262830; color: #e6e7ea;
    border: 1px solid #3a3c46; padding: 5px;
}}
"""
