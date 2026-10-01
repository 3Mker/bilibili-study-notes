# Local Chinese ASR options (reviewed 2026-09-29)

- `whisper.cpp` with a multilingual model is an optional fallback. In one prior Chinese history-video comparison it produced substantial Traditional Chinese output and misrecognized proper names. Traditional-to-simplified conversion changes script, not recognition accuracy. It requires `whisper-cli` and a model file supplied with `--model`.
- Qwen3-ASR 0.6B/1.7B (Qwen, 2026) supports Mandarin; `qwen3-asr-mlx` is an independent Apple MLX implementation. The 0.6B version is the default local ASR. In one roughly 31-minute history-video run on Apple Silicon with 16 GB unified memory, it completed 21 checkpointed chunks and produced simplified text. It still missed some names and phrases; this is an anecdotal check, not a character-error-rate benchmark or proof of superiority on future videos. Runtime warnings can appear despite completion, so inspect each run's output.
- SenseVoiceSmall via sherpa-onnx is a lightweight Chinese candidate. Its ONNX runtime and Mandarin support are documented; it is older than Qwen3-ASR. Test local speed and accuracy before claiming superiority.
- FireRedASR2S is a newer Mandarin-focused release, but reported results are not a direct comparison on videos processed by this skill or on Apple devices. Treat it as a research option until tested.

Sources: https://github.com/QwenLM/Qwen3-ASR ; https://github.com/gabrimatic/qwen3-asr-mlx ; https://github.com/k2-fsa/sherpa-onnx ; https://github.com/FireRedTeam/FireRedASR2S
