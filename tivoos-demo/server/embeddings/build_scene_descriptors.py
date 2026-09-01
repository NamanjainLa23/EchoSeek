#!/usr/bin/env python3
# scripts/build_scene_descriptors.py
from __future__ import annotations
import os, re, sys, json, base64, subprocess, argparse, shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse, parse_qs
# from server.bedrock_client import AnthropicModel 
from server.local_client import OllamaLLM
import shutil, subprocess
from pathlib import Path
from typing import List

SCENES_DEBUG = os.getenv("SCENES_DEBUG", "0") == "1"

FFMPEG = shutil.which("ffmpeg")
if not FFMPEG:
    try:
        import imageio_ffmpeg
        FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        FFMPEG = None

# --- Config defaults ---------------------------------------------------------
CAPTIONS_DIR = Path("data/captions")
SCENES_DIR   = Path("data/scenes")
T_MIN_GAP_S  = 6.0      # minimum silence gap to consider
T_MAX_RANGE_S= 45.0     # cap overly long ranges; will split if longer
SPLIT_EVERY_S= 25.0     # when longer than T_MAX_RANGE_S, split chunks ~this long
MERGE_GAP_S  = 2.0      # merge adjacent gaps separated by < MERGE_GAP_S
MAX_FRAMES   = 3        # frames per range
FRAME_WIDTH  = 854      # scale video frames to this width (height auto)
USE_IMAGES   = False    # start text-only; set True after your Bedrock wrapper supports images


