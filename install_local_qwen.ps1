param([int]$DownloadProcessId = 0)
$ErrorActionPreference = 'Stop'
$project = $PSScriptRoot
$runtime = Join-Path $project 'ollama-runtime'
$archive = Join-Path $runtime 'runtime.zip'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
if ($DownloadProcessId -gt 0) {
    Wait-Process -Id $DownloadProcessId -ErrorAction SilentlyContinue
}
if (-not (Test-Path -LiteralPath (Join-Path $runtime 'ollama.exe'))) {
    if (-not (Test-Path -LiteralPath $archive) -or (Get-Item -LiteralPath $archive).Length -ne 1468064949) {
        & curl.exe -L --fail --retry 3 -C - 'https://github.com/ollama/ollama/releases/download/v0.40.0/ollama-windows-amd64.zip' -o $archive
        if ($LASTEXITCODE -ne 0) { throw 'Runtime download failed. Run this script again to resume.' }
    }
    Write-Output 'Extracting project-local runtime...'
    Expand-Archive -LiteralPath $archive -DestinationPath $runtime -Force
}
Push-Location $project
try {
    & (Join-Path $project 'venv\Scripts\python.exe') -u 'tests/install_vision_model.py' 'qwen3-vl:2b-instruct'
    if ($LASTEXITCODE -ne 0) { throw 'Qwen download failed. Run this script again to resume.' }
    $settingsPath = Join-Path $project 'settings.json'
    $settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
    $settings.ollama_model = 'qwen3-vl:2b-instruct'
    $settings.ollama_models_folder = 'llm-models'
    $settings.ollama_context = 2048
    $settings | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $settingsPath -Encoding utf8
    if ((Resolve-Path -LiteralPath $archive -ErrorAction SilentlyContinue)) { Remove-Item -LiteralPath $archive }
    Write-Output 'Qwen 2B installed. Sakura is configured for Qwen 2B with 2048 context.'
} finally { Pop-Location }
