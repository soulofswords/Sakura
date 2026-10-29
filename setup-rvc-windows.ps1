# Explicit optional install; never run at application startup.
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$gpu=Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name
$backend=if($gpu -match 'NVIDIA'){'cuda'}elseif($gpu -match 'AMD|Radeon|Intel'){'directml'}else{'cpu'}
Write-Host "Installing a self-contained RVC $backend runtime. This can download several GB."
$assets=Join-Path $PSScriptRoot 'rvc-assets'
New-Item -ItemType Directory -Force -Path $assets | Out-Null
$models=@{
 'hubert_base.pt'='f54b40fd2802423a5643779c4861af1e9ee9c1564dc9d32f54f20b5ffba7db96'
 'rmvpe.pt'='6d62215f4306e3ca278246188607209f09af3dc77ed4232efdd069798c4ec193'
}
foreach($name in $models.Keys){
 $target=Join-Path $assets $name
 if((Test-Path -LiteralPath $target) -and (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -eq $models[$name]){continue}
 $pending=Join-Path $assets ($name+'.'+[guid]::NewGuid().ToString('N')+'.download')
 try{
  Invoke-WebRequest -UseBasicParsing -Uri ('https://huggingface.co/Daswer123/RVC_Base/resolve/main/'+$name) -OutFile $pending
  if((Get-FileHash -LiteralPath $pending -Algorithm SHA256).Hash.ToLowerInvariant() -ne $models[$name]){throw "RVC asset checksum failed: $name. Existing files were kept."}
  Move-Item -LiteralPath $pending -Destination $target -Force
 }finally{if(Test-Path -LiteralPath $pending){Remove-Item -LiteralPath $pending}}
}
& (Join-Path $PSScriptRoot 'setup-rvc-amd.ps1') -Backend $backend
if($LASTEXITCODE -ne 0){throw 'RVC runtime installation failed. See the preceding error.'}