def _parse_ts_val(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if ":" in s:
        try:
            hh, mm, ss = s.split(":")
            return float(hh) * 3600 + float(mm) * 60 + float(ss)
        except Exception:
            return 0.0
    try:
        return float(s)
    except Exception:
        return 0.0
# --- Bedrock / Claude wrapper -----------------------------------------------
def _coerce_text(resp) -> str:
    """Coerce various response shapes to plain string."""
    if resp is None:
        return ""
    if isinstance(resp, str):
        return resp
    if isinstance(resp, dict):
        # common shapes
        if "output_text" in resp and isinstance(resp["output_text"], str):
            return resp["output_text"]
        if "content" in resp and isinstance(resp["content"], list):
            parts = []
            for item in resp["content"]:
                if isinstance(item, dict) and item.get("type") == "text" and "text" in item:
                    parts.append(item["text"])
            if parts:
                return "\n".join(parts)
        if "message" in resp and isinstance(resp["message"], dict):
            msg = resp["message"]
            if "content" in msg and isinstance(msg["content"], list):
                parts = []
                for item in msg["content"]:
                    if isinstance(item, dict) and item.get("type") == "text" and "text" in item:
                        parts.append(item["text"])
                if parts:
                    return "\n".join(parts)
        return json.dumps(resp, ensure_ascii=False)
    try:
        return resp.decode("utf-8")
    except Exception:
        return str(resp)

def call_claude_text(prompt: str, model_id: str = None):
    """
    Calls your AnthropicModel in text-in/text-out mode.
    Tries .invoke_text, then .invoke_model, then .invoke.
    """
    # import here so the script doesn't require server/ at import time
    # absolute import; ensure PYTHONPATH=repo_root/tivoos-demo

    # client = AnthropicModel()
    # client.create_bedrock_client()
    # model_id = client.model_id if model_id is None else model_id
    # resp = None
    # resp = client.call_model(prompt=prompt)
    # else:
    #     resp = client.invoke(model_id=model_id, prompt=prompt, temperature=0, max_tokens=300)

    client = OllamaLLM()
    resp = client.call_model(prompt=prompt)

    return _coerce_text(resp)

# --- Subtitle parsing --------------------------------------------------------
_ts_pat = re.compile(r"(?:(\d{1,2}):)?(\d{2}):(\d{2})(?:[.,](\d{1,3}))?")  # HH:MM:SS.mmm

def _parse_timecode(s: str) -> float:
    m = _ts_pat.search(s.strip())
    if not m: return 0.0
    hh = int(m.group(1) or 0); mm = int(m.group(2) or 0); ss = int(m.group(3) or 0); ms = int(m.group(4) or 0)
    return hh*3600 + mm*60 + ss + (ms/1000.0)

def _sec_to_hhmmss(t: float) -> str:
    h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def extract_frames_for_range(
    video_src: str,
    out_dir: Path,
    start: float,
    end: float,
    max_frames: int = 3,
    width: int = 854
) -> List[Path]:
    """
    Extract up to max_frames PNG images between [start, end].
    1) Try scene-change detection (diverse frames).
    2) Fallback to fixed ~1 fps sampling.
    PNG + RGB avoids MJPEG/YUV errors.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    t0, t1 = _sec_to_hhmmss(start), _sec_to_hhmmss(end)
    pattern = out_dir / "scene_%03d.png"

    # Filters (NO extra quotes; escape comma)
    vf_scene = f"select=gt(scene\\,0.3),scale={width}:-2,format=rgb24"
    vf_fps   = f"fps=1,scale={width}:-2,format=rgb24"

    # 1) Scene-change PNGs
    cmd1 = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-ss", t0, "-to", t1, "-i", video_src,
        "-vf", vf_scene,
        "-vsync", "vfr",
        "-frames:v", str(max_frames),
        "-c:v", "png",                 # encode PNG
        str(pattern)
    ]
    try:
        run_ffmpeg(cmd1)
    except Exception:
        pass

    files = sorted(out_dir.glob("scene_*.png"))
    if len(files) >= max_frames:
        return files

    for f in files:
        try: f.unlink()
        except Exception: pass

    # 2) Fallback: fixed sampling PNGs
    cmd2 = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-ss", t0, "-to", t1, "-i", video_src,
        "-vf", vf_fps,
        "-vsync", "vfr",
        "-frames:v", str(max_frames),
        "-c:v", "png",
        str(pattern)
    ]
    run_ffmpeg(cmd2)
    return sorted(out_dir.glob("scene_*.png"))



def load_subtitles(path: Path) -> List[dict]:
    """
    Returns list of segments: [{"start": float, "end": float, "text": str}]
    Supports .srt and .vtt (basic).
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    items: List[dict] = []
    if path.suffix.lower() == ".srt":
        # split by blank line
        blocks = re.split(r"\n\s*\n", text.strip())
        for b in blocks:
            lines = [ln.strip("\ufeff") for ln in b.splitlines() if ln.strip()]
            if len(lines) < 2: 
                continue
            # lines[0] may be index, lines[1] is times
            time_line = lines[1] if "-->" in lines[1] else next((ln for ln in lines if "-->" in ln), "")
            if "-->" not in time_line: 
                continue
            start_s = _parse_timecode(time_line.split("-->")[0])
            end_s   = _parse_timecode(time_line.split("-->")[1])
            txt = " ".join(l for l in lines if "-->" not in l and not l.isdigit())
            items.append({"start": start_s, "end": end_s, "text": txt})
    else:
        # VTT (skip header)
        blocks = re.split(r"\n\s*\n", text.strip())
        for b in blocks:
            if "-->" not in b: 
                continue
            lines = [ln for ln in b.splitlines() if ln.strip() and not ln.strip().startswith("WEBVTT")]
            time_line = next((ln for ln in lines if "-->" in ln), "")
            if not time_line: 
                continue
            start_s = _parse_timecode(time_line.split("-->")[0])
            end_s   = _parse_timecode(time_line.split("-->")[1])
            txt = " ".join(ln for ln in lines if "-->" not in ln)
            items.append({"start": start_s, "end": end_s, "text": txt})
    # sort by start
    items.sort(key=lambda x: x["start"])
    return items

def load_segments_from_meta(meta_path: Path, default_dur: float = 2.0) -> list[dict]:
    raw = json.loads(meta_path.read_text(encoding="utf-8"))
    rows = raw.get("segments", raw) if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        raise RuntimeError(f"meta.json rows must be a list; got {type(rows).__name__}")

    segs = []
    for r in rows:
        text = (r.get("text") or "").strip()
        if "start" in r or "end" in r:
            start = _parse_ts_val(r.get("start", r.get("timestamp", 0)))  # fall back to timestamp
            end   = _parse_ts_val(r.get("end", start + default_dur))
        else:
            # only timestamp
            start = _parse_ts_val(r.get("timestamp", 0))
            end   = start + default_dur
        if end <= start:  # safety
            end = start + default_dur
        segs.append({"start": float(start), "end": float(end), "text": text})

    segs.sort(key=lambda x: x["start"])
    # clamp overlaps
    for i in range(len(segs)-1):
        if segs[i]["end"] > segs[i+1]["start"]:
            segs[i]["end"] = segs[i+1]["start"]
    return segs

# --- Silence detection -------------------------------------------------------
def detect_silence_ranges(segments: List[dict],
                          t_min: float = T_MIN_GAP_S,
                          t_max: float = T_MAX_RANGE_S,
                          merge_gap: float = MERGE_GAP_S,
                          split_every: float = SPLIT_EVERY_S) -> List[dict]:
    """
    Returns ranges: [{"start": float, "end": float, "prev_text": str, "next_text": str}]
    Based purely on subtitle gaps.
    """
    ranges: List[Tuple[float,float,int,int]] = []  # (start,end,prev_idx,next_idx)
    for i in range(len(segments) - 1):
        end_i   = segments[i]["end"]
        start_i1= segments[i+1]["start"]
        gap = start_i1 - end_i
        if gap >= t_min:
            ranges.append((end_i, start_i1, i, i+1))

    # merge close ranges
    merged: List[Tuple[float,float,int,int]] = []
    for r in ranges:
        if not merged:
            merged.append(r); continue
        last = merged[-1]
        if r[0] - last[1] <= merge_gap:
            # merge
            merged[-1] = (last[0], r[1], last[2], r[3])
        else:
            merged.append(r)

    # split long ones
    final: List[dict] = []
    for (s,e,pi,ni) in merged:
        length = e - s
        prev_text = segments[pi]["text"] if 0 <= pi < len(segments) else ""
        next_text = segments[ni]["text"] if 0 <= ni < len(segments) else ""
        if length <= t_max:
            final.append({"start": s, "end": e, "prev_text": prev_text, "next_text": next_text})
        else:
            # split into chunks ~split_every
            t = s
            while t < e:
                t2 = min(t + split_every, e)
                final.append({"start": t, "end": t2, "prev_text": prev_text, "next_text": next_text})
                t = t2
    return final

# --- Frame extraction --------------------------------------------------------
def _sec_to_hhmmss(t: float) -> str:
    h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def run_ffmpeg(cmd: List[str]) -> None:
    subprocess.run(cmd, check=False)

def run_ffmpeg(cmd: list[str]) -> None:
    if not FFMPEG:
        raise RuntimeError("ffmpeg not found. Install it (brew install ffmpeg) or pip install imageio-ffmpeg.")
    # swap program name with resolved path
    cmd = [FFMPEG if c == "ffmpeg" else c for c in cmd]
    subprocess.run(cmd, check=True)

# --- Claude descriptor generation -------------------------------------------
def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")

def build_descriptor_prompt(movie_title: str, rng: dict, frames: List[Path]) -> str:
    """
    Text-only prompt. If USE_IMAGES=True, we include small base64 notes for FYI,
    but your wrapper may ignore images unless you wire vision inputs explicitly.
    """
    t0 = _sec_to_hhmmss(rng["start"]); t1 = _sec_to_hhmmss(rng["end"])
    prev_line = (rng.get("prev_text") or "").strip()
    next_line = (rng.get("next_text") or "").strip()

    prompt = []
    prompt.append("System:")
    prompt.append("You generate concise, factual scene descriptors for a time range in a movie.")
    prompt.append("Only describe what is clearly visible or supported by the nearby dialogue.")
    prompt.append("Return STRICT JSON with keys: title, summary, entities, locations, actions, visual_tags, tone, confidence.")
    prompt.append("")
    prompt.append("User:")
    prompt.append(f"Movie Title: {movie_title or 'Unknown'}")
    prompt.append(f"Time Range: {t0}–{t1} (hh:mm:ss)")
    if prev_line:
        prompt.append(f"Previous line: {prev_line}")
    if next_line:
        prompt.append(f"Next line: {next_line}")
    if USE_IMAGES and frames:
        prompt.append("Frames (base64 JPEG, small excerpts; use only if helpful):")
        for p in frames[:3]:
            try:
                b64 = _b64(p)
                prompt.append(f"[image/jpeg;base64]: {b64[:1200]}...")  # truncate to keep prompt small
            except Exception:
                pass
    prompt.append("")
    prompt.append("Output STRICT JSON only, e.g.:")
    prompt.append("{")
    prompt.append('  "title": "…",')
    prompt.append('  "summary": "… (<= 40 words)",')
    prompt.append('  "entities": ["..."],')
    prompt.append('  "locations": ["..."],')
    prompt.append('  "actions": ["..."],')
    prompt.append('  "visual_tags": ["..."],')
    prompt.append('  "tone": "…",')
    prompt.append('  "confidence": "low|medium|high"')
    prompt.append("}")
    return "\n".join(prompt)

import time, json, re

def _force_json_object(text: str) -> dict:
    """Return first JSON object in text or {}."""
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return {}
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}

