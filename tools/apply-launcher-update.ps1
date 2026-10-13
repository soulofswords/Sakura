$ErrorActionPreference = 'Stop'
Wait-Process -Id 20496 -ErrorAction SilentlyContinue
$source = 'F:\AI\assistant\Sakura\launcher\Sakura-launcher-pending.exe'
$destination = 'F:\AI\assistant\Desktop Companion.exe'
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        Copy-Item -LiteralPath $source -Destination $destination -Force
        'Applied Sakura OBS runtime branding update.' | Set-Content -LiteralPath 'F:\AI\assistant\Sakura\logs\launcher-update.log'
        exit 0
    } catch { Start-Sleep -Milliseconds 500 }
}
throw 'Could not replace the closed Sakura launcher.'
