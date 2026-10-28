# JioAICloud storage investigation

Checked 26 October 2026. This includes a contract review and a tested owner login
utility, not a verified authenticated model-delivery integration. The owner has
completed live email OTP and profile verification; model uploads remain zero.

## Finding

A custom connector appears technically possible. The personal website has real
authenticated small-file and resumable upload implementations. No supported public
developer API for the personal service was found. Enterprise object storage is a
different product; its S3 API does not establish that a personal account supports S3.

Jio public share links allow access without Jio login. They cannot enforce Sakura
sign-in by themselves. The proposed private delivery path is: Sakura sign-in,
server authorization, server-side Jio fetch, bounded streaming, client SHA256
verification, existing staged importer. Owner credentials must never ship in the
desktop app, APK, catalogue or preview URLs. Once downloaded, a user can copy the
model; authentication cannot prevent that.

## Primary evidence

- Official upload help: https://www.jioaicloud.com/help/file-upload-and-backup
- Official public/private sharing distinction:
  https://www.jioaicloud.com/help/file-sharing/how-can-I-share-files-from-jiocloud
- Public deployed website entry point: https://www.jioaicloud.com/
- Current public runtime: `runtime.348818b81e1e5f18.js`
- Upload implementation chunk:
  `default-projects_common-repo_src_app_core_controller_JioPhoneCallController_ts-projects_commo-af3f1c.2154c837ec007377.js`
  (Despite the chunk name, webpack module 3109 contains the upload queue and its
  small/large upload implementations.)

Public asset copies for this review are in ignored `audit-results/jio-integration`.
They contain no browser session exports or owner account credentials.

Observed contracts in the official client:

- Small upload: POST `/upload/files`, multipart fields `metadataString` (JSON)
  and `file`. HTTP 201 supplies an `objectKey`.
- Large upload: POST `/upload/files/chunked/initiate` with file metadata. HTTP
  200 supplies `offset` and `transactionId`; HTTP 201 can indicate completion.
- Chunk upload: PUT `/upload/files/chunked?uploadId=<transactionId>` with raw
  bytes, `X-Offset`, and the client's `Content-MD5` checksum. HTTP 200 supplies
  continuation state; HTTP 201 supplies the final stored object metadata.
- Regional upload and API hosts are selected from account/environment state.
  Do not guess the region or assume all accounts use the same host.

The full metadata and checksum representation, authenticated download route,
token refresh and expiry behavior still need executable verification. Seeing a
method in public JavaScript is not evidence that our own request succeeded.

Third-party projects reviewed provide OTP/session and download examples, but
none reviewed establishes a tested complete uploader suitable for this release.
Do not install them blindly or import an owner's Chrome cookies.

## Required implementation and acceptance checks

1. Implement an owner-only connector login using a fresh legitimate Jio session.
   Confirm the account identity and intended destination before writes. The
   currently open Chrome login is not automatically available to this tool session.
2. Store owner credentials encrypted locally; if hosted delivery is used, keep
   the necessary refresh credentials only in a server-side secret store.
3. Upload one small test package into the confirmed destination, read it back,
   verify exact length and SHA256. Test a chunked package and interrupted resume.
4. Verify refresh/expiry failure handling, anonymous denial and Sakura account
   authorization. Do not expose a reusable owner session or public storage link.
5. Establish hosting size, duration and bandwidth limits before promising that
   the existing hosted API can proxy every package on a free tier.
6. Only after those checks, migrate the 209 prepared packages and preview images,
   verify the resulting catalogue, then re-enable a Jio-specific sync job.

## Verified owner uploader

`venv/Scripts/python.exe tools/upload-library-jio.py --workers 3` uploads the
prepared packages, portraits and credential-free catalogue to the confirmed
existing folder. It refuses an unconfirmed destination or a ledger for another
account/folder. It does not create a folder, share link, permission or catalogue
publication. The original source Drive is not modified.

