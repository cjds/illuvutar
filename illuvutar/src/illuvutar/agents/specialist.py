"""SpecialistAgent: a focused agent driven by a YAML mandate file."""
from pathlib import Path
import yaml
import ollama
from illuvutar.agents.tools import AgentTools


class SpecialistAgent:
    def __init__(self, model: str, mandate_path: Path, tools: AgentTools):
        self.model = model
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
            response = ollama.chat(
                model=self.model, messages=self.messages, tools=tool_defs or None
            )
            msg = response.message
            self.messages.append({"role": "assistant", "content": msg.content or ""})

            if not msg.tool_calls:
                return msg.content or ""

            for tc in msg.tool_calls:
                result = self._dispatch(tc.function.name, tc.function.arguments)
                self.messages.append({"role": "tool", "content": str(result)})

    def _dispatch(self, name: str, args: dict) -> str:
        method = getattr(self.tools, name, None)
        if method is None:
            return f"Unknown tool: {name}"
        try:
            return method(**args)
        except Exception as e:
            return f"Tool error: {e}"
