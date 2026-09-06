$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$version = (Get-Content (Join-Path $root 'VERSION') -Raw).Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid VERSION: $version" }
$releaseRoot = Join-Path $root 'release'
$stagingRoot = Join-Path $releaseRoot 'staging'
$artifactRoot = Join-Path $releaseRoot 'artifacts'
$bundleName = "FB-Automation-Portable-v$version"
$bundle = Join-Path $stagingRoot $bundleName
$zip = Join-Path $artifactRoot "$bundleName-Windows-x64.zip"
New-Item -ItemType Directory -Path $stagingRoot,$artifactRoot -Force | Out-Null
if (Test-Path $bundle) { Remove-Item $bundle -Recurse -Force }
New-Item -ItemType Directory -Path $bundle -Force | Out-Null
$dirs = @('api','migrations','repositories','services','static')
foreach ($d in $dirs) { Copy-Item (Join-Path $root $d) $bundle -Recurse -Force }
$files = @('ai_spinner.py','brand_profiles.py','db.py','fb_auth.py','fb_comment.py','fb_create_page.py','fb_group.py','fb_interact.py','fb_join_group.py','fb_page.py','fb_page_api.py','fb_scraper.py','fb_thread.py','main.py','paths.py','scheduler.py','server.py','utils.py','README.md','HUONG_DAN_SU_DUNG.html','requirements.txt','RUN_FB_AUTOMATION.bat','START_LINUX.sh','START_MAC.command','start_portable.bat','VERSION')
foreach ($f in $files) { if (Test-Path (Join-Path $root $f)) { Copy-Item (Join-Path $root $f) $bundle -Force } }
# Runtime dependencies are copied, but never runtime state.
if (Test-Path (Join-Path $root 'runtime')) { Copy-Item (Join-Path $root 'runtime') $bundle -Recurse -Force }
$data = Join-Path $bundle 'data'
New-Item -ItemType Directory -Path $data,(Join-Path $data 'uploads'),(Join-Path $data 'logs\jobs'),(Join-Path $data 'backups'),(Join-Path $data 'processed_media') -Force | Out-Null
Get-ChildItem $bundle -Recurse -Directory -Force | Where-Object Name -eq '__pycache__' | Remove-Item -Recurse -Force
Get-ChildItem $bundle -Recurse -File -Force | Where-Object { $_.Extension -in @('.pyc','.pyo','.log') } | Remove-Item -Force
$tmpZip = $zip + '.tmp.zip'
$tmpHash = $zip + '.sha256.tmp'
if (Test-Path $tmpZip) { Remove-Item $tmpZip -Force }
if (Test-Path $tmpHash) { Remove-Item $tmpHash -Force }
Compress-Archive -Path $bundle -DestinationPath $tmpZip -CompressionLevel Optimal
if (-not (Test-Path $tmpZip) -or (Get-Item $tmpZip).Length -lt 1MB) { throw 'Build produced an invalid ZIP artifact.' }
$hash = (Get-FileHash $tmpZip -Algorithm SHA256).Hash
Set-Content -LiteralPath $tmpHash -Value "$hash  $(Split-Path $zip -Leaf)" -Encoding ASCII
Move-Item -LiteralPath $tmpZip -Destination $zip -Force
Move-Item -LiteralPath $tmpHash -Destination ($zip + '.sha256') -Force
Write-Host "Built $zip"
Write-Host "SHA256 $hash"
