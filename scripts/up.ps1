<#
.SYNOPSIS
    Avvia J.A.R.V.I.S. con Docker + Host Metrics Server automatico.
.DESCRIPTION
    Avvia il server metriche Windows host in background, poi lancia docker compose up -d.
    All'uscita ferma tutto automaticamente.
.EXAMPLE
    .\scripts\up.ps1
#>

$root = Split-Path -Parent $PSScriptRoot

Write-Host "=== J.A.R.V.I.S. Docker Launcher ===" -ForegroundColor Cyan
Write-Host ""

# ── 1. Start Host Metrics Server ──────────────────────────────────────────────
Write-Host "[1/3] Avvio Host Metrics Server..." -ForegroundColor Yellow

$pythonPath = (Get-Command python).Source
Write-Host "  Python: $pythonPath" -ForegroundColor Gray

$metricsJob = Start-Job -Name "HostMetrics" -ScriptBlock {
    param($py, $dir)
    Set-Location $dir
    & $py host_metrics_server.py
} -ArgumentList $pythonPath, (Join-Path $root "backend")

Start-Sleep -Seconds 3
$ms = Get-Job -Name "HostMetrics" -ErrorAction SilentlyContinue

if ($ms.State -eq 'Running') {
    Write-Host "  OK - http://localhost:18765" -ForegroundColor Green
} else {
    Write-Host "  ERRORE:" -ForegroundColor Red
    $ms | Receive-Job -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
    $ms | Remove-Job -Force -ErrorAction SilentlyContinue
    $metricsJob = $null
}

# ── 2. Start Docker containers ────────────────────────────────────────────────
Write-Host "[2/3] Avvio container Docker..." -ForegroundColor Yellow
Write-Host "  docker compose up -d --build" -ForegroundColor Gray
Write-Host ""

try {
    docker compose up -d --build
    $exit = $LASTEXITCODE
    if ($exit -ne 0 -and $exit -ne 130) {
        Write-Host "  Docker compose terminato con codice: $exit" -ForegroundColor Red
    } else {
        Write-Host "  Container in esecuzione!" -ForegroundColor Green
        Write-Host "  Frontend: http://localhost:80" -ForegroundColor Cyan
        Write-Host "  Backend:  http://localhost:8765" -ForegroundColor Cyan
        if ($metricsJob) {
            Write-Host "  Metrics:  http://localhost:18765 (metriche reali)" -ForegroundColor Cyan
        }
        Write-Host ""
        Write-Host "Premi Ctrl+C per fermare i container." -ForegroundColor Cyan
        docker compose logs -f
    }
} catch {
    Write-Host "Errore Docker: $_" -ForegroundColor Red
} finally {
    # ── 3. Cleanup ────────────────────────────────────────────────────────────
    Write-Host ""
    Write-Host "[3/3] Pulizia..." -ForegroundColor Yellow
    if ($metricsJob) {
        Write-Host "  Fermo Host Metrics Server..." -ForegroundColor Yellow
        Stop-Job -Name "HostMetrics" -ErrorAction SilentlyContinue
        Remove-Job -Name "HostMetrics" -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  Fatto." -ForegroundColor Green
}

Write-Host ""
Write-Host "J.A.R.V.I.S. arrestato." -ForegroundColor Cyan
