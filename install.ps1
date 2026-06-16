# Instalador de la Memoria Legal CR (Windows / PowerShell) — potencia completa.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { "py" }

Write-Host "[1/3] Instalando paquete (neuronal + reranker)..." -ForegroundColor Cyan
& $py -m pip install -e .

Write-Host "[2/3] Construyendo indice + cacheando modelos (~1.3 GB la 1a vez)..." -ForegroundColor Cyan
& $py -m legal_rag setup

Write-Host "[3/3] Registrando MCP en Codex y Claude Code..." -ForegroundColor Cyan
& $py -m legal_rag register --all

Write-Host "`nListo. Reinicia tu agente (Codex / Claude Code)." -ForegroundColor Green
