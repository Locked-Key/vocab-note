"""GUI 진입점. `python -m vocab_note gui` 또는 `open_gui()`로 실행."""

from __future__ import annotations

import sys


def run(db_path=None) -> int:
    from PySide6.QtWidgets import QApplication

    from .main_window import MainWindow
    from .theme import apply_theme

    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(app, dark=False)
    win = MainWindow(db_path=db_path)
    win.show()
    return app.exec()


def open_gui() -> None:
    raise SystemExit(run())
