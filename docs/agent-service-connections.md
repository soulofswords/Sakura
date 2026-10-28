# Unified Agent connections

## Current user-selected setup: external MCP servers

The user clarified that Google and LinkedIn must be added exactly like NVIDIA
Broadcast, using Add MCP server with the external provider URL and credentials.
The built-in Add service selector and account cards are therefore removed from
the UI. Legacy account records are preserved for Companion features; legacy
built-in MCP adapter discoveries are omitted from the active planner catalogue.
No existing NVIDIA connection or credential is deleted or rewritten.

Use Add MCP server, select Streamable HTTP or stdio, save the server, then request
Discover tools and review the action before approving it. Authorization remains
provider-specific. A bearer token must be supplied when required by that server;
this change does not add automatic remote OAuth discovery or bypass provider
permissions. Google/LinkedIn external servers are not connected automatically.
The Schedule panel remains visible only for an already-connected legacy Google
calendar. External calendar servers expose their own tools in Agent workflows.

The section below records the previous adapter implementation, retained solely
for compatibility; it is no longer the visible connection workflow.

## Previous built-in adapter implementation

Agent now has one Connections manager for Google Calendar, Google Drive/Docs/Sheets,
LinkedIn, and custom MCP servers. The old Google account and LinkedIn sign-in cards
are no longer shown separately; their developer setup forms remain available in
Connection setup dialogs. The Schedule card remains available independently.

Built-in services are actual MCP servers using the installed MCP SDK and in-memory
client/server streams. They wrap Sakura's existing account APIs and reuse encrypted
credentials. They are Sakura adapters, not the official Google remote preview
endpoints. Users still authorize their accounts; MCP does not bypass OAuth or
LinkedIn API permissions. LinkedIn inbox/jobs are not unlocked by this change.

Add service saves the adapter configuration. Connect/Reconnect opens the provider's
authorization flow in the normal browser. Discover tools creates a review proposal;
it never starts discovery without approval. Every MCP action still uses the normal
review gate. Calendar and Drive share the existing Google account connection;
disconnecting either signs out both, clears discovered adapter tools, and leaves
ordinary Companion calendar commands using the same account state.

Discovered schemas carry an account fingerprint. It is verified again before an
action executes, so reconnecting or switching accounts invalidates stale proposals.
No account tokens, OAuth client secrets, or MCP credentials are placed in installers
or source control. The cloud model library account and password-reset flow are
unaffected.

Validation: tests/agent-services.cjs exercises the real Agent page and unified
manager. tests/test_agent_services.py exercises MCP SDK initialization, discovery,
tool execution, service isolation and schema/account binding. Existing Google,
Calendar, runtime and Agent API tests remain applicable.
