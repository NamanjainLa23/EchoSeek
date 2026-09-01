# server/embeddings/embedder.py
import json
from typing import List, Dict
import numpy as np
import boto3
from server.bedrock_client import TitanModel

class EmbeddingGenerator:
    def __init__(self):
        # self.client = boto3.client("bedrock-runtime", region_name=region)
        # self.model_id = model_id
        self.model = TitanModel()
        self.model.create_bedrock_client()

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        for text in texts:
            result = self.model.call_model(text)
            embeddings.append(result["embedding"])
        return embeddings

    def embed_chunks(self, chunks: List[Dict]) -> List[Dict]:
        texts = [c["text"] for c in chunks]
        embs = self.embed_texts(texts)
        for i, e in enumerate(embs):
            chunks[i]["embedding"] = e
        return chunks
