from engine.entities.store import EntityStore
from engine.entities.components import Inventory, ItemStack


class InventorySystem:
    def __init__(self, store: EntityStore):
        self._store = store

    def run(self, tick: int, transfer_intents: list[dict]) -> list[dict]:
        events = []
        for intent in transfer_intents:
            if intent["action"] == "pick_up":
                inv = self._store.get_component(intent["entity_id"], Inventory)
                if inv and len(inv.slots) < inv.capacity:
                    inv.slots.append(ItemStack(item_id=intent["item_id"]))
                    inv.carrying = intent["item_id"]
                    events.append({"kind": "item_picked_up", "entity": intent["entity_id"], "item": intent["item_id"]})
        return events
