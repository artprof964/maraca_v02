param(
    [switch]$InstallDocker,
    [switch]$StartServices
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

if (-not (Test-Path ".venv")) {
    py -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install -e ".[full]"

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
}

$EnvFile = if (Test-Path ".env") { ".env" } else { ".env.example" }

$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    if ($InstallDocker) {
        winget install --id Docker.DockerDesktop --exact --accept-package-agreements --accept-source-agreements
        Write-Host "Docker Desktop install was requested. Reopen the terminal after install/restart, then rerun this script with -StartServices."
    } else {
        Write-Host "Docker CLI is not available. Install Docker Desktop or rerun with -InstallDocker."
    }
} elseif ($StartServices) {
    docker compose up -d qdrant neo4j
}

.\.venv\Scripts\rag-center-health.exe --env-file $EnvFile
.\.venv\Scripts\rag-center-smoke.exe
