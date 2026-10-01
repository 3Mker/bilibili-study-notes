# Bilibili Study Notes

A Codex skill that turns one Bilibili video or video part into a simplified-Chinese Obsidian study note. It uses available subtitles first, then local Qwen3-ASR on Apple MLX, selects useful frames, and produces source metadata, transcript-derived keywords, review questions, and a readable full-text section. Generated media is removed only after the published note and selected frames pass byte-for-byte checks.

## Install

Clone this repository into your Codex skills directory:

```sh
git clone https://github.com/3Mker/bilibili-study-notes.git "${CODEX_HOME:-$HOME/.codex}/skills/bilibili-study-notes"
```

## Configure Obsidian

Before publishing, set `BILIBILI_NOTES_VAULT` to the root of your Obsidian vault. The skill writes notes under `Video Notes/History/` or `Video Notes/Literature/` and selected images under `Video Notes/assets/`. For example:

```sh
export BILIBILI_NOTES_VAULT="/path/to/your/Obsidian/vault"
```

## Requirements

The workflow uses Python, `yt-dlp`, and `ffmpeg`; `uv` is an optional environment installer. Local ASR uses `qwen3-asr-mlx` and `soundfile`; transcript drafting uses `opencc-python-reimplemented`. Qwen3-ASR can use substantial unified memory, so process one video at a time. See [SKILL.md](SKILL.md) for the workflow and cleanup checks.

## Reproducible local setup and checks

On macOS ARM64, use Python 3.12 with `requirements-macos.lock` in an isolated environment. This is an environment snapshot, not a cross-platform lockfile. Install `ffmpeg` separately, or put the imageio-ffmpeg executable on PATH; installing its Python package alone does not create an `ffmpeg` command. The workflow has no Whisper fallback or paid transcription API.

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-macos.lock
.venv/bin/python -m unittest discover -s tests -v
```

Keep machine settings outside the installation. For example, create a private JSON file with your actual paths:

```json
{
  "vault": "/path/to/Obsidian/vault",
  "model": "/path/to/local/model/snapshot",
  "environment": "/path/to/.venv",
  "cache": "/path/to/model/cache",
  "chunk_seconds": 60,
  "max_minutes": 90
}
```

```sh
export BILIBILI_CONFIG="/path/to/private/bilibili-local.json"
.venv/bin/python scripts/runtime.py doctor
.venv/bin/python scripts/runtime.py prepare URL --workdir /path/to/new/workdir
.venv/bin/python scripts/runtime.py status /path/to/workdir
```

The interpreter must be the configured environment's Python. `runtime.py` supplies PATH and defaults, but does not install dependencies or switch Python. Existing vault/model/cache environment variables override the JSON values. The target chunk default stays60 seconds; changing inputs or ASR settings requires a new workdir. The duration guard rejects a whole video longer than `max_minutes`; it does not trim the video.

Before publishing, complete both `coverage.json` and `quality.json` against the full source. Run `quality WORKDIR` and `publish WORKDIR --category History --validate-only`. Publish never overwrites existing notes. `--keep-media` retains media after exact note/image readback. Inventory anchors, hashes and model self-reports do not prove semantic accuracy. Sentence boundaries receive a listening checklist; overlap and automatic text deduplication are not enabled.

Checkpoints are emitted live to stderr and available through `status`. They do not automatically wake an inactive parent conversation; the active caller must poll and relay progress. Writing/review stages require explicit `stage` updates. See [quality and progress](references/quality-and-progress.md) and [testing and dependency boundaries](references/testing-and-dependencies.md).
