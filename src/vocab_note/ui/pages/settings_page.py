"""AI 설정 본문 페이지: provider·모델·키 저장 + 연결 테스트.

키는 .env에만 저장하고 화면에는 마스킹해서 표시합니다.
"""

import os

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...ai.providers import DEFAULT_MODELS, KEY_ENV_VARS, PROVIDERS
from ...ai.service import (
    AISettings,
    get_provider,
    load_dotenv,
    load_settings,
    save_key_to_dotenv,
    save_settings,
)


class SettingsPage(QWidget):
    title_text = "설정"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = load_settings()

        heading = QLabel("AI 설정")
        font = heading.font()
        font.setPointSize(18)
        font.setBold(True)
        heading.setFont(font)

        self.provider_box = QComboBox()
        self.provider_box.addItems([p for p in PROVIDERS if p != "mock"])
        self.provider_box.setCurrentText(self._settings.provider)
        self.provider_box.currentTextChanged.connect(self._on_provider_changed)

        self.model_edit = QLineEdit(self._settings.model)
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("입력 시에만 .env에 저장됨")
        self.key_status = QLabel("")

        self.test_result = QLabel("")
        self.test_result.setWordWrap(True)

        form = QFormLayout()
        form.addRow("LLM", self.provider_box)
        form.addRow("모델(비우면 기본값)", self.model_edit)
        form.addRow("API 키", self.key_edit)
        form.addRow("저장된 키", self.key_status)

        test_btn = QPushButton("연결 테스트")
        test_btn.clicked.connect(self._on_test)
        save_btn = QPushButton("저장")
        save_btn.clicked.connect(self._on_save)
        row = QHBoxLayout()
        row.addWidget(test_btn)
        row.addStretch(1)
        row.addWidget(save_btn)

        layout = QVBoxLayout()
        layout.addWidget(heading)
        layout.addSpacing(8)
        layout.addLayout(form)
        layout.addWidget(self.test_result)
        layout.addLayout(row)
        layout.addSpacing(16)

        # 화면 설정
        appearance_heading = QLabel("화면")
        font2 = appearance_heading.font()
        font2.setPointSize(14)
        font2.setBold(True)
        appearance_heading.setFont(font2)
        self.dark_check = QCheckBox("다크 모드")

        layout.addWidget(appearance_heading)
        layout.addWidget(self.dark_check)
        layout.addStretch(1)
        self.setLayout(layout)
        self._refresh_model_placeholder()
        self._refresh_key_status()

    # -- 상태 표시 ---------------------------------------------------------
    def reset(self) -> None:
        """페이지 진입 시 저장된 설정을 다시 읽습니다."""
        self._settings = load_settings()
        self.provider_box.setCurrentText(self._settings.provider)
        self.model_edit.setText(self._settings.model)
        self.test_result.setText("")
        self._refresh_model_placeholder()
        self._refresh_key_status()
        # dark_check 동기화는 MainWindow.set_dark_mode에서 처리

    def _refresh_model_placeholder(self) -> None:
        provider = self.provider_box.currentText()
        self.model_edit.setPlaceholderText(DEFAULT_MODELS.get(provider, ""))

    def _refresh_key_status(self) -> None:
        load_dotenv()
        key = os.environ.get(KEY_ENV_VARS.get(self.provider_box.currentText(), ""), "")
        if key:
            masked = key[:4] + "…" + key[-2:] if len(key) > 8 else "****"
            self.key_status.setText(f"있음 ({masked})")
        else:
            self.key_status.setText("없음 — 키가 없으면 Mock으로 동작합니다")

    def _on_provider_changed(self) -> None:
        self.model_edit.clear()
        self.test_result.setText("")
        self._refresh_model_placeholder()
        self._refresh_key_status()

    def _collect(self) -> AISettings:
        return AISettings(provider=self.provider_box.currentText(),
                          model=self.model_edit.text().strip())

    # -- 액션 --------------------------------------------------------------
    def _on_save(self) -> None:
        s = self._collect()
        save_settings(s)
        if self.key_edit.text():
            save_key_to_dotenv(s.provider, self.key_edit.text().strip())
            self.key_edit.clear()
            QMessageBox.information(self, "저장", "설정과 키(.env)를 저장했습니다.")
        else:
            QMessageBox.information(self, "저장", "설정을 저장했습니다.")
        self._settings = load_settings()
        self._refresh_key_status()

    def _on_test(self) -> None:
        """저장 없이 현재 입력으로 연결 테스트 (입력 키는 메모리에만)."""
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
