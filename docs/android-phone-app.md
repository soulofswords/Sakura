# Sakura Mobile — Android testing build

The APK is at `C:\AI\Installer ready\Sakura Mobile\Sakura-Mobile-Android.apk`. Requires Android 9 or newer and a current Android System WebView. This is a locally signed testing build, not a Play Store release.

## Connect

1. Restart Sakura Companion or Sakura VTuber on the PC. Click **Connect to Phone** in the toolbar; it opens Settings → General and enables pairing.
2. Install the APK on Android. Put the phone and PC on the same trusted home Wi-Fi.
3. Enter the PC address and six-digit pairing code shown in Sakura. Codes expire after five minutes. Toggle the PC connection off/on to create a new code.
4. If Windows Firewall prompts, allow Sakura/Python on your private network. The phone relay uses TCP port 8771 for Companion and 8772 for the separate VTuber edition. Router port forwarding is not needed.

After the first pairing, both apps remember the connection. On the PC choose **Existing devices** to see known phones, or **New device** for a fresh code. On Android choose **Existing devices** and tap your saved PC to reconnect without a code. Pairing credentials are encrypted with Android Keystore; the PC saves only token hashes. Use **Forget** on the PC to revoke a phone. If the PC's network address changes, pair its new address again.

## Phone modes

- Companion: text chat through the running PC companion. Select Gemini using the PC's saved API key or supply a key from the phone. The PC stores it through its existing credential storage. The phone displays periodic avatar previews; it does not render a 3D model independently.
- Expressions: buttons for the currently loaded PMX, VRM or Live2D expressions. Multiple expressions can remain active; tap again to remove one, or clear them all.
- VTuber: select Front camera or Rear camera for head, eye and mouth tracking. The choice is remembered and can be changed during tracking. Face measurements are sent to the PC, which renders the avatar. Calibrate while looking straight ahead. Backgrounding the APK stops the camera. This first version does not transmit hand tracking or phone audio.

Version 0.2.2 requests 24 FPS phone tracking and avoids applying the same head filter again on the PC. Live2D uses a short final smoothing step while retaining the phone's spike rejection. Actual frame rate depends on the phone and camera.

Phone tracking enters tracking-only mode on the PC and pauses assistant speech. Use the PC's existing restore-AI control to return to companion mode after tracking.

The phone link is off by default. Only paired phones can use its limited commands; the general PC backend stays on localhost. Turning it off blocks all phone access while retaining remembered devices for the next time it is enabled. Forget revokes a saved device. This testing version uses HTTP on the private LAN; use only a trusted home network, not public Wi-Fi. Prefer the Gemini key already saved on the PC. The APK contains no imported character models, personal settings or API keys.

## Validation

Build checks cover Java compilation, DEX/resources, APK signature and archive integrity. Automated tests cover pairing, rate limits, current-model expression validation, latest-frame transfer, private-network restriction and session revocation. Browser tests cover phone screens and controls. A physical Android camera and actual home Wi-Fi connection need device testing; no physical Android device was attached during the build.

## Rebuild

Run `venv\Scripts\python.exe tools\build-android.py` from the Sakura project. Android SDK Platform 35, Build Tools 35 and JDK 17 are located under `tools/android-cache` on the build PC. The testing signing key is generated locally there and must be retained to install updates over the previous testing APK. Build errors go to `C:\AI\Installer ready\Sakura Mobile\Errors.md`.

Google sign-in for Gemini is not included. OAuth requires a configured Google Cloud project/client, consent screen and appropriate API access. Antigravity is also not configured as a reply provider in this APK.