def _sanitize_desc(obj: dict) -> dict:
    # Ensure shape and strings
    out = {
        "title": (obj.get("title") or "").strip(),
        "summary": (obj.get("summary") or "").strip(),
        "entities": obj.get("entities") or [],
        "locations": obj.get("locations") or [],
        "actions": obj.get("actions") or [],
        "visual_tags": obj.get("visual_tags") or [],
        "tone": (obj.get("tone") or "").strip(),
        "confidence": (obj.get("confidence") or "").strip(),
    }
    # hard clamp lengths a bit
    out["title"] = out["title"][:120]
    out["summary"] = out["summary"][:280]
    return out

def describe_range_with_claude(movie_title: str, rng: dict, frames: List[Path]) -> dict:
    # 1st attempt
    prompt = build_descriptor_prompt(movie_title, rng, frames)
    if SCENES_DEBUG:
        from pprint import pprint
        print("\n[SCENES PROMPT]\n")
        # don't spam console—trim to ~2k chars
        print(prompt[:2000])
        print("\n")

    raw = call_claude_text(prompt)

    # --- PART 1 DEBUG: after receiving Claude's response ---
    if SCENES_DEBUG:
        print("[SCENES RAW TYPE]", type(raw))
        # raw may be dict or string; show safely
        try:
            preview = raw[:2000] if isinstance(raw, str) else str(raw)[:2000]
        except Exception:
            preview = "<unprintable>"
        print("[SCENES RAW PREVIEW]\n", preview, "\n")
    raw = call_claude_text(prompt)
    obj = _force_json_object(raw)
    desc = _sanitize_desc(obj)

    # If empty-ish, retry once with a shorter, even stricter prompt (no examples)
    if not desc["title"] and not desc["summary"]:
        time.sleep(0.6)  # be polite to the API
        short_prompt = (
            "System:\n"
            "Return STRICT JSON describing the scene between the given times. "
            "Only include fields you are confident in. Do NOT include any extra text.\n\n"
            "User:\n"
            f"Movie: {movie_title or 'Unknown'}\n"
            f"Time Range: {_sec_to_hhmmss(rng['start'])}–{_sec_to_hhmmss(rng['end'])}\n"
            f"Previous line: {(rng.get('prev_text') or '').strip()}\n"
            f"Next line: {(rng.get('next_text') or '').strip()}\n"
            "{"
            "\"title\":\"...\"," 
            "\"summary\":\"<= 40 words...\"," 
            "\"entities\":[],\"locations\":[],\"actions\":[],"
            "\"visual_tags\":[],\"tone\":\"\",\"confidence\":\"low|medium|high\""
            "}"
        )
        raw2 = call_claude_text(short_prompt)
        obj2 = _force_json_object(raw2)
        desc = _sanitize_desc(obj2)

    # Final fallback if still empty: synthesize something minimal so you don’t waste the range
    if not desc["title"] and not desc["summary"]:
        prev_t = (rng.get("prev_text") or "").strip()
        next_t = (rng.get("next_text") or "").strip()
        window = f"{_sec_to_hhmmss(rng['start'])}–{_sec_to_hhmmss(rng['end'])}"
        title = "Silent / non-dialogue sequence"
        summary_bits = [f"Silent interval {window}."]
        if prev_t: summary_bits.append(f"Before: {prev_t[:60]}")
        if next_t: summary_bits.append(f"After: {next_t[:60]}")
        desc = {
            "title": title,
            "summary": " ".join(summary_bits),
            "entities": [],
            "locations": [],
            "actions": [],
            "visual_tags": [],
            "tone": "",
            "confidence": "low",
        }

    return desc

