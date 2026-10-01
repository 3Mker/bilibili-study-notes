# B站视频学习笔记

这是一个 Codex Skill，可将单个 B 站视频或分 P 视频整理成简体中文 Obsidian 复习笔记。它优先使用视频字幕；没有可用字幕时，使用 Apple MLX 上的本地 Qwen3-ASR；随后筛选重要画面，并生成来源元数据、全文归纳关键词、自测题和易读的完整转写。只有在发布后的笔记与选定画面通过逐字节核对后，才会删除生成的媒体文件。

## 安装

将本仓库克隆到 Codex skills 目录：

```sh
git clone https://github.com/3Mker/bilibili-study-notes.git "${CODEX_HOME:-$HOME/.codex}/skills/bilibili-study-notes"
```

## 配置 Obsidian

发布前，将 `BILIBILI_NOTES_VAULT` 设置为 Obsidian 库的根目录。Skill 会将笔记写入 `Video Notes/History/` 或 `Video Notes/Literature/`，将选定画面放入 `Video Notes/assets/`。例如：

```sh
export BILIBILI_NOTES_VAULT="/path/to/your/Obsidian/vault"
```

## 依赖

工作流需要 `uv`、`yt-dlp` 和 `ffmpeg`。本地转写使用 `qwen3-asr-mlx` 与 `soundfile`；转写稿草稿生成使用 `opencc-python-reimplemented`。Qwen3-ASR 可能占用较多统一内存，因此一次处理一个视频。完整流程与清理校验见 [SKILL.md](SKILL.md)。
