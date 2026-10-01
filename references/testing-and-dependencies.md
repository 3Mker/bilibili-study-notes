# Validation and dependency boundaries

The pinned environment targets macOS ARM64 and Python3.12. `requirements-macos.lock` lists exact installed package versions; it is not a portable multi-platform lockfile and does not contain model weights or an ffmpeg command. Put a separately installed ffmpeg executable on PATH. `imageio-ffmpeg` can provide an executable, but its Python installation does not automatically name it `ffmpeg` on PATH.

Run from the repository root, using the isolated interpreter:

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m py_compile scripts/*.py
```

The21 regression tests use synthetic text, temporary directories/vaults and short generated WAV arrays. Worker inference is mocked for resume/failure tests; they do not download a model, publish personal notes or establish ASR accuracy. They cover:

- Checkpoint source/config binding, interrupted-worker recovery, corrupted rows and host/workdir locks retained by a surviving worker.
- Short VTT timestamps, prepare task identity and publication no-overwrite/readback/retained-media behavior.
- Missing item anchors/examples, disallowed substantive omission, unresolved or unmarked doubts and stale note hashes.
- Live stderr stage events, external-tool heartbeat/output preservation and nested-stage failure reporting.
- Repeated speech preserved by boundary inspection; JSON/environment precedence; install backup and rollback retaining private settings.

Real media integration, Metal peak memory, download authentication, model/temperature accuracy, full-text semantic coverage and active parent-message delivery are outside this regression suite. A successful suite or item gate is not a human transcript accuracy/CER benchmark. `doctor` inspects versions/files, without loading weights or proving ffmpeg codec support. Live checkpoints require the active caller to poll/relay them; there is no automatic parent-conversation push connector. Overlap and text deduplication remain disabled.

## External licenses

This repository does not vendor dependencies, downloaded weights or ffmpeg binaries. They retain their upstream licenses. Package metadata for the pinned core dependencies identifies qwen3-asr-mlx/MLX/PyYAML as MIT, SoundFile as BSD3-Clause, imageio-ffmpeg as BSD2-Clause, yt-dlp as Unlicense and OpenCC's Python reimplementation as Apache. NumPy declares a composite license expression covering its bundled components; consult its installed notices rather than treating it as a single redistributed binary. The full dependency graph has its own notices.

The community runtime's [MIT license](https://github.com/gabrimatic/qwen3-asr-mlx/blob/main/LICENSE) is separate from the [model card](https://huggingface.co/mlx-community/Qwen3-ASR-0.6B-bf16) and official model license. Read the exact chosen model's card/license when downloading it. FFmpeg's license depends on build options; [upstream explains LGPL/GPL differences](https://ffmpeg.org/legal.html). Check your executable with `ffmpeg -L`; a build with GPL components must not be described merely as the Python wrapper's BSD license. This update does not choose or add a license for the repository itself, which currently has no LICENSE file.
