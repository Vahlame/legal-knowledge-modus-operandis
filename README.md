# Memoria Legal CR — asesoría jurídica para agentes de IA

Base de conocimiento de derecho costarricense (códigos + temarios) convertida a
Markdown token-eficiente y **recuperable por artículo**, con un motor de búsqueda
estilo RAG (FTS5 BM25 + semántico, *passage-first*) para que un agente de IA
**cite la fuente exacta** al asesorar casos.

> Encargo para despacho legal. Mismo ADN que un sistema de memoria híbrido, pero
> dedicado al dominio jurídico y portátil: núcleo Python + MCP + CLI.

## Estado

| Fase | Qué | Estado |
|---|---|---|
| F1 | Conversión PDF → Markdown (14 docs, 3.274 artículos) | ✅ |
| F2 | Recuperación léxica FTS5 + CLI con citación (3.313 chunks) | ✅ |
| F3 | Capa semántica (embeddings) + fusión RRF | ⬜ |
| F4 | Servidor MCP + grafo de referencias cruzadas | ⬜ |
| F5 | Capa de asesoría (cita siempre la fuente, anti-alucinación) | ⬜ |

## Estructura

- `pdfs data/` — PDFs fuente (SCIJ / PGR / Colegio de Abogados).
- `markdown/` — Markdown estructurado, un `## Artículo N` por artículo + frontmatter.
- `legal_rag/` — núcleo: `chunker.py`, `index.py`, `search.py`.
- `scripts/` — utilidades (`convert_pdfs.py`, sondas de diagnóstico).
- `legal.db` — índice SQLite FTS5 (regenerable, no versionar).

## Uso

Requisitos: Python 3.11+. Para reconvertir PDFs: `pip install pymupdf4llm`.

```powershell
python scripts/convert_pdfs.py                 # 1) PDFs -> markdown/
python -m legal_rag.index                      # 2) (re)construir índice FTS5
python -m legal_rag.search usufructo uso habitacion          # 3a) búsqueda
python -m legal_rag.search prescripcion adquisitiva --code codigo-civil-2026
python -m legal_rag.search --art 1045 --code codigo-civil-2026   # 3b) artículo exacto
```

## Diseño

- **Troceo por artículo**: cada artículo es la unidad recuperable. El agente recibe
  el artículo + su cita (`Código Civil, art. 1045`) y ruta (Capítulo), no el código entero.
- **FTS5 `unicode61 + remove_diacritics`**: "prescripcion" encuentra "prescripción".
- **Anti-alucinación**: el agente cita artículo y código; no inventa norma. El texto
  legal indexado es la fuente autoritativa; este sistema solo lo recupera y cita.

## Fuentes

Legislación costarricense vigente (SCIJ/PGR) y temarios del Examen de Incorporación
del Colegio de Abogados y Abogadas de Costa Rica.
