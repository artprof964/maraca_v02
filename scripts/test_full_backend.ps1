param(
    [switch]$StrictServices
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$EnvFile = if (Test-Path ".env") { ".env" } else { ".env.example" }

.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\rag-center-health.exe --env-file $EnvFile

if ($StrictServices) {
    .\.venv\Scripts\rag-center-health.exe --strict-services --env-file $EnvFile
}

.\.venv\Scripts\rag-center-smoke.exe
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m pytest
