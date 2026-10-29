# OpenJarvis report: verified Sakura changes — 29 October 2026

The report is a useful comparison, but its provider, skill-learning and packaging
claims partly describe older Sakura code. Sakura already has cloud-provider
adapters beyond Gemini, an owned llama.cpp/Colibri worker, learned procedures
that can become skills, source-linked history, and restricted disposable Docker
execution. These are retained. No OpenJarvis binaries or cryptocurrency mining
components are installed.

## Implemented

### Inference usage and budgets

Agent planning/reviewer windows capture Gemini `usageMetadata`, Ollama evaluation
counts, OpenAI-compatible usage and native-worker usage. Aggregate run records
survive restarts. **Agent → Task history → Agent telemetry** shows reported
input/output tokens, a separate cache-independent prompt estimate, cost and GPU
device energy. This is Agent inference accounting; ordinary Companion chat does
not yet have a persistent billing ledger.

Prices are configured under **Inference budgets and prices**, using keys such as
`gemini/exact-model-id`, `ollama/exact-model-name` or
`sakura-native/native-model-id`. Input/output prices are USD per million tokens.
There is no stale built-in price table, automatic billing query or invented zero
cost. Unknown usage or unconfigured prices remain unknown. Estimates exclude
cache discounts, tiered billing and tax; Gemini thought tokens are included in
output accounting when reported separately. Local model prices can explicitly
be set to zero; electricity is not API cost.

Optional limits apply per task and are checked **between planner calls**. The
token limit conservatively uses the larger of reported input and the byte-based
prompt estimate, plus output tokens. A configured cost limit refuses the first
call without an exact configured model price, and blocks subsequent planning if
reported usage is unavailable. An in-flight call can exceed a limit. Older run
totals are not retroactively repriced.

NVML samples device power at approximately 2 Hz and integrates joules over the
planning window. This includes rendering and other GPU processes. It is not
per-task electricity attribution, total-PC energy, CPU energy or cloud energy.
Unsupported hardware returns unmeasured. No CPU/GPU/SoC units are mixed.

### Planner loop guard

The planner receives a warning before a fourth identical ordinary action is
blocked. Six alternating calls are detected, and explicit polling tools have a
separate bounded budget. Manual proposals remain possible for legitimate user
requests. Changing argument order does not evade the fingerprint. The original
step cap, cancellation and completion reviewer are preserved.

### Opt-in local evidence index

**Agent → Skills → Local evidence index** proposes indexing a selected local
text/Markdown/CSV/JSON file or one completed tool result from the selected task.
Indexing and clearing use the existing approval flow; nothing crawls Google
Drive, email or other accounts automatically. File/result hashes are rechecked
at execution.

The SQLite index is scoped to workspace identity and uses FTS5 BM25 fused with
bounded local lexical-vector similarity via reciprocal-rank fusion. Hits include
adjacent chunks and source references. These are **not learned semantic
embeddings**. Existing upstream truncated connector responses cannot be recovered
by indexing them. No remote embedding service is invoked, and credentials are
redacted before storage. Original sources should be re-read before editing.

### Skill import and persistence

**Agent → Skills → Import SKILL.md** accepts a browser-selected Markdown file.
The bounded frontmatter subset accepts name/title, description, tool requirements
and dependencies; common tool aliases map to Sakura names. It records a source
label and SHA-256, rejects duplicates, missing dependencies and cycles, and checks
required tools before planning. Nested YAML/folded values and arbitrary vendor
extensions are not claimed to be fully supported. Required tools are availability
checks, never permission grants.

No archives, filesystem trees, symlinks, binaries or `scripts/` are installed by
this importer. Skill instructions remain untrusted guidance. Learned procedures
continue using the existing explicit skill-creation path; they do not retrain
model weights or acquire account permissions.

Skills and learning state now use unique temporary files, atomic replacement,
and cross-process Windows/POSIX locks with bounded retry. Two app instances can
update the same skills file without silently losing one update.

### Sandbox mount protection

The existing Docker runner keeps immutable image digests, no image pull, no
network, a read-only root, resource limits, dropped capabilities, an unprivileged
user and owned-container cleanup. It now rejects mounts containing credentials,
private keys, `.env`, `.ssh`, `.aws`, `.git/config`, private Sakura configuration,
symlinks or junctions. The scan runs before proposal and again before execution.
Choose a dedicated task folder without secrets; it will refuse a normal repo
with `.git/config` instead of silently exposing it. The scan is bounded to 50,000
entries. As with any host bind mount, a hostile same-user process can race file
creation after validation; this is not a VM or a hostile-user security boundary.

### Doctor and CI

Run `venv\Scripts\python.exe sakura_doctor.py --json` or use **Check installation
health** in Agent telemetry. It checks required modules, packaged UI assets and
disk space without starting a model or contacting cloud services. Optional
`--probe-local` performs bounded loopback-only health probes. The shared health
probe helper runs independent endpoints concurrently and rejects remote URLs.

`.github/workflows/windows-quality.yml` adds Windows Python/JavaScript checks,
Agent safety/usage/import tests, package/release contracts and a dependency-audit
job. These workflows run on GitHub **after this commit is pushed**. This is not a
claim that a new protected installer was built on a clean machine or that the
GitHub jobs have already passed. Hardware/model/owner-account tests remain local.

## Model comparison

`tools/benchmark-assistant.py` runs five small, real inference probes covering
follow-up context, explanation, unavailable sensors, JSON tool selection and
unsupported action claims. Generated tool calls are scored, never executed.
Scores are simple rubric checks, not GPQA, GAIA or a general intelligence rating.
Each result records model ID, dataset fingerprint, latency, usage, optional cost
and GPU device energy. JSONL output resumes completed cells; failed cells retry.
Only metrics and scores are retained, not generated replies or keys.

Examples from the Sakura folder:

```powershell
venv\Scripts\python.exe tools\benchmark-assistant.py --provider ollama --model sakura-native:YOUR_MODEL_ID --output desktop-profile\bench-native.jsonl
venv\Scripts\python.exe tools\benchmark-assistant.py --provider ollama --model qwen3-vl:4b-instruct --output desktop-profile\bench-qwen4b.jsonl
venv\Scripts\python.exe tools\benchmark-assistant.py --provider gemini --model YOUR_GEMINI_MODEL_ID --allow-cloud-cost --output desktop-profile\bench-gemini.jsonl
```

Gemini uses the key already saved through Sakura settings and requires explicit
`--allow-cloud-cost`. The benchmark does not change the universal AI, download
models, run shell actions generated by a model, or silently fall back to cloud.
The current UI/model need not be restarted to configure a benchmark; running
inference alongside gameplay or another generation can skew the measurement.

## Deliberately not represented as completed

This is not an OpenJarvis platform port. Full dataset suites, automatic connector
sync, learned semantic embeddings, GRPO/SFT/DSPy weight/prompt training, a provider
streaming rewrite, and non-NVIDIA energy backends remain separate work. Existing
approval memory is not broadened to domain-wide or remembered permission grants.
No new installer, APK or GitHub release is produced by these source changes.
