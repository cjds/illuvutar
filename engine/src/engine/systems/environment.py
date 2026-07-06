from engine.entities.store import EntityStore


class EnvironmentSystem:
    def __init__(self, store: EntityStore):
        self._store = store
        self.tick_of_day = 0
        self.day_length_ticks = 1200  # 2 minutes at 10 ticks/sec

    def run(self, tick: int) -> dict:
        self.tick_of_day = tick % self.day_length_ticks
        hour = (self.tick_of_day / self.day_length_ticks) * 24
        return {"hour": hour}
