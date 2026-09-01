# server/embeddings/runtime.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, List
import json
import numpy as np
import faiss
import os, re  # add
from typing import Any  # add
from pprint import pprint
# from server.bedrock_client import AnthropicModel 
# from titanmodel import EmbeddingGenerator

from server.local_client import OllamaLLM
from .local_embedder import EmbeddingGenerator

# ---- Paths & caches ---------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
INDEX_ROOT = ROOT / "data" / "index"

_INDEX_CACHE: Dict[str, faiss.Index] = {}
_META_CACHE: Dict[str, List[dict]] = {}
_EMBEDDER: EmbeddingGenerator | None = None


# ---- Internal helpers -------------------------------------------------------

def _video_dir(video_id: str) -> Path:
    p = INDEX_ROOT / video_id
    if not p.exists():
        raise FileNotFoundError(f"No index directory for video_id={video_id}. Expected {p}")
    return p

def _get_index(video_id: str) -> faiss.Index:
    idx = _INDEX_CACHE.get(video_id)
    if idx is None:
        idx_path = _video_dir(video_id) / "faiss.index"
        if not idx_path.exists():
            raise FileNotFoundError(f"Missing FAISS index at {idx_path}")
        idx = faiss.read_index(str(idx_path))
        _INDEX_CACHE[video_id] = idx
    return idx

def _get_meta_rows(video_id: str) -> List[dict]:
    rows = _META_CACHE.get(video_id)
    if rows is None:
        meta_path = _video_dir(video_id) / "meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Missing meta.json at {meta_path}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        # Support both shapes: list[...] or {"segments": [...]}
        if isinstance(meta, dict):
            rows = meta.get("segments", [])
        else:
            rows = meta
        if not isinstance(rows, list):
            raise RuntimeError(f"meta.json rows must be a list; got {type(rows).__name__}")
        _META_CACHE[video_id] = rows
    return rows

def _get_embedder() -> EmbeddingGenerator:
    global _EMBEDDER
    if _EMBEDDER is None:
        _EMBEDDER = EmbeddingGenerator()
    return _EMBEDDER

def _embed_query_vector(query: str) -> np.ndarray:
    """
    Returns (1, dim) float32 embedding for the query using the same embedder
    (API: embed_texts or embed_chunks) used to build the index.
    """
    eg = _get_embedder()
    if hasattr(eg, "embed_texts"):
        vec_1d = np.asarray(eg.embed_texts([query])[0], dtype="float32")
    elif hasattr(eg, "embed_chunks"):
        out = eg.embed_chunks([{"text": query}])[0]["embedding"]
        vec_1d = np.asarray(out, dtype="float32")
    else:
        raise RuntimeError("EmbeddingGenerator must implement embed_texts(list[str]) or embed_chunks(list[dict]).")

    if vec_1d.ndim != 1:
        raise RuntimeError(f"Expected 1-D embedding, got shape {vec_1d.shape}")
    return vec_1d.reshape(1, -1)

def _parse_ts(ts) -> int:
    """
    Accepts seconds (int/float) or a 'HH:MM:SS(.mmm)' string; returns int seconds.
    """
    if ts is None:
        return 0
    if isinstance(ts, (int, float)):
        return int(ts)
    s = str(ts)
    if ":" in s:
        try:
            hh, mm, ss = s.split(":")
            return int(float(hh) * 3600 + float(mm) * 60 + float(ss))
        except Exception:
            return 0
    try:
        return int(float(s))
    except Exception:
        return 0

def _extract_json_block(s: str) -> Dict[str, Any]:
    try:
        return json.loads(s)
    except Exception:
        m = re.search(r"\{.*\}", s, re.S)
        if not m:
            return {}
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}
        
def _build_llm_jsonl(hits: List[dict]) -> str:
    # hits: {"timestamp": int, "text": str, "score": float}
    lines = []
    for h in hits:
        lines.append(json.dumps({
            "timestamp": int(h.get("timestamp", 0)),
            "text": (h.get("text") or "").strip(),
            "score": float(h.get("score", 0.0)),
        }, ensure_ascii=False))
    return "\n".join(lines)

