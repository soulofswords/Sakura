# Sakura cloud character library

Current hosted storage is **JioAICloud**, serving 209 Live2D and 362 PMX character
packages. PMX browsing is game → character with animated turntable previews.
The Jio adapter has passed real signed-in download/import checks for both formats.
See [Jio model publishing](jio-model-publishing.md) for adding characters to the
existing source folders, the private package-folder purpose and owner sync command.
Drive-specific publisher instructions below are retained as historical tooling;
the deleted Drive destination and its scheduled publisher remain disabled.

## Implemented in source

The Models panel in standalone VTuber, Companion and Companion VTuber gets a
Cloud import PMX, Cloud import VRM and Cloud import Live2D button beside its local
upload controls. Nothing contacts the catalogue or opens account fields until the
user selects one of those cloud buttons. The panel filters to the chosen format;
remembered sessions open the matching catalogue without asking the user to sign
in again. Local model import and selection handlers are preserved.
Downloaded characters enter the existing PMX / VRM / Live2D selectors. The existing
Send model to mobile action can transfer installed characters to a paired phone.
Direct Android cloud browsing is not implemented by this desktop change.

Cloud characters use a searchable grid of square preview cards. Selecting a card
highlights it; Download installs the package and refreshes its existing format
selector. The gallery is hidden until a cloud-import button is opened and the
user signs in. PMX/VRM cards display looping 360-degree renders, while Live2D cards
use a supplied portrait. Missing previews show the model's folder name rather than
broken images. Local PMX, VRM and Live2D buttons remain separate.

Each local format button now opens a folder browser with a search box above the
cards. Folder navigation follows the existing model paths; searching spans all
folders of that format. Leaf cards select through the original native selector's
change event. Live2D uses its portrait PNG or the folder name; PMX/VRM thumbnails
render in one isolated preview frame, which rotates on hover. The shared frame
stays in place instead of being reparented, preventing iframe reloads during hover.

Previews are authenticated raster assets served through the local app proxy;
storage IDs and owner tokens never become image URLs in the browser. The service
uses `/v1/models/{id}/preview` and a bounded WebP response. Animated WebP turntables
avoid loading multiple full 3D scenes while the user is tracking or streaming.

The client downloads only packages listed by the authenticated service, verifies
exact size and SHA256, and passes them to the existing staged model importer.
Repeated downloads do not replace a user's existing character or edits. Account
tokens use the existing encrypted credential store; passwords are not saved.

## Owner preparation

Approved Live2D source folder: `1IxXw-fjPVnl6vPAvM6DAcyzRYoAhiJLT`.
All its immediate character folders are selected. The exporter follows nested
folders and pagination, includes runtime assets and credits, and validates MOC3
and required textures before producing a package. Failures are reported instead
of adding broken models. Multiple model entry points are marked incompatible
with the phone's single-model ZIP importer.

Run on the owner PC with an authorized Google connection that has Drive read
access (the Calendar-only connection is insufficient):

    venv/Scripts/python.exe tools/publish-model-library.py --owner-google-connection --inventory-only --output private-model-library
    venv/Scripts/python.exe tools/publish-model-library.py --owner-google-connection --output private-model-library

Alternatively provide a short-lived owner Drive access token in the environment
variable SAKURA_LIBRARY_DRIVE_ACCESS_TOKEN. Never place it in an app, APK, source
file, command argument, screenshot or chat. No Drive writes or sharing changes
are made by this tool. Output is local; running it is not internet publication.

The Live2D exporter writes `<id>.webp` beside each ZIP, preferring preview/portrait/
thumbnail PNGs and excluding all texture files referenced by `.model3.json`.
If no portrait exists, supply one before publication; an atlas is not a preview.
For a PMX or VRM character served by the owner's local Sakura app, render a loop:

    node tools/render-library-turntable.cjs "vrm/character.vrm" "private-model-library/character.webp"

This renders 48 angles with physics/idle animation stopped, and writes a six-second
loop. It does not modify the model or its saved settings. Test renders were checked
against real local PMX and VRM models; those private models were not published.

Before publishing previews on the hosted service, re-run
`tools/model-library-schema.sql` to add the two optional preview columns, deploy
the updated `tools/model-library-edge.js`, and set `preview_storage_path` or
`preview_drive_file_id` for each published model. Upload `<id>.webp` as a separate
private asset. The catalogue returns only `preview: true`, never either private
storage location. Existing packages without a preview still install normally.

## Automatic owner publishing

Current owner setup is paused: the owner deleted the generated Drive destination
and selected JioAICloud instead. The Windows task is disabled, the owner publish
endpoint returns 410, and the old Drive-backed catalogue rows are unpublished
(retained for migration). Do not re-enable Drive uploads without confirming the
destination with the owner. All 209 prepared packages remain locally available.
`F:/AI/assistant/Sakura Jio Upload` contains only packages, preview images and a
credential-free catalogue, ready for a manual Jio folder upload. Jio storage or
private automatic delivery is not configured or claimed to work yet.

