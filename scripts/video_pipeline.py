#!/usr/bin/env python3
"""Prepare one Bilibili video for a grounded Obsidian study note."""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

VAULT_ENV = "BILIBILI_NOTES_VAULT"
CURRENT_WORKDIR = None


def configured_vault() -> Path:
    value = os.environ.get(VAULT_ENV, "").strip()
    if not value:
        raise RuntimeError(f"Set {VAULT_ENV} to the root of your Obsidian vault before publishing or cleanup")
    return Path(value).expanduser().resolve()

BVID_RE = re.compile(r"BV[0-9A-Za-z]{10}")
TIME_RE = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})(?:[.,](\d{1,3}))?")


def call(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    if args and args[0] == "yt-dlp" and "--ignore-config" not in args:
        args = [args[0], "--ignore-config", *args[1:]]
    process = subprocess.Popen(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    while True:
        try:
            stdout,stderr=process.communicate(timeout=15)
            break
        except subprocess.TimeoutExpired:
            if CURRENT_WORKDIR is not None:
                from progress import emit
                state=json.loads((CURRENT_WORKDIR/'progress.json').read_text())['current']
                emit(CURRENT_WORKDIR,state['phase'],tool=args[0],message="Tool still running; preserve this workdir if interrupted")
        except BaseException:
            process.terminate();process.wait();raise
    result = subprocess.CompletedProcess(args,process.returncode,stdout,stderr)
    if check and result.returncode:
        tail = (result.stderr or result.stdout)[-1800:].strip()
        raise RuntimeError(f"{args[0]} failed ({result.returncode}): {tail}")
    return result


def stamp(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"


def parse_time(value: str) -> float:
    match = TIME_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Invalid timestamp: {value}")
    hours, minutes, seconds, millis = match.groups()
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds) + int((millis or "0").ljust(3, "0")) / 1000


def parse_subtitle(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        data = json.loads(raw)
        body = data.get("body") if isinstance(data, dict) else None
        if isinstance(body, list):
            return [
                {"start": float(row["from"]), "end": float(row.get("to", row["from"])), "text": str(row["content"]).strip()}
                for row in body if isinstance(row, dict) and row.get("content")
            ]
        return []
    rows = []
    pattern = re.compile(r"((?:\d{2}:)?\d{2}:\d{2}[.,]\d{1,3})\s*-->\s*((?:\d{2}:)?\d{2}:\d{2}[.,]\d{1,3})")
    for block in re.split(r"\n\s*\n", raw.replace("\r\n", "\n")):
        lines = block.splitlines()
        idx = next((i for i, line in enumerate(lines) if pattern.search(line)), None)
        if idx is None:
            continue
        match = pattern.search(lines[idx])
        assert match
        content = " ".join(re.sub(r"<[^>]*>", "", line).strip() for line in lines[idx + 1:]).strip()
        if content:
            rows.append({"start": parse_time(match.group(1)), "end": parse_time(match.group(2)), "text": html.unescape(content)})
    return rows


def transcript_from_asr(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    output = []
    for row in data.get("transcription", []):
        text = str(row.get("text", "")).strip()
        offsets = row.get("offsets") or {}
        if not text:
            continue
        if "from" in offsets:
            start = float(offsets["from"]) / 1000
            end = float(offsets.get("to", offsets["from"])) / 1000
        else:
            times = row.get("timestamps") or {}
            start = parse_time(str(times.get("from", "00:00:00")))
            end = parse_time(str(times.get("to", "00:00:00")))
        output.append({"start": start, "end": end, "text": text})
    return output


def subtitle_files(workdir: Path) -> list[Path]:
    return sorted(p for p in workdir.glob("subtitle.*") if p.suffix.lower() in {".json", ".srt", ".vtt"})


def find_subtitles(url: str, workdir: Path, browser: str | None, metadata: dict) -> tuple[list[dict], str | None]:
    tracks = metadata.get("subtitles") or {}
    tracks.update(metadata.get("automatic_captions") or {})
    useful = [key for key in tracks if re.search(r"zh|chinese|cn", key, re.I) and not re.search(r"danmaku|comment", key, re.I)]
    if not useful:
        return [], None
    options = ["yt-dlp", "--no-playlist", "--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", ",".join(useful), "-o", str(workdir / "subtitle.%(ext)s")]
    if browser:
        options += ["--cookies-from-browser", browser]
    result = call(options + [url], check=False)
    if result.returncode:
        return [], None
    candidates = []
    for path in subtitle_files(workdir):
        try:
            rows = parse_subtitle(path)
        except (UnicodeError, ValueError, KeyError, TypeError):
            continue
        candidates.append((sum(len(row["text"]) for row in rows), rows, path.name))
    if not candidates:
        return [], None
    _, rows, name = max(candidates, key=lambda item: item[0])
    return rows, name


def get_media(url: str, workdir: Path, browser: str | None) -> Path:
    options = ["yt-dlp", "--no-playlist", "--no-write-playlist-metafiles", "-f", "bv*[height<=720]+ba/b[height<=720]/bv*+ba/b", "--merge-output-format", "mp4", "-o", str(workdir / "source.%(ext)s")]
    if browser:
        options += ["--cookies-from-browser", browser]
    call(options + [url])
    files = [p for p in workdir.glob("source.*") if p.suffix.lower() in {".mp4", ".mkv", ".webm"}]
    if len(files) != 1:
        raise RuntimeError("Expected one downloaded video file")
    return files[0]


def scene_times(media: Path, duration: float) -> list[float]:
    result = call(["ffmpeg", "-hide_banner", "-loglevel", "info", "-i", str(media), "-vf", "select=gt(scene\\,0.20),showinfo", "-an", "-f", "null", "-"], check=False)
    if result.returncode:
        return []
    raw = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", result.stderr)]
    return [x for x in raw if 1 <= x <= duration - 1]


def candidate_times(duration: float, scenes: list[float]) -> list[float]:
    periodic = [min(duration - 1, float(x)) for x in range(20, math.ceil(duration), 60)]
    chosen = set(round(x, 1) for x in periodic if x >= 0)
    for value in scenes:
        if all(abs(value - current) >= 25 for current in chosen):
            chosen.add(round(value, 1))
    values = sorted(chosen)
    if len(values) > 40:
        values = [values[round(i * (len(values) - 1) / 39)] for i in range(40)]
    return values or [max(0.0, duration / 2)]


def extract_frame(media: Path, seconds: float, output: Path, *, preview: bool) -> None:
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{seconds:.3f}", "-i", str(media), "-frames:v", "1"]
    if preview:
        args += ["-vf", "scale=480:-2"]
    call(args + [str(output)])
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"Frame extraction failed at {stamp(seconds)}")


def prepare(args: argparse.Namespace) -> None:
    from qwen_mlx_asr import job_lock, atomic_json
    workdir = args.workdir.expanduser().resolve()
    with job_lock(workdir, ".pipeline.lock"):
        request = {"url": args.url, "hotwords": args.hotwords, "chunk_seconds": args.chunk_seconds,
                   "series_part": args.series_part, "browser": args.browser}
        identity = workdir / "prepare_request.json"
        if identity.exists() and json.loads(identity.read_text()) != request:
            raise ValueError("Preparation input differs; preserve this workdir and use a new one")
        if not identity.exists():
            # Existing workdirs may contain subtitles/media from another request.
            if any(p.name != ".pipeline.lock" for p in workdir.iterdir()):
                raise ValueError("Unbound existing workdir; use a new workdir")
            atomic_json(identity, request)
        from progress import emit
        emit(workdir,"prepare",recovery="Repeat identical prepare after failure; after manifest exists continue select/draft/coverage.")
        _prepare(args)


def _prepare(args: argparse.Namespace) -> None:
    parsed = urlparse(args.url)
    if parsed.hostname not in {"www.bilibili.com", "bilibili.com", "m.bilibili.com", "b23.tv"}:
        raise ValueError("Expected a Bilibili video URL")
    workdir = args.workdir.expanduser().resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    if (workdir / "manifest.json").exists():
        raise FileExistsError(f"Existing prepared workdir: {workdir}")
    meta_cmd = ["yt-dlp", "--no-playlist", "--dump-single-json"]
    if args.browser:
        meta_cmd += ["--cookies-from-browser", args.browser]
    from progress import emit
    emit(workdir, "metadata")
    meta = json.loads(call(meta_cmd + [args.url]).stdout)
    emit(workdir, "metadata", "completed")
    bvid_match = BVID_RE.search(str(meta.get("id", ""))) or BVID_RE.search(str(meta.get("webpage_url", "")))
    if not bvid_match:
        raise RuntimeError("Could not resolve a Bilibili BV ID")
    bvid = bvid_match.group(0)
    part = int(parse_qs(urlparse(str(meta.get("webpage_url") or args.url)).query).get("p", ["1"])[0])
    duration = float(meta.get("duration") or 0)
    if duration <= 0:
        raise RuntimeError("Video duration is unavailable")
    if duration > args.max_minutes * 60:
        raise RuntimeError(f"Video is {stamp(duration)}; limit is {args.max_minutes} minutes")
    source_url = f"https://www.bilibili.com/video/{bvid}/?p={part}"
    emit(workdir, "subtitles")
    rows, subtitle_name = find_subtitles(source_url, workdir, args.browser, meta)
    emit(workdir, "subtitles", "completed", segments=len(rows))
    emit(workdir, "download")
    media = get_media(source_url, workdir, args.browser)
    emit(workdir, "download", "completed", media=media.name)
    has_subtitles = sum(len(row["text"]) for row in rows) >= 50
    source = "subtitle" if has_subtitles else "local-asr-qwen3-mlx-0.6b"
    if not has_subtitles:
        from qwen_mlx_asr import transcribe as qwen_transcribe
        rows = qwen_transcribe(media, workdir, hotwords=args.hotwords, chunk_seconds=args.chunk_seconds)
    if not rows or sum(len(row["text"]) for row in rows) < 30:
        raise RuntimeError("Transcript is empty or too short; no note was published")
    transcript = "\n".join(f"[{stamp(row['start'])}] {row['text']}" for row in rows) + "\n"
    (workdir / "transcript.md").write_text(transcript, encoding="utf-8")
    emit(workdir, "frames")
    times = candidate_times(duration, scene_times(media, duration))
    preview_dir = workdir / "candidates"
    preview_dir.mkdir(exist_ok=True)
    candidates = []
    for index, seconds in enumerate(times, start=1):
        name = f"candidate-{index:02d}.jpg"
        extract_frame(media, seconds, preview_dir / name, preview=True)
        emit(workdir, "frames", completed=index, total=len(times))
        candidates.append({"index": index, "seconds": seconds, "timestamp": stamp(seconds), "file": f"candidates/{name}"})
    columns = min(4, len(candidates))
    rows = math.ceil(len(candidates) / columns)
    call(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-pattern_type", "glob", "-i", str(preview_dir / "*.jpg"), "-vf", f"tile={columns}x{rows}", "-frames:v", "1", str(workdir / "contact-sheet.jpg")])
    emit(workdir, "frames", "completed", completed=len(times), total=len(times))
    title = str(meta.get("title") or "")
    title_series_match = re.search(r"P(\d+)】?$", title.strip(), re.I)
    series_part = args.series_part or (int(title_series_match.group(1)) if title_series_match else None)
    slug_part = series_part or part
    slug = f"{bvid}-P{slug_part:02d}"
    manifest = {"id": slug, "bvid": bvid, "part": part, "series_part": series_part, "title": meta.get("title"), "creator": meta.get("uploader"), "source_tags": meta.get("tags") or [], "duration_seconds": duration, "duration": stamp(duration), "source_url": source_url, "processed": dt.date.today().isoformat(), "transcript_source": source, "subtitle_file": subtitle_name if source == "subtitle" else None, "media_file": media.name, "candidates": candidates, "selected": []}
    (workdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"workdir": str(workdir), "id": slug, "title": manifest["title"], "transcript_source": source, "candidate_count": len(candidates)}, ensure_ascii=False))


def load_manifest(workdir: Path) -> dict:
    return json.loads((workdir / "manifest.json").read_text(encoding="utf-8"))


def select(args: argparse.Namespace) -> None:
    workdir = args.workdir.expanduser().resolve()
    manifest = load_manifest(workdir)
    media = workdir / manifest["media_file"]
    selected_dir = workdir / "assets"
    selected_dir.mkdir(exist_ok=True)
    indices = [int(x) for x in args.indices.split(",") if x.strip()]
    if len(indices) != len(set(indices)) or len(indices) > 12:
        raise ValueError("Choose at most 12 unique frame indices")
    by_index = {row["index"]: row for row in manifest["candidates"]}
    if any(x not in by_index for x in indices):
        raise ValueError("Frame index is absent from the candidate list")
    selected = []
    for index in indices:
        row = by_index[index]
        name = f"{manifest['id']}-frame-{int(row['seconds']):06d}.png"
        if not (selected_dir / name).is_file():
            extract_frame(media, row["seconds"], selected_dir / name, preview=False)
        selected.append({**row, "file": f"../assets/{name}"})
    wanted = {Path(row["file"]).name for row in selected}
    for old in manifest["selected"]:
        old_file = selected_dir / Path(old["file"]).name
        if old_file.name not in wanted and old_file.is_file():
            old_file.unlink()
    manifest["selected"] = selected
    (workdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(selected, ensure_ascii=False))


def draft(args: argparse.Namespace) -> None:
    """Create a simplified, time-aligned editing scaffold without changing raw ASR."""
    from opencc import OpenCC

    workdir = args.workdir.expanduser().resolve()
    manifest = load_manifest(workdir)
    cc = OpenCC("t2s")
    frames = sorted(manifest["selected"], key=lambda row: row["seconds"])
    lines = []
    paragraph = []
    length = 0
    frame_index = 0

    def flush() -> None:
        nonlocal paragraph, length
        if paragraph:
            value = "".join(paragraph).rstrip("，,；; ")
            if value and value[-1] not in "。！？!?":
                value += "。"
            lines.append(value)
            paragraph = []
            length = 0

    for raw in (workdir / "transcript.md").read_text(encoding="utf-8").splitlines():
        match = re.match(r"\[(\d{2}:\d{2}:\d{2})\]\s*(.+)", raw)
        if not match:
            continue
        at = parse_time(match.group(1))
        while frame_index < len(frames) and frames[frame_index]["seconds"] <= at:
            flush()
            lines.append(f"![](<{frames[frame_index]['file']}>)\n\n*画面说明待核查。*")
            frame_index += 1
        value = cc.convert(match.group(2)).strip()
        if not value:
            continue
        for sentence in re.split(r"(?<=[。！？!?])", value):
            if not sentence:
                continue
            if sentence[-1] not in "。！？!?；;，,":
                sentence += "，"
            paragraph.append(sentence)
            length += len(sentence)
            if length >= 220:
                flush()
    flush()
    while frame_index < len(frames):
        lines.append(f"![](<{frames[frame_index]['file']}>)\n\n*画面说明待核查。*")
        frame_index += 1
    output = workdir / "transcript_draft.md"
    output.write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"draft": str(output), "paragraphs_and_frames": len(lines)}, ensure_ascii=False))


