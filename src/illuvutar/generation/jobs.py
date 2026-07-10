"""Fixed catalog of 20 jobs the god uses to populate a town."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Job:
    id: str
    title: str
    site: str
    biome: str        # grassland | forest | water | ruins
    blurb: str


JOBS: list[Job] = [
    Job("blacksmith", "Blacksmith", "Forge Lane", "grassland", "shapes iron and steel for the town"),
    Job("carpenter", "Carpenter", "Timber Yard", "grassland", "raises beams and mends roofs"),
    Job("baker", "Baker", "Market Row", "grassland", "bakes the town's daily bread"),
    Job("brewer", "Brewer", "The Malthouse", "grassland", "brews ale for the inn"),
    Job("innkeeper", "Innkeeper", "The Crossroads Inn", "grassland", "keeps beds and gossip for travelers"),
    Job("merchant", "Merchant", "Market Row", "grassland", "trades goods from distant roads"),
    Job("weaver", "Weaver", "Loom Street", "grassland", "spins wool into cloth"),
    Job("tanner", "Tanner", "The Tannery", "grassland", "cures hides at the town's edge"),
    Job("healer", "Healer", "The Infirmary", "grassland", "tends the sick and wounded"),
    Job("priest", "Priest", "Temple Yard", "grassland", "keeps the rites and comforts the grieving"),
    Job("scribe", "Scribe", "The Archive", "grassland", "copies letters and keeps the town's records"),
    Job("watchman", "Watchman", "The Gate", "grassland", "guards the road and watches for strangers"),
    Job("midwife", "Midwife", "Willow Row", "grassland", "births the town's children"),
    Job("potter", "Potter", "The Kiln", "grassland", "throws jars and bowls of river clay"),
    Job("hunter", "Hunter", "The Wood", "forest", "tracks game beneath the canopy"),
    Job("forester", "Forester", "The Wood", "forest", "fells timber and keeps the woodland paths"),
    Job("herbalist", "Herbalist", "The Wood's Edge", "forest", "gathers healing herbs and roots"),
    Job("fisher", "Fisher", "The Docks", "water", "casts nets on the mirror lake"),
    Job("ferryman", "Ferryman", "The Docks", "water", "poles travelers across the lake"),
    Job("scholar", "Scholar", "The Ruined Keep", "ruins", "reads the ruins for lost knowledge"),
]

_NAME_POOLS: dict[str, list[str]] = {
    "blacksmith": ["Bram Ashfoot", "Doren Ironhand", "Sela Cinder"],
    "carpenter": ["Tobin Oakes", "Marta Plank", "Ewan Sawyer"],
    "baker": ["Nessa Crumb", "Aldo Wheatley", "Perrin Dough"],
    "brewer": ["Hollis Mash", "Greta Barley", "Cob Hopwood"],
    "innkeeper": ["Wendel Roon", "Ferra Tallow", "Ottis Ledger"],
    "merchant": ["Silas Vane", "Ruta Coin", "Amberly Trade"],
    "weaver": ["Linna Spindle", "Cael Warp", "Odette Skein"],
    "tanner": ["Garrick Hyde", "Bela Cure", "Nym Leather"],
    "healer": ["Mira Salve", "Edwin Poultice", "Rosa Fenn"],
    "priest": ["Father Alric", "Sister Vesna", "Brother Ode"],
    "scribe": ["Quill Marrow", "Lena Inkwell", "Petro Vellum"],
    "watchman": ["Kael Stern", "Bors Watch", "Dilla Ward"],
    "midwife": ["Anna Willow", "Sefa Birch", "Corra Mild"],
    "potter": ["Jem Clayborn", "Ula Kiln", "Pip Sherd"],
    "hunter": ["Fenn Quiver", "Rue Track", "Alder Snare"],
    "forester": ["Bryn Timber", "Hazel Grove", "Corin Bough"],
    "herbalist": ["Wynn Nettle", "Isolde Root", "Tam Sage"],
    "fisher": ["Marlo Netter", "Sib Roe", "Dunn Cormar"],
    "ferryman": ["Osric Pole", "Vela Reed", "Hob Skiff"],
    "scholar": ["Doran Vale", "Ysra Palimpsest", "Emmet Cairn"],
}


def name_pool(job_id: str) -> list[str]:
    return _NAME_POOLS.get(job_id, ["Wanderer", "Stranger", "Traveler"])