def _maybe_llm_rerank_hits(query: str, video_id: str, hits: List[dict]) -> List[dict]:
    """
    If SMART_SEEK_BEDROCK=1 and bedrock client is available, ask the model
    to choose the best timestamp among the top-k and put that hit first.
    On any error, return hits unchanged.
    similar for SMART_SEEK_LLM_RERANK=1 and OllamaLLM is available.
    """
    model = None
    if not hits:
        return hits
    # if os.getenv("SMART_SEEK_BEDROCK", "0") != "1":
    if os.getenv("SMART_SEEK_LLM_RERANK", "0") != "1":
        return hits
    pprint("Inside rerank")
    try:
        # client = AnthropicModel()
        client = OllamaLLM()
        pprint(f"Created client: {client}")
        client.create_bedrock_client()

        movie_title = os.getenv("SMART_SEEK_MOVIE_TITLE", "")

        jsonll = _build_llm_jsonl(hits)
        pprint(f"jsonll: {jsonll}")

        system_prompt = (
            "You are a precise scene selector for a smart media player. "
            "The user has given a voice utterance of this query to navigate the TV content to."
            "Choose exactly ONE candidate that best satisfies the user's request so the media playback can seek to the exact scene"
            "If none fits, return the top one."
        )
        user_prompt = (
            f"User query: \"{query}\"\n"
            f"Movie Title: \"{movie_title or 'Unknown'}\"\n\n"
            "Candidates (JSONL; each line has: timestamp, text, score):\n"
            f"{jsonll}\n\n"
            "Rules:\n"
            "- Always consider context first.\n"
            "Think of the movie plot by name if available, select the scene accordingly.\n"
            "- If none is adequate, choose the first one back\n"
            "- Return STRICT JSON in the same format only:\n"
            "{\n"
            "  \"chosen_timestamp\": <int|\"none\">,\n"
            "  \"rationale\": \"<<=120 chars>\",\n"
            "  \"confidence\": \"low|medium|high\"\n"
            "}\n"
        )
    
        pprint(f"type of prompt {type(user_prompt)}")
        resp_text = client.call_model(sys_prompt=system_prompt, prompt=user_prompt)
        pprint(f"type of resp_text {type(resp_text)}")
        obj = resp_text
        pprint(obj)
        obj_text = obj.get("content", {})[0].get("text", "")
        chosen = json.loads(obj_text).get("chosen_timestamp")
        pprint(chosen)
        conf = (obj.get("confidence") or "").lower()
        pprint(resp_text)
        # Only accept if it's an int and not explicitly low confidence
        if not isinstance(chosen, int) or conf == "low":
            return hits
        # find the closest hit by absolute timestamp distance
        idx = min(range(len(hits)), key=lambda i: abs(int(hits[i]["timestamp"]) - int(chosen)))
        # stable reorder: put chosen first, keep relative order of the rest
        if idx != 0:
            return [hits[idx]] + hits[:idx] + hits[idx+1:]
        return hits
    except Exception as e:
        pprint(f"Exception: {e}")
        return hits

# --- Scene-descriptor side index (optional) ---------------------------------

_SCENES_INDEX: Dict[str, faiss.Index] = {}
_SCENES_META: Dict[str, List[dict]] = {}

def _get_scenes_index(video_id: str) -> faiss.Index | None:
    """
    Load data/index/<video_id>/faiss_scenes.index if SCENES_ENABLE=1.
    Returns None if disabled or missing.
    """
    if os.getenv("SCENES_ENABLE", "0") != "1":
        return None
    idx = _SCENES_INDEX.get(video_id)
    if idx is None:
        p = _video_dir(video_id) / "faiss_scenes.index"
        if not p.exists():
            return None
        idx = faiss.read_index(str(p))
        _SCENES_INDEX[video_id] = idx
    return idx

