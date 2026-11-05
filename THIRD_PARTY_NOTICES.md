# Third-party components and assets

The top-level GPL applies to Sakura's original source, not third-party code, service accounts, downloaded weights or imported artwork. Preserve existing component notices when distributing builds. This overview does not replace a review of the actual dependencies in your build.

| Component | Terms |
| --- | --- |
| Three.js | `static/vendor/three/LICENSE` (MIT); individual example libraries may carry additional notices. |
| PixiJS / pixi-live2d-display | `static/vendor/live2d/pixi-LICENSE` and `pixi-live2d-LICENSE` (MIT). |
| Live2D Cubism Core | Proprietary, not GPL. Its original header in `static/vendor/live2d/live2dcubismcore.min.js` points to the [Live2D agreement](https://www.live2d.com/eula/live2d-proprietary-software-license-agreement_en.html). The [SDK publication terms](https://www.live2d.com/en/sdk/license/) also apply where relevant. |
| VRM, tracking and Ammo | Existing `LICENSE` files under `static/vendor/vrm`, `static/vendor/tracking`, `static/vendor/ammo`, and notices in individual files. |
| Kokoro / Kokoro ONNX | `docs/KOKORO-LICENSE.md`, `docs/KOKORO-ONNX-LICENSE.md`, and terms of separately downloaded voice/model files. |
| Reaction audio / wake assets | `static/audio/reactions/LICENSE.md` and `android/assets/licenses/Wake-NOTICE.txt`. |
| Python, Qt/PySide6 and other dependencies | Upstream licences and installed package metadata; retain LGPL components and notices. See `requirements*.txt`. |
| Optional NVIDIA, PMX Editor/MMD, OBS/Spout, inference engines and external tools | Their respective upstream licences. Sakura's licence does not grant rights to redistribute proprietary SDKs or external executables. |

PMX/VRM/Live2D avatars, textures, motions, RVC weights and LLM weights are not included in this source repository. Obtain permission and comply with the creator's/model publisher's terms before sharing them. Cloud-library access is not a blanket commercial-use licence.
