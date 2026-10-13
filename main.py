"""
🌸 Sakura — Anime AI Assistant
  CLI mode:  python main.py
  GUI mode:  python main.py --gui   (opens browser with 3D model viewer)
"""
import sys

# Configure UTF-8 encoding safely on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ── pretty printing ────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.panel import Panel

    _con = Console(force_terminal=True, legacy_windows=False)
    def _banner():
        try:
            _con.print(Panel(
                "[bold magenta]🌸 Sakura — Anime AI Assistant 🌸[/]\n"
                "[dim]Local  •  Private  •  Cute[/]",
                border_style="magenta",
            ))
        except Exception:
            print("\n🌸 Sakura — Anime AI Assistant 🌸\n")
    def _sakura(txt):
        _con.print(f"[magenta bold]🌸 Sakura:[/] {txt}")
    def _user(txt):
        _con.print(f"[cyan bold]👤 You:[/] {txt}")
    def _info(txt):
        _con.print(f"[dim]{txt}[/]")
except ImportError:
    def _banner():
        print("\n  🌸 Sakura — Anime AI Assistant 🌸")
        print("     Local  •  Private  •  Cute\n")
    def _sakura(txt):
        print(f"🌸 Sakura: {txt}")
    def _user(txt):
        print(f"👤 You: {txt}")
    def _info(txt):
        print(f"   {txt}")


# ── main ───────────────────────────────────────────────────────
def main():
    _banner()
    print("\n⏳ Loading components…\n")

    from config import WAKE_WORD_ENABLED, ASSISTANT_NAME
    from stt import SpeechToText
    from llm import LLM
    from tts import TextToSpeech

    stt = SpeechToText()
    llm = LLM()
    tts = TextToSpeech()

    wake = None
    if WAKE_WORD_ENABLED:
        from wake_word import WakeWordDetector
        wake = WakeWordDetector()

    # Pre-flight: is Ollama up?
    if not llm.is_available():
        print(f"\n❌ Ollama isn't running or model '{llm.model}' not found.")
        print("   1) Start Ollama  →  ollama serve")
        print(f"   2) Pull model    →  ollama pull {llm.model}")
        sys.exit(1)

    print("\n✅ All systems go!")
    _info("Commands:  type → toggle keyboard mode  |  clear → reset memory  |  quit → exit")
    print()

    # Greeting
    greeting = llm.chat(
        "The user just booted you up. Give a short cute greeting "
        "introducing yourself (1-2 sentences max)."
    )
    _sakura(greeting)
    tts.speak(greeting)

    typing_mode = False

    try:
        while True:
            # Wake word gate
            if WAKE_WORD_ENABLED and wake:
                wake.wait_for_wake_word()

            # ── get user input ─────────────────────────────────
            if typing_mode:
                try:
                    user_input = input("\n👤 You: ").strip()
                except EOFError:
                    break
            else:
                user_input = stt.listen()
                if not user_input:
                    _info("(didn't catch that — try again)")
                    continue
                _user(user_input)

            # ── commands ───────────────────────────────────────
            low = user_input.lower().strip()

            if low in ("quit", "exit", "bye", "goodbye", "stop"):
                bye = llm.chat("User is leaving. One short sweet farewell.")
                _sakura(bye)
                tts.speak(bye)
                break

            if low == "clear":
                llm.clear_history()
                _info("🗑️  Memory cleared!")
                continue

            if low == "type":
                typing_mode = not typing_mode
                mode = "⌨️  keyboard" if typing_mode else "🎤 voice"
                _info(f"Switched to {mode} mode")
                continue

            # ── LLM response ──────────────────────────────────
            reply = llm.chat(user_input)
            _sakura(reply)
            tts.speak(reply)

    except KeyboardInterrupt:
        print("\n\n👋 Interrupted")
    finally:
        tts.cleanup()
        print("Bye bye~ 🌸")


if __name__ == "__main__":
    if "--gui" in sys.argv:
        # Launch the web GUI with 3D model viewer
        import gui_server
        print()
        print("  🌸 Sakura — Anime AI Assistant (GUI Mode)")
        print("  ──────────────────────────────────────────")
        print("  Put .pmx model folders in: anime-assistant/models/")
        print()
        gui_server.launch()
    else:
        main()
