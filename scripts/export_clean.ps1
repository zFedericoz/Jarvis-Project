<#
.SYNOPSIS
  Crea uno ZIP pulito del progetto Jarvis, escludendo cache, dipendenze e dati runtime.
  Output: jarvis-export.zip nella root del progetto (~5 MB invece di ~1.5 GB).

.DESCRIPTION
  Esclude automaticamente:
    - Cache Python (__pycache__, *.pyc, .pytest_cache, .mypy_cache)
    - Dipendenze (node_modules, .venv, venv)
    - Build artifacts (dist, .vite, *.tsbuildinfo)
    - Dati runtime (data/, models/)
    - Git e IDE (.git, .idea, .vscode)
    - Secrets (.env)
#>

$source = Split-Path -Parent $PSScriptRoot
$dest = Join-Path $source "jarvis-export.zip"

# Rimuovi zip precedente se esiste
Remove-Item -LiteralPath $dest -ErrorAction SilentlyContinue

Write-Host "Creazione archivio pulito di Jarvis..." -ForegroundColor Cyan

$excludePatterns = @(
    '__pycache__', '*.pyc', '.pytest_cache', '.mypy_cache', '.ruff_cache'
    'node_modules', '.venv', 'venv'
    'dist', '.vite', '*.tsbuildinfo'
    'data', 'models'
    '.git', '.idea', '.vscode'
    '.env', '*.swp', '*.swo', '*~', '.DS_Store', 'Thumbs.db'
    '*.zip'
)

$arguments = @(
    "-Path", $source
    "-DestinationPath", $dest
    "-CompressionLevel", "Optimal"
)
foreach ($p in $excludePatterns) {
    $arguments += "-Exclude"
    $arguments += $p
}

try {
    Compress-Archive @arguments
    $size = (Get-Item $dest).Length
    Write-Host "Creato: jarvis-export.zip ($([math]::Round($size/1MB,1)) MB)" -ForegroundColor Green
} catch {
    Write-Host "Errore: $_" -ForegroundColor Red
    exit 1
}
