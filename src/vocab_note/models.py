"""Word/Sense 데이터 클래스. Word와 Sense 분리로 동음이의어를 지원합니다."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Sense:
    id: int
    word_id: int
    part_of_speech: str = ""
    meaning_ko: str = ""
    example_en: str = ""
    example_ko: str = ""


@dataclass
class Word:
    id: int
    spelling: str
    normalized_spelling: str
    created_at: str = ""
    senses: list[Sense] = field(default_factory=list)
