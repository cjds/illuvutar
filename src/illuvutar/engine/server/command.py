import tomlkit
from dataclasses import dataclass


@dataclass
class RawCommand:
    agent_id: str
    action: str
    params: dict


def parse_command(toml_str: str) -> RawCommand | None:
    try:
        doc = tomlkit.loads(toml_str)
        cmd = doc.get("command", {})
        return RawCommand(
            agent_id=str(cmd.get("agent_id", "")),
            action=str(cmd.get("action", "")),
            params={k: v for k, v in cmd.items() if k not in ("agent_id", "action", "tick_submitted")},
        )
    except Exception:
        return None
