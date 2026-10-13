$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path $PSScriptRoot -Parent
$installDirectory = Split-Path $projectDirectory -Parent
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$launcherDirectory = Join-Path $projectDirectory 'launcher'
$stagedExecutable = Join-Path $launcherDirectory 'Sakura-launcher-build.exe'
$targetExecutable = Join-Path $installDirectory 'Desktop Companion.exe'
& $compiler /nologo /target:winexe /optimize+ /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll "/win32icon:$launcherDirectory\companion.ico" "/out:$stagedExecutable" "$launcherDirectory\Launcher.cs" "$launcherDirectory\StartupDialog.cs" "$launcherDirectory\LocalModelDialog.cs"
if ($LASTEXITCODE -ne 0) { throw 'Launcher compilation failed; installed executable was not changed.' }
if (Test-Path -LiteralPath $targetExecutable) {
    $backupDirectory = Join-Path $launcherDirectory 'previous-launchers'
    New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null
    $backupPath = Join-Path $backupDirectory ('Desktop Companion-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.exe')
    Copy-Item -LiteralPath $targetExecutable -Destination $backupPath
}
Copy-Item -LiteralPath $stagedExecutable -Destination $targetExecutable -Force
Write-Output "Built $targetExecutable"
