Write-Host "=== J.A.R.V.I.S. - Model Setup ===" -ForegroundColor Cyan
Write-Host ""

# 1. Check Ollama
Write-Host "[1/4] Checking Ollama..." -ForegroundColor Yellow
try {
    $ollamaVer = ollama --version
    Write-Host "  Ollama: $ollamaVer" -ForegroundColor Green
} catch {
    Write-Host "  Ollama not found. Download from https://ollama.com" -ForegroundColor Red
    Write-Host "  Install and re-run this script." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[2/4] Pulling LLM model (llama3.1:8b)..." -ForegroundColor Yellow
ollama pull llama3.1:8b

Write-Host ""
Write-Host "[3/4] Pulling embedding model..." -ForegroundColor Yellow
ollama pull mxbai-embed-large

Write-Host ""
Write-Host "[4/4] Creating voice directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path "..\models\voice" -Force | Out-Null
Write-Host "  Place your Jarvis voice sample as: models\voice\jarvis_sample.wav" -ForegroundColor Yellow
Write-Host "  (10-30 second clip of the voice you want to clone)" -ForegroundColor Yellow

Write-Host ""
Write-Host "=== Setup complete! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. pip install -r ..\backend\requirements.txt"
Write-Host "  2. cd ..\frontend && npm install"
Write-Host "  3. .\run.ps1"
