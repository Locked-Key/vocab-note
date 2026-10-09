"""7단계: AI 테스트. 실제 네트워크 호출 없음 (urlopen을 가짜로 교체)."""

import io
import json
import os
import urllib.error
import urllib.request

import pytest

from vocab_note.ai.providers import (
    AIError,
    AnthropicProvider,
    GeminiProvider,
    MockProvider,
    OpenAIProvider,
)
from vocab_note.ai.service import (
    AISettings,
    ask_about_word,
    get_provider,
    load_dotenv,
    load_settings,
    save_key_to_dotenv,
    save_settings,
    suggest_examples,
    suggest_word,
)
from vocab_note.db import get_connection, init_db
from vocab_note.vocab_service import add_sense, add_word


class FakeResponse:
    def __init__(self, payload: dict):
        self._data = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture()
def fake_http(monkeypatch):
    """urlopen 가짜. sent 리스트에 Request를 기록하고 canned 응답 반환."""
    sent = []
    canned = {}

    def fake_urlopen(req, timeout=None):
        sent.append(req)
        return FakeResponse(canned["body"])

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return sent, canned


def _body_of(req):
    return json.loads(req.data.decode("utf-8"))


def test_gemini_complete(fake_http):
    sent, canned = fake_http
    canned["body"] = {"candidates": [{"content": {"parts": [
        {"text": '{"meaning_ko": "사과"}'}]}}]}
    out = GeminiProvider("KEY", "gemini-3.7-flash").complete("sys", "hi")
    assert json.loads(out)["meaning_ko"] == "사과"
    assert "generateContent" in sent[0].full_url
    assert sent[0].full_url.endswith("key=KEY")
    body = _body_of(sent[0])
    assert body["contents"][0]["parts"][0]["text"] == "hi"
    assert body["system_instruction"]["parts"][0]["text"] == "sys"


def test_openai_complete(fake_http):
    sent, canned = fake_http
    canned["body"] = {"choices": [{"message": {"content": '{"a": 1}'}}]}
    out = OpenAIProvider("KEY", "gpt-4o-mini").complete("sys", "hi")
    assert json.loads(out) == {"a": 1}
    assert sent[0].full_url == "https://api.openai.com/v1/chat/completions"
    assert sent[0].headers["Authorization"] == "Bearer KEY"
    assert _body_of(sent[0])["model"] == "gpt-4o-mini"


def test_anthropic_complete(fake_http):
    sent, canned = fake_http
    canned["body"] = {"content": [{"type": "text", "text": '{"a": 1}'}]}
    out = AnthropicProvider("KEY", "m").complete("sys", "hi")
    assert json.loads(out) == {"a": 1}
    assert sent[0].headers["X-api-key"] == "KEY"
    assert sent[0].headers["Anthropic-version"] == "2023-06-01"
    body = _body_of(sent[0])
    assert body["system"] == "sys" and body["max_tokens"] == 1024


def test_http_error_becomes_aierror(monkeypatch):
    def fail(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"error": {"message": "bad key"}}'))

    monkeypatch.setattr(urllib.request, "urlopen", fail)
    with pytest.raises(AIError, match="401"):
        GeminiProvider("BAD", "m").complete("s", "u")


def test_url_error_becomes_aierror(monkeypatch):
    def fail(req, timeout=None):
        raise urllib.error.URLError("no route")

    monkeypatch.setattr(urllib.request, "urlopen", fail)
    with pytest.raises(AIError, match="연결 실패"):
        OpenAIProvider("K", "m").complete("s", "u")


def test_mock_suggest_and_test():
    s = suggest_word(MockProvider(), "apple")
    assert "apple" in s.meaning_ko and s.tags == ["mock"]
    assert "mock" in MockProvider().test_connection()


def test_mock_ask_and_examples():
    ask = MockProvider().complete("sys", 'Word: "bank"\n\nQuestion: 둑과 뭐가 달라?')
    assert "둑과 뭐가 달라?" in ask and "Mock 답변" in ask
    pairs = suggest_examples(MockProvider(), "apple", "사과", 2)
    assert len(pairs) == 2 and all(en and ko for en, ko in pairs)


def test_suggest_parses_code_fence():
    class Fence(MockProvider):
        def complete(self, system, user):
            return '```json\n{"meaning_ko": "사과", "tags": ["과일"]}\n```'

    s = suggest_word(Fence(), "apple")
    assert (s.meaning_ko, s.tags) == ("사과", ["과일"])


def test_ask_about_word_uses_saved_senses(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    conn = get_connection(db)
    try:
        w = add_word(conn, "bank")
        add_sense(conn, w.id, "noun", "은행")
        seen = {}

        class Spy(MockProvider):
            def complete(self, system, user):
                seen["user"] = user
                return "둑과의 차이: 강둑은..."

        assert ask_about_word(conn, Spy(), w.id, "둑과 뭐가 달라?") == "둑과의 차이: 강둑은..."
        assert "은행" in seen["user"] and "둑과 뭐가 달라?" in seen["user"]
    finally:
        conn.close()


def test_suggest_examples():
    class Ex(MockProvider):
        def complete(self, system, user):
            return '{"examples": [{"en": "I eat apples.", "ko": "나는 사과를 먹는다."}]}'

    assert suggest_examples(Ex(), "apple", "사과", 3) == [
        ("I eat apples.", "나는 사과를 먹는다.")]
    with pytest.raises(AIError):
        suggest_examples(MockProvider(), "apple", "사과", 0)


def test_settings_roundtrip(tmp_path):
    p = tmp_path / "settings.json"
    save_settings(AISettings(provider="openai", model="gpt-4o"), p)
    loaded = load_settings(p)
    assert (loaded.provider, loaded.effective_model) == ("openai", "gpt-4o")
    assert load_settings(p).is_mock is False
    default = AISettings(provider="gemini")
    assert default.effective_model == "gemini-3.7-flash"
    assert load_settings(tmp_path / "없음.json").provider == "gemini"


def test_dotenv_and_key_save(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('OLD=1\nGEMINI_API_KEY=aaa\n', encoding="utf-8")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OLD", raising=False)
    load_dotenv(env)
    assert os.environ["GEMINI_API_KEY"] == "aaa"
    save_key_to_dotenv("gemini", "bbb", env)
    text = env.read_text(encoding="utf-8")
    assert "GEMINI_API_KEY=bbb" in text and "OLD=1" in text
    assert text.count("GEMINI_API_KEY") == 1


def test_get_provider_mock_without_key(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    s = load_settings(tmp_path / "없음.json")
    provider = get_provider(s)
    assert isinstance(provider, MockProvider) and s.is_mock is True