def frame_paths(workdir: Path, slug: str, row: dict, vault: Path | None = None) -> tuple[Path, Path | None]:
    link = row["file"]
    match = re.fullmatch(rf"\.\./assets/({re.escape(slug)}-frame-[0-9]+\.png)", link)
    if not match:
        raise ValueError(f"Invalid selected frame link: {link}")
    name = match.group(1)
    published_frame = vault / "Video Notes" / "assets" / name if vault is not None else None
    return workdir / "assets" / name, published_frame


def publish(args: argparse.Namespace) -> None:
    vault = None if args.validate_only else configured_vault()
    workdir = args.workdir.expanduser().resolve()
    manifest = load_manifest(workdir)
    note = workdir / "note.md"
    body = note.read_text(encoding="utf-8")
    from coverage import validate as validate_coverage
    validate_coverage(workdir)
    from quality import validate as validate_quality
    validate_quality(workdir)
    if "## 完整转写" not in body or "## 自测问题" not in body or not body.startswith("---\n"):
        raise ValueError("Note needs frontmatter, review questions, and full transcript")
    frontmatter_match = re.match(r"\A---\n(.*?)\n---\n", body, re.S)
    if not frontmatter_match:
        raise ValueError("Invalid YAML frontmatter")
    frontmatter = frontmatter_match.group(1)
    for key in ("title", "creator", "video_keywords", "content_keywords", "transcript_source"):
        if not re.search(rf"(?m)^{key}:\s*\S", frontmatter):
            raise ValueError(f"Missing frontmatter property: {key}")
    def property_value(key: str):
        match = re.search(rf"(?m)^{key}:\s*(.+)$", frontmatter)
        if not match:
            raise ValueError(f"Missing frontmatter property: {key}")
        try:
            return ast.literal_eval(match.group(1).strip())
        except (ValueError, SyntaxError) as exc:
            raise ValueError(f"Use a quoted scalar or inline list for {key}") from exc
    for key in ("title", "creator"):
        if property_value(key) != manifest[key]:
            raise ValueError(f"Frontmatter {key} differs from source metadata")
    video_keywords = property_value("video_keywords")
    content_keywords = property_value("content_keywords")
    if not isinstance(video_keywords, list) or not isinstance(content_keywords, list) or not content_keywords:
        raise ValueError("Keyword properties must be inline lists; content_keywords cannot be empty")
    if any(tag not in manifest.get("source_tags", []) for tag in video_keywords):
        raise ValueError("video_keywords must contain only original Bilibili tags")
    if property_value("transcript_source") != manifest["transcript_source"]:
        raise ValueError("Frontmatter transcript_source differs from manifest")
    if property_value("part") != manifest["part"]:
        raise ValueError("Frontmatter part differs from Bilibili page part")
    if manifest.get("series_part") is not None and property_value("series_part") != manifest["series_part"]:
        raise ValueError("Frontmatter series_part differs from manifest")
    import yaml
    metadata = yaml.safe_load(frontmatter)
    tags = metadata.get("tags", [])
    required_tags = [f"UP主/{manifest['creator']}"]
    if metadata.get("series"):
        required_tags.append(f"系列/{metadata['series']}")
    if args.category == "History":
        dynasties = metadata.get("dynasties")
        if not isinstance(dynasties, list) or any(not isinstance(d, str) for d in dynasties):
            raise ValueError("History notes require a dynasties list")
        required_tags.extend(f"朝代/{d}" for d in dynasties)
    if not isinstance(tags, list) or any(tag not in tags for tag in required_tags):
        raise ValueError("Missing creator, series, or dynasty tags")
    full_text = body.split("## 完整转写", 1)[1]
    if len(re.sub(r"\s|!\[[^]]*\]\([^)]*\)", "", full_text)) < 100:
        raise ValueError("Full transcript section is too short")
    if re.search(r"(?m)^\[\d{2}:\d{2}:\d{2}\]", full_text):
        raise ValueError("Full transcript still contains timestamped ASR lines")
    for row in manifest["selected"]:
        staged_frame, _ = frame_paths(workdir, manifest["id"], row, vault)
        if row["file"] not in body or not staged_frame.is_file():
            raise ValueError(f"Selected frame is missing from note or workdir: {row['file']}")
        if body.count(row["file"]) != 1 or full_text.count(row["file"]) != 1:
            raise ValueError(f"Selected frame must appear once inside the full prose: {row['file']}")
        if f"(<{row['file']}>)" not in body and f"({row['file']})" not in body:
            raise ValueError(f"Frame link must be relative to the note: {row['file']}")
    mentioned_frames = set(re.findall(rf"\.\./assets/{re.escape(manifest['id'])}-frame-[0-9]+\.png", body))
    available_frames = {row["file"] for row in manifest["selected"]}
    if mentioned_frames != available_frames:
        raise ValueError("Note frame links and selected frames differ")
    if args.validate_only:
        print(json.dumps({"valid": True, "note": str(note), "frames": len(available_frames)}, ensure_ascii=False))
        return
    assert vault is not None
    target_dir = vault / "Video Notes" / args.category
    target_note = target_dir / f"{manifest['id']}.md"
    if target_note.exists():
        raise FileExistsError(f"Output already exists: {target_note}")
    frame_pairs = [frame_paths(workdir, manifest["id"], row, vault) for row in manifest["selected"]]
    for _, target_frame in frame_pairs:
        if target_frame.exists():
            raise FileExistsError(f"Frame already exists in shared assets: {target_frame}")
    target_dir.mkdir(parents=True, exist_ok=True)
    shared_assets = vault / "Video Notes" / "assets"
    if frame_pairs:
        shared_assets.mkdir(parents=True, exist_ok=True)
    copied = []
    note_created = False
    try:
        for staged_frame, target_frame in frame_pairs:
            with staged_frame.open("rb") as source, target_frame.open("xb") as destination:
                copied.append(target_frame)
                shutil.copyfileobj(source, destination)
        with target_note.open("x", encoding="utf-8") as file:
            note_created = True
            file.write(body)
    except Exception:
        if note_created:
            target_note.unlink(missing_ok=True)
        for target_frame in copied:
            target_frame.unlink(missing_ok=True)
        raise
    result = {"note": str(target_note), "frames": len(manifest["selected"]), "transcript_source": manifest["transcript_source"]}
    if getattr(args, "keep_media", False):
        verify_publication(workdir, manifest, args.category)
        result["publication_verified"] = True
        result["media_retained"] = True
        print(json.dumps(result, ensure_ascii=False))
        return
    try:
        result["removed_staging_files"] = cleanup_staging(workdir, manifest, args.category)
    except (OSError, ValueError) as exc:
        result["cleanup_error"] = str(exc)
    print(json.dumps(result, ensure_ascii=False))


