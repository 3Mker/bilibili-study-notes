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

The workflow uses `uv`, `yt-dlp`, and `ffmpeg`. Local ASR uses `qwen3-asr-mlx` and `soundfile`; transcript drafting uses `opencc-python-reimplemented`. Qwen3-ASR can use substantial unified memory, so process one video at a time. See [SKILL.md](SKILL.md) for the workflow and cleanup checks.
