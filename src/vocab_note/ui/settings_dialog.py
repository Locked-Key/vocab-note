"""AI 설정 다이얼로그(팝업). 본문은 pages.SettingsPage를 그대로 재사용합니다.

메인 화면은 사이드바로 SettingsPage를 직접 띄우며, 이 래퍼는 팝업이 필요한
경우(외부 호출·테스트)를 위해 남겨둔 얇은 어댑터입니다.
"""

from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QVBoxLayout

from .pages.settings_page import SettingsPage

__all__ = ["SettingsDialog", "SettingsPage"]


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI 설정")
        self.page = SettingsPage(self)

        close = QPushButton("닫기")
        close.clicked.connect(self.reject)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(close)

        layout = QVBoxLayout()
        layout.addWidget(self.page, 1)
        layout.addLayout(bottom)
        self.setLayout(layout)

    def __getattr__(self, name):
        """page의 위젯·메서드(provider_box/model_edit/…)를 그대로 노출."""
        page = self.__dict__.get("page")
        if page is not None and hasattr(page, name):
            return getattr(page, name)
        raise AttributeError(name)
