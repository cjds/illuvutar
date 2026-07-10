"""Entry point: python -m engine  OR  illuvutar-engine"""
import argparse
import uvicorn
from pathlib import Path
from engine.loader import load_world
from engine.server.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="illuvutar simulation engine")
    parser.add_argument("world_dir", help="Path to world-state directory")
    parser.add_argument("--port", type=int, default=8080, help="HTTP port (default 8080)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--ai-model", default="llama3.2", help="Ollama model for entity AI")
    parser.add_argument("--memory-words", type=int, default=None,
                        help="Override entity memory word limit (else constitution/default)")
    parser.add_argument("--facts-words", type=int, default=None,
                        help="Override entity identity-facts word limit")
    args = parser.parse_args()

    world_dir = Path(args.world_dir)
    if not world_dir.is_dir():
        print(f"Error: {world_dir} is not a directory")
        raise SystemExit(1)

    print(f"Loading world from {world_dir}...")
    data = load_world(world_dir, memory_word_limit=args.memory_words,
                      facts_word_limit=args.facts_words)
    print(f"  World: {data.world_id}  ({data.width}×{data.height})  "
          f"entities: {len(list(data.store.all_ids()))}")

    app = create_app(
        store=data.store,
        passability=data.passability,
        palette=data.palette,
        tilemap_data=data.tilemap_data,
        world_id=data.world_id,
        width=data.width,
        height=data.height,
        sprite_dir=data.sprite_dir,
        ai_model=args.ai_model,
        world_dir=world_dir,
    )
    print(f"Engine ready. Open http://{args.host}:{args.port} in your browser.")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
