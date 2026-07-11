"""SpecialistAgent: a focused agent driven by a YAML mandate file."""
from pathlib import Path
import yaml
from illuvutar.agents.tools import AgentTools
from illuvutar.llm.client import LLMClient


class SpecialistAgent:
    def __init__(self, client: LLMClient, mandate_path: Path, tools: AgentTools):
        self.client = client
        self.tools = tools
        mandate = yaml.safe_load(Path(mandate_path).read_text())
        self.mandate = mandate

        context_parts = [
            f"You are a specialist agent with role: {mandate['role']}.",
            f"Task: {mandate['task']}",
        ]
        if mandate.get("constraints"):
            context_parts.append(
                "Constraints:\n" + "\n".join(f"- {c}" for c in mandate["constraints"])
            )
        if mandate.get("read_files"):
            for fname in mandate["read_files"]:
                content = tools.read_file(fname)
                context_parts.append(f"[{fname}]\n{content}")
        context_parts.append(
            f"When done, write your output using the write_world_state tool to file '{mandate['output_file']}'."
        )

        self.messages = [
            {"role": "system", "content": "\n\n".join(context_parts)},
            {"role": "user", "content": "Begin your task."},
        ]

    def run(self) -> str:
        tool_defs = AgentTools.definitions()
        while True:
            msg = self.client.chat(self.messages, tools=tool_defs or None)
            self.messages.append(msg.raw)

            if not msg.tool_calls:
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
            return f"Tool error: {e}"
