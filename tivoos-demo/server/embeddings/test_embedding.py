# server/embeddings/query_faiss.py
import json
import numpy as np
import faiss
import boto3
from dotenv import load_dotenv
import yaml, os

# ---------- 1) Embed the query ----------
def embed_query(query: str, region="us-west-2", model_id="amazon.titan-embed-text-v2:0"):
    """Generate an embedding for a search query using Bedrock Titan Embeddings."""
    load_dotenv()

    with open("server/config.yaml", "r") as fp:
        cfg = yaml.safe_load(fp)
    aws_region = os.getenv("AWS_REGION")
    if aws_region:
        cfg["aws_region"] = aws_region
    aws_profile = os.getenv("AWS_PROFILE_NAME")
    if aws_profile:
        cfg["aws_profile"] = aws_profile

    client = boto3.client("bedrock-runtime", region_name=aws_region)
    resp = client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": query}),
    )
    data = json.loads(resp["body"].read())
    return np.array(data["embedding"], dtype="float32")


# ---------- 2) Search the FAISS index ----------
def search_index(query_emb, index_path="/Users/jigyasa.luthra/work/hackathon/tivoos-demo/server/captions/faiss.index", meta_path="/Users/jigyasa.luthra/work/hackathon/tivoos-demo/server/captions/segments.json", top_k=5):
    index = faiss.read_index(index_path)
    meta = json.load(open(meta_path))
    D, I = index.search(np.array([query_emb]), top_k)
    results = [meta[i] for i in I[0]]
    # for r, dist in zip(results, D[0]):
    #     print(f"[{r['start']} - {r['end']}] ({dist:.2f}) → {r['text'][:120]}...")
    return results


# ---------- 3) Run it ----------
if __name__ == "__main__":
    query = input("Enter your search phrase: ")
    emb = embed_query(query)
    search_index(emb, top_k=5)
