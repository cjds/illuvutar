from illuvutar.generation.jobs import JOBS, Job, name_pool

VALID_BIOMES = {"grassland", "forest", "water", "ruins"}


def test_exactly_twenty_unique_jobs():
    assert len(JOBS) == 20
    assert len({j.id for j in JOBS}) == 20


def test_all_fields_present_and_valid():
    for j in JOBS:
        assert isinstance(j, Job)
        assert j.id and j.title and j.site and j.blurb
        assert j.biome in VALID_BIOMES


def test_name_pool_has_options_for_every_job():
    for j in JOBS:
        assert len(name_pool(j.id)) >= 3
