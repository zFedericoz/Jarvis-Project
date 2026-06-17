param(
    [switch]$NoFrontend,
    [switch]$NoBackend,
    [switch]$NoMetrics
)

$root = Split-Path -Parent $PSScriptRoot

Write-Host "=== J.A.R.V.I.S. Launcher ===" -ForegroundColor Cyan

$backendDir = Join-Path $root "backend"

# ── Detect host Python (skip MS Store stub) ─────────────────────────────────
$pythonPath = $null
$pythonCandidates = @(
    "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "C:\Program Files\Python313\python.exe",
    "C:\Program Files\Python312\python.exe",
    "C:\Program Files\Python311\python.exe",
    "C:\Python313\python.exe",
    "C:\Python312\python.exe"
)
foreach ($candidate in $pythonCandidates) {
    if (Test-Path $candidate) {
        $pythonPath = $candidate
        break
    }
}

if ($pythonPath) {
    Write-Host "  Python: $pythonPath" -ForegroundColor Gray
} else {
    Write-Host "  Python host non trovato, metriche/RPA host disabilitati." -ForegroundColor DarkYellow
}

if (-not $NoMetrics -and $pythonPath) {
    Write-Host "Avvio Host Metrics Server (metriche reali del PC)..." -ForegroundColor Yellow
    $metricsJob = Start-Job -Name "HostMetrics" -ScriptBlock {
        param($py, $dir)
        Set-Location $dir
        & $py host_metrics_server.py
    } -ArgumentList $pythonPath, $backendDir
    Start-Sleep -Seconds 3
    $ms = Get-Job -Name "HostMetrics" -ErrorAction SilentlyContinue
    if ($ms.State -eq 'Running') {
        Write-Host "  Host Metrics: http://localhost:18765" -ForegroundColor Green
    } else {
        Write-Host "  Host Metrics: ERRORE" -ForegroundColor Red
        $ms | Receive-Job -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        Remove-Job -Name "HostMetrics" -Force -ErrorAction SilentlyContinue
        $metricsJob = $null
    }
} elseif (-not $NoMetrics) {
    Write-Host "Host Metrics: Skipped (Python host non disponibile)" -ForegroundColor DarkYellow
}

if (-not $NoBackend) {
    Write-Host "Avvio backend..." -ForegroundColor Yellow
    $backendJob = Start-Job -ScriptBlock {
        Set-Location $using:root\backend
        python main.py
    }
    Write-Host "  Backend PID: $($backendJob.Id)" -ForegroundColor Green
    Start-Sleep -Seconds 2
}

if (-not $NoFrontend) {
    Write-Host "Avvio frontend..." -ForegroundColor Yellow
    $frontendJob = Start-Job -ScriptBlock {
        Set-Location $using:root\frontend
        npm run dev
    }
    Write-Host "  Frontend PID: $($frontendJob.Id)" -ForegroundColor Green
}

Write-Host ""
Write-Host "J.A.R.V.I.S. è in esecuzione!" -ForegroundColor Green
Write-Host "  Frontend:       http://localhost:5173"
Write-Host "  Backend:        http://localhost:8765"
if (-not $NoMetrics) {
    Write-Host "  Host Metrics:  http://localhost:18765 (metriche reali)"
}
Write-Host ""
Write-Host "Premi Ctrl+C per fermare tutto." -ForegroundColor Cyan

try {
    while ($true) {
        Start-Sleep -Seconds 1
        if ((-not $NoBackend) -and $backendJob) {
            $bj = Get-Job -Id $backendJob.Id -ErrorAction SilentlyContinue
            if ($bj.State -eq 'Failed') { Receive-Job -Job $bj; throw "Backend crashed" }
        }
    }
} finally {
    Write-Host "Arresto in corso..." -ForegroundColor Yellow
    if ($frontendJob) { Stop-Job -Id $frontendJob.Id -ErrorAction SilentlyContinue; Remove-Job -Id $frontendJob.Id -Force -ErrorAction SilentlyContinue }
    if ($backendJob) { Stop-Job -Id $backendJob.Id -ErrorAction SilentlyContinue; Remove-Job -Id $backendJob.Id -Force -ErrorAction SilentlyContinue }
    if ($metricsJob) { Stop-Job -Id $metricsJob.Id -ErrorAction SilentlyContinue; Remove-Job -Id $metricsJob.Id -Force -ErrorAction SilentlyContinue }
    Write-Host "Fatto." -ForegroundColor Green
}
