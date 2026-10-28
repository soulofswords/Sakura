# Agent mode: local AI and automations

Open Companion's **Agent mode**. The workspace has **Tasks**, **Local AI** and
**Automations**. These controls belong to Agent mode; they do not replace the
Companion or VTuber model selectors.

## Native local AI

1. Open **Local AI**. Install the inference engine once (~37 MB download).
   Sakura verifies the pinned llama.cpp release checksum before installing it
   in this installation's private profile. No separate LM Studio or Ollama
   service is required. llama.cpp is MIT licensed; its notices are retained.
2. Search a model name. Select a Hugging Face GGUF repository, then a weight
   quantization and **Download**. Size and model license are shown. Downloads
   resume when supported and are checked against the repository's SHA256.
   Gated repositories and split multi-file GGUF sets are not supported yet.
3. Alternatively, expand **Add weights already on this PC** and enter the full
   file path. Files are registered in place; they are not duplicated or renamed.
   GGUF data in an existing blob file can be registered without an extension.
4. Choose installed weights. For vision, separately install/register the matching
   mmproj projector and select it. The architecture must be supported by the
   bundled llama.cpp release. A text-only model does not gain vision by adding
   an unrelated projector.
5. Select context size and GPU layers, then **Load model**. Zero GPU layers uses
   CPU. Larger context, image processing and GPU offloading need additional RAM/
   VRAM beyond the weight file size. A failed load reports an error; reduce the
   settings or choose a smaller model. Details are in the private runtime log.
6. Use Local chat, optionally attaching an image under 4 MB. Replies use the
   existing Companion speech hook. For tools/tasks, choose **Sakura Local AI**
   under **Planning AI** after loading a model.
7. **Unload** releases the owned worker. **Remove from library** only unregisters
   an entry. **Delete downloaded weights** requires confirmation and only deletes
   files downloaded into Sakura's private model store. Imported originals are
   protected. Closing Sakura closes its inference worker.

This is a native GGUF workspace, not a claim of full LM Studio/Ollama parity.
The older local provider remains available for compatibility. Colibri and other
engines are not installed or silently substituted. Local AI does not expose an
unauthenticated public API; its internal worker binds loopback with a private key.
Multi-model serving, split GGUF sets and cancellation mid-generation are future
work. Keep llama.cpp and individual model license notices when distributing.

## Recurring workflows

1. Run a task in **Tasks** and review its actual actions/results. Only workflows
   whose recorded steps completed successfully can be scheduled.
2. Select that task, open **Automations**, name it and choose the interval.
3. Tick the explicit recurring-workflow approval and choose **Schedule**.
   The saved template contains the exact tools, arguments, workspace and account/
   schema bindings. It does not give a language model permission to invent new
   unattended actions.
4. Read operations can repeat automatically. Changed file contents can be read
   again. Changed service connections, accounts or tool schemas stop for review.
   Every file edit, command, MCP call or service mutation stops for fresh approval.
   Existing output files are never overwritten to satisfy a recurring workflow.
5. **Pause**, **Resume**, **Run now**, **Open latest run** and **Remove schedule**
   are available per workflow. Failures and pending approvals pause the schedule.
   Review the task record, resolve the issue and explicitly resume when ready.
6. Sakura must be running in Companion AI mode and the PC must be awake. Closing
   the window/app or switching to tracking-only does not start a hidden AI service.
   After a missed interval, one run occurs; missed intervals are not replayed in
   bulk. A run interrupted by an app restart is paused for review, never replayed.

Schedules are local and bounded to 30 workflows, ten steps each. No publisher
credentials, connected accounts, task history, schedules or private weights are
included in installers. The owner's Jio publisher has a separate, locally registered workflow; tester
accounts never receive its credentials or publishing access.

## Windows startup

In Companion **Settings → Theme**, tick **Run Sakura when Windows starts** to
start the Companion launcher when this Windows user signs in. Unticking removes
Sakura's own current-user startup entry. No administrator permission is required.
This setting is not shown in standalone VTuber mode. It does not start a cloud
service or run when the PC is powered off.

## Owner model-library publishing

On the registered owner PC, open Agent mode → Automations → Owner model library.
Approve the fixed workflow, then choose Sync model library now, or enable its
repeat schedule. This owner's installation is configured to check hourly while
Companion AI mode is running. The workflow discovers Jio folders, validates
packages, creates previews, uploads and publishes, then checks the authenticated
catalogue and performs a temporary installation before reporting complete.
Existing transfers are detected and never duplicated. Original files are retained.

