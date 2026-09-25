param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot 'backend'
$pythonPath = Join-Path $backendRoot '.venv\Scripts\python.exe'
$wslProjectRoot = (& wsl.exe wslpath -a $projectRoot).Trim()
$wslBackendRoot = "$wslProjectRoot/backend"
$wslUser = (& wsl.exe whoami).Trim()
$wslEnvironment = "/home/$wslUser/.venvs/helm-ai"

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

    Write-Host 'Starting local authentication and database services...'
    $previousErrorPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $supabaseOutput = & npx supabase start --ignore-health-check 2>&1
    $ErrorActionPreference = $previousErrorPreference
    if ($LASTEXITCODE -ne 0) {
        throw 'Local Supabase could not start. Confirm that Docker Desktop shows Engine running, then retry.'
    }
    if (-not (Test-Path (Join-Path $backendRoot '.env'))) {
        throw 'backend/.env is missing. Run the local Supabase configuration step before starting Helm.'
    }

    # The Windows Python runtime can be blocked from loading PostgreSQL's libpq DLL.
    # Run API and worker in WSL, which uses the same checked-out source and local Supabase.
    $syncCommand = 'cd "{0}" && UV_PROJECT_ENVIRONMENT="{1}" ~/.local/bin/uv sync --no-dev' -f $wslBackendRoot, $wslEnvironment
    & wsl.exe -e bash -lc $syncCommand
    if ($LASTEXITCODE -ne 0) { throw 'WSL could not prepare the Helm API runtime.' }

    $bootstrapCommand = 'cd "{0}" && UV_PROJECT_ENVIRONMENT="{1}" ~/.local/bin/uv run --no-sync python scripts/bootstrap_demo_accounts.py' -f $wslBackendRoot, $wslEnvironment
    & wsl.exe -e bash -lc $bootstrapCommand
    if ($LASTEXITCODE -ne 0) { throw 'The Helm demo accounts could not be prepared.' }

    $marketplaceSeedCommand = 'cd "{0}" && UV_PROJECT_ENVIRONMENT="{1}" ~/.local/bin/uv run --no-sync python scripts/seed_marketplace_providers.py' -f $wslBackendRoot, $wslEnvironment
    & wsl.exe -e bash -lc $marketplaceSeedCommand
    if ($LASTEXITCODE -ne 0) { throw 'The marketplace providers and demo logins could not be prepared.' }

    $apiPort = 8000
    if (-not (Test-LocalPort $apiPort)) {
        $apiCommand = 'cd "{0}" && export UV_PROJECT_ENVIRONMENT="{1}" && ~/.local/bin/uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port 8000' -f $wslBackendRoot, $wslEnvironment
        Start-Process -FilePath wsl.exe -ArgumentList '-e', 'bash', '-lc', $apiCommand -WindowStyle Hidden
    }
    $workerCheck = (& wsl.exe -e bash -lc "pgrep -f '[p]ython -m app.worker'" 2>$null)
    if (-not $workerCheck) {
        $workerCommand = 'cd "{0}" && export UV_PROJECT_ENVIRONMENT="{1}" && ~/.local/bin/uv run --no-sync python -m app.worker' -f $wslBackendRoot, $wslEnvironment
        Start-Process -FilePath wsl.exe -ArgumentList '-e', 'bash', '-lc', $workerCommand -WindowStyle Hidden
    }

    if (-not (Test-LocalPort 5174)) {
        Start-Process -FilePath 'npm.cmd' -ArgumentList '--prefix', 'frontend', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', '5174' -WorkingDirectory $projectRoot -WindowStyle Hidden
    }

    $capabilities = $null
    for ($attempt = 0; $attempt -lt 20 -and -not $capabilities; $attempt++) {
        Start-Sleep -Milliseconds 500
        try { $capabilities = Invoke-RestMethod "http://127.0.0.1:$apiPort/api/config" -TimeoutSec 2 } catch { }
    }
    if (-not $capabilities) { throw "The Helm API did not become ready on port $apiPort." }
    $groqConfigured = Select-String -Path (Join-Path $backendRoot '.env') -Pattern '^GROQ_API_KEY=\S+' -Quiet
    if ($groqConfigured -and -not $capabilities.ai_available) {
        throw 'GROQ_API_KEY exists in backend/.env, but the refreshed API did not load it.'
    }

    Write-Host ''
    Write-Host 'Helm AI is ready at http://127.0.0.1:5174/login'
    Write-Host "API:                 http://127.0.0.1:$apiPort"
    Write-Host "Groq assistant:      $($capabilities.ai_available)"
    Write-Host 'Member with broker: member@example / password'
    Write-Host 'Broker:              broker@example / password'
    Write-Host 'Regular member:      regular@example / password'
    Write-Host 'Provider logins:     see README.md#demo-accounts'
}
finally {
    Pop-Location
}
