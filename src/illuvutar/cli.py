"""CLI entry point for illuvutar world generation."""
import click


@click.group()
def main():
    pass


@main.command()
def create_world():
    """Deprecated — build worlds in the studio: `studio --palette <dir> --world <dir>`."""
    raise SystemExit("world-building moved to the studio: `studio --palette <dir> --world <dir>`")
