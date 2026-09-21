"""라이트/다크 QSS 테마. UI 코드는 색상값을 직접 쓰지 않고 이 모듈을 통합니다."""

DARK_QSS = """
QWidget { background-color: #2b2b2b; color: #e6e6e6; font-size: 14px; }
QLineEdit, QComboBox, QListWidget, QTextEdit {
    background-color: #3a3a3a; border: 1px solid #555; border-radius: 4px; padding: 4px;
}
QPushButton {
    background-color: #3c3c3c; border: 1px solid #666; border-radius: 4px; padding: 6px 12px;
}
QPushButton:hover { background-color: #4a4a4a; }
QPushButton:checked { background-color: #4a6fa5; border-color: #4a6fa5; }
QListWidget::item:selected { background-color: #4a6fa5; }
QSplitter::handle { background-color: #555; }
"""

LIGHT_QSS = """
QWidget { font-size: 14px; }
QLineEdit, QComboBox, QListWidget, QTextEdit {
    border: 1px solid #bbb; border-radius: 4px; padding: 4px;
}
QPushButton {
    border: 1px solid #999; border-radius: 4px; padding: 6px 12px;
}
QPushButton:checked { background-color: #cfe3ff; border-color: #4a6fa5; }
"""


def apply_theme(app, dark: bool) -> None:
    """QApplication에 테마 적용."""
    app.setStyleSheet(DARK_QSS if dark else LIGHT_QSS)