# --- Orchestration -----------------------------------------------------------
def _find_downloaded_video(out_dir: Path, video_id: str) -> Optional[Path]:
    """yt-dlp writes <id>.mp4 when it can merge; otherwise <id>.fNNN.mp4."""
    merged = out_dir / f"{video_id}.mp4"
    if merged.exists():
        return merged
    parts = sorted(out_dir.glob(f"{video_id}.f*.mp4"))
    return parts[0] if parts else None


def _mux_video_audio(out_dir: Path, video_id: str, dest: Path) -> Optional[Path]:
    """Merge yt-dlp split streams into dest if both video and audio exist."""
    videos = sorted(out_dir.glob(f"{video_id}.f*.mp4"))
    audios = sorted(out_dir.glob(f"{video_id}.f*.m4a"))
    if not videos:
        return None
    if not audios or not FFMPEG:
        return videos[0]
    cmd = [
        FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(videos[0]), "-i", str(audios[0]),
        "-c", "copy", str(dest),
    ]
    print("[MUX]", " ".join(cmd))
    subprocess.run(cmd, check=True)
    return dest if dest.exists() else videos[0]


def ensure_video(video_path: Optional[str], youtube_url: Optional[str], video_id: str) -> str:
    """
    Ensures a local mp4 exists. If video_path is provided and exists, use it.
    Else, if youtube_url is provided, downloads ~480p mp4 via yt-dlp to data/videos/<id>.mp4
    Returns local path string.
    """
    if video_path and Path(video_path).exists():
        return video_path
    out_dir = Path("data/videos")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{video_id}.mp4"

    existing = _find_downloaded_video(out_dir, video_id)
    if existing:
        if existing == out_file:
            return str(out_file)
        muxed = _mux_video_audio(out_dir, video_id, out_file)
        return str(muxed or existing)

    if not youtube_url:
        raise FileNotFoundError("No local video and no --youtube URL provided. Cannot extract frames.")

    cmd = [
        "yt-dlp",
        "-f", "bv*[height<=480][ext=mp4]+ba[ext=m4a]/b[height<=480]",
        "--merge-output-format", "mp4",
        "-o", str(out_file),
        youtube_url,
    ]
    if FFMPEG:
        cmd[1:1] = ["--ffmpeg-location", FFMPEG]
    print("[DL] ", " ".join(cmd))
    subprocess.run(cmd, check=True)

    found = _find_downloaded_video(out_dir, video_id)
    if found == out_file:
        return str(out_file)
    muxed = _mux_video_audio(out_dir, video_id, out_file)
    if muxed:
        return str(muxed)
    raise FileNotFoundError(f"Download finished but no video found under {out_dir} for {video_id}")

