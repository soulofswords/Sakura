# Published GitHub release — 22 October 2026

Published as `windows-beta-2026-10-22` in the public Sakura-Downloads repository. Source changes were pushed to the private Sakura repository. See [UPDATE-2026-10-22.md](UPDATE-2026-10-22.md) for the release summary.

## Pending Windows changes
PC tools dashboard, system status, Windows volume controls with read-back, read-only file-name search, bounded action sequences with cancellation/results, and separately opt-in paired-phone status/volume and explicit clipboard text transfer. See ASSISTANT-TOOLS-2026-10-21.md. Windows installers must be rebuilt from current sources before publishing these changes; the existing public Windows installers predate them.

## Pending Android changes
Sakura Mobile 0.3.20 (version code 26), same app.sakura.mobile package and signing identity. APK: C:/AI/Installer ready/Sakura Mobile/Sakura-Mobile-Android-0.3.20.apk.
- Dedicated sakura_flower launcher and round icon resources, verified against the flower artwork. Obsolete generated icon resource removed.
- PC tools tab from 0.3.18, including status/volume and explicit clipboard transfer. Needs updated PC app with corresponding permission enabled.
- Phone-local Gemini/OpenAI conversation rules now prohibit invented personal lore and unsupported shared-memory claims; reject evasive filler and near-duplicate long replies, retry model generation once without re-executing phone actions, and fail rather than speak a second rejected draft.
- Common Hindi/Romanized Hindi questions handled directly; specific reported garbled Hindi phrases rejected.
- Emoji cleanup before provider/native fallback speech. Devanagari replies select Hindi for background native fallback TTS.

Parity limits: PC-connected phone chat uses PC behavior. Standalone phone chat is a separate Java/cloud path with Android recognition and provider/native speech; it does not run PC Whisper/Kokoro. Phone chat/history lifecycle remains separate, and phone microphone language is still Android-managed. These changes do not claim all PC behavior or all Hindi quality is identical on phone.

Validation: actual compiled Java conversation-rule tests passed, Android compilation/R8/signature/archive checks passed, same signing certificate and version checked, visible icon pixels/alpha verified from packaged APK, packaged obfuscated WebView checks passed. Provider requests and physical Android operation were not live-tested. Prior packages and public release are retained.

## Additional pending PC status update
Fresh quarter-second CPU sampling for each request, current GPU utilization and dedicated VRAM used/total/percentage, plus RAM used/total/percentage in spoken status and the live PC-tools panel. Windows GPU counters and DXGI support driver-exposed adapters; NVIDIA NVML prefers physical device metrics and avoids duplicate adapter aliases. Missing/unsupported readings are stated as unavailable. Multiple GPU entries are reported separately when exposed. Same live values reach paired-phone PC-status requests. No new Windows installer/GitHub upload for this change.

Validation: 28 targeted Python tests and PC-tools/utility interface checks passed. Two live Windows/NVIDIA queries returned numeric CPU/GPU/RAM/VRAM measurements; no GPU load test was run. A short sample is current at request time, not a continuous spoken stream. GPU engines/NVML and Task Manager can use different utilization definitions and sampling windows.

Implementation references: https://learn.microsoft.com/en-us/windows/win32/api/pdh/nf-pdh-pdhgetformattedcounterarrayw ; https://learn.microsoft.com/en-us/windows/win32/api/dxgi/ns-dxgi-dxgi_adapter_desc1 ; https://docs.nvidia.com/deploy/nvml-api/latest/api/group__nvmlDeviceQueries.html .

## Additional pending PC speech-start latency fix
The warmed voice engine was not the only issue: the old splitter merged the CPU and RAM sentences into the opening speech request. The opening is now limited to 48 characters at word boundaries and is never merged into later details; remaining phrases keep the existing ordered prefetch behavior. Animation asset preparation runs alongside synthesis rather than blocking it; stale/cancelled responses remain guarded. No voice substitution, speech-rate change, GPU inference or transcript truncation.

Controlled local CPU Kokoro af_heart tests: old CPU+RAM opening took 6.375/6.390 seconds; new CPU-only opening took 2.484/2.516 seconds, after warmup. This measures synthesis of the opening phrase, not total model response time, and is not a guarantee for every PC/voice. Voice loading, RVC, runtime contention and synthesis still contribute latency. Speech-pipeline, lip-sync, voice-runtime and imported-greeting checks passed. Local PC apps refreshed; no installer/GitHub/APK build for this change.


## Pending 22 October 2026: reply relevance and performed expression cues
- Reject a bare “I’m good/fine” as an answer to unrelated questions such as an opinion about PC specs; retry once through the existing bounded quality path. Preserve genuine wellbeing answers.
- Remove the reported leading “eyes widen slightly” narration from chat/speech, including marked variants. Convert that allowlisted cue into surprised-expression metadata, applied at speech presentation through the existing reaction controller.
- Respect Reactions off, manual expressions, tracking, and model-authored expression availability. No fabricated unsupported eye animation.
- Regression tests cover the reported question, genuine how-are-you, cue removal, ordinary descriptive sentences, and metadata extraction. Local products refreshed; no new installer or GitHub publication in this change.


