"""
llm_provider.py — Thin abstraction over LLM providers so the app is not
tightly coupled to one vendor. Supports Anthropic and OpenAI, and degrades
gracefully to a deterministic rule-based mode if no API key is configured
(so the app is fully runnable/demoable without any credentials).

API keys live only on the backend and are never sent to the frontend.
"""
import json
from config import settings


class LLMProvider:
    """Common interface: generate() and generate_structured()."""

    def is_available(self) -> bool:
        raise NotImplementedError

    def generate(self, system: str, prompt: str, max_tokens: int = 600) -> str:
        raise NotImplementedError

    def generate_structured(self, system: str, prompt: str, schema_hint: str, max_tokens: int = 600) -> dict:
        """Ask the model to return JSON matching schema_hint; parse and return a dict."""
        raise NotImplementedError


class AnthropicProvider(LLMProvider):
    def __init__(self):
        self._client = None
        try:
            import anthropic
            if settings.LLM_API_KEY:
                self._client = anthropic.Anthropic(api_key=settings.LLM_API_KEY)
        except Exception:  # noqa: BLE001
            self._client = None

    def is_available(self) -> bool:
        return self._client is not None

    def generate(self, system: str, prompt: str, max_tokens: int = 600) -> str:
        resp = self._client.messages.create(
            model=settings.LLM_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")

    def generate_structured(self, system: str, prompt: str, schema_hint: str, max_tokens: int = 600) -> dict:
        full_system = f"{system}\n\nRespond ONLY with valid JSON matching this shape, no prose, no markdown fences:\n{schema_hint}"
        text = self.generate(full_system, prompt, max_tokens)
        return _safe_json_parse(text)


class OpenAIProvider(LLMProvider):
    """Also used for any OpenAI-compatible API (e.g. Groq) via LLM_BASE_URL."""

    def __init__(self, base_url: str | None = None):
        self._client = None
        try:
            from openai import OpenAI
            if settings.LLM_API_KEY:
                kwargs = {"api_key": settings.LLM_API_KEY}
                if base_url:
                    kwargs["base_url"] = base_url
                self._client = OpenAI(**kwargs)
        except Exception:  # noqa: BLE001
            self._client = None

    def is_available(self) -> bool:
        return self._client is not None

    def generate(self, system: str, prompt: str, max_tokens: int = 600) -> str:
        resp = self._client.chat.completions.create(
            model=settings.LLM_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""

    def generate_structured(self, system: str, prompt: str, schema_hint: str, max_tokens: int = 600) -> dict:
        full_system = f"{system}\n\nRespond ONLY with valid JSON matching this shape, no prose, no markdown fences:\n{schema_hint}"
        text = self.generate(full_system, prompt, max_tokens)
        return _safe_json_parse(text)


class NullProvider(LLMProvider):
    """Offline fallback: no external calls. agent.py already has deterministic
    templates for explanations, so this provider simply signals unavailability."""

    def is_available(self) -> bool:
        return False

    def generate(self, system: str, prompt: str, max_tokens: int = 600) -> str:
        return ""

    def generate_structured(self, system: str, prompt: str, schema_hint: str, max_tokens: int = 600) -> dict:
        return {}


def _safe_json_parse(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        return {}


def get_provider() -> LLMProvider:
    provider = settings.LLM_PROVIDER.lower()
    if provider == "anthropic":
        p = AnthropicProvider()
    elif provider == "openai":
        p = OpenAIProvider(base_url=settings.LLM_BASE_URL or None)
    elif provider == "groq":
        # Groq exposes an OpenAI-compatible Chat Completions API.
        p = OpenAIProvider(base_url=settings.LLM_BASE_URL or "https://api.groq.com/openai/v1")
    else:
        p = NullProvider()
    return p if p.is_available() else NullProvider()