This capability is bound to the local owner account and checked publisher files.
It is hidden on other installations and excluded from releases. Changed code or
account registration requires local re-registration; failures pause automatic runs.
This schedule requires Sakura to remain open and the PC awake.

## Agent studio navigation

Agent mode uses the same circular icon rail and light/dark/system appearance
as Companion and VTuber. Tasks opens the goal, workspace, planning model and
activity. Local AI opens native model management and chat. Connections opens
MCP setup and the existing schedule manager. Skills opens reusable procedures;
Automations opens approved recurring workflows and the owner publisher where
registered. Task history reopens saved runs in Tasks.

A pending tool approval appears in a separate review panel with visible
Approve & run / Reject controls. On narrow windows it moves into the document
above the workspace. Changing views does not approve, discard or run a tool.
All mutations retain the existing local-origin, session-token and action-binding
checks. Companion mode returns to the main full-window companion. Sakura
continues speaking Agent progress through the existing parent-window speech bridge.

## Memory & learning

The brain icon opens persistent local notes, preferences and learned procedures.
Learning is enabled on this owner's PC as requested. Complete a task with at
least two actual successful steps; Sakura saves the tool sequence and verified
success count. Similar future plans receive up to three relevant sequences as
guidance. Learning updates repeat-success counts and survives restarts. Failed,
rejected, cancelled, empty and unfinished tasks create no learned procedure.
Old tasks are not mined retroactively.

Only broad task category, tool names, timestamps and counts are learned
automatically. Document content, filenames, command arguments, URLs, account
identities and conversation transcripts are excluded. Notes (2,200 characters)
and preferences (1,375 characters) are manually editable, not inferred as facts.
Memory is capped at 100 procedures. Disable it to pause both learning and recall;
Forget procedure removes one sequence; Forget all clears notes/preferences and
learned entries. Save as skill makes an explicit reusable procedure. Existing
user-created skills and task history are managed separately.

Memory may reach the selected planning provider. It is fallible context, never
authority or evidence, and cannot bypass current action approvals. Private
memory is excluded from installers and Git. This is a Hermes-inspired bounded
learning loop, not Hermes integration or model-weight training.


## CUDA and Colibri engines (October 27)

Agent mode > Local AI now offers an engine installer selector and a separate acceleration selector. Choose llama.cpp CUDA for NVIDIA GPUs with a CUDA 12.4-compatible driver, Vulkan for other supported GPUs, or CPU when loading. Auto prefers the installed CUDA GGUF engine; GPU layers controls GGUF offload (999 requests all layers; lower it to leave avatar/game VRAM). Offload is not a promise that any model fits.

The Companion Windows installer offers Skip or an optional CUDA inference engine/runtime download (~670 MB maximum). Existing Sakura CUDA installations are kept. When CUDA_PATH contains the three CUDA 12 runtime/cuBLAS DLLs, the installer reuses those instead of downloading the runtime bundle. The engine archive is still needed if it has never been installed. A full CUDA developer Toolkit is not required; drivers are not installed or replaced. CUDA setup failures leave Sakura installed and can be retried in Local AI.

Colibri v2.0.0 is an optional, SHA256-pinned Windows runtime (~11 MB) for Qwen3.8-Flash-Next safetensors folders. Add the existing complete model folder in Local AI; original files are registered in place and cannot be deleted by the app. Weights (~186 GB) are not downloaded with either the installer or engine. The current upstream Windows CUDA overlay does not include qwen38.exe, so this model uses Vulkan (Auto) or CPU. Selecting CUDA explicitly produces an explanation, rather than silently claiming CUDA. Other Colibri model families are not enabled by this integration yet.

Managed workers bind only to 127.0.0.1 with a random API key and die with Sakura. They share Local AI chat and the existing Sakura Local AI planner choice; existing tool approvals still apply. Qwen3.8 grammar-constrained JSON is unsupported upstream, so Sakura requests ordinary output and retains planner validation/repair. Thinking is disabled for conversational latency. Speech continues through Sakura's existing voice layer.

Validation on the owner's RTX 3080 12 GB / CUDA 12.8: verified CUDA device enumeration, loaded the existing Qwen3-VL 4B with GPU offload and received a real response. This is not a Qwen3.8 speed benchmark: its weights have not been downloaded. Neither engine runtime nor personal model registries are bundled in the release payload; the new root Python modules are picked up by the existing native-core build.


