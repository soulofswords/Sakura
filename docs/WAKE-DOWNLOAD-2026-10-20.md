# Sakura Mobile 0.3.9 — resumable wake pack download

- Previous mobile downloader deleted its partial file after any failed connection and reopened in overwrite mode on retry. A separate 160-second JavaScript timeout could report a failure while native downloading continued. Progress was sent to the general model status instead of the wake-settings status.
- Saved partial file with HTTP Range resume, five bounded automatic attempts, 12-second connection/read timeout, and explicit manual Resume download when interrupted. If a server ignores Range, it safely replaces the file instead of appending duplicate bytes.
- Download status shows actual decimal MB, percent, KB/s and retry state in Wake phrase settings. Polling reflects downloads still running after leaving/reopening the view, and prevents duplicate actions. Optional download jobs have a longer UI wait budget; ordinary chat retains its timeout.
- Exact 41,205,931-byte size and pinned SHA-256 required before safe model extraction. Corrupted completed downloads are discarded and fetched again. Interrupted files are preserved; Android can still evict cache files under storage pressure.
- Install over Sakura Mobile without uninstalling. An interrupted download from the previous build may already have been deleted by that build. No alternate/unverified model source or TLS bypass was added.

Validation: real Java downloader against controlled HTTP tests passed for mid-stream disconnect and byte-range retry, repeated 503 failures retaining partial bytes, manual resume, servers ignoring Range, and corrupt full-file hash recovery. Android Java/R8/signature/archive checks passed. Packaged WebView checks cover visible progress/speed and Resume button along with existing wake/menu/chat/model flows. Actual download speed depends on the upstream server and connection; the cause of this user connection slowdown was not directly measured.

SHA256: abe13d229039605775fe2fdb9383d0d289aca3017da6d19f48d3ba0400022de8
