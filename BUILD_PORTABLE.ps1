$ErrorActionPreference = 'Stop'
$root    = Split-Path -Parent $MyInvocation.MyCommand.Path
$release = Join-Path $root 'release'
$bundleName = 'FB-Automation-Portable-v5.4.7'
$bundle  = Join-Path $release $bundleName
$zip     = Join-Path $release "$bundleName-Windows-x64.zip"
$installer = Join-Path $bundle 'runtime\python-3.12.10-amd64.exe'

# Clean old bundle
if (Test-Path $bundle) { Remove-Item -LiteralPath $bundle -Recurse -Force }
New-Item -ItemType Directory -Path (Join-Path $bundle 'runtime') -Force | Out-Null

# Excluded top-level names
$excluded = @('.git', 'venv', '__pycache__', 'profiles', 'uploads', 'release', '.codex', '.gitignore', '.env')

# Copy source files (top-level)
Get-ChildItem -LiteralPath $root -Force | Where-Object { $_.Name -notin $excluded } | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $bundle -Recurse -Force
}

# Remove runtime data files that should NOT ship
$runtimeFiles = @(
    '.env', 'state.json', 'scheduler_state.json', 'config.json',
    'publication_queue.json', 'campaigns.json', 'profile_activity.json', 'auth_status.json',
    'group_registry.json', 'manual_group_queue.json', 'accounts.json'
)
Get-ChildItem -LiteralPath $bundle -Recurse -File -Force |
    Where-Object { $_.Name -in $runtimeFiles -or $_.Extension -in @('.pyc', '.pyo', '.log') } |
    Remove-Item -Force
# Ship empty accounts.json (required by app on first run)
Set-Content -LiteralPath (Join-Path $bundle 'accounts.json') -Value '[]' -Encoding UTF8

# Remove all *.log files recursively
Get-ChildItem -LiteralPath $bundle -Filter '*.log' -Recurse -Force | Remove-Item -Force

# Remove all __pycache__ directories recursively
Get-ChildItem -LiteralPath $bundle -Filter '__pycache__' -Recurse -Directory -Force | Remove-Item -Recurse -Force

# Remove .pytest_cache if present
Get-ChildItem -LiteralPath $bundle -Filter '.pytest_cache' -Recurse -Directory -Force | Remove-Item -Recurse -Force

# Download bundled Python installer
Write-Host "Dang tai Python 3.12.10 installer..."
Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $installer

# Create zip
if (Test-Path $zip) { Remove-Item -LiteralPath $zip -Force }
Compress-Archive -Path $bundle -DestinationPath $zip -CompressionLevel Optimal

$sizeMB = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Write-Host "Da tao: $zip ($sizeMB MB)"
