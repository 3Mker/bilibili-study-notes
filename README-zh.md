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

工作流需要 Python、`yt-dlp` 和 `ffmpeg`；`uv` 用于建立隔离环境。本地转写使用 `qwen3-asr-mlx` 与 `soundfile`；转写稿草稿生成使用 `opencc-python-reimplemented`。Qwen3-ASR 可能占用较多统一内存，因此一次处理一个视频。完整流程与清理校验见 [SKILL.md](SKILL.md)。

## 隔离环境与独立配置

macOS ARM64 使用 Python3.12 和锁定依赖。锁文件是环境快照，不是跨平台锁文件。ffmpeg 需单独加入 PATH；仅安装 imageio-ffmpeg 的 Python 包不会自动生成 ffmpeg 命令。

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-macos.lock
.venv/bin/python -m unittest discover -s tests -v
```

在 skill 安装目录外保存私人 JSON，例如：

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

使用配置环境的 Python；runtime.py 提供 PATH 和默认值，不会安装依赖或切换解释器。已有 vault、model、cache 环境变量优先于 JSON。默认目标60秒，输入或转写参数变化必须用新工作区。max_minutes 是整片时长上限，会拒绝更长视频，不会截取开头。未启用 Whisper 或付费转写 API。

## 审查、进度与更新

发布前逐项完成 coverage.json 和 quality.json，核对源内容与完整正文，给人物、年份、引文疑点提供查验依据或可见标记。先运行 quality WORKDIR，再运行 publish WORKDIR --category History --validate-only。发布拒绝覆盖既有笔记；--keep-media 在逐字节读回后保留媒体。门禁、哈希与模型自评不能证明语义准确。句界只生成复听清单，未开启重叠或自动去重。

检查点实时输出至 stderr，也可查询 status；不会自动唤醒闲置父对话，活跃调用者需读取并回报。模型整理和审核由调用者主动更新 stage。更新脚本先备份、保留私人运行说明与独立配置，支持回滚。

详见 [完整流程](SKILL.md)、[逐项审查与进度](references/quality-and-progress.md)、[测试及依赖许可边界](references/testing-and-dependencies.md)。21项回归使用合成素材和模拟 worker，不证明完整视频转写准确或长片性能。本仓库不提交个人配置、笔记、转写、模型、缓存或测试媒体。
