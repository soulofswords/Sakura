# Sakura RVC runtime for AMD / Intel GPUs (DirectML).
# Creates rvc-amd-runtime\ with torch + torch-directml and RVC's dependencies.
# Run once on an AMD machine from the Sakura folder:
#   powershell -ExecutionPolicy Bypass -File setup-rvc-amd.ps1
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$runtime = Join-Path $PSScriptRoot 'rvc-amd-runtime'
if (Test-Path (Join-Path $runtime 'Scripts\python.exe')) {
    Write-Host "rvc-amd-runtime already exists - recreating torch-directml packages only." -ForegroundColor Yellow
}

function Find-Python312 {
    $candidates = @(
        @{ Command = (Join-Path $PSScriptRoot 'venv\Scripts\python.exe'); Arguments = @() },
        @{ Command = 'python3.12'; Arguments = @() },
        @{ Command = 'py'; Arguments = @('-3.12') }
    )
    foreach ($candidate in $candidates) {
        try {
            $argsForPython = $candidate.Arguments
            $version = & $candidate.Command @argsForPython --version 2>$null
            if ($LASTEXITCODE -eq 0 -and $version -match '^Python 3\.12\.') { return $candidate }
        } catch { }
    }
    throw "Python 3.12 not found. Install it from python.org (or 'winget install Python.Python.3.12') and rerun."
}

$python = Find-Python312
Write-Host "Using: $($python.Command)" -ForegroundColor Cyan

if (-not (Test-Path (Join-Path $runtime 'Scripts\python.exe'))) {
    Write-Host 'Creating isolated runtime...' -ForegroundColor Cyan
    $argsForPython = $python.Arguments
    & $python.Command @argsForPython -m venv $runtime
    if ($LASTEXITCODE -ne 0) { throw 'venv creation failed.' }
}

$pip = Join-Path $runtime 'Scripts\pip.exe'

# DirectML builds on top of regular torch; the CPU wheel keeps inference
# correct on any machine, and torch-directml accelerates it on AMD/Intel.
Write-Host 'Installing torch (CPU wheel) + torch-directml...' -ForegroundColor Cyan
# Pin against torch-directml's published wheel metadata, including torchaudio's
# matching ABI. Explicit CPU index avoids downloading NVIDIA CUDA packages.
& $pip install torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw 'CPU torch / torchaudio install failed.' }
& $pip install torch-directml==0.2.5.dev240914
if ($LASTEXITCODE -ne 0) { throw 'torch-directml install failed.' }

# Same dependency set as the NVIDIA runtime, but rvc-python must be
# installed WITHOUT dependency resolution (its metadata pins legacy
# versions like omegaconf 2.0.6 that conflict with the pinned set), so
# filter its entry out of the requirements list first.
Write-Host 'Installing RVC dependencies...' -ForegroundColor Cyan
$deps = Join-Path $env:TEMP ("sakura-rvc-deps-" + [guid]::NewGuid().ToString() + '.txt')
$constraints = Join-Path $env:TEMP ("sakura-rvc-pins-" + [guid]::NewGuid().ToString() + '.txt')
try {
    @('torch==2.4.1', 'torchvision==0.19.1', 'torchaudio==2.4.1', 'torch-directml==0.2.5.dev240914') | Set-Content -Encoding ASCII $constraints
    Get-Content requirements-rvc.txt | Where-Object { $_ -notmatch '^\s*rvc-python' } | Set-Content -Encoding ASCII $deps
    & $pip install -r $deps -c $constraints
    if ($LASTEXITCODE -ne 0) { throw 'RVC dependency install failed.' }
} finally {
    Remove-Item -LiteralPath $deps, $constraints -ErrorAction SilentlyContinue
}
& $pip install --no-deps rvc-python==0.1.5
if ($LASTEXITCODE -ne 0) { throw 'rvc-python install failed.' }

Write-Host ''
# Check the actual service imports too, not merely a trivial tensor operation.
& (Join-Path $runtime 'Scripts\python.exe') -c "import torch, torchaudio, fairseq, rvc_python.infer, fastapi, uvicorn; print('RVC imports OK')"
if ($LASTEXITCODE -ne 0) { throw 'RVC package verification failed.' }
Write-Host 'Verifying DirectML...' -ForegroundColor Cyan
$code = "import torch, torch_directml; d = torch_directml.device(); print('DirectML OK:', (torch.ones(2, device=d) + 1).cpu().tolist())"
& (Join-Path $runtime 'Scripts\python.exe') -c $code
if ($LASTEXITCODE -ne 0) {
    Write-Warning 'DirectML verification failed. RVC will fall back to CPU but should still work.'
} else {
    Write-Host 'AMD/Intel RVC runtime ready. Sakura will pick it up automatically.' -ForegroundColor Green
}
