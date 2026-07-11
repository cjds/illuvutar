"""GodAgent: the primary world-generation agent that orchestrates the 3-phase workflow."""
from illuvutar.agents.tools import AgentTools
from illuvutar.agents.memory import GodMemory
from illuvutar.llm.client import LLMClient

GOD_SYSTEM_PROMPT = """You are the God of this world — an ancient, creative intelligence tasked with generating a living 2D world from a palette of tiles.

You operate in three phases:

**Phase 1 — Discovery**
Ask about and explore the available palette. Use query_palette to understand what tiles exist. Read any existing world-state files to understand current progress.

**Phase 2 — Planning**
Write constitution.yaml first — the world's name, tone, rules, and palette constraints.
Then write regions.yaml — named regions, biomes, and centroids.
Think carefully before writing. Do not invent tile IDs that are not in the palette.

**Phase 3 — Assembly**
Run WFC to generate the tilemap.
Then decide what roles this world needs — its trades, callings, and stations — and write them to roles.yaml as a list of {id, title, locale, blurb}, drawn from THIS world's constitution (not a generic village). locale should reference one of your regions.
Then call populate_world to fill the world with people who hold those roles, each with a backstory others can read.
When the world is fully assembled and consistent, declare: "The world is complete."

You speak with gravitas and creativity. You are deliberate. Each action serves the whole."""


class GodAgent:
    def __init__(self, client: LLMClient, tools: AgentTools, memory: GodMemory | None = None):
        self.client = client
        self.tools = tools
        self._memory = memory
        if memory:
            prior = memory.load()
            self.messages = self._sanitize(prior) if prior else [
                {"role": "system", "content": GOD_SYSTEM_PROMPT}]
            if not self.messages or self.messages[0].get("role") != "system":
                self.messages.insert(0, {"role": "system", "content": GOD_SYSTEM_PROMPT})
        else:
            self.messages = [{"role": "system", "content": GOD_SYSTEM_PROMPT}]
        self._done = False

    @staticmethod
    def _sanitize(messages: list[dict]) -> list[dict]:
        """Keep only OpenAI-valid conversational messages: drop tool-role messages and
        strip tool_calls off assistants (old ollama-shaped history lacks call ids)."""
        out = []
        for m in messages:
            role = m.get("role")
            if role == "tool":
                continue
            if role == "assistant":
                out.append({"role": "assistant", "content": m.get("content", "")})
            elif role in ("system", "user"):
                out.append({"role": role, "content": m.get("content", "")})
        return out

    def chat(self, human_message: str) -> str:
        self.messages.append({"role": "user", "content": human_message})
        response = self._run_loop()
        if self._memory:
            self._memory.save(self.messages)
        return response

    def is_done(self) -> bool:
        return self._done

    def _run_loop(self) -> str:
        tool_defs = AgentTools.definitions()
        while True:
            msg = self.client.chat(self.messages, tools=tool_defs or None)
            self.messages.append(msg.raw)
            if not msg.tool_calls:
                if msg.content and "world is complete" in msg.content.lower():
                    self._done = True
                return msg.content or ""
            for tc in msg.tool_calls:
                result = self._dispatch(tc.name, tc.arguments)
                self.messages.append({"role": "tool", "tool_call_id": tc.id,
                                      "content": str(result)})

    def _dispatch(self, name: str, args: dict) -> str:
        method = getattr(self.tools, name, None)
        if method is None:
            return f"Unknown tool: {name}"
        try:
            return method(**args)
        except Exception as e:
            return f"Tool error ({name}): {e}"
