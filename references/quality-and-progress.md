# Item-level review and visible checkpoints

Run `doctor` through the installed launcher before media work. Default target remains 60 seconds; do not expand it based on word count or a successful short sample.

## Grounded full-content review

`coverage WORKDIR` creates pending `coverage.json` and `quality.json`. Build the item inventory **from the entire source before polishing the draft**. Each source segment can contain several distinct events, people, arguments, examples, qualifications and transitions; split them into individual items rather than treating a segment summary as coverage. Record the substantive items in source order. For each item:

```json
{"kind":"example","source_quote":"母亲剪发换酒肉","decision":"included","note_quote":"母亲剪下头发换来酒肉，设宴款待来客。"}
```

`source_quote` must occur literally in its source segment; `note_quote` must occur literally in the **完整转写** prose. They locate passages; they do not prove the paraphrase is correct. Keep ASR's raw spelling in the source anchor, and put corrected wording in the note anchor. `kind` is event/person/argument/example/qualification/transition/conclusion. Only filler/advertisement/asr_debris may be omitted with an explicit reason; restore substantive omissions. An unintelligible factual phrase can be inventoried as asr_debris with its raw phrase and reason, but this must not disguise understandable content as garbage.

Set each segment's `inventory_reviewed` and `uncertainties_reviewed` to true only after comparing the source and finished prose. Complete source and final-note hashes and identify the actual reviewer. The parent must independently inspect the source items and matching passages, especially writer corrections and omitted examples; a writer's self-assessment and hashes are not evidence of full accuracy.

Record uncertain people, year/number, quotation, claim and boundary text in `uncertainties`:

```json
{"kind":"year","source_quote":"315年","status":"marked","note_quote":"视频称315年；年份未核查。","reason":"No inspected original citation"}
```

A `verified` issue needs concrete inspected-audio/frame/reference `evidence`; a `marked` issue needs a visible matching note quote and reason. Pending or unsupported claims block publication. Check the entire source for names/ASR homophones, years, genealogy, negation, pronoun referents and quote interpretation; the year/quotation heuristic cannot detect all names or factual errors. Do not fabricate a historical reconstruction to satisfy the schema. `quality WORKDIR` prints and saves audit findings, but the report explicitly does not certify semantic accuracy. `quality-init WORKDIR` can create pending item review for a legacy staging task, leaving old coverage untouched; do not run it on historical tasks unless revising them is authorized. Publish requires completed item review even for legacy segment coverage. Old published files are never migrated.

## Sentence boundaries

`boundaries WORKDIR` reads Qwen checkpoint rows and lists each previous tail/next head with a six-second listen interval. Exact suffix/prefix matches are **review candidates**, not deletion instructions. Do not strip matching strings: repeated emphasis, repeated names and valid adjacent examples are legitimate. Current Qwen result has no aligned word timestamps; small overlapping audio plus text-only deduplication cannot reliably decide who owns each word. Keep low-energy, non-overlapping 60-second target cuts. Review across boundaries and retain uncertain words marked in prose. No overlap mode is enabled in production.

## Active conversation checkpoints

CLI stages write `progress.json`/`progress.jsonl` and immediately emit flushed `[bilibili checkpoint]` events to stderr. Download and frame tools emit a heartbeat every15 seconds; ASR emits completed/total and next segment, plus each worker's timing/resources. `status WORKDIR` returns the current stage, elapsed wall time, counters and any failure point/recovery instructions. Elapsed time spans a stage's saved start and may include interruption downtime; it is not pure CPU/inference time.

Writing is performed by the selected language model, not silently by a CLI. The writer/caller must report it explicitly:

```sh
.venv/bin/python scripts/runtime.py stage WORKDIR --phase writing --state running --completed 0 --total 34 --message 'Full source read; drafting'
.venv/bin/python scripts/runtime.py stage WORKDIR --phase writing --state completed --completed 34 --total 34 --message 'Draft ready; parent item review still pending'
.venv/bin/python scripts/runtime.py stage WORKDIR --phase review --state completed --completed 34 --total 34 --message 'Source items and doubts checked; see quality.json'
.venv/bin/python scripts/runtime.py status WORKDIR
```

An executing Codex caller must use yielding commands and poll their output at most every30 seconds, relay meaningful stage/segment checkpoints into commentary, and report a failure with the exact stage and next recovery action. If running as a delegated task, the parent must continue reading the delegated tool's live output/status when that surface exists. Local Python cannot push a message into an arbitrary parent conversation; no hidden messaging connector or paid API is configured. Tool output is live for the active caller, but an inactive parent does not wake merely because a log file changed. If the selected delegation surface exposes only completion, report that limitation and have the parent poll this status entrypoint instead of promising automatic parent notification.
