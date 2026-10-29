# Agent workspace and tool setup

The Agent workspace uses a task sidebar, a central activity stream and a bottom
composer. The avatar remains in its existing pane outside this workspace.

Choose a workspace, planning model and optional skill under **Task settings**.
Send creates a new task; Ctrl+Enter also sends. Recent tasks resume through the
sidebar. Advanced command, browser and delegation controls remain under
**Tools & command permissions**. Pending changes have a separate review panel.

The composer approval menu controls this app session:

- **Ask for approval:** changes, commands, unknown MCP calls and web requests
  stop for review. Enabled auto-continue can still read the selected workspace
  and use the existing read-only calendar/profile tools.
- **Approve for me:** also permits public search/fetch and browser observation.
  It does not automatically authorize arbitrary commands, MCP calls or edits.
- **Full access:** the planner may run available tools, commands and changes
  automatically. Commands run with the Windows user's permissions. Existing
  workspace validation, connected-account bindings, step limits, scan-origin
  authorization and cancellation controls remain in force. This is not a new
  OS privilege or a bypass of Windows permissions.

Broader modes require native Windows confirmation and reset to Ask after an app
restart or history clear. Turn off auto-continue to review every planned step.

## Add tools by asking Sakura

In Teacher mode, say **“add Playwright”**, **“add Firecrawl”**, or **“install Nuclei”**.
Sakura creates a real setup task with a pending review, without inventing a
connection or asking for a key in chat. These named setups have a deterministic
route; more complex repository installation still needs the planning model to
produce the appropriate reviewed steps. In Agent mode the planner can use
`integrations.status`, `integrations.setup` and `mcp.add` directly.

Under **Connections → Web & security tools**:

- **Playwright** uses Sakura's existing browser.open/snapshot/click/fill/close
  tools. Edge/Chrome or downloaded Chromium must be available. Setup downloads
  Chromium only if a usable browser is absent.
- **Firecrawl** uses the official hosted v2 scrape/search API. Enter your key in
  the password field; protected credential storage retains it, not task history.
  The website URL/query is sent to Firecrawl and provider credits may be used.
  Having a key configured is not proof that a particular extraction succeeded.
- **Nuclei** installs the official Windows x64 release after checking its
  published SHA256. Authorize exact website origins you own or have permission
  to test before `nuclei.scan` can run. Scans use signed HTTP templates, exclude
  disruptive/code/headless/fuzz tags, disable out-of-band callbacks, limit traffic
  to five requests/second and stop after 120 seconds. A timeout is incomplete
  evidence; findings need review, and no findings do not prove a site secure.

`mcp.add` saves and discovers the exact reviewed URL or local executable. It
does not invent credentials or approve future tool calls. A failed discovery is
reported as configured-but-unavailable; enter any required secret in Connections.
Installations and tool use always report their actual result.

Sources: https://github.com/microsoft/playwright,
https://docs.firecrawl.dev/api-reference/endpoint/scrape,
https://github.com/projectdiscovery/nuclei.