def verify_publication(workdir: Path, manifest: dict, category: str) -> None:
    """Remove bulky generated media only after verifying the published note and frames."""
    slug = manifest["id"]
    if not re.fullmatch(r"BV[0-9A-Za-z]{10}-P[0-9]{2,}", slug):
        raise ValueError("Invalid manifest ID; staging files were kept")
    vault = configured_vault()
    target_dir = vault / "Video Notes" / category
    staged_note = workdir / "note.md"
    published_note = target_dir / f"{slug}.md"
    if not staged_note.is_file() or not published_note.is_file() or staged_note.read_bytes() != published_note.read_bytes():
        raise ValueError("Published note is missing or differs from staged note; staging files were kept")
    for row in manifest["selected"]:
        staged_frame, published_frame = frame_paths(workdir, slug, row, vault)
        if not staged_frame.is_file() or not published_frame.is_file() or staged_frame.read_bytes() != published_frame.read_bytes():
            raise ValueError(f"Published frame is missing or differs: {row['file']}; staging files were kept")
def cleanup_staging(workdir: Path, manifest: dict, category: str) -> list[str]:
    """Remove generated media only after exact publication readback."""
    verify_publication(workdir, manifest, category)
    removed = []
    media_names = {"audio.m4a", "audio.wav", "contact-sheet.jpg"}
    for path in workdir.iterdir():
        if not path.is_file() or path.is_symlink():
            continue
        if path.name in media_names or (path.stem == "source" and path.suffix.lower() in {".mp4", ".mkv", ".webm"}) or re.fullmatch(r"sample-[0-9]+\.wav", path.name):
            path.unlink()
            removed.append(path.name)
    candidates = workdir / "candidates"
    if candidates.is_dir() and not candidates.is_symlink():
        for path in candidates.iterdir():
            if path.is_file() and not path.is_symlink() and re.fullmatch(r"candidate-[0-9]+\.jpg", path.name):
                path.unlink()
                removed.append(f"candidates/{path.name}")
        if not any(candidates.iterdir()):
            candidates.rmdir()
    return sorted(removed)


