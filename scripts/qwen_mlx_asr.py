#!/usr/bin/env python3
"""Checkpointed Qwen3-ASR transcription for Apple Silicon; run with uv dependencies."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path


def transcribe(media: Path, workdir: Path, *, hotwords: str = "", model_id: str = "mlx-community/Qwen3-ASR-0.6B-bf16") -> list[dict]:
    import numpy as np
    import soundfile as sf

    workdir.mkdir(parents=True, exist_ok=True)
    wav = workdir / "audio.wav"
    if not wav.exists():
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(media), "-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(wav)], check=True)
    audio, rate = sf.read(wav, dtype="float32")
    if rate != 16000 or audio.ndim != 1:
        raise ValueError("Expected 16 kHz mono WAV")
    checkpoint = workdir / "qwen_segments.jsonl"
    rows = [json.loads(line) for line in checkpoint.read_text(encoding="utf-8").splitlines()] if checkpoint.exists() else []
    saved = {int(row["index"]): row for row in rows}
    duration = len(audio) / rate
    # Find a low-energy cut near each 90-second boundary to reduce clipped words.
    cut_seconds = [0.0]
    target = 90
    while target < duration:
        lo = max(cut_seconds[-1] + 60, target - 5)
        hi = min(duration - 1, target + 5)
        candidates = np.arange(lo, hi, 0.25)
        def energy(at: float) -> float:
            start = int(at * rate)
            window = audio[start:start + int(0.18 * rate)]
            return float(np.mean(window * window)) if len(window) else math.inf
        cut = float(min(candidates, key=energy)) if len(candidates) else float(target)
        cut_seconds.append(cut)
        target += 90
    cuts = [int(value * rate) for value in cut_seconds] + [len(audio)]
    if cuts[0] != 0:
        raise AssertionError("Invalid first cut")
    for index, row in saved.items():
        if index >= len(cuts) - 1 or abs(row["start"] - cuts[index] / rate) > 0.3 or abs(row["end"] - cuts[index + 1] / rate) > 0.3 or row.get("model") != model_id:
            raise ValueError("Existing Qwen checkpoint differs from this audio or model")
    # A fresh child process per chunk releases MLX model memory after inference.
    del audio
    for index, (start, end) in enumerate(zip(cuts[:-1], cuts[1:])):
        if index in saved:
            continue
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", str(wav), str(checkpoint), str(index), str(start), str(end), model_id, hotwords], check=True)
        rows = [json.loads(line) for line in checkpoint.read_text(encoding="utf-8").splitlines()]
        saved = {int(row["index"]): row for row in rows}
        row = saved[index]
        print(json.dumps({"completed": index + 1, "total": len(cuts) - 1, "start": row["start"], "end": row["end"]}, ensure_ascii=False), flush=True)
    ordered = [saved[index] for index in range(len(cuts) - 1)]
    transcript = "\n".join(f"[{int(row['start']) // 3600:02d}:{int(row['start']) // 60 % 60:02d}:{int(row['start']) % 60:02d}] {row['text']}" for row in ordered) + "\n"
    (workdir / "transcript_qwen.md").write_text(transcript, encoding="utf-8")
    return ordered


def worker(wav: Path, checkpoint: Path, index: int, start: int, end: int, model_id: str, hotwords: str) -> None:
    import soundfile as sf
    from qwen3_asr_mlx import Qwen3ASR

    audio, rate = sf.read(wav, dtype="float32")
    with Qwen3ASR.from_pretrained(model_id) as model:
        result = model.transcribe(audio[start:end], language="Chinese", context=f"Vocabulary: {hotwords}" if hotwords else None)
    row = {"index": index, "start": start / rate, "end": end / rate, "text": result.text.strip(), "language": result.language, "model": model_id}
    with checkpoint.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    if len(sys.argv) == 9 and sys.argv[1] == "--worker":
        worker(Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), sys.argv[7], sys.argv[8])
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("media", type=Path)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--hotwords", default="")
    parser.add_argument("--model", default="mlx-community/Qwen3-ASR-0.6B-bf16")
    args = parser.parse_args()
    transcribe(args.media.expanduser().resolve(), args.workdir.expanduser().resolve(), hotwords=args.hotwords, model_id=args.model)


if __name__ == "__main__":
    main()
