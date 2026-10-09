"""7단계: LLM Provider 추상화. 앱은 AIProvider만 보고, 업체 차이는 각 클래스 안에.

- 전송: 표준 urllib만 사용 (의존성 없음)
- 업체별 차이(인증·요청·응답)는 complete()가 흡수하고 텍스트만 반환
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field


class AIError(Exception):
    """인증·쿼터·타임아웃 등 AI 호출 실패 (키 값은 절대 포함하지 않음)."""


@dataclass
class Suggestion:
    meaning_ko: str = ""
    part_of_speech: str = ""
    example_en: str = ""
    example_ko: str = ""
    tags: list[str] = field(default_factory=list)


def _post_json(url: str, headers: dict, payload: dict, timeout: int = 30) -> dict:
    """JSON POST 후 dict 반환. HTTP/네트워크 오류는 AIError로 변환."""
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode("utf-8", "replace"))
            msg = detail.get("error", {}).get("message") or detail.get("error") or e
        except Exception:
            msg = e
        raise AIError(f"API 오류 ({e.code}): {msg}") from e
    except urllib.error.URLError as e:
        raise AIError(f"연결 실패: {e.reason}") from e
    except TimeoutError as e:
        raise AIError("시간 초과 (30초)") from e


class AIProvider:
    """인터페이스. complete()만 구현하면 새 업체 추가 끝."""

    name = "base"

    def __init__(self, api_key: str, model: str):
        if not api_key or not api_key.strip():
            raise AIError("API 키가 없습니다.")
        self.api_key = api_key.strip()
        self.model = model

    def complete(self, system: str, user: str) -> str:
        raise NotImplementedError

    def test_connection(self) -> str:
        """저비용 실호출. 성공 시 모델 정보 문자열, 실패 시 AIError."""
        out = self.complete("Reply with exactly: OK", "Reply with exactly: OK")
        if "OK" not in out:
            raise AIError(f"예상과 다른 응답: {out[:100]}")
        return f"{self.name}/{self.model} 연결 OK"


class GeminiProvider(AIProvider):
    name = "gemini"

    def _url(self) -> str:
        return (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )

    def complete(self, system: str, user: str) -> str:
        # 키는 URL 쿼리로 전달 (Gemini 방식). 로그·예외에 URL을 담지 않음.
        data = _post_json(
            self._url() + "?key=" + self.api_key,
            {},
            {"system_instruction": {"parts": [{"text": system}]},
             "contents": [{"parts": [{"text": user}]}],
             "generationConfig": {"temperature": 0.2,
                                  "responseMimeType": "application/json"}},
        )
        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, TypeError) as e:
            raise AIError(f"응답 파싱 실패: {str(data)[:150]}") from e


class OpenAIProvider(AIProvider):
    name = "openai"

    def complete(self, system: str, user: str) -> str:
        data = _post_json(
            "https://api.openai.com/v1/chat/completions",
            {"Authorization": "Bearer " + self.api_key},
            {"model": self.model, "temperature": 0.2,
             "response_format": {"type": "json_object"},
             "messages": [{"role": "system", "content": system},
                          {"role": "user", "content": user}]},
        )
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise AIError(f"응답 파싱 실패: {str(data)[:150]}") from e


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def complete(self, system: str, user: str) -> str:
        data = _post_json(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            {"model": self.model, "max_tokens": 1024, "temperature": 0.2,
             "system": system,
             "messages": [{"role": "user", "content": user}]},
        )
        try:
            texts = [b.get("text", "") for b in data["content"]
                     if b.get("type") == "text"]
            return "".join(texts)
        except (KeyError, TypeError) as e:
            raise AIError(f"응답 파싱 실패: {str(data)[:150]}") from e


class MockProvider(AIProvider):
    """키 없을 때·테스트용. 네트워크 호출 없음."""

    name = "mock"

    def __init__(self, api_key: str = "mock", model: str = "mock"):
        self.api_key = api_key
        self.model = model

    def complete(self, system: str, user: str) -> str:
        import re

        m = re.search(r'"([^"]+)"', user)
        word = m.group(1) if m else (user.split()[0] if user.split() else "word")
        if "Question:" in user:
            question = user.split("Question:", 1)[1].strip()
            return (f"Mock 답변입니다. '{question}'에 대한 실제 답변은 "
                    f"API 키를 설정하면 받을 수 있습니다.")
        if "example sentences" in user:
            return json.dumps({
                "examples": [
                    {"en": f"This is an example with {word}.",
                     "ko": f"{word} 예문입니다(Mock)."},
                    {"en": f"She likes {word}.",
                     "ko": f"그녀는 {word}을(를) 좋아합니다(Mock)."},
                ],
            }, ensure_ascii=False)
        return json.dumps({
            "meaning_ko": f"{word}의 뜻(Mock)",
            "part_of_speech": "noun",
            "example_en": f"This is an example with {word}.",
            "example_ko": f"{word} 예문입니다(Mock).",
            "tags": ["mock"],
        }, ensure_ascii=False)

    def test_connection(self) -> str:
        return "mock 연결 OK (실제 호출 없음)"


PROVIDERS: dict[str, type[AIProvider]] = {
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "mock": MockProvider,
}

DEFAULT_MODELS = {
    "gemini": "gemini-3.7-flash",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-latest",
}

KEY_ENV_VARS = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}