def main():
    ap = argparse.ArgumentParser(description="Build scene descriptors from subtitle silence ranges.")
    ap.add_argument("--subs", help="Path to subtitle file (.srt/.vtt). If omitted, picks first in data/captions/", default=None)
    ap.add_argument("--video", help="Local video file path (mp4).", default=None)
    ap.add_argument("--youtube", help="YouTube URL (used if --video not provided).", default=None)
    ap.add_argument("--movie-title", help="Movie title (optional; else derivable from yt-dlp if you want).", default=None)
    ap.add_argument("--max-ranges", type=int, default=80, help="Cap number of ranges processed.")
    ap.add_argument("--out", help="Output directory base (default data/scenes/<video_id>)", default=None)
    ap.add_argument("--video-id", help="Video ID used under data/index/<video_id>/meta.json", default=None)
    args = ap.parse_args()

    # 1) pick subtitle file
    # subs_path = Path(args.subs) if args.subs else next(iter(sorted(CAPTIONS_DIR.glob("*.srt")) or CAPTIONS_DIR.glob("*.vtt")), None)
    # if not subs_path or not subs_path.exists():
    #     print(f"Subtitle file not found. Provide --subs or put a .srt/.vtt in {CAPTIONS_DIR}", file=sys.stderr)
    #     sys.exit(1)

    # video_id inferred from subs filename stem
    #video_id = subs_path.stem.split(".")[0]  # handles cases like "<id>.en"
    movie_title = args.movie_title or os.getenv("SMART_SEEK_MOVIE_TITLE") or "Unknown"

    # 2) ensure local video exists (if you want frames)
    video_id = getattr(args, "video_id", None)
    video_src = ensure_video(args.video, args.youtube, video_id)
    video_id = args.video_id or (Path(args.video).stem if args.video else None)
    if not video_id and args.video:
    # e.g., data/videos/abcd1234.mp4 -> abcd1234
        ideo_id = Path(args.video).stem

    if not video_id and args.youtube:
    # parse ?v=VIDEO_ID from the YouTube URL
        q = parse_qs(urlparse(args.youtube).query)
        video_id = (q.get("v") or [None])[0]

    if not video_id and args.subs:
        # e.g., captions/abcd1234.en.vtt -> abcd1234
        video_id = Path(args.subs).stem.split(".")[0]

    if not video_id:
        print("ERROR: Could not determine video_id. Pass --video-id or provide --video / --youtube / --subs.", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Using video_id={video_id}")

    if not video_id:
        print("Provide --video-id (or pass --video so we can infer it).", file=sys.stderr); sys.exit(1)

    meta_path = Path("/Users/namanjain/EchoSeek/tivoos-demo/data/index") / video_id / "meta.json"
    if not meta_path.exists():
        print(f"meta.json not found at {meta_path}", file=sys.stderr); sys.exit(1)

    segments = load_segments_from_meta(meta_path)
    # 3) parse subtitles
    # segments = load_subtitles(subs_path)
    # if not segments:
    #     print("No subtitle segments parsed.", file=sys.stderr); sys.exit(1)

    # 4) detect silence ranges
    ranges = detect_silence_ranges(segments)
    if not ranges:
        print("No silence ranges found with current thresholds.", file=sys.stderr); sys.exit(0)

    if args.max_ranges and len(ranges) > args.max_ranges:
        # pick the longest ranges first
        ranges = sorted(ranges, key=lambda r: (r["end"] - r["start"]), reverse=True)[:args.max_ranges]

    # 5) prepare output dirs
    out_base = Path(args.out) if args.out else (SCENES_DIR / video_id)
    frames_root = out_base / "frames"
    frames_root.mkdir(parents=True, exist_ok=True)
    scenes_path = out_base / "scenes.jsonl"
    if scenes_path.exists():
        # start fresh for this run
        scenes_path.unlink()

    # 6) process
    with scenes_path.open("w", encoding="utf-8") as fout:
        for idx, rng in enumerate(ranges, 1):
            rdir = frames_root / f"range_{idx:04d}"
            if rdir.exists():
                shutil.rmtree(rdir)
            rdir.mkdir(parents=True, exist_ok=True)

            # frames
            frames = extract_frames_for_range(video_src, rdir, rng["start"], rng["end"], MAX_FRAMES, FRAME_WIDTH)

            # describe
            desc = describe_range_with_claude(movie_title, rng, frames if USE_IMAGES else [])
            # build embed_text compactly
            embed_text = ". ".join(filter(None, [
                desc.get("title", "").strip(),
                desc.get("summary", "").strip(),
                ("Entities: " + ", ".join(desc.get("entities", []))) if desc.get("entities") else "",
                ("Tags: " + ", ".join(desc.get("visual_tags", []))) if desc.get("visual_tags") else "",
            ]))

            rec = {
                "id": f"scene_{idx:05d}",
                "video_id": video_id,
                "start": rng["start"],
                "end": rng["end"],
                "title": desc.get("title", ""),
                "summary": desc.get("summary", ""),
                "entities": desc.get("entities", []),
                "locations": desc.get("locations", []),
                "actions": desc.get("actions", []),
                "visual_tags": desc.get("visual_tags", []),
                "tone": desc.get("tone", ""),
                "confidence": desc.get("confidence", ""),
                "embed_text": embed_text,
                "frame_preview": str(frames[0]) if frames else "",
                "frames_dir": str(rdir),
            }
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"[{idx}/{len(ranges)}] {rec['id']}  {rec['start']:.1f}-{rec['end']:.1f}s  frames={len(frames)}  title={rec['title']!r}")

    print(f"\nWrote {scenes_path}  (ranges: {len(ranges)})")
    print(f"Frames under {frames_root}/")
    print("Next: build a FAISS index over 'embed_text' from scenes.jsonl and fuse with your subtitle retrieval.")
    
if __name__ == "__main__":
    main()
