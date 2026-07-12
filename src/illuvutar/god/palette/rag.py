import json
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from illuvutar.god.palette.indexer import Tile


class PaletteRAG:
    COLLECTION = "palette_tiles"

    def __init__(self, client: chromadb.Client, tiles_by_id: dict[str, Tile]):
        self._client = client
        self._tiles_by_id = tiles_by_id
        self._collection = client.get_collection(
            self.COLLECTION,
            embedding_function=SentenceTransformerEmbeddingFunction(),
        )

    @classmethod
    def build(cls, tiles: list[Tile], persist_dir: str) -> "PaletteRAG":
        client = chromadb.PersistentClient(path=persist_dir)
        ef = SentenceTransformerEmbeddingFunction()
        try:
            client.delete_collection(cls.COLLECTION)
        except Exception:
            pass
        collection = client.create_collection(cls.COLLECTION, embedding_function=ef)

        documents = [
            f"{t.id} layer={t.layer} tags={' '.join(t.tags)} adjacent={' '.join(t.adjacent)}"
            for t in tiles
        ]
        collection.add(
            documents=documents,
            ids=[t.id for t in tiles],
            metadatas=[{"tile_json": json.dumps(t.__dict__)} for t in tiles],
        )

        tiles_by_id = {t.id: t for t in tiles}
        return cls(client, tiles_by_id)

    def query(self, description: str, n: int = 5) -> list[Tile]:
        results = self._collection.query(
            query_texts=[description],
            n_results=min(n, len(self._tiles_by_id)),
        )
        ids = results["ids"][0]
        return [self._tiles_by_id[tile_id] for tile_id in ids if tile_id in self._tiles_by_id]
