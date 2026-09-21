"""PySide6 데스크톱 UI. 데이터 로직은 vocab_service/tag_service에 있고,
이 패키지는 화면(위젯·시그널·레이아웃·테마)만 담당합니다."""

from .app import run

__all__ = ["run"]
