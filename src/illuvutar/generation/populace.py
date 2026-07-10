"""Generate a town populace: one NPC per job, placed on walkable tiles, with per-NPC
LLM-generated backstories and a deterministic fallback so it never fails."""
import json
import ollama
from illuvutar.generation.jobs import Job, name_pool

_KIND_FOR_JOB = {"scholar": "scholar", "watchman": "guardian"}  # reuse existing sprites


def _truncate_words(text: str, limit: int) -> str:
    return " ".join((text or "").split()[:limit])


def _region_ids_for_biome(regions: list[dict], biome: str) -> set[int]:
    return {int(r["id"]) for r in regions if r.get("biome") == biome}


def _walkable_cells(tilemap: list[dict], region_ids: set[int], walkable: set[str]) -> list[dict]:
    cells = [c for c in tilemap
             if c.get("tile_id") in walkable and int(c.get("region", -1)) in region_ids]
    return cells


def _prompt(job: Job, world_name: str, world_tone: str) -> str:
    return (
        f"Invent a resident of the town of {world_name or 'the crossroads'}.\n"
        f"Tone: {world_tone or 'a quiet world of forest, ruin, and still water'}.\n"
        f"They are the {job.title} at {job.site} — they {job.blurb}.\n"
        "Respond with ONLY valid JSON (no markdown):\n"
        '{"name": "...", "backstory": "2-3 vivid sentences of their history", '
        '"goal": "their current aim", "facts": "one line of self-belief"}'
    )


def generate_populace(
    jobs: list[Job],
    tilemap: list[dict],
    regions: list[dict],
    walkable_tile_ids: set[str],
    model: str,
    world_name: str = "",
    world_tone: str = "",
    facts_word_limit: int = 30,
    backstory_word_limit: int = 60,
) -> list[dict]:
    all_walkable = [c for c in tilemap if c.get("tile_id") in walkable_tile_ids]
    used: set[tuple[int, int]] = set()
    people: list[dict] = []

    for i, job in enumerate(jobs):
        # --- placement (deterministic): prefer the job's biome region ---
        region_ids = _region_ids_for_biome(regions, job.biome)
        candidates = _walkable_cells(tilemap, region_ids, walkable_tile_ids) or all_walkable
        cell = None
        for c in candidates:
            if (c["x"], c["y"]) not in used:
                cell = c
                break
        if cell is None:  # every candidate taken — reuse any free walkable cell
            for c in all_walkable:
                if (c["x"], c["y"]) not in used:
                    cell = c
                    break
        if cell is None:  # map has fewer walkable tiles than jobs — stack as last resort
            cell = (candidates or all_walkable or [{"x": 0, "y": 0}])[0]
        x, y = int(cell["x"]), int(cell["y"])
        used.add((x, y))

        # --- generation (per-NPC LLM with deterministic fallback) ---
        pool = name_pool(job.id)
        name = pool[i % len(pool)]
        backstory = f"{name} has served as the {job.title} of {job.site} for many years."
        goal = job.blurb
        facts = f"I am {name}, the {job.title}."
        try:
            resp = ollama.chat(model=model, messages=[{"role": "user",
                     "content": _prompt(job, world_name, world_tone)}])
            data = json.loads((resp.message.content or "").strip().strip("`"))
            name = str(data.get("name") or name).strip() or name
            backstory = str(data.get("backstory") or backstory).strip() or backstory
            goal = str(data.get("goal") or goal).strip() or goal
            facts = str(data.get("facts") or facts).strip() or facts
        except Exception:
            pass  # deterministic fallback values already set

        people.append({
            "id": job.id,
            "kind": _KIND_FOR_JOB.get(job.id, "humanoid"),
            "x": x, "y": y,
            "name": name,
            "job": job.title,
            "backstory": _truncate_words(backstory, backstory_word_limit),
            "behavior": goal,
            "facts": _truncate_words(facts, facts_word_limit),
        })
    return people
