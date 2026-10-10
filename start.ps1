$ErrorActionPreference = 'Stop'
$candidates = @(
    (Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'),
    (Join-Path $env:USERPROFILE 'VUE-Modern\runtime\Scripts\pythonw.exe')
)
$runtime = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$app = Join-Path $PSScriptRoot 'app.py'

if (-not $runtime) {
    throw 'No se encontro Python con PySide6. Crea .venv e instala requirements.txt; consulta README.md.'
}

& $runtime $app
