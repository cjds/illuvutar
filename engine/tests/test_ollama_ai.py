import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock
from engine.entities.store import EntityStore
from engine.entities.components import Position, Label, AIComponent, Tags, PhysicsComponent
from engine.physics.passability import PassabilityMap
from engine.systems.ollama_ai import OllamaAISystem


@pytest.fixture
def store():
    s = EntityStore()
    s.create("wanderer", "humanoid", [
        Position(5, 5),
        Label("Elara the Wanderer"),
        AIComponent(agent_id="wanderer", goal="explore"),
        Tags(["agent"]),
        PhysicsComponent(),
    ])
    return s


@pytest.fixture
def passability():
    tilemap = [["grass"] * 10 for _ in range(10)]
    return PassabilityMap(tilemap=tilemap, rules={"grass": "open"})


@pytest.fixture
def ai_system(store, passability):
    return OllamaAISystem(store=store, passability=passability, model="llama3.2", think_interval=50)


@pytest.mark.asyncio
async def test_ai_does_not_think_before_interval(ai_system):
    """At tick 0, no thinking is scheduled yet."""
    await ai_system.schedule_thinks(tick=0)
    results = await ai_system.drain_results()
    assert results == []


@pytest.mark.asyncio
async def test_ai_schedules_think_at_interval(ai_system):
    """At tick==think_interval, a think is scheduled."""
    mock_response = MagicMock()
    mock_response.message.content = json.dumps({
        "action": "think",
        "thought": "The ruins feel alive with memory.",
    })

    with patch("engine.systems.ollama_ai.ollama") as mock_ollama:
        mock_ollama.AsyncClient.return_value.chat = AsyncMock(return_value=mock_response)
        await ai_system.schedule_thinks(tick=50)
        # Wait for async thinking to complete
        await asyncio.sleep(0.1)
        results = await ai_system.drain_results()

    assert len(results) == 1
    from engine.wrl.schema import WRLThought
    assert isinstance(results[0], WRLThought)
    assert results[0].entity_id == "wanderer"
    assert "ruins" in results[0].text


@pytest.mark.asyncio
async def test_ai_move_action_produces_command(ai_system):
    """A 'move' action produces a Command in drain_results."""
    mock_response = MagicMock()
    mock_response.message.content = json.dumps({
        "action": "move",
        "direction": "north",
        "thought": "I should go north.",
    })

    with patch("engine.systems.ollama_ai.ollama") as mock_ollama:
        mock_ollama.AsyncClient.return_value.chat = AsyncMock(return_value=mock_response)
        await ai_system.schedule_thinks(tick=50)
        await asyncio.sleep(0.1)
        results = await ai_system.drain_results()

    from engine.systems.input import Command
    commands = [r for r in results if isinstance(r, Command)]
    thoughts = [r for r in results if not isinstance(r, Command)]
    assert len(commands) == 1
    assert commands[0].params["direction"] == "north"
    assert len(thoughts) == 1
