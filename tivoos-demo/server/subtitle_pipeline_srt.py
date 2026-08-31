# subtitle_pipeline.py (merge-only, per-video folders)
import os, re, json, argparse, glob
from dataclasses import dataclass
from typing import List, Optional, Tuple
from pathlib import Path

# -------- Utilities --------
TIMECODE = re.compile(
    r"(?P<sh>\d{2}):(?P<sm>\d{2}):(?P<ss>\d{2}),(?P<sms>\d{3})\s*-->\s*"
    r"(?P<eh>\d{2}):(?P<em>\d{2}):(?P<es>\d{2}),(?P<ems>\d{3})"
)

def to_seconds(h, m, s, ms) -> float:
    return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000.0

@dataclass
class Cue:
    start: float
    end: float
    text: str

# -------- 1) Download SRT (manual → auto) --------
def download_youtube_srt(url: str, lang: str, out_dir: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        import yt_dlp
    except ModuleNotFoundError:
        raise RuntimeError("pip install yt-dlp")

    os.makedirs(out_dir, exist_ok=True)

    def find_srt(video_id: Optional[str]) -> Optional[str]:
        if video_id:
            hits = glob.glob(os.path.join(out_dir, f"{video_id}.*.srt")) + \
                   glob.glob(os.path.join(out_dir, f"{video_id}.srt"))
            if hits: return hits[0]
        hits = sorted(glob.glob(os.path.join(out_dir, "*.srt")), key=os.path.getmtime, reverse=True)
        return hits[0] if hits else None

    # probe id first
    video_id = None
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        info = ydl.extract_info(url, download=False)
        video_id = info.get("id")

    base = {"skip_download": True, "outtmpl": os.path.join(out_dir, "%(id)s.%(ext)s"),
            "quiet": True, "no_warnings": True}
    # Try manual captions first
    try:
        with yt_dlp.YoutubeDL({**base,
                               "writesubtitles": True,
                               "writeautomaticsub": False,
                               "subtitleslangs": [lang],
                               "subtitlesformat": "srt"}) as ydl:
            ydl.download([url])
        p = find_srt(video_id)
        if p: return p, video_id
    except Exception:
        pass
    # Fallback to auto-captions
    with yt_dlp.YoutubeDL({**base,
                           "writesubtitles": False,
                           "writeautomaticsub": True,
                           "subtitleslangs": [lang],
                           "subtitlesformat": "srt"}) as ydl:
        ydl.download([url])
    return find_srt(video_id), video_id

# -------- 2) Parse SRT (no cleaning) --------
def parse_srt(path: str) -> List[Cue]:
    cues: List[Cue] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        block = []
        for line in f:
            if line.strip():
                block.append(line.rstrip("\n"))
                continue
            if block:
                cue = _parse_block(block)
                if cue: cues.append(cue)
                block = []
        if block:
            cue = _parse_block(block)
            if cue: cues.append(cue)
    return cues

def _parse_block(lines: List[str]) -> Optional[Cue]:
    # blocks typically: [index?, timecode, text...]
    if not lines: return None
    # timecode could be on first or second line (if first is numeric index)
    for i in range(min(2, len(lines))):
        m = TIMECODE.search(lines[i])
        if m:
            sh, sm, ss, sms = m.group("sh","sm","ss","sms")
            eh, em, es, ems = m.group("eh","em","es","ems")
            start = to_seconds(sh,sm,ss,sms)
            end   = to_seconds(eh,em,es,ems)
            text_lines = lines[i+1:]  # keep text EXACTLY as-is
            text = " ".join(t for t in text_lines if t.strip())
            return Cue(start, end, text)
    return None

# -------- 3) Merge (NO cleaning) --------
def merge_cues(
    cues: List[Cue],
    merge_gap: float = 0.6,
    max_window_duration: float = 25.0,
    max_chars: int = 600,
    joiner: str = " "
) -> List[Cue]:
    if not cues: return []
    out: List[Cue] = []
    cur = Cue(cues[0].start, cues[0].end, cues[0].text)

    for nxt in cues[1:]:
        gap = max(0.0, nxt.start - cur.end)
        would_duration = max(nxt.end, cur.end) - cur.start
        would_chars = len(cur.text) + len(joiner) + len(nxt.text)
        if gap <= merge_gap and would_duration <= max_window_duration and would_chars <= max_chars:
            cur.text = f"{cur.text}{joiner}{nxt.text}".strip()
            cur.end = max(cur.end, nxt.end)
        else:
            out.append(cur)
            cur = Cue(nxt.start, nxt.end, nxt.text)
    out.append(cur)
    return out

def _sec_to_tc(s: float) -> str:
    h = int(s // 3600); s -= h*3600
    m = int(s // 60);   s -= m*60
    return f"{h:02d}:{m:02d}:{s:06.3f}"

# -------- 4) CLI --------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--tmp-out", default="captions")  # temp download dir
    ap.add_argument("--merge-gap", type=float, default=0.6)
    ap.add_argument("--max-window-duration", type=float, default=25.0)
    ap.add_argument("--max-chars", type=int, default=600)
    ap.add_argument("--joiner", default=" ")
    # ap.add_argument("--build-index", action="store_true", help="After writing segments.json, build FAISS for this video id.")

    args = ap.parse_args()

    # 1) download srt and detect video_id
    srt, video_id = download_youtube_srt(args.url, args.lang, args.tmp_out)
    if not srt or not video_id:
        raise SystemExit("No SRT captions found for this URL/lang.")

    # 2) parse + merge
    cues = parse_srt(srt)
    merged = merge_cues(
        cues,
        merge_gap=args.merge_gap,
        max_window_duration=args.max_window_duration,
        max_chars=args.max_chars,
        joiner=args.joiner
    )

    # 3) write per-video folder under data/index/<video_id>/segments.json
    ROOT = Path(__file__).resolve().parents[0]  # points to folder containing this file
    VIDEO_DIR = (ROOT / ".." / "data" / "index" / video_id).resolve()
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)

    segs = [{
        "video_id": video_id,
        "start": c.start,
        "end": c.end,
        "start_tc": _sec_to_tc(c.start),
        "end_tc": _sec_to_tc(c.end),
        "text": c.text
    } for c in merged]

    out_path = VIDEO_DIR / "segments.json"
    out_path.write_text(json.dumps(segs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] wrote {out_path} with {len(segs)} merged segments.")

    ##NEED FIXING
    # 4) optional: build FAISS index for this video now
    # if args.build_index:
    #     # import here to avoid hard dependency when just merging
    #     from server.embeddings.index_store import SubtitleIndex  # your class
    #     from .embeddings.local_embedder import EmbeddingGenerator

    #     embedder = EmbeddingGenerator()
    #     vectors, meta_rows = [], []
    #     for ch in segs:
    #         vec = embedder.embed_texts(ch["text"])
    #         vectors.append(vec)
    #         meta_rows.append({
    #             "video_id": video_id,
    #             "timestamp": int(ch["start"]),
    #             "end": int(ch["end"]),
    #             "text": ch["text"]
    #         })

    #     dim = len(vectors[0])
    #     faiss_path = VIDEO_DIR / "faiss.index"
    #     meta_path  = VIDEO_DIR / "meta.json"

    #     index = SubtitleIndex(dim, index_path=str(faiss_path), meta_path=str(meta_path))
    #     index.add(vectors, meta_rows)
    #     index.save()
    #     print(f"[ok] built index at {faiss_path} and meta at {meta_path}")

if __name__ == "__main__":
    main()
