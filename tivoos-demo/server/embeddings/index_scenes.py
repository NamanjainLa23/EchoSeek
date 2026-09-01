from __future__ import annotations
from pathlib import Path
import json, faiss, numpy as np
# from .embedder import EmbeddingGenerator  # your existing embedder
from .local_embedder import EmbeddingGenerator

def build_scenes_index(video_id: str,
                       scenes_jsonl: Path = None,
                       out_dir: Path = None):
    scenes_jsonl = scenes_jsonl or Path("data/scenes")/video_id/"scenes.jsonl"
    out_dir = out_dir or Path("data/index")/video_id
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    with scenes_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))

    texts = [r.get("embed_text","").strip() for r in rows]
    # filter empty
    keep = [i for i,t in enumerate(texts) if t]
    rows = [rows[i] for i in keep]; texts = [texts[i] for i in keep]
    if not texts:
        raise RuntimeError("No non-empty embed_text to index.")

    eg = EmbeddingGenerator()
    if hasattr(eg, "embed_texts"):
        vecs = np.asarray(eg.embed_texts(texts), dtype="float32")
    else:
        vecs = np.asarray([x["embedding"] for x in eg.embed_chunks([{"text":t} for t in texts])], dtype="float32")

    dim = vecs.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(vecs)

    faiss.write_index(index, str(out_dir/"faiss_scenes.index"))
    (out_dir/"scenes_meta.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_dir/'faiss_scenes.index'} and scenes_meta.json ({len(rows)} rows)")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--scenes", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    build_scenes_index(a.video_id,
                       scenes_jsonl=Path(a.scenes) if a.scenes else None,
                       out_dir=Path(a.out) if a.out else None)
