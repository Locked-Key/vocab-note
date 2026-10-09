"""AI 설정 다이얼로그: provider·모델·키 저장 + 연결 테스트.

- 키는 .env에만 저장 (화면·로그에 평문 표시 안 함)
"""

import os

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..ai.providers import DEFAULT_MODELS, KEY_ENV_VARS, PROVIDERS
from ..ai.service import (
    get_provider,
    load_settings,
    save_key_to_dotenv,
    save_settings,
)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI 설정")
        self._settings = load_settings()

        self.provider_box = QComboBox()
        self.provider_box.addItems([p for p in PROVIDERS if p != "mock"])
        self.provider_box.setCurrentText(self._settings.provider)
        self.provider_box.currentTextChanged.connect(self._on_provider_changed)

        self.model_edit = QLineEdit(self._settings.model)
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("입력 시에만 .env에 저장됨")

        self.test_result = QLabel("")
        self.test_result.setWordWrap(True)

        form = QFormLayout()
        form.addRow("LLM", self.provider_box)
        form.addRow("모델(비우면 기본값)", self.model_edit)
        form.addRow("API 키", self.key_edit)

        test_btn = QPushButton("연결 테스트")
        test_btn.clicked.connect(self._on_test)
        save_btn = QPushButton("저장")
        save_btn.clicked.connect(self._on_save)
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addWidget(test_btn)
        row.addStretch(1)
        row.addWidget(save_btn)
        row.addWidget(close_btn)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(self.test_result)
        layout.addLayout(row)
        self.setLayout(layout)
        self._refresh_model_placeholder()

    def _refresh_model_placeholder(self) -> None:
        provider = self.provider_box.currentText()
        self.model_edit.setPlaceholderText(DEFAULT_MODELS.get(provider, ""))

    def _on_provider_changed(self) -> None:
        self.model_edit.clear()
        self._refresh_model_placeholder()

    def _collect(self):
        from ..ai.service import AISettings

        return AISettings(provider=self.provider_box.currentText(),
                          model=self.model_edit.text().strip())

    def _on_save(self) -> None:
        s = self._collect()
        save_settings(s)
        if self.key_edit.text():
            save_key_to_dotenv(s.provider, self.key_edit.text().strip())
            self.key_edit.clear()
            QMessageBox.information(self, "저장", "설정과 키(.env)를 저장했습니다.")
        else:
            QMessageBox.information(self, "저장", "설정을 저장했습니다.")
        self.accept()

    def _on_test(self) -> None:
        """저장 없이 현재 입력으로 연결 테스트 (입력 키는 메모리에만)."""
        from ..ai.service import load_dotenv

        load_dotenv()
        s = self._collect()
        typed_key = self.key_edit.text().strip()
        if typed_key:
            os.environ[KEY_ENV_VARS[s.provider]] = typed_key
        try:
            result = get_provider(s).test_connection()
            is_mock = "mock" in result
            self.test_result.setText(
                result + (" (키 없음 — Mock)" if is_mock else ""))
        except Exception as e:
            self.test_result.setText(f"연결 실패: {e}")
        finally:
            if typed_key:
                # 입력 키는 테스트 후 환경에서 제거 (.env 저장은 [저장] 버튼으로만)
                os.environ.pop(KEY_ENV_VARS[s.provider], None)
                load_dotenv()
