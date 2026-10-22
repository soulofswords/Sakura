Current active PC setting: response_restriction_level=off. Normal responses use the original tool-first chat/controller path; missing evidence no longer forces a refusal. The optional medium/strict policies below remain available internally for regression testing.

# Evidence-gated PC responses

Medium is now the default PC policy. Factual answers still require cited Verified evidence; ordinary social dialogue can use guarded generation. The optional strict policy continues to block inferred replies. Qwen remains installed.

## Routing

The public chat endpoint validates inputs before running tools. The server checks PC commands/status/file-name search/time, manufacturer specifications, weather/news and confirmed user facts before generation. Explicit general-reference questions can use Wikipedia search and exact cited extracts. Hardware/software versions/prices/current events cannot use that general-reference fallback. Unsupported or below-threshold answers return: “I couldn't verify that information. I don't know.” with a request for evidence or an available verification method. Private/file/credential questions never become public-reference searches.

Medium permits social acknowledgement, feelings, preferences and casual follow-ups without treating them as factual lookup requests. Drafts remain inference and cannot become verified evidence through model confidence or client-supplied labels. Unsupported factual details, invented biography and shared-history claims in social drafts are filtered. This is a conservative gate, not a semantic proof system for unrestricted natural language.

## Provenance and confidence

Every chat response exposes `statements`, `sources` and `verification`. Statement labels are Verified, User-provided, Inference or Unknown. Chat displays the labels and clickable HTTPS citations; sources are not read aloud. Verified means backed by the selected tool/source, not independently proven universally true. Publisher reporting can be wrong.

`evidence_confidence_threshold` defaults to 0.9, is adjustable in Settings and validated as a finite number from 0 to 1. Scores are deterministic source-policy scores, not calibrated probabilities or a model rating itself. Measured/deterministic tool outputs score 1.0; a matching, unambiguous reference extract scores 0.9. Missing evidence remains Unknown even at a threshold of zero.

Available specification retrieval is deliberately limited to reviewed NVIDIA memory pages. General source search is a bounded reference lookup, not unrestricted internet browsing. Unconfigured sources and unavailable tools are valid Unknown outcomes.

## Memory

Temporary conversation context and the trusted evidence ledger are separate. Persisted schema version 2 excludes generated chat history and generated summaries. Explicit first-person user declarations and server-constructed trusted tool evidence can enter the ledger; questions, uncertain statements, generated guesses and Unknown responses cannot. Summaries are deterministic ledger serialization, never model-authored. Old untyped generated memory is not loaded as evidence. External observations must be retrieved again after reopening; only eligible user declarations reload. The existing PC session-only preference remains: normal PC conversations and the session ledger clear on exit.

## Visual behavior

Unverified spontaneous screen/camera reactions are quiet under this strict policy. Generated visual timeline descriptions are not stored as factual memory. A verified visual-event detector would be required to restore factual game announcements under the same rules. Tracking, expressions and model rendering are independent of this change.

## Validation and scope

Builder Python unit checks, dedicated evidence tests, real PC/specification checks and browser citation rendering checks are recorded in audit-results/evidence-*. PC-connected phone chat inherits the PC endpoint. Standalone phone-local generation is a separate implementation and is not represented as covered by this PC gate. No installer or GitHub publication is part of this change.
