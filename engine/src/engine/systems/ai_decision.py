from engine.entities.store import EntityStore


class AIDecisionSystem:
    def __init__(self, store: EntityStore):
        self._store = store

    def run(self, tick: int, agent_commands: list[dict]) -> list[dict]:
        # Translate raw agent commands into typed intents for other systems
        # Commands arrive pre-parsed from the command queue
        return agent_commands