## Pending 22 October 2026: reduce ungrounded factual replies, keep Qwen
- Added shared factual-grounding instructions for local/cloud PC conversation: separate measured tool data, user claims and uncertain knowledge; no invented exact specs, citations or claimed tool execution. Hardware usage is not a performance specification.
- Official NVIDIA memory lookup for reviewed desktop RTX 5090, 5080 and 4090 URLs. Parses only an unambiguous labelled memory field; ignores script content, refuses missing/ambiguous data and timeouts. One-hour in-memory cache avoids repeated network delay. Unknown GPU memory requests get an explicit verification limitation instead of generated numbers. This is a limited lookup, not a general web-search engine or universal fact checker.
- Integrated before generation for Companion and AI VTuber, local and cloud. The reported 64GB premise is corrected from the manufacturer data. Sources remain in chat and are omitted from speech. Measured PC status still follows the existing system tool path.
- Reject generated claims of searches/completed device actions without tools and generated source URLs absent from the supplied question. Existing bounded retry rejects repeated failure without committing the invalid draft to history. Explicit fiction and conditional examples remain allowed.
- Phone-local source instructions updated as well; no new APK built. PC-connected phone chat uses the updated PC backend.
- Live source parser returned 5090=32GB, 5080=16GB, 4090=24GB. Targeted Python and Java conversation tests passed. No claim of eliminating hallucinations in unrestricted generated answers. No GitHub publication or installer rebuild in this change.


## Pending 22 October 2026: fail-closed PC evidence pipeline
- Source-first routing; unsupported factual/current/specification requests return an explicit Unknown without asking Qwen to invent an answer.
- Statement provenance and HTTPS citations in chat; configurable source-policy threshold, default 0.9; no model-assigned confidence or client-label override.
- Verbatim user/tool ledger replaces generated persistent history/summaries; legacy generated memory is excluded. PC session-only clearing remains.
- Unverified spontaneous visual announcements are suppressed and vision-generated timeline prose is not factual memory. This intentionally trades unsupported reactions for reliability.
- Bounded general-reference retrieval; dedicated sources required for hardware/version/price/current topics. Review docs/EVIDENCE-PIPELINE.md for coverage and limitations.
- Python builder unit checks and dedicated browser/live checks passed. No new installer, APK or GitHub publication. Standalone Android-local pipeline remains separate; PC-connected chat inherits these PC changes.


## Pending 22 October 2026: Astra Strict Mode
- Replaced the remaining conversational-generation fallback with Verified-only, citation-validated answers on PC chat and AI VTuber reply endpoints. No model calls for missing evidence, inference or uncited claims.
- Exact refusal: “I couldn't verify that.” Approved local source receipts and HTTPS citations accompany factual statements.
- User-provided facts may be stored but are not independent factual proof; memory-write acknowledgements and later quotes cite their actual record/receipt.
- Memory admission now requires Verified with approved citations or explicit User-provided records. Inference/Unknown cannot be stored. Tests cover source spoofing and parametric fallback attempts.
- Free-form greetings and creative conversation without verified evidence refuse under this stricter policy. Sources can still be wrong; this enforces provenance rather than universal truth.
- No new installer/APK/GitHub upload; PC-connected phone chat inherits the PC gate. Standalone phone-local remains separate.


## Pending 22 October 2026: coordinated Irida import and visibility
- Copied finished repaired Irida PMX and six PNG textures into models/pmx/AI_Assistant_PMX_Models/Repair_2026_10_22 after export-ready confirmation; prior imported files backed up in backups/irida-before-visibility-2026-10-22 and hashes recorded.
- Added Model Settings → Visibility: Show Wings, Show Horns, Show Top clothing for authored Hide_Wings/Hide_Horns/Hide_Top controls. Dedicated materials are hidden explicitly (material.visible) because the Three PMX path does not execute material-opacity morphs reliably. Tail/skin/lower hanging panel remain independent.
- Per-model visibility preferences persist and reapply independently of face expressions, tracking or physics. Exact names only; no guessed texture regions.
- Real Irida runtime audit: vowel morph mapping and speech peak0.90, mouth reset at silence, finite mapped arm/bend gestures, hide/restore each dedicated material while tail/skin remain unchanged. Added settings text distinguishing tracking arms from companion speech gestures.
- Refreshed both local apps. No installer/GitHub publication.


