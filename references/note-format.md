# Note format

Use simplified Chinese. Metadata separates original Bilibili tags from concepts derived from the full transcript. Use `video_keywords: []` if none of the original tags are useful. Keep the raw timestamped `transcript.md` in the staging workdir for audit; publish a readable prose transcript.

```markdown
---
title: "视频原始标题"
source: "https://www.bilibili.com/video/BV.../?p=1"
bvid: "BV..."
series: "大唐开国" # Include when identified from the title or source metadata.
part: 1
series_part: 2 # Include when the title identifies a numbered installment; `part` remains the Bilibili page index.
creator: "UP 主名称"
video_keywords: ["从视频原生标签筛选的关键词"]
content_keywords: ["全文归纳的事件", "时间节点", "人物或文学知识点"]
dynasties: ["北魏", "南梁"] # History notes only; include main dynasties covered.
tags:
  - "UP主/创作者名称"
  - "系列/大唐开国"
  - "朝代/北魏"
  - "朝代/南梁"
duration: "00:05:23"
processed: "YYYY-MM-DD"
transcript_source: "subtitle"
topics: [history] # or literature
---

# 视频原始标题

> 来源与转写说明：注明字幕或 ASR、专名是否校对，及笔记记录的是视频观点。

## 速览
几句话概括讨论范围和主线。

## 要点与脉络
概括论证、事件或文学知识，可给少量源视频跳转链接。

## 自测问题
1. ……？

## 待核查
有意义的 ASR 疑点与未经外部核查的说法。没有则省略。

## 完整转写

将全文整理为段落。保留叙事、论据、例子、转折和结论，不把摘要冒充全文。不确定的专名标记疑点，不凭印象补出引文、数字或因果。

![](../assets/BV...-P01-frame-000130.png)

*画面说明：只描述实际检查过的内容。*

继续正文……
```

The full transcript is a complete paraphrase of the video's substantive speech, not a condensed summary; retain the important sequence, evidence, explanations, examples, and turns in the speaker's argument while removing filler and repetition. Omit unrelated advertising from the study prose and disclose the omission. It has no timestamp prefixes. Source-time links may appear in captions, but not before every spoken segment. Place every selected image once in the prose near the closest relevant passage. Mention when a frame is only an illustration. Do not claim local ASR is a human-verified verbatim transcript.

## Creator, series, dynasty, and Obsidian tags

- Keep `creator` as the uploader property. Add `series` when the title or source metadata identifies one, and keep its numbered installment in `series_part`; do not infer a series from subject similarity alone.
- For History notes, `dynasties` is a YAML list of the main dynasties materially covered by the video. Include multiple dynasties when central to the narrative, but exclude passing mentions and unrelated later context.
- Use one Obsidian `tags` list for stable navigation: `UP主/<creator>`, `系列/<series>` when known, and `朝代/<dynasty>` for each main dynasty. Merge with any existing `tags` property rather than creating a second one. Do not copy every `video_keywords` or `content_keywords` entry into tags.
- Keep `video_keywords` for selected original Bilibili tags and `content_keywords` for ideas extracted from the transcript; these are distinct from the structured creator/series/dynasty fields and the stable Obsidian tag taxonomy.

## Luna editing handoff and coverage check

When Luna edits `note.md`, provide `transcript.md` as the full source, `transcript_draft.md` as a timing and image-placement aid, `manifest.json` for source metadata, the selected-frame list, this format reference, and any existing `note.md` draft. The transcript is authoritative for coverage; the scaffold, title, and summary are not substitutes for reading it.

Use this task instruction, filling in the actual workdir paths:

> Edit `note.md` using the supplied source files and this note format. Read all of `transcript.md` before editing. Rewrite all substantive spoken content in its original order, preserving each segment's events, explanations, evidence, examples, qualifications, transitions, and conclusions. Use the timestamped ASR segments as an internal coverage checklist, then merge them into natural continuous prose: the final note must not show timestamps or feel like separate segment summaries. Remove filler, repetition, ASR debris, and unrelated ads; disclose omitted ads. Do not invent facts or add external research. Mark uncertain names, dates, numbers, and quotations. Preserve correct metadata and every selected image link, placing each image once near the relevant passage. Before returning, compare the full source against the finished `完整转写` section. Report the number of source segments checked, any deliberate omissions, and remaining uncertainties in a brief handoff message; keep this checklist out of the note.

The parent must review source coverage before publishing. Check every ASR segment from beginning to end and confirm each substantive point is represented or deliberately omitted for a stated reason. A large difference in source and rewrite length is a warning to inspect for missing content, not a word-count target or a substitute for the segment review. The pipeline's structural validation checks note fields and image links; it does not prove that the full spoken content was covered.
