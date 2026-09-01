from typing import List, Dict
from server.local_client import LocalEmbedder

class EmbeddingGenerator:
    def __init__(self):
        self.model = LocalEmbedder()

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return self.model.embed_batch(texts)

    def embed_chunks(self, chunks: List[Dict]) -> List[Dict]:
        texts = [c["text"] for c in chunks]
        embs = self.embed_texts(texts)
        for i, emb in enumerate(embs):
            chunks[i]["embedding"] = emb
        return chunks
    
