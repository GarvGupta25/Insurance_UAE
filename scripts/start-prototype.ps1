param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot

function Test-LocalPort([int] $Port) {
    return $null -ne (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1)
}

Push-Location $projectRoot
try {
    $dockerJob = Start-Job { docker version --format '{{.Server.Version}}' 2>$null }
    $dockerReady = Wait-Job -Job $dockerJob -Timeout 8
    if (-not $dockerReady) {
        Stop-Job -Job $dockerJob
        throw 'Docker Desktop is not running. Open Docker Desktop and wait for Engine running, then run this command again.'
    }
    Remove-Job -Job $dockerJob -Force

    npx supabase start --ignore-health-check | Out-Host
    if (-not (Test-Path (Join-Path $projectRoot 'backend\.env'))) {
        $status = npx supabase status -o json
        $status | & (Join-Path $projectRoot 'backend\.venv\Scripts\python.exe') (Join-Path $projectRoot 'backend\scripts\configure_local.py')
    }

    & (Join-Path $projectRoot 'backend\.venv\Scripts\python.exe') (Join-Path $projectRoot 'backend\scripts\bootstrap_demo_accounts.py')

    if (-not (Test-LocalPort 8000)) {
        Start-Process -FilePath (Join-Path $projectRoot 'backend\.venv\Scripts\python.exe') -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000' -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden
    }
    if (-not (Test-LocalPort 5174)) {
        Start-Process -FilePath 'npm.cmd' -ArgumentList '--prefix', 'frontend', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', '5174' -WorkingDirectory $projectRoot -WindowStyle Hidden
    }

    Write-Host ''
    Write-Host 'Helm AI is ready at http://127.0.0.1:5174/login'
    Write-Host 'Member with broker: member@example / password'
    Write-Host 'Broker:              broker@example / password'
    Write-Host 'Regular member:      regular@example / password'
}
finally {
    Pop-Location
}
