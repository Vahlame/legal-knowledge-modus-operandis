# AGENTS.md — instalación automática para agentes

Eres un agente de IA y te pidieron **instalar esta herramienta** (memoria legal RAG de
derecho costarricense, que se expone como servidor MCP y como CLI). Ejecuta los pasos de
abajo **desde la raíz del repo**. Es seguro, reproducible y no requiere intervención.

## Requisitos
- **Python 3.11+** — usa el que exista en la plataforma: `python`, `python3` o `py`.
- Internet la primera vez (descarga ~1.3 GB de modelos neuronales).

## Instalar (ejecuta en este orden)
```sh
python -m pip install -e .       # paquete + dependencias (motor neuronal + reranker)
python -m legal_rag setup        # índice + grafo + cachea modelos (~1.3 GB la 1ª vez)
python -m legal_rag doctor       # verifica: debe decir OK en corpus/índice
```
> `setup` puede tardar varios minutos por la descarga de modelos: **es normal, no abortes.**
>
> Si `pip install -e .` falla compilando `fastembed`/`onnxruntime` en esta plataforma,
> instala sin él: `python -m pip install -e . --no-deps`. El sistema cae solo al embedder
> **stdlib** (cero dependencias, sin descarga) y sigue funcionando con menos recall semántico.

## Registrar el MCP (para usarlo como herramienta nativa del agente)
```sh
python -m legal_rag register --all     # Codex (~/.codex/config.toml), Claude Code, Cursor
# solo el tuyo:   --codex | --claude | --cursor
# previsualizar:  python -m legal_rag register --dry-run --all
```
Reinicia el agente para cargar el servidor **`legal-memory-cr`** (tools: `legal_search`,
`legal_article`, `legal_related`, `legal_consult`).

## Usar sin MCP (funciona de inmediato, por CLI)
```sh
python -m legal_rag consult "que pasa si no pago la pension alimentaria"
python -m legal_rag search  "prescripcion adquisitiva" --code codigo-civil-2026
python -m legal_rag article 1045 --code codigo-civil-2026
```

## Verificación final
- `python -m legal_rag doctor` → índice OK; `fastembed: sí` (o `stdlib` si caíste al fallback).
- `python -m unittest discover -s tests` → 19 tests en verde.
- Una consulta de prueba devuelve artículos **citados**.

## Reglas del producto (al asesorar con esta herramienta)
- Responde **solo con artículos de ley vigente**: los derogados se excluyen del resultado.
- **Cita siempre** la fuente (código + artículo); no inventes norma.
- Los **temarios** son guía de estudio, **no** son la ley — van en su propio carril.
- Tras cambiar/añadir PDFs en `pdfs data/`: `python -m pip install -e ".[convert]"` y
  `python scripts/convert_pdfs.py` y luego `python -m legal_rag setup`.