## Irida visibility editor follow-up, 22 October 2026
- Fixed conflicting UI state: Hide_Wings/Hide_Horns/Hide_Top Preview, Turn off, strength and hotkeys now route through persistent partVisibility instead of manual facial-expression weights that were overwritten every frame.
- Authored visibility controls bypass facial Reactions ownership; facial previews/hotkeys still respect Reactions on/off. Visibility remains independent of auto-expression clearing.
- Cache versions updated across app/expression/settings/viewer/visibility imports. Native UI expression tests and actual Irida rendered UI checks passed, plus independent repair-task screenshot verification of wing removal.

- Irida UI consolidation: removed separate Visibility tab/pane; authored Hide Wings, Hide Horns, Hide Top clothing cards live only in Expressions, with explicit Hide/Show toggles and existing preview/off/strength/hotkeys. Saved visibility controller/state retained. Real model UI/render and unit checks passed; both local bundles refreshed, cache irida100.

- Irida Hide Top clothing now removes only red fabric (Irida_Top), preserving Irida_Top_Details chains/straps/ornaments. Coordinated matching PMX material morph imported with backup; rendered UI and separate material-preservation checks passed. Both local apps refreshed, cache irida101.

- Irida A-pose fix: calculate relaxed arm rest for Companion as well as VTuber at load; companion arm gestures now offset the model-derived arms-down baseline instead of a fixed legacy A-angle. Actual upper-arm directions point down (Y below -0.90); audio, gestures, hide controls and frame-rate/tracking-isolation checks passed. No PMX geometry/bind edits.

- Corrected overbroad factual refusals for greetings, wellbeing check-ins, thanks and identity spelling variants (including who areu). Authored social dialogue never enters trusted fact memory; unsupported external facts still refuse.

- Restored greeting_wave on the strict response path for hello and hello/how-are-you combinations, using the existing speech-synchronised imported animation and rig capability checks.

- Medium response restrictions are now the PC default: casual self-reports and follow-ups use guarded conversation, while factual answers retain evidence requirements. Social replies are session context only and show no fact-verification badge. Greeting waves remain enabled. Applies to local/cloud Companion and AI VTuber replies.

- Removed the response verification gate from the active PC configuration. Normal generation and existing avatar actions/visual reactions are restored for Companion and AI VTuber, local and cloud. Live information tools, repetition/persona guards and trusted-memory validation remain.

- Unknown answers now offer a Google search. Chrome opens the exact original question only after a one-shot affirmative reply; refusal, expiry, a different message or clearing chat cancels the pending offer. Background/viewer reactions cannot authorize a browser launch. Applies to PC normal local/cloud chat.

- While the companion speaks, an enabled/previously used microphone can recognize short stop/wait commands without a wake phrase. It cancels queued speech and stale replies, then allows a new question for 15 seconds. Selected microphone, echo cancellation, microphone pause and AI VTuber microphone exclusion remain respected.
- Approved Google searches can save source-backed manufacturer/reference answers in a separate persistent local cache; the same question reuses the answer with its citation for up to 30 days. Failed/unverified retrieval is not learned. Live weather/news/status/prices remain fresh. Current automatic learning supports the registered manufacturer and reference retrieval paths, not arbitrary Chrome page contents.

- Every generated local/cloud reply now receives a fresh timezone-aware PC clock reading, including AI VTuber replies and language-repair requests. Natural check/read-clock and date/time questions use the system tool directly; unrelated conversation should not ask the user to check the clock.

- Eyes-sparkle stage directions are removed from dialogue and mapped to a model-authored sparkle expression (happy fallback) when automatic Reactions are enabled.
- Added chat attachment upload for PDF, DOCX, plain text/code and PNG/JPEG/WebP images: up to three files, 10 MB each, removable file chips, bounded excerpt context and selected-provider analysis. Scanned PDFs require a page image; files are session-only data and never executed or learned as verified facts.
- Fixed the RTX 5060 learning failure: read NVIDIA product-family specification tables by exact model column, distinguish 5060/Ti memory, and verify other NVIDIA product pages after approved searches. Saved GPU-memory facts match paraphrased questions without reopening Google.

- Integrated Sakura Agent into Sakura Companion behind a top-bar Agent mode button. The avatar stays visible in a compact left pane while the approval-based workspace fills the right side, and Sakura speaks task and approval updates. The standalone Agent launcher was removed. Existing file, shell, MCP, planning and LinkedIn capabilities remain in Companion.
- Character Lighting can now pick one 3D material as the gloss/bloom target; with no picked material, both effects still apply to the whole model. The existing color picker remains per material.

## Calendar title correction, 22 October 2026
- Companion and Mobile calendar title parsing removes command wording and keeps only the event subject. “I have an interview, add that to the calendar” is saved as “Interview.”
- The Companion flow still requires Google Calendar to be connected and the user to confirm the exact event before saving. Mobile opens a draft in the phone's Calendar app; the user must tap Save there.
- Added event-title regression coverage and rebuilt the signed Sakura Mobile 0.3.20 APK (version code 26).