The owner PC has a limited-user, hidden Windows task named `Sakura Library
Publisher`. It checks every 15 minutes and after the owner's Windows sign-in,
running `tools/sync-library-drive.py`. This is not installed on testers' PCs and
is not included as an enabled service in release installers. The owner PC must
be on, signed into Windows, and online; this is not a cloud-side ZIP builder.

Each pass inventories the approved Drive folder, prepares new folders, uploads
validated packages and portraits into a separate private app-created Drive folder,
then publishes their metadata through the owner-only endpoint. Failed preparation
is retried on the next pass. Completed packages, uploads and publications are
checkpointed outside the repository in `F:/AI/assistant/private-model-library`.
`publisher-sync.log` records scheduled runs. Existing characters are not uploaded
again, and downloaded user edits are never overwritten.

Only the original source reads use the owner's local Workspace authorization.
The server holds a separate `drive.file` grant for publisher-created files,
encrypted in Supabase Vault. It cannot read the owner's Gmail or Calendar.
The catalogue publisher has a distinct random owner proof stored with Windows
DPAPI; only its hash is deployed. Its endpoint accepts bounded Live2D catalogue
records, not arbitrary SQL or commands. Neither credential ships with clients.

Clients refresh an open, signed-in cloud gallery once a minute, pause refreshes
during a download, and never download new models automatically. Adding source
folders therefore does not force downloads or sign-in prompts on testers.

Preparation safely deduplicates identical Drive texture copies (matching checksum
and size), while conflicting duplicates remain errors. An omitted model3 descriptor
can be reconstructed only with exactly one MOC and an unambiguous texture directory;
this changes only the prepared copy, never the source Drive folder.

The public folder currently contains Workshop-named models. Source availability
does not grant redistribution rights: retain creator attribution and establish
permission before making these packages available to testers or the public.
Make the original Drive folder private before promising Sakura-only downloads.

## Account service

Create a Supabase project and configure Auth with email confirmation and a
production email sender. The built-in email sender is limited to project-team
addresses, so ordinary public email registration needs custom SMTP. Free Auth
currently includes 50,000 monthly active users; provider limits can change.

On the catalogue host set:

- SAKURA_LIBRARY_ROOT: private package output directory.
- SAKURA_LIBRARY_SUPABASE_URL: the HTTPS Supabase project URL.
- SAKURA_LIBRARY_SUPABASE_PUBLISHABLE_KEY: the publishable/anon key, never a service-role key.

Run model_library_server:create_app with an ASGI server and HTTPS reverse proxy.
Do not expose the package directory as a public static directory. The service
verifies Supabase user sessions before serving the catalogue or packages. Account
sign-up, sign-in, refresh and password recovery are delegated to Supabase; no password
database is maintained by Sakura. Configure request rate limits on the public reverse proxy
and Supabase CAPTCHA/rate limits before opening registration broadly.

A library address typed into Advanced connection answers `/v1/auth/signin`, `/signup`,
`/refresh` and must return `access_token`, `refresh_token` and a positive `expires_in`, or
`confirmation_required` to send the user to their email instead. Sakura checks that shape
before saving a session, so any other 200 is reported as the service's own fault rather than
a wrong password. `GET /api/model-library/connection` returns the built-in cloud address as
`cloud`, and the panel shows the access-code field only for an address that is not the cloud:
codes exist in the self-hosted service below, while the Sakura cloud signs in with email and
password alone.

The confirmation email must not keep the default `{{ .ConfirmationURL }}`: that link
points at Supabase's own verify endpoint and then redirects to a web origin the
desktop app never opens, so nobody spends the token and the account stays
unconfirmed. Point the Confirm signup template at Sakura instead:

```
{{ .SiteURL }}/api/model-library/confirm?confirmation_token={{ .TokenHash }}
```

Set Site URL to the companion origin (`http://127.0.0.1:8766`) and add the matching
redirect entry `http://127.0.0.1:8766/*`. `model_library_confirm.py` posts that hash
to Auth and answers with a plain page; it is wired to the Host-only
`_served_locally` check rather than the CSRF-style guard the write routes use,
because a link clicked inside webmail is a cross-site navigation and would
otherwise be refused. The companion port rolls forward when 8766 is busy, so widen
both values if the app starts on another port. Sign-up and recovery replies say so
when Sakura is answering on a rolled port, because the emailed link would otherwise
point at a port nothing is listening to and the account would silently stay
unconfirmed.

Password recovery needs the same treatment, because a recovery link has nowhere to
land either. Point the Recovery template at Sakura:

```
{{ .SiteURL }}/api/model-library/reset?recovery_token={{ .TokenHash }}
```

