# OpenJarvis feature audit for Sakura

Reviewed on 22 October 2026 against the OpenJarvis README and user guide, then compared with the Sakura source tree and its Agent/assistant documentation.

OpenJarvis describes five layers: model intelligence, inference engines, agents, tools plus memory, and a learning loop. Its published feature set also includes scheduled agents, local memory and document indexing, community skills, hardware-aware engine selection, telemetry/evaluations, a CLI/SDK, and a streaming OpenAI-compatible API. This is a research framework as well as a desktop assistant, so feature parity does not mean copying its architecture wholesale.

## What Sakura already has

| OpenJarvis area | Sakura today |
| --- | --- |
| Local and cloud inference | Local Ollama/Qwen plus configured cloud providers. Sakura does not have OpenJarvis's ten-plus interchangeable native inference backends. |
| Voice-first desktop/mobile experience | Native Companion, Sakura Mobile, speech input/output, wake handling, camera/screen/audio perception and character animation. This is broader than OpenJarvis's general-purpose chat UI. |
| Tools and computer access | Timers, app launching, system status, file attachments, screen/audio context, web-backed time/weather/news, and approval-gated Agent file/shell/MCP/LinkedIn operations. |
| Multi-step agent | Agent planner proposes one step at a time; the user reviews and approves each action. It supports local file read/write/run, PowerShell, MCP and LinkedIn basic profile/post actions. It does not pretend to have tools for unavailable LinkedIn inbox/job operations. |
| Evidence and memory controls | PC answer pipeline uses evidence retrieval/citations for factual claims, with authored conversation responses and a restricted verified/user-confirmed fact ledger. This is distinct from OpenJarvis's general semantic document/memory store. |
| Device/resource awareness | PC status reports CPU, GPU/VRAM, RAM and disk; it is not yet used to auto-recommend or route every model/backend. |
| Security and approvals | Agent is local-only, uses exact one-shot action approval, rechecks file and MCP bindings, and stores provider credentials through protected OS storage. |

## Gaps found

1. **Agent work disappeared on app exit.** This made a partially completed workflow difficult to resume. Implemented in this audit: Agent task goals, step states, and actual tool results now persist locally; interrupted approvals are invalidated on restart; the panel has a clear-history control.
2. **Reusable skill catalog:** Agent tools are registered in code or discovered from a configured MCP server. There is no user-managed, installable skill catalog like OpenJarvis's markdown/pipeline skills.
3. **Scheduled/continuous Agent workflows:** Sakura has timers/reminders and a task planner, but it does not run arbitrary monitor/research workflows on a schedule. Existing approval requirements mean unattended external writes should not be added without explicit scheduling and permission design.
4. **Indexed personal knowledge base:** the Agent can read approved files in a selected workspace but does not build a persistent semantic index and retrieval pipeline over folders.
5. **Inference telemetry and evaluation:** system resource status exists, but per-turn token/cost/latency/energy reporting and repeatable Agent benchmarks are not a user-facing feature.
6. **Provider abstraction and hardware routing:** Sakura supports its current local runtime and cloud API choices; it does not offer all OpenJarvis engines or automatically benchmark and select among them.
7. **Developer interfaces and messaging connectors:** Sakura is a desktop/mobile product, not a Python SDK/CLI or general OpenAI-compatible streaming server. Discord, email, calendar and other channels are not built in; users can add MCP servers for supported account capabilities.

## Implementation decision

The persistence gap was implemented because it directly affected the user's interrupted Agent workflow. History stays in the local desktop profile, is bounded to 30 runs, truncates oversized output fields, and can be cleared from the Agent panel. Pending/running operations are marked interrupted after restart and are never replayed; the user must request and approve a fresh action. MCP credentials and ephemeral approval bindings are excluded from durable records.

The remaining gaps are separate product capabilities, not safe one-line integrations. In particular, importing third-party executable skills, running scheduled tools, and automatically training from conversation traces would need explicit trust, permissions, data-retention and evaluation controls. They remain documented gaps rather than being silently enabled.

## Source references

- [OpenJarvis README](https://github.com/open-jarvis/OpenJarvis)
- [OpenJarvis architecture and feature overview](https://open-jarvis.github.io/OpenJarvis/)
- [OpenJarvis skills guide](https://open-jarvis.github.io/OpenJarvis/user-guide/skills/)
- [OpenJarvis scheduled monitor guide](https://open-jarvis.github.io/OpenJarvis/user-guide/scheduled-monitor/)