## Inspect an existing AI model folder

In Agent > Local AI, enter the model folder under Check your own model folder and click Check model folder. The local scan checks at most three subfolder levels and 5,000 entries, identifies GGUF metadata and tensor directories (including extensionless Ollama blobs), distinguishes vision projectors, and checks architecture names against the pinned llama.cpp engine. Complete Qwen3.8-Flash-Next safetensors folders use Colibri. Other Transformers/PyTorch weights are identified with a conversion explanation. Unsupported, split, truncated and unknown architectures are not offered an Add button. The bounded check is metadata compatibility, not full tensor integrity, a hardware-fit guarantee or a model execution test. Use Load model for that final check.

Adding rechecks metadata and registers original files in place. It does not move/copy originals or execute code from a model folder. The scan/import APIs require the same local Agent authorization as downloads and model loading.

Companion > Voice & speech includes Friend and Teacher conversation modes. Friend is warm and casual; Teacher gives patient explanations and examples. The selection is saved in settings, restored at startup, and added to ordinary spoken requests before local/cloud provider dispatch. Structured Agent planning and tool approvals are unchanged.


## Companion controls and Game mode follow-up

The opaque small Companion window has a round transparency shortcut beside the mic; it uses the same native character-only toggle and recovery hotkey as the existing control. Full-window/Agent/VTuber views do not show this compact shortcut.

Game type is selectable as Single-player or Multiplayer beside Auto game (Memory & privacy > Screen & games in the Companion toolbar). The selection is validated and saved. Entering an explicitly enabled Auto game session uses the selected microphone; startup outside Game mode still respects the microphone-off default. Resuming a microphone that was already enabled after Sakura speaks now preserves that intent. Single-player continuous microphone input does not require an extra wake phrase solely because gameplay audio is active; the user's explicit wake-word setting still applies. Multiplayer continuous input requires the wake phrase to keep unrelated team/game audio out of commands. A stopped microphone is not restarted on every game poll. Device/permission failures are shown rather than reporting a microphone that did not start.

Avatar switching is serialized with the latest queued selection taking priority. During Game mode the previous avatar is released before replacement upload, and new screen-reaction/VRAM polling work waits during the switch. This limits overlapping allocations; a large model and a game can still exceed hardware capacity. Targeted queue, GPU-presentation, resource-disposal and game-routing tests passed; the reported live-game crash has not been reproduced on a running game.

Clock commands now handle the exact phrase “so tell me what's the date and time now” directly from the PC clock, without relying on model generation.

## Qwen3.6 converted Colibri containers

Agent Local AI accepts Qwen3.6-35B-A3B int4 Colibri containers as well as Flash Next safetensors. Select the converted folder containing config.json, qwen36_meta.json, tokenizer.json, all numbered layer shards and model-globals.safetensors. Raw Transformers shards do not substitute for this converted layout. The importer validates the layer count and every required file and registers the original folder in place.

The managed Windows runtime uses Vulkan, a 64-slot per-layer CPU expert cache, a 5 GiB Vulkan expert tier and disabled OpenMP auto-tuning for this family. The CUDA expert tier requires full expert residency and is not enabled by this bounded-cache profile. These defaults bound allocations, not guaranteed latency or total memory; loading and response tests are still required. Quantization changes weight precision, not the number of model parameters. A text-only conversion remains text-only; a model's advertised vision architecture alone does not provide the vision encoder. Existing GGUF vision models and their projectors remain separately selectable.

## Companion uses the downloaded Colibri model

A universal local selection of sakura-native:<registered-id> sends ordinary Companion text and configured Agent planning to the managed local model. The worker loads lazily, so startup does not preload the full model. The previous model selection is backed up in desktop-profile/pre-colibri-default.json. Existing 4B weights and projector files are preserved.

Screen/camera images use the existing vision model. Before the larger text worker starts, Sakura requests that the vision worker release its weights; before vision generation the managed text worker is released. This avoids intentional simultaneous model residency, at the cost of model reload latency. Game mode uses the configured 2B vision model throughout gameplay and restores the universal Colibri selection afterwards. Screens and reactions become visibly active before microphone startup, so microphone failure does not block screen reactions. No change grants camera/screen permission silently; the capture must still succeed.
