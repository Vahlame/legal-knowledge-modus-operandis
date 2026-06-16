#!/usr/bin/env bash
# Instalador de la Memoria Legal CR (macOS / Linux) — potencia completa.
set -euo pipefail
cd "$(dirname "$0")"
PY="$(command -v python3 || command -v python)"

echo "[1/3] Instalando paquete (neuronal + reranker)..."
"$PY" -m pip install -e .

echo "[2/3] Construyendo indice + cacheando modelos (~1.3 GB la 1a vez)..."
"$PY" -m legal_rag setup

echo "[3/3] Registrando MCP en Codex y Claude Code..."
"$PY" -m legal_rag register --all

echo
echo "Listo. Reinicia tu agente (Codex / Claude Code)."
