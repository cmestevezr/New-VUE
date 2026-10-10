param(
    [string]$Version = "0.1.0"
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$pythonCandidates = @(
    (Join-Path $root '.venv\Scripts\python.exe'),
    (Join-Path $env:USERPROFILE 'VUE-Modern\runtime\Scripts\python.exe')
)
$python = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $python) {
    throw 'No se encontro el entorno de Python para construir el instalador.'
}

$output = Join-Path $root 'installer-output'
$work = Join-Path $output "build-$Version"
$package = Join-Path $output "VUE-Modern-$Version"
$appOutput = Join-Path $package 'app'

Remove-Item -LiteralPath $package -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $package -Force | Out-Null

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name 'VUE Modern' `
    --add-data "$(Join-Path $root 'assets');assets" `
    --distpath $appOutput `
    --workpath $work `
    --specpath $output `
    (Join-Path $root 'app.py')

if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller no pudo crear VUE Modern.'
}

Copy-Item -LiteralPath (Join-Path $root 'installer\Install-VUE-Modern.ps1') -Destination $package
Copy-Item -LiteralPath (Join-Path $root 'installer\Install-VUE-Modern.cmd') -Destination $package
Copy-Item -LiteralPath (Join-Path $root 'installer\Uninstall-VUE-Modern.ps1') -Destination $package
Copy-Item -LiteralPath (Join-Path $root 'LICENSE') -Destination $package
Copy-Item -LiteralPath (Join-Path $root 'README.md') -Destination $package

$zip = Join-Path $output "VUE-Modern-$Version-windows.zip"
Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $package '*') -DestinationPath $zip -CompressionLevel Optimal

Write-Host "Instalador creado: $zip"