def cleanup(args: argparse.Namespace) -> None:
    workdir = args.workdir.expanduser().resolve()
    removed = cleanup_staging(workdir, load_manifest(workdir), args.category)
    print(json.dumps({"workdir": str(workdir), "removed_staging_files": removed}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    from progress import emit
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("url")
    prep.add_argument("--workdir", type=Path, required=True)
    prep.add_argument("--browser", choices=["chrome", "edge", "firefox", "safari"])
    prep.add_argument("--chunk-seconds", type=int, default=60)
    prep.add_argument("--hotwords", default="", help="Comma-separated verified terms for Qwen3-ASR context")
    prep.add_argument("--series-part", type=int, help="Series installment number when the title does not end in P<N>")
    prep.add_argument("--max-minutes", type=int, default=90)
    prep.set_defaults(func=prepare)
    selection = commands.add_parser("select")
    selection.add_argument("workdir", type=Path)
    selection.add_argument("--indices", required=True, help="Comma-separated candidate indices; empty string selects none")
    selection.set_defaults(func=select)
    drafting = commands.add_parser("draft")
    drafting.add_argument("workdir", type=Path)
    drafting.set_defaults(func=draft)
    publication = commands.add_parser("publish")
    publication.add_argument("workdir", type=Path)
    publication.add_argument("--category", choices=["History", "Literature"], required=True)
    publication.add_argument("--validate-only", action="store_true", help="Check the staged note without writing to Obsidian")
    publication.add_argument("--keep-media", action="store_true", help="Retain source media for user-requested follow-up tests")
    publication.set_defaults(func=publish)
    cleaning = commands.add_parser("cleanup", help="Remove generated media after verifying the published note and frames")
    cleaning.add_argument("workdir", type=Path)
    cleaning.add_argument("--category", choices=["History", "Literature"], required=True)
    cleaning.set_defaults(func=cleanup)
    review = commands.add_parser("coverage", help="Create pending source-segment review checklist")
    review.add_argument("workdir", type=Path)
    def make_coverage(args):
        from coverage import create
        print(create(args.workdir.expanduser().resolve()))
    review.set_defaults(func=make_coverage)
    status = commands.add_parser("status", help="Show latest stages, failures and recovery instructions")
    status.add_argument("workdir", type=Path)
    status.set_defaults(func=lambda a: print((a.workdir/'progress.json').read_text()))
    quality_cmd = commands.add_parser("quality", help="Audit grounded inventory and flag source doubts")
    quality_cmd.add_argument("workdir", type=Path)
    def audit_quality(a):
        from quality import audit
        report=audit(a.workdir)
        print(json.dumps(report,ensure_ascii=False))
        if not report["gate"]["valid"]:raise ValueError("Quality review blocked; see quality-report.json: "+report["gate"]["error"])
    quality_cmd.set_defaults(func=audit_quality)
    init_quality=commands.add_parser("quality-init",help="Create pending item review for a legacy staged transcript; never migrate historical notes")
    init_quality.add_argument("workdir",type=Path)
    def create_quality(a):
        from quality import create
        print(create(a.workdir))
    init_quality.set_defaults(func=create_quality)
    boundary=commands.add_parser("boundaries",help="Generate listen-around-boundary checklist without deleting text")
    boundary.add_argument("workdir",type=Path)
    def inspect_boundaries(a):
        from boundaries import inspect
        print(json.dumps(inspect(a.workdir),ensure_ascii=False))
    boundary.set_defaults(func=inspect_boundaries)
    stage = commands.add_parser("stage", help="Report externally performed writing or review checkpoint")
    stage.add_argument("workdir",type=Path); stage.add_argument("--phase",choices=["writing","review"],required=True)
    stage.add_argument("--state",choices=["running","completed","failed"],required=True);stage.add_argument("--message",required=True)
    stage.add_argument("--completed",type=int);stage.add_argument("--total",type=int)
    stage.set_defaults(func=lambda a: emit(a.workdir,a.phase,a.state,message=a.message,completed=a.completed,total=a.total))
    args = parser.parse_args()
    global CURRENT_WORKDIR
    CURRENT_WORKDIR=args.workdir.expanduser().resolve()
    try:
        tracked=args.command not in {"status","stage","quality"}
        if tracked and args.command!="prepare":emit(args.workdir,args.command,recovery="Repeat identical command; prepared manifest: continue select/draft/coverage. Never overwrite existing published output.")
        args.func(args)
        if tracked:emit(args.workdir,args.command,"completed")
    except (RuntimeError, ValueError, OSError, KeyError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        if getattr(args,"workdir",None) is not None:
            failed_phase=json.loads((args.workdir/'progress.json').read_text())['current']['phase'] if (args.workdir/'progress.json').exists() else args.command
            emit(args.workdir,args.command,"failed",failure_point=failed_phase,failure=str(exc),recovery="Preserve workdir. Fix reported error, repeat identical command. For stale review renew hashes and item review; for published target inspect existing output.")
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
