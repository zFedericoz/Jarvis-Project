param(
    [switch]$NoFrontend,
    [switch]$NoBackend
)

Write-Host "=== J.A.R.V.I.S. Launcher ===" -ForegroundColor Cyan

$root = Split-Path -Parent $PSScriptRoot

if (-not $NoBackend) {
    Write-Host "Starting backend..." -ForegroundColor Yellow
    $backendJob = Start-Job -ScriptBlock {
        Set-Location $using:root\backend
        python main.py
    }
    Write-Host "  Backend PID: $($backendJob.Id)" -ForegroundColor Green
    Start-Sleep -Seconds 2
}

if (-not $NoFrontend) {
    Write-Host "Starting frontend..." -ForegroundColor Yellow
    $frontendJob = Start-Job -ScriptBlock {
        Set-Location $using:root\frontend
        npm run dev
    }
    Write-Host "  Frontend PID: $($frontendJob.Id)" -ForegroundColor Green
}

Write-Host ""
Write-Host "J.A.R.V.I.S. is running!" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:5173"
Write-Host "  Backend:  http://localhost:8765"
Write-Host ""
Write-Host "Press Ctrl+C to stop all services." -ForegroundColor Cyan

try {
    while ($true) {
        Start-Sleep -Seconds 1
        if (-not $NoBackend) {
            $bj = Get-Job -Id $backendJob.Id -ErrorAction SilentlyContinue
            if ($bj.State -eq 'Failed') {
                Receive-Job -Job $bj
                throw "Backend crashed"
            }
        }
    }
} finally {
    Write-Host "Shutting down..." -ForegroundColor Yellow
    if (-not $NoBackend) { Stop-Job -Id $backendJob.Id -ErrorAction SilentlyContinue; Remove-Job -Id $backendJob.Id -Force -ErrorAction SilentlyContinue }
    if (-not $NoFrontend) { Stop-Job -Id $frontendJob.Id -ErrorAction SilentlyContinue; Remove-Job -Id $frontendJob.Id -Force -ErrorAction SilentlyContinue }
    Write-Host "Done." -ForegroundColor Green
}