def _get_scenes_meta(video_id: str) -> List[dict] | None:
    rows = _SCENES_META.get(video_id)
    if rows is None:
        p = _video_dir(video_id) / "scenes_meta.json"
        if not p.exists():
            return None
        rows = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            return None
        _SCENES_META[video_id] = rows
    return rows

def _search_scenes(video_id: str, qvec: np.ndarray, k: int = 3) -> List[dict]:
    """
    Returns scene hits shaped like your normal hits:
    [{"timestamp": int, "text": str, "score": float}]
    timestamp uses the *midpoint* of the scene range for a nicer seek target.
    """
    idx = _get_scenes_index(video_id)
    meta = _get_scenes_meta(video_id)
    if not idx or not meta:
        return []

    if qvec.shape[1] != idx.d or idx.ntotal == 0:
        return []

    k = max(1, min(int(k), idx.ntotal))
    D, I = idx.search(qvec, k)

    out: List[dict] = []
    for j, i in enumerate(I[0].tolist()):
        if i < 0:
            continue
        row = meta[i]
        start = float(row.get("start", row.get("timestamp", 0)))
        end = float(row.get("end", start))
        mid = int((start + end) / 2.0)  # nicer than start
        # short text for re-rank prompt & UI
        title = (row.get("title") or "").strip()
        summary = (row.get("summary") or "").strip()
        text = (title + (". " if title and summary else "") + summary)[:400]
        out.append({
            "timestamp": mid,
            "text": text,
            "score": float(D[0][j]),
        })
    return out


# ---- Public API -------------------------------------------------------------

def search_timestamps(video_id: str, query: str, k: int = 5) -> List[dict]:
    """
    Top-k nearest neighbors for the query in the video's FAISS index.

    Returns: list of { "timestamp": int (seconds), "text": str, "score": float }
    - Assumes index built with the same embedder/model & L2 metric.
    - Assumes FAISS row i corresponds to rows[i] in meta.
    """
    # 1) embed query
    vec = _embed_query_vector(query)  # (1, dim)

    # 2) load index & meta rows
    index = _get_index(video_id)
    rows = _get_meta_rows(video_id)

    # Quick sanity checks (raise with clear info)
    if vec.shape[1] != index.d:
        raise RuntimeError(f"Embedding dim {vec.shape[1]} != index.d {index.d} for video_id={video_id}")
    if index.ntotal == 0:
        raise RuntimeError(f"Index for video_id={video_id} is empty.")
    if len(rows) != index.ntotal:
        # Proceeding can return wrong timestamps if order/length mismatch.
        # Fail fast so the caller fixes the build.
        raise RuntimeError(f"Index/meta mismatch: ntotal={index.ntotal}, meta_rows={len(rows)} for video_id={video_id}")

    # 3) clamp k and search
    k = max(1, min(int(k), index.ntotal))
    D, I = index.search(vec, k)  # shapes: (1, k)

    # 4) map ids → rows
    hits: List[dict] = []
    for j, i in enumerate(I[0].tolist()):
        if i < 0:
            continue
        row = rows[i]
        ts = _parse_ts(row.get("timestamp", row.get("start", 0)))
        hits.append({
            "timestamp": ts,
            "text": row.get("text", ""),
            "score": float(D[0][j]),
        })
    
    if os.getenv("SCENES_ENABLE", "0") == "1":
        scene_hits = _search_scenes(video_id, vec, k=3)
        if scene_hits:
            # Simple fusion: append then de-dup near-equal timestamps (±2s), keep first occurrence
            merged = hits + scene_hits
            fused: List[dict] = []
            for h in merged:
                if not any(abs(h["timestamp"] - u["timestamp"]) <= 2 for u in fused):
                    fused.append(h)
            # Keep at most 5 to preserve your API’s “top-k” feel
            hits = fused[:k]
    
    hits = _maybe_llm_rerank_hits(query=query, video_id=video_id, hits=hits)
    return hits


def reload_video(video_id: str) -> None:
    """
    Clear caches so next call reloads index and meta from disk.
    """
    _INDEX_CACHE.pop(video_id, None)
    _META_CACHE.pop(video_id, None)
