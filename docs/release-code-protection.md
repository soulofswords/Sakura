# Local release code protection

These builds make source inspection harder. They are not irreversible encryption and cannot prevent a determined person or coding agent from reverse engineering software running on their own device.

- Windows Companion and VTuber: proprietary root Python modules are compiled by Nuitka into `sakura_core.pyd`. Original application `.py` files and their `.pyc` caches are omitted. Only tiny startup/bootstrap Python files remain. First-party browser JavaScript is obfuscated without source maps. Third-party libraries and license notices remain intact.
- Android: R8 release shrinking/obfuscation protects the Java implementation, with explicit keep rules for Android activity callbacks and the WebView bridge. First-party JavaScript assets are obfuscated. The APK still exposes inspectable HTML, UI assets, public identifiers and third-party runtimes.
- macOS: existing DMGs have not received this native protection. A protected Apple Silicon native core requires compilation and verification on a Mac. The Windows protected build deliberately does not overwrite them with an unprotected source package.

Development sources in `F:\AI\assistant\Sakura` remain editable. Local developer apps retain those sources; the distributed installers/APK use the protected release profile. Imported user models, voice weights, personal settings and API keys stay excluded. Signing and obfuscation do not guarantee that SmartScreen will trust an unsigned Windows publisher.

Build commands:

```
venv\Scripts\python.exe tools\build-split-installers.py --output "C:\AI\Installer ready"
venv\Scripts\python.exe tools\build-android.py
```

Windows builds require Nuitka, a C compiler and the JavaScript obfuscator installed under `tools/hardening-node`. The build caches/generated C files and Android testing signing key must never be distributed as application source. Build errors are logged separately. The installer smoke test verifies the native library is present, original `app.py`/`llm.py` and original bytecode are absent, and both edition backends still function.
