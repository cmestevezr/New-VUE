$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'app\VUE Modern'
$destination = Join-Path $env:LOCALAPPDATA 'VUE Modern'
$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$shortcutPath = Join-Path $startMenu 'VUE Modern.lnk'

if (-not (Test-Path -LiteralPath (Join-Path $source 'VUE Modern.exe'))) {
    throw 'No se encontro el paquete de VUE Modern. Extrae el archivo ZIP completo antes de instalar.'
}

New-Item -ItemType Directory -Path $destination -Force | Out-Null
Copy-Item -Path (Join-Path $source '*') -Destination $destination -Recurse -Force

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $destination 'VUE Modern.exe'
$shortcut.WorkingDirectory = $destination
$shortcut.Description = 'Editor local de mapas conceptuales VUE Modern'
$shortcut.Save()

Start-Process -FilePath (Join-Path $destination 'VUE Modern.exe')
