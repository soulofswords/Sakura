# Cloud API keys and routing

The startup Cloud API card and Settings → AI support Gemini, OpenAI, Anthropic Claude, OpenRouter, Groq, xAI, DeepSeek and custom OpenAI-compatible endpoints. This is not universal API compatibility: custom services must expose Chat Completions and their model may not support images or the same parameters. Enter the provider's exact model ID; OpenRouter/Groq/xAI require it. OpenAI defaults to gpt-4.1-mini, Claude to claude-haiku-4-5 and DeepSeek to deepseek-flash. Availability and billing belong to the provider.

Auto-detection uses distinctive prefixes (AIza, sk-proj-/sk-svcacct-, sk-ant-, sk-or-, gsk_, xai-). A plain sk- key is ambiguous and requires explicit provider selection. It is never tested across multiple providers. Detection is a routing hint, not proof that a key is valid. Test saved connection performs a small real generation request to the chosen service and may incur usage charges. It tests text, not image capability.

Gemini keys retain their existing encrypted file. Other keys are encrypted using Windows DPAPI or stored in macOS Keychain. They remain outside settings JSON, API settings responses, source commits and installer payloads. Other-provider keys use separate provider slots; custom keys are additionally bound to the exact configured base URL. Changing the custom URL requires saving a key for that URL. Requests do not follow redirects, and provider HTTP error bodies are not echoed to the user. Existing Gemini/local configuration remains compatible.

Camera and screen requests use the same selected provider, only when their access controls are enabled. Explicit image support must match the selected model; text-only models produce a clear error rather than falling back to another service. Messages, conversation context and enabled images/transcripts go to the selected cloud provider/custom endpoint. Local Ollama remains available. Speech remains the separate Kokoro/RVC pipeline.

Windows startup has Auto-detect plus explicit provider choices and an optional model field. Custom URLs are configured in Settings → AI. Leaving the startup key blank keeps the saved cloud configuration, including the last cloud provider when returning from local mode.

Tests use synthetic keys and mocked provider responses for routing, images, error handling, encryption, endpoint separation and settings redaction. A real Gemini connection was tested previously. OpenAI, Anthropic and other-provider live billing/accounts have not been verified here.

Protocol references:
- https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create
- https://platform.claude.com/docs/en/claude_api_primer
