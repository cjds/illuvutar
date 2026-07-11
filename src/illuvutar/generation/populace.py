"""Generate a world's populace from god-authored roles: batched, tool-free LLM
generation with deterministic placement and fallback. Never raises."""
from illuvutar.llm.client import parse_json

_NAME_A = ["Vel", "Bram", "Sef", "Cor", "Mira", "Dun", "Hollis", "Wynn", "Tam", "Rue", "Alder", "Isa"]
_NAME_B = ["a", "en", "ric", "wyn", "eth", "os", "il", "ara", "und", "is", "or", "ella"]


def _fallback_name(i: int) -> str:
    return f"{_NAME_A[i % len(_NAME_A)]}{_NAME_B[(i // len(_NAME_A)) % len(_NAME_B)]}"


def _truncate_words(text: str, limit: int) -> str:
    return " ".join((text or "").split()[:limit])


def _regions_for_locale(regions: list[dict], locale: str) -> set[int]:
    """Positional indices of regions whose name matches the role's free-text locale."""
    loc = (locale or "").strip().lower()
    if not loc:
        return set()
    out = set()
    for i, r in enumerate(regions):
        if isinstance(r, dict):
            name = str(r.get("name", "")).strip().lower()
            if name and (name in loc or loc in name):
                out.add(i)
    return out


def _walkable_cells(tilemap, region_ids, walkable):
    out = []
    for c in tilemap:
        if c.get("tile_id") not in walkable:
            continue
        try:
            reg = int(c.get("region", -1))
        except (TypeError, ValueError):
            continue
        if reg in region_ids:
            out.append(c)
    return out


def _batch_prompt(slots, world_name, world_tone):
    lines = [
        f"You are peopling the world of {world_name or 'this land'}.",
        f"Tone: {world_tone or 'a strange and specific place'}.",
        "Invent one distinct resident for each numbered role below.",
        "Respond with ONLY a JSON array, one object per number, in order:",
        '[{"name": "...", "extra_roles": ["<other role ids they also hold, 0-2>"], '
        '"backstory": "2-3 vivid sentences", "goal": "their current aim", '
        '"facts": "one line of self-belief"}]',
        "Roles:",
    ]
    for n, (role, _ids) in enumerate(slots, 1):
        lines.append(f"{n}. {role['title']} — {role.get('blurb','')} "
                     f"(role id: {role['id']}; other ids available: {_ids})")
    return "\n".join(lines)


def generate_populace(roles, tilemap, regions, walkable_tile_ids, client,
                      world_name: str = "", world_tone: str = "",
                      count: int = 40, batch_size: int = 12,
                      facts_word_limit: int = 30, backstory_word_limit: int = 60):
    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 40
    count = max(1, min(count, 1000))
    if not roles:
        roles = [{"id": "townsfolk", "title": "Townsfolk", "locale": "", "blurb": "lives here"}]
    role_ids = {r["id"] for r in roles}
    all_walkable = [c for c in tilemap if c.get("tile_id") in walkable_tile_ids]
    used: set[tuple[int, int]] = set()

    def place(role):
        region_ids = _regions_for_locale(regions, role.get("locale", ""))
        candidates = _walkable_cells(tilemap, region_ids, walkable_tile_ids) or all_walkable
        for c in candidates:
            if (c["x"], c["y"]) not in used:
                return c
        for c in all_walkable:
            if (c["x"], c["y"]) not in used:
                return c
        return (candidates or all_walkable or [{"x": 0, "y": 0}])[0]

    people = []
    for start in range(0, count, batch_size):
        n = min(batch_size, count - start)
        slots = []
        for j in range(n):
            role = roles[(start + j) % len(roles)]
            other = sorted(role_ids - {role["id"]})
            slots.append((role, other))
        # one tool-free call per batch
        entries = []
        try:
            data = parse_json(client.complete(_batch_prompt(slots, world_name, world_tone)))
            if isinstance(data, list):
                entries = data
        except Exception:
            entries = []

        for j, (role, other) in enumerate(slots):
            i = start + j
            e = entries[j] if j < len(entries) and isinstance(entries[j], dict) else {}
            name = str(e.get("name") or _fallback_name(i)).strip() or _fallback_name(i)
            backstory = str(e.get("backstory") or
                            f"{name} has kept to the work of a {role['title'].lower()} for many years.").strip()
            goal = str(e.get("goal") or role.get("blurb", "endure")).strip()
            facts = str(e.get("facts") or f"I am {name}, a {role['title'].lower()}.").strip()
            extra = [r for r in (e.get("extra_roles") or []) if r and r != role["id"]]
            npc_roles = [role["id"]] + extra[:2]
            cell = place(role)
            x, y = int(cell["x"]), int(cell["y"])
            used.add((x, y))
            people.append({
                "id": f"e_{i}", "kind": "humanoid", "x": x, "y": y, "name": name,
                "roles": npc_roles,
                "backstory": _truncate_words(backstory, backstory_word_limit),
                "behavior": goal,
                "facts": _truncate_words(facts, facts_word_limit),
            })
    return people