The small-file multipart upload and a larger chunked upload have both succeeded
against Jio and were downloaded back with matching size/SHA256. The chunk protocol
uses blocks up to 16 MiB (within the official client's 20 MiB maximum), hex MD5,
provider offsets and transaction IDs. File-like request bodies bound individual
TLS writes, avoiding the Windows SSLWantWriteError seen with large byte buffers.
The 16 MiB transfer path has passed an authenticated upload/download checksum test.
Large interrupted
transfers can resume through a repeat initiate request. Existing same-name files
must have matching size and downloaded SHA256; conflicts are not overwritten.

Every uploaded file is downloaded back and verified. The owner-only
`jio-uploaded-assets.json` checkpoint contains object IDs and checksums, not login
tokens. It is outside the repository. Failed downloads retain an unverified
receipt so a later run can recover without uploading another copy. Login refresh
credentials stay DPAPI encrypted. Jio transfer hosts are explicitly allowlisted
and redirects do not receive owner credentials.

`--test-only --workers 1` tests one larger package and its portrait. The full
batch completed: 209 packages, 195 portraits and one catalogue (405 remote files),
with no duplicate names or failed entries. All were downloaded and size/SHA256
verified; `jio-upload-completion.json` records the final inventory check.
The catalogue is uploaded only after every package/portrait succeeds. This storage
step does not activate the hosted Sakura catalogue: its Jio storage adapter and
server-side credentials still need configuration and authorization tests.

## PMX upload audit and extension limitation

The owner's `PMX/zenless zone zero` upload was compared recursively against
`F:/AI/assistant/Sakura/models/pmx/zenless zone zero` (not the D-drive copy).
The initial remote tree had 1,314 of 1,318 local files and all 232 subfolders.
All present files matched local size and provider MD5. Four missing files were:
`evelyn/tex/衣.tga`, `evelyn/tex/衣2.tga`, `evelyn/tex/颜.tga`, and
`seed/席德/tex/椅子.png`.

The three .tga-named local files actually contain PNG bytes. Jio infers PNG and
changes their extension on upload; restoring .tga through its official rename
operation was rejected with `NMSOM0106: Invalid Operation for User.` Original
bytes and names are now preserved in `Sakura-original-TGA-textures.zip` in the
existing `PMX/zenless zone zero/evelyn/tex` folder. The transient provider-renamed
artifact created by the repair was moved to trash after the archive verified.
The missing Seed PNG was uploaded directly into its original `tex` folder.
All repaired uploads were downloaded and SHA256 checked; archive entries also
match the original local filenames and bytes. No existing matching files were
overwritten. The PMX packaging stage must restore those archive entries into
`evelyn/tex` before creating a complete downloadable model package. Storage alone
is not a complete PMX catalogue integration.

Owner tools: `tools/audit-jio-folder.py` performs read-only recursive comparisons;
`tools/repair-jio-audit.py` repairs the audit's missing list with explicit source
and destination checks. Private audit/repair reports are outside the repository.

## Owner login utility

Run `venv/Scripts/python.exe tools/jio_library_owner.py` on the owner's PC.
It opens an expiring loopback-only setup page in the default browser. Enter the
JioAICloud email/mobile and OTP there, not in a terminal argument or chat. Accounts
with passphrase protection get a separate challenge; the passphrase is not saved.
The account profile and the existing `My Files / live2d` folder are checked before
the owner can confirm the destination. Missing or duplicate destination folders
block confirmation. The utility cannot upload, delete, move or share files.

Once the profile confirms the login identity, connection state is DPAPI encrypted at
`F:/AI/assistant/private-model-library/.jio-owner-session.bin`, outside the source
repository and installer payload, with `destination: null` until the owner confirms
the account/folder. No Chrome cookies or browser session databases
are read. Setup uses a per-run capability, validates the Host and Origin, follows
no credential-bearing redirects and bounds responses/pagination. It closes after
30 minutes. The utility can restore a saved verified session and repeat the
read-only profile/folder check. The uploader refreshes an expired transfer session
once; the login-page utility itself does not refresh tokens yet.

Validation: 29 owner-login/uploader Python tests pass (including actual Windows DPAPI persistence),
and the Playwright owner-page flow passes with a simulated provider. The current
official public runtime configuration was fetched successfully. Provider login,
folder access and transfer still require an owner to complete the live login;
the simulated checks are not proof that Jio accepted the connection.

Live owner email OTP verification and account profile checking succeeded. The
folder listing then returned HTTP 400 / `NMSOM0001`. Adding the official sorting
parameter alone did not resolve it. Reading the authenticated provider error
identified the actual cause: `Accept language is null or empty.` The connector now
sends `Accept-Language: en`. A live authenticated retry succeeded and found exactly
one `live2d` folder. The query matches the official folder picker: `/nms/metadata`,
`limit=2000`, root `folderKey`, `sort=+objectName`, `type=w`. Name matching ignores
capitalization. The later upload and hosted-delivery checks are recorded below.

The email OTP payload now follows the official screen's browser name/version
fields rather than sending the Windows OS name/version. Errors distinguish OTP,
profile and folder requests and show only a bounded provider error code. If OTP
verification succeeded but a later GET failed, retrying the check reuses the
accepted in-memory session. A tab reload retains the local setup capability and
restores the current page state; it does not send an OTP or repeat login.

## Current state

Jio owner login utility: implemented and locally tested; live email authentication,
profile verification and corrected folder listing all succeeded.
Owner upload/download connector: implemented and tested against Jio. Bulk upload
completed and verified (209 packages, 195 portraits, one catalogue). Hosted
catalogue delivery is now migrated to Jio. It serves 209 Live2D models and 362
PMX character packages, including 362 animated turntable previews across the five
approved games. Live end-to-end installs of both formats passed through the
authenticated hosted service; anonymous requests returned 401. Vault read/write
RPCs were checked to deny anon/authenticated execution. Owner publishing uses a
separate high-entropy encrypted capability; its hash is the only deployed proof.

PMX cloud browsing now shows game folders, character cards and rotating previews;
global search and an animated download activity indicator are shared across both
installed desktop editions. Esper Zero's coat deformation was traced to omitted
auxiliary sleeve IK. The real rig test verified target convergence and no drift
over 200 updates; primary body/leg IK is excluded from this fix. Existing model
settings and source assets are preserved.

See `docs/jio-model-publishing.md` for the owner folder-addition workflow and
`tools/sync-jio-library.py` for the manual owner sync. Live inventory of the five
Jio game trees completed: 1,005 folders and 6,488 files. Inventory is read-only;
the complete future-addition pipeline is not scheduled to run automatically.
Drive publisher remains paused; its deleted destination is not a fallback.
All 209 prepared packages remain available locally in
`F:/AI/assistant/private-model-library` and the clean hardlinked upload folder
`F:/AI/assistant/Sakura Jio Upload`.
