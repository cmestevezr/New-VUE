$ErrorActionPreference = 'Stop'
$destination = Join-Path $env:LOCALAPPDATA 'VUE Modern'
$shortcutPath = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\VUE Modern.lnk'

Remove-Item -LiteralPath $shortcutPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $destination -Recurse -Force -ErrorAction SilentlyContinue
