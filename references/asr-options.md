# Local Chinese ASR scope

This workflow prefers available Chinese subtitles and otherwise uses community Qwen3-ASR0.6B on Apple MLX. Whisper is no longer supported. A fresh child process handles each target60-second chunk, with low-energy cuts near target boundaries. Shorter bounded runs can be configured; none of these settings proves proper-name, quote or factual accuracy.

Do not infer that16GB memory is sufficient for arbitrary audio length or concurrent work. Keep ASR jobs serial, inspect worker RSS and MLX peaks as separate measurements, and monitor system pressure before enlarging a workload. No overlap/deletion strategy is enabled. The optional boundary checklist assists listening; it does not recover missing words automatically.

`qwen3-asr-mlx` is an independent community implementation, not the official Qwen runtime. Alternative recognizers are not installed or benchmarked by these scripts. See [testing and dependencies](testing-and-dependencies.md) for the pinned setup and validation limits.

Upstream: https://github.com/QwenLM/Qwen3-ASR ; https://github.com/gabrimatic/qwen3-asr-mlx
