"""GodAgent: the primary world-generation agent that orchestrates the 3-phase workflow."""
import ollama
from illuvutar.agents.tools import AgentTools

GOD_SYSTEM_PROMPT = """You are the God of this world — an ancient, creative intelligence tasked with generating a living 2D world from a palette of tiles.

You operate in three phases:

**Phase 1 — Discovery**
Ask about and explore the available palette. Use query_palette to understand what tiles exist. Read any existing world-state files to understand current progress.

**Phase 2 — Planning**
Write constitution.yaml first — the world's name, tone, rules, and palette constraints.
Then write regions.yaml — named regions, biomes, and centroids.
Think carefully before writing. Do not invent tile IDs that are not in the palette.

**Phase 3 — Assembly**
Spawn specialist agents as needed to flesh out factions, history, or initial agent placements.
Run WFC to generate the tilemap.
When the world is fully assembled and consistent, declare: "The world is complete."

You speak with gravitas and creativity. You are deliberate. Each action serves the whole."""


class GodAgent:
    def __init__(self, model: str, tools: AgentTools):
        self.model = model
        self.tools = tools
        self.messages: list[dict] = [{"role": "system", "content": GOD_SYSTEM_PROMPT}]
        self._done = False

    def chat(self, human_message: str) -> str:
        self.messages.append({"role": "user", "content": human_message})
        return self._run_loop()

    def is_done(self) -> bool:
        return self._done

    def _run_loop(self) -> str:
        tool_defs = AgentTools.definitions()
        while True:
            response = ollama.chat(
                model=self.model,
                messages=self.messages,
                tools=tool_defs if tool_defs else None,
            )
            msg = response.message
            self.messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in (msg.tool_calls or [])
                ],
            })

            if not msg.tool_calls:
                if msg.content and "world is complete" in msg.content.lower():
                    self._done = True
                return msg.content or ""

            for tool_call in msg.tool_calls:
                result = self._dispatch(tool_call.function.name, tool_call.function.arguments)
                self.messages.append({"role": "tool", "content": str(result)})

    def _dispatch(self, name: str, args: dict) -> str:
        method = getattr(self.tools, name, None)
        if method is None:
            return f"Unknown tool: {name}"
        try:
            return method(**args)
        except Exception as e:
            return f"Tool error ({name}): {e}"
