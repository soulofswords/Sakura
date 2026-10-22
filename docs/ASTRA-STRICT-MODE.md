# Astra Strict Mode — PC pipeline

Current default: Medium. Set response_restriction_level to strict to use the factual-only policy described below. Medium keeps factual retrieval and memory validation, while allowing guarded nonfactual conversation; casual replies do not display fact-verification badges.

The enforced path is: question → registered retrieval → source/citation validation → exact evidence response → refusal if unsupported. Qwen is retained but cannot produce answers through the public PC chat or AI VTuber reply endpoints. Greetings, wellbeing check-ins and thanks use bounded authored dialogue; identity replies use the saved application configuration. They do not require web retrieval. There is no free-form fictional or inference fallback in Strict Mode. The direct LLM chat/viewer wrappers also pass retrieval results through strict_answer before any generation path; production strict_answer always returns evidence or a refusal.

A factual answer needs classification Verified, a score meeting the configured threshold, and citations matching the registered retrieval path. An uncited Verified label is insufficient. Inference, Unknown and User-provided-only evidence cannot answer a factual question, even at a zero threshold. Missing/failed retrieval returns exactly: I couldn't verify that.

External citations must match approved manufacturer pages, the weather/news source hosts, or the exact reference-page format. Unknown sources, impersonated hosts, credentials in URLs and unexpected ports are refused. Local measurements, time, configuration and command receipts use named sakura:// citations displayed as local source receipts. External sources remain clickable HTTPS links. Scores express source policy, not a probability that a publisher is correct.

User-provided facts may enter memory only through the explicit declaration checks. Verified facts also need approved citations before being stored. A successful memory write can return a cited receipt without asserting that the supplied claim is independently true. A later quoted user statement is cited as a conversation record, never as independent proof of its contents. Generated conversation, guesses and refusals cannot enter the trusted ledger. Normal PC session-only clearing remains in place.

Unsupported background visual guesses stay quiet; no factual game/camera claim is generated from an unverified visual inference. Ordinary greetings, wellbeing check-ins and thanks are conversational acts, not factual lookup requests. Their local source receipt identifies authored dialogue; they never enter fact memory. Mixed social/factual questions still require evidence. Unsupported opinions and creative requests remain restricted. Registered deterministic facts, including the saved assistant identity, still work.

Tests: tests/test_astra_strict.py, the full builder Python unit list, tools/check-response-evidence.cjs and audit-results/astra-live-check.json cover refusals, source validation, memory rules, citations and zero model calls. This is an evidence-provenance policy, not a guarantee that an approved source is itself error-free.

Scope: PC local/cloud and AI VTuber reply paths, including phone chat connected to the PC. Standalone phone-local uses a separate implementation and is not claimed as covered by this PC policy. No installer or GitHub publication is included.