`GET /api/model-library/reset` posts that hash to Auth with `type: recovery`, which
answers with a short-lived session rather than a confirmation. The session goes
neither into the page nor into a URL: it waits in memory behind a single-use random
id while the page shows a plain form, and the form's `POST /api/model-library/reset`
sends the new password to Auth as `PUT /auth/v1/user` with that session as a Bearer
token. Only the page's own submit may carry a password, so the POST is guarded by the
stricter `_started_locally` while the GET keeps the Host-only check. A wrong length, a
mismatch, a rejected password or an unreachable service returns the slot, so one
mistyped try does not cost a fresh email; a successful change consumes it. A slot lives
for `RESET_TTL` seconds and at most `MAX_PENDING` links wait at a time. Both password
fields carry a show/hide eye, which needs one inline script, so that page's policy gains
a `script-src` naming a nonce minted for that response alone; a reset page without the
form ships no script and no `script-src`.

Spending the link is not the reset. Opening the emailed page only proves the token, so
the account keeps answering the old password until that page's form is submitted, and
the recovery reply says so. Auth consumes the token on that first open, so a mail
scanner, a second tab or the back button used to leave the reader staring at a dead page
while the verified session was still sitting in this process, and Auth answers a link it
has already spent with the same `otp_expired` 403 it gives a link that went stale, so the
refusal carries no diagnosis worth acting on. The slot table therefore also remembers the
link token, and re-opening a link this server already verified hands back that held
session and a fresh id. A token it never verified still gets the dead page, because then
nothing really is waiting to be finished, and a link that could not be reached at all is
never answered with a form either.

The held session is offered inside Sakura too, so a browser tab nobody submits cannot
lose the password. If a sign-in is refused while a verified link still waits for that
address, the reply carries `reset_pending` and says the new password is not live yet,
because from the sign-in box an unfinished reset is indistinguishable from a wrong
password; the panel reads that flag and reveals a two-field Set new password box that
posts to `POST /api/model-library/finish-reset`. That route keeps the stricter
`_started_locally` guard, claims the live slot by the casefolded address Auth named, and
runs the same length, mismatch and `PUT /auth/v1/user` path as the page's own form, so a
typo returns the slot and a change that lands consumes it. It answers with one plain
sentence and never with the provider's detail or the password. A slot only ever speaks for
the address it was held for, and `PUT /auth/v1/user` may report success only when Auth
answers with an updated user object for the same email.

An Auth `same_password` refusal means the submitted password is already set; it does
not prove a new change happened. Both forms explain this and preserve the waiting
session so the user can choose a different password. HTTP 429 and server errors also
keep the form usable until its original deadline. Successful changes remain single-use.
`tools/sync-model-library.py` copies both library modules and the confirmation/reset
module, and attaches both routers without replacing unrelated application changes.

For initial non-public smoke tests an optional SAKURA_LIBRARY_MEMBERS file maps
tester labels to SHA256 hashes of random access codes of at least 32 characters.
It must stay outside the public root and source control. Removing a member entry
revokes that code. There is no shared administrator key embedded in the client.

Set SAKURA_MODEL_LIBRARY_URL in a distributed client to the catalogue HTTPS origin.
Otherwise the test connection form accepts the service address. Only loopback
HTTP is accepted for local tests; internet addresses must use HTTPS.

## Remaining deployment work

### October 25 setup progress

The owner created the Supabase project `gclwwyznseuuixnbwpyz` on the Free plan.
Its public project URL and publishable key are in model_library_config.py (no
administrator credential). A live Auth settings request confirmed email sign-up
enabled and email confirmation required. The protected sakura_model_catalogue
table was created in the dashboard; SQL returned rls_enabled=true. A direct
anonymous REST request returned HTTP 401, confirming catalogue access is blocked.
The owner approved deployment and the sakura-library Edge Function is now deployed
at https://gclwwyznseuuixnbwpyz.supabase.co/functions/v1/sakura-library.
A live unauthenticated GET to /v1/models returned HTTP 401 with the function's
own `Sign into Sakura first.` response, confirming the deployed handler executes.
No model files are published yet. Email delivery and both reset paths were subsequently
verified by the owner and Qoder. Publishing prepared model packages and testing an
authenticated package download remain separate deployment steps.

Source setup scripts are tools/model-library-schema.sql and
tools/model-library-edge.js. The library function verifies the user with Supabase
Auth, reads only published catalogue entries, and keeps storage file IDs and
server credentials out of catalogue responses. Tests/model-library-edge.cjs
checks anonymous, expired and unconfirmed user rejection plus published-only reads.

No public service or Supabase project is created automatically by the app. Owner Google
authorization, service hosting, SMTP and account configuration must be provided
before a real user can register or download the supplied folder. This Python host
is a reference implementation; a free Cloudflare Worker + private R2 backend can
implement the same API without exposing storage credentials. This code does not
promise permanently free hosting or bypass Drive/API bandwidth limits.
