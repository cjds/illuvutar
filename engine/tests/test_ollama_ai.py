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


from engine.entities.components import Mind


@pytest.fixture
def store_with_mind():
    s = EntityStore()
    s.create("wanderer", "humanoid", [
        Position(5, 5),
        Label("Elara"),
        AIComponent(agent_id="wanderer", goal="explore"),
        Tags(["agent"]),
        PhysicsComponent(),
        Mind(memory="I passed the old well", facts="I am curious",
             memory_word_limit=60, facts_word_limit=30),
    ])
    return s


def _mock_decision(**fields):
    mock_response = MagicMock()
    mock_response.message.content = json.dumps({"action": "think",
                                                "thought": "hmm", **fields})
    return mock_response


@pytest.mark.asyncio
async def test_prompt_includes_memory_and_facts(store_with_mind, passability, tmp_path):
    sys = OllamaAISystem(store_with_mind, passability, world_dir=tmp_path)
    captured = {}

    async def fake_chat(*, model, messages):
        captured["prompt"] = messages[0]["content"]
        return _mock_decision()

    with patch("engine.systems.ollama_ai.ollama") as mock_ollama:
        mock_ollama.AsyncClient.return_value.chat = AsyncMock(side_effect=fake_chat)
        await sys.schedule_thinks(tick=50)
        await asyncio.sleep(0.1)
        await sys.drain_results()

    assert "I passed the old well" in captured["prompt"]
    assert "I am curious" in captured["prompt"]
    assert "60" in captured["prompt"] and "30" in captured["prompt"]


@pytest.mark.asyncio
async def test_decision_rewrites_memory_facts_goal_and_persists(store_with_mind, passability, tmp_path):
    sys = OllamaAISystem(store_with_mind, passability, world_dir=tmp_path)
    with patch("engine.systems.ollama_ai.ollama") as mock_ollama:
        mock_ollama.AsyncClient.return_value.chat = AsyncMock(
            return_value=_mock_decision(memory="I now recall the storm",
                                        facts="I fear lightning",
                                        set_goal="find shelter"))
        await sys.schedule_thinks(tick=50)
        await asyncio.sleep(0.1)
        await sys.drain_results()

    mind = store_with_mind.get_component("wanderer", Mind)
    ai = store_with_mind.get_component("wanderer", AIComponent)
    assert mind.memory == "I now recall the storm"
    assert mind.facts == "I fear lightning"
    assert ai.goal == "find shelter"
    # persisted to disk
    from engine.entities.persistence import load_entity_state
    assert load_entity_state(tmp_path, "wanderer")["goal"] == "find shelter"


@pytest.mark.asyncio
async def test_overlimit_memory_is_truncated(passability, tmp_path):
    s = EntityStore()
    s.create("w", "humanoid", [
        Position(1, 1), Label("W"), AIComponent(agent_id="w", goal="g"),
        Tags(["agent"]), PhysicsComponent(),
        Mind(memory_word_limit=3, facts_word_limit=3),
    ])
    sys = OllamaAISystem(s, passability, world_dir=tmp_path)
    with patch("engine.systems.ollama_ai.ollama") as mock_ollama:
        mock_ollama.AsyncClient.return_value.chat = AsyncMock(
            return_value=_mock_decision(memory="one two three four five"))
        await sys.schedule_thinks(tick=50)
        await asyncio.sleep(0.1)
        await sys.drain_results()
    assert s.get_component("w", Mind).memory == "one two three"


@pytest.mark.asyncio
async def test_flush_all_writes_every_ai_entity(store_with_mind, passability, tmp_path):
    sys = OllamaAISystem(store_with_mind, passability, world_dir=tmp_path)
    sys.flush_all()
    from engine.entities.persistence import load_entity_state
    state = load_entity_state(tmp_path, "wanderer")
    assert state is not None
    assert state["memory"] == "I passed the old well"
