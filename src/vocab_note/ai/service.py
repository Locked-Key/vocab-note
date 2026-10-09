"""AI 서비스: 설정·팩토리·프롬프트. 업체별 차이는 providers가 처리.

- 비밀키: .env / 환경변수에만 (GEMINI_API_KEY 등) — 파일·로그에 남기지 않음
- 일반 설정: data/settings.json {"provider": "gemini", "model": "..."}
- 키가 없으면 MockProvider (실제 호출 없음)
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ..config import BASE_DIR, DATA_DIR
from ..tag_service import get_word_tags
from ..vocab_service import get_word
from .providers import (
    AIError,
    AIProvider,
    DEFAULT_MODELS,
    KEY_ENV_VARS,
    PROVIDERS,
    Suggestion,
)

DOTENV_PATH = BASE_DIR / ".env"
SETTINGS_PATH = DATA_DIR / "settings.json"


@dataclass
class AISettings:
    provider: str = "gemini"
    model: str = ""  # 비어 있으면 업체 기본 모델
    is_mock: bool = False  # 키가 없어 Mock으로 동작 중인지

    @property
    def effective_model(self) -> str:
        return self.model or DEFAULT_MODELS.get(self.provider, "")


def load_dotenv(path: Path | None = None) -> None:
    """KEY=VALUE 한 줄씩 환경변수에 (이미 있으면 덮지 않음). 의존성 없음."""
    p = path or DOTENV_PATH
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_settings(path: Path | None = None) -> AISettings:
    p = path or SETTINGS_PATH
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            provider = str(data.get("provider", "gemini"))
            model = str(data.get("model", ""))
        except (json.JSONDecodeError, AttributeError):
            provider, model = "gemini", ""
    else:
        provider, model = "gemini", ""
    if provider not in PROVIDERS:
        provider = "gemini"
    return AISettings(provider=provider, model=model)


def save_settings(settings: AISettings, path: Path | None = None) -> Path:
    p = path or SETTINGS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"provider": settings.provider,
                             "model": settings.model},
                            ensure_ascii=False, indent=2),
                 encoding="utf-8")
    return p


def save_key_to_dotenv(provider: str, api_key: str,
                       path: Path | None = None) -> Path:
    """키를 .env에 저장 (같은 키가 있으면 교체, 없으면 추가)."""
    env_var = KEY_ENV_VARS.get(provider)
    if env_var is None:
        raise AIError(f"알 수 없는 provider: {provider}")
    p = path or DOTENV_PATH
    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    updated, found = [], False
    for line in lines:
        if line.strip().startswith(env_var + "="):
            updated.append(f"{env_var}={api_key}")
            found = True
        else:
            updated.append(line)
    if not found:
        updated.append(f"{env_var}={api_key}")
    p.write_text("\n".join(updated) + "\n", encoding="utf-8")
    os.environ[env_var] = api_key
    return p


def get_provider(settings: AISettings | None = None) -> AIProvider:
    """현재 설정의 Provider. 키가 없으면 Mock (is_mock=True로 표시)."""
    load_dotenv()
    s = settings or load_settings()
    key = os.environ.get(KEY_ENV_VARS.get(s.provider, ""), "")
    cls = PROVIDERS[s.provider]
    if not key and s.provider != "mock":
        mock = PROVIDERS["mock"]()
        s.is_mock = True
        return mock
    return cls(key, s.effective_model)


def _parse_json_object(text: str) -> dict:
    """모델이 코드펜스나 앞뒤 설명을 붙여도 첫 JSON 객체를 추출."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise AIError(f"JSON 응답이 아님: {text[:120]}")
    try:
        obj = json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        raise AIError(f"JSON 파싱 실패: {text[:120]}") from e
    if not isinstance(obj, dict):
        raise AIError("JSON 객체가 아님")
    return obj


SUGGEST_SYSTEM = (
    "You are an English-Korean dictionary assistant. "
    "Reply with a single JSON object only, no other text. Keys: "
    "meaning_ko (Korean gloss), part_of_speech (e.g. noun), "
    "example_en, example_ko, tags (list of short topic words)."
)


def suggest_word(provider: AIProvider, spelling: str) -> Suggestion:
    """뜻·품사·예문·태그 추천. 저장은 호출자가 (제안으로만 표시)."""
    spelling = spelling.strip()
    if not spelling:
        raise AIError("단어가 비어 있습니다.")
    raw = provider.complete(SUGGEST_SYSTEM, f'Word: "{spelling}"')
    obj = _parse_json_object(raw)
    tags = obj.get("tags", [])
    return Suggestion(
        meaning_ko=str(obj.get("meaning_ko", "")),
        part_of_speech=str(obj.get("part_of_speech", "")),
        example_en=str(obj.get("example_en", "")),
        example_ko=str(obj.get("example_ko", "")),
        tags=[str(t) for t in tags] if isinstance(tags, list) else [],
    )


def ask_about_word(conn: sqlite3.Connection, provider: AIProvider,
                   word_id: int, question: str) -> str:
    """단어 상세 질문. 저장된 뜻·예문을 컨텍스트로 함께 보냄."""
    if not question.strip():
        raise AIError("질문이 비어 있습니다.")
    word = get_word(conn, word_id)
    tags = get_word_tags(conn, word_id)
    lines = [f"Word: {word.spelling}"]
    if tags:
        lines.append("Tags: " + ", ".join(t.name for t in tags))
    for s in word.senses:
        pos = f"({s.part_of_speech}) " if s.part_of_speech else ""
        lines.append(f"- {pos}{s.meaning_ko}")
        if s.example_en:
            lines.append(f"  ex: {s.example_en} / {s.example_ko}")
    context = "\n".join(lines)
    return provider.complete(
        "You are an English tutor for Korean learners. "
        "Answer in Korean, concisely.",
        f"{context}\n\nQuestion: {question.strip()}",
    ).strip()


def suggest_examples(provider: AIProvider, spelling: str, meaning_ko: str,
                     n: int = 3) -> list[tuple[str, str]]:
    """예문 검색: 추가 예문 n개를 (영어, 한국어) 쌍으로."""
    if n < 1 or n > 10:
        raise AIError("예문 수는 1~10이어야 합니다.")
    raw = provider.complete(
        "You are an English tutor. Reply with a single JSON object only: "
        '{"examples": [{"en": "...", "ko": "..."}]}',
        f'Give {n} example sentences for "{spelling.strip()}" '
        f'meaning "{meaning_ko.strip()}" in Korean.',
    )
    obj = _parse_json_object(raw)
    items = obj.get("examples", [])
    if not isinstance(items, list):
        raise AIError("예문 형식이 올바르지 않음")
    return [(str(e.get("en", "")), str(e.get("ko", "")))
            for e in items if isinstance(e, dict)][:n]
