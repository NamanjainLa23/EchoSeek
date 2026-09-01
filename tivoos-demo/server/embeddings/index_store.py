# server/embeddings/index_store.py
from __future__ import annotations
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import faiss
import numpy as np

# IMPORTANT: run from repo root using module mode:
#   python -m server.embeddings.index_store --video-id GhbWy6d23k4
# from embedder import EmbeddingGenerator
from .local_embedder import EmbeddingGenerator

# ---------- Paths ----------
ROOT = Path(__file__).resolve().parents[2]          # .../tivoos-demo
DATA_DIR = ROOT / "data" / "index"                  # per-video: data/index/<VIDEO_ID>/
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ---------- FAISS Wrapper ----------
class SubtitleIndex:
    """
    Thin wrapper over a FAISS index + a parallel meta.json.
    One instance per VIDEO_ID (directory: data/index/<video_id>/).
    Stores only lightweight metadata: {video_id, timestamp, end, text}
    """
    def __init__(self, dim: int, index_path: Path, meta_path: Path, metric: str = "l2"):
        """
        metric: 'l2' (IndexFlatL2; lower is better) or 'ip' (IndexFlatIP; higher is better).
        For 'ip', you typically use normalized vectors for cosine similarity.
        """
        metric = metric.lower()
        if metric not in {"l2", "ip"}:
            raise ValueError("metric must be 'l2' or 'ip'")

        self.metric = metric
        self.index_path = Path(index_path)
        self.meta_path = Path(meta_path)

        if metric == "l2":
            self.index = faiss.IndexFlatL2(dim)
        else:
            self.index = faiss.IndexFlatIP(dim)

        self.meta: List[Dict] = []

    def add(self, vectors: np.ndarray, meta_rows: List[Dict]):
        if not isinstance(vectors, np.ndarray):
            vectors = np.asarray(vectors, dtype="float32")
        if vectors.dtype != np.float32:
            vectors = vectors.astype("float32")

        # If using IP/cosine, you likely want normalized vectors
        if self.metric == "ip":
            faiss.normalize_L2(vectors)

        self.index.add(vectors)
        self.meta.extend(meta_rows)

    def save(self):
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path))
        self.meta_path.write_text(json.dumps(self.meta, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self):
        self.index = faiss.read_index(str(self.index_path))
        self.meta = json.loads(self.meta_path.read_text(encoding="utf-8"))

    def search(self, query_emb: np.ndarray, k: int = 5) -> List[Dict]:
        if query_emb.ndim == 1:
            query_emb = query_emb[None, :]
        q = query_emb.astype("float32")

        # Normalize for IP/cosine if used
        if self.metric == "ip":
            faiss.normalize_L2(q)

        D, I = self.index.search(q, k)
        out: List[Dict] = []
        for i, d in zip(I[0], D[0]):
            if i < 0:
                continue
            row = self.meta[i]
            out.append({**row, "score": float(d)})
        # l2: lower is better; ip: higher is better
        out.sort(key=lambda r: r["score"], reverse=(self.metric == "ip"))
        return out


# ---------- Helpers ----------
def _load_segments_json(video_dir: Path) -> Tuple[str, List[Dict]]:
    """
    Reads data/index/<video_id>/segments.json and returns (video_id, segments)
    Expected segment shape:
      { "video_id": "<id>", "start": <sec>, "end": <sec>, "text": "...", ... }
    """
    seg_path = video_dir / "segments.json"
    if not seg_path.exists():
        raise FileNotFoundError(f"segments.json not found at {seg_path}")
    segs = json.loads(seg_path.read_text(encoding="utf-8"))
    if not isinstance(segs, list) or not segs:
        raise ValueError(f"segments.json at {seg_path} is empty or invalid")

    v_id = segs[0].get("video_id") or video_dir.name
    return v_id, segs


def _ensure_vectors(embedder: EmbeddingGenerator, segs: List[Dict]) -> np.ndarray:
    """
    Embeds each segment's 'text'. Tries to use a batch API if available.
    Returns np.ndarray of shape (N, D), dtype float32
    """
    texts = [s.get("text", "") for s in segs]

    # Try common method names the user's embedder might have
    vectors: Optional[List[List[float]]] = None
    if hasattr(embedder, "embed_texts"):
        vectors = embedder.embed_texts(texts)
    elif hasattr(embedder, "embed_chunks"):
        # Some versions accept a list[dict] and put "embedding" back in each dict
        embedded = embedder.embed_chunks([{"text": t} for t in texts])
        vectors = [e["embedding"] for e in embedded]
    elif hasattr(embedder, "embed_text"):
        vectors = [embedder.embed_text(t) for t in texts]
    else:
        raise AttributeError("EmbeddingGenerator is missing embed_texts/embed_chunks/embed_text")

    arr = np.asarray(vectors, dtype="float32")
    if arr.ndim != 2:
        raise ValueError(f"Embeddings shape invalid: {arr.shape} (expected 2-D)")
    return arr


def build_index_for_video(video_id: str, metric: str = "l2", overwrite: bool = True) -> Path:
    """
    Builds FAISS index + meta.json for a single video id.
    Reads:  data/index/<video_id>/segments.json
    Writes: data/index/<video_id>/{faiss.index, meta.json}
    """
    video_dir = DATA_DIR / video_id
    video_dir.mkdir(parents=True, exist_ok=True)

    faiss_path = video_dir / "faiss.index"
    meta_path = video_dir / "meta.json"

    if faiss_path.exists() and meta_path.exists() and not overwrite:
        print(f"[skip] {video_id} already has an index. Use --overwrite to rebuild.")
        return faiss_path

    v_id, segs = _load_segments_json(video_dir)

    # Build meta rows (no embeddings here)
    meta_rows: List[Dict] = []
    for s in segs:
        meta_rows.append({
            "video_id": v_id,
            "timestamp": int(s.get("start", 0)),
            "end": int(s.get("end", s.get("start", 0))),
            "text": s.get("text", "")
        })

    # Embed
    embedder = EmbeddingGenerator()
    vectors = _ensure_vectors(embedder, segs)
    dim = vectors.shape[1]

    # Create index
    idx = SubtitleIndex(dim=dim, index_path=faiss_path, meta_path=meta_path, metric=metric)
    idx.add(vectors, meta_rows)
    idx.save()

    print(f"[ok] Built index for {video_id} → {faiss_path}")
    return faiss_path


def build_all_indices(metric: str = "l2", overwrite: bool = False) -> List[str]:
    """
    Scans data/index/*/segments.json and builds indices for all videos found.
    """
    built: List[str] = []
    for child in DATA_DIR.iterdir():
        if not child.is_dir():
            continue
        seg_path = child / "segments.json"
        if not seg_path.exists():
            continue
        vid = child.name
        try:
            build_index_for_video(vid, metric=metric, overwrite=overwrite)
            built.append(vid)
        except Exception as e:
            print(f"[err] Failed building index for {vid}: {e}")
    if built:
        print(f"[ok] Built indices for: {', '.join(built)}")
    else:
        print("[warn] No segments.json found under data/index/*/")
    return built


# ---------- CLI ----------
def _parse_args():
    ap = argparse.ArgumentParser(description="Build per-video FAISS indices from merged segments.json.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--video-id", help="Build index for a single video id (expects data/index/<id>/segments.json)")
    g.add_argument("--all", action="store_true", help="Build indices for all data/index/*/segments.json")
    ap.add_argument("--metric", choices=["l2", "ip"], default="l2", help="FAISS metric: l2 (default) or ip (cosine)")
    ap.add_argument("--overwrite", action="store_true", help="Rebuild even if index already exists")
    return ap.parse_args()


def main():
    args = _parse_args()
    if args.video_id:
        build_index_for_video(args.video_id, metric=args.metric, overwrite=args.overwrite)
    else:
        build_all_indices(metric=args.metric, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
