"""Model-independent LLM client over any OpenAI-compatible endpoint."""
import json
import os
import re
from dataclasses import dataclass
from openai import OpenAI

DEFAULT_ENDPOINT = "http://localhost:11434/v1"
DEFAULT_MODEL = "llama3.2"


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMMessage:
    content: str
    tool_calls: list  # list[ToolCall]
    raw: dict          # OpenAI-shaped assistant message, ready to append to history


class LLMClient:
    def __init__(self, endpoint: str | None = None, model: str | None = None,
                 api_key: str | None = None):
        self.endpoint = endpoint or os.environ.get("ILLUVUTAR_LLM_ENDPOINT") or DEFAULT_ENDPOINT
        self.model = model or os.environ.get("ILLUVUTAR_LLM_MODEL") or DEFAULT_MODEL
        self.api_key = api_key or os.environ.get("ILLUVUTAR_LLM_API_KEY") or "ollama"
        self._client = OpenAI(base_url=self.endpoint, api_key=self.api_key)

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMMessage:
        resp = self._client.chat.completions.create(
            model=self.model, messages=messages, tools=tools or None,
        )
        m = resp.choices[0].message
        calls, raw_calls = [], []
        for tc in (m.tool_calls or []):
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
            raw_calls.append({"id": tc.id, "type": "function",
                              "function": {"name": tc.function.name,
                                           "arguments": tc.function.arguments}})
        raw = {"role": "assistant", "content": m.content or ""}
        if raw_calls:
            raw["tool_calls"] = raw_calls
        return LLMMessage(content=m.content or "", tool_calls=calls, raw=raw)

    def complete(self, prompt: str) -> str:
        """One-shot, tool-free completion; returns the raw text."""
        resp = self._client.chat.completions.create(
            model=self.model, messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""


def parse_json(text: str):
    """Best-effort JSON extraction that tolerates code fences and surrounding prose."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        if t.endswith("```"):
            t = t[: t.rfind("```")]
    t = t.strip().strip("`").strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    for pat in (r"\[.*\]", r"\{.*\}"):
        m = re.search(pat, t, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                continue
    return None
