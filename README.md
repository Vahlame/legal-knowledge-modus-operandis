# Memoria Legal CR — asesoría y formación jurídica para agentes de IA

Base de conocimiento de **derecho costarricense** (códigos + temarios) convertida a
Markdown **fiel y token-eficiente**, indexada para **recuperación híbrida** y expuesta
como **servidor MCP**, para que un agente de IA **asesore casos y forme abogados
citando SIEMPRE la fuente** — sin inventar norma.

> Encargo para despacho legal. Mismo ADN que un sistema de memoria híbrido (BM25 +
> semántico + RRF, *passage-first*), pero dedicado al dominio jurídico. **Portátil**:
> backend semántico neuronal (fastembed) por defecto, con fallback automático a un
> embedder stdlib de cero dependencias.

## Estado — completo

| Fase | Qué | Estado |
|---|---|---|
| F1 | Conversión PDF → Markdown, **fidelidad probada** (cero pérdida de comas) | ✅ |
| F2 | Recuperación léxica FTS5 + citación | ✅ |
| F3 | Recuperación **híbrida** (BM25 + neuronal + **reranking** cross-encoder), **N adaptativo** | ✅ |
| F4 | **Grafo de concordancias** (cita / citado por / misma materia) | ✅ |
| F5 | Capa de **asesoría + formación** (núcleo + relacionados + temario) | ✅ |
| — | **Servidor MCP** (stdlib) para cualquier agente | ✅ |

## Arranque rápido

Requisitos: Python 3.11+ y `pip install -r requirements.txt` (instala `fastembed` para el
backend neuronal — baja ~0.22 GB de modelo la 1ª vez — y `pymupdf4llm` para reconvertir).
Si `fastembed` no está, el sistema cae solo al embedder stdlib (cero dependencias).

```powershell
pip install -r requirements.txt
python scripts/convert_pdfs.py            # 1) PDFs -> markdown/  (fiel)
python scripts/verify_fidelity.py         # 2) auditar fidelidad (debe dar 14/14 OK)
python -m legal_rag.index                 # 3) índice híbrido (neuronal) + grafo
python -m legal_rag.advisor "puede el inquilino subarrendar"   # 4) asesoría
python -m unittest discover -s tests -v   # 5) tests de regresión (cero dependencias)
```

## Uso (CLI)

```powershell
# Búsqueda híbrida, N adaptativo (devuelve todos los relevantes, no un tope fijo)
python -m legal_rag.search que pasa si no pago la pension alimentaria
python -m legal_rag.search prescripcion adquisitiva --code codigo-civil-2026
python -m legal_rag.search homicidio culposo --lexical      # solo BM25

# Artículo exacto (texto VERBATIM)
python -m legal_rag.search --art 1045 --code codigo-civil-2026

# Concordancias: artículos relacionados que ayudan al caso
python -m legal_rag.graph --art 1124 --code codigo-civil-2026

# Asesoría completa: núcleo + relacionados + temario, todo citado
python -m legal_rag.advisor "responsabilidad por danos que causa un animal" --code codigo-civil-2026
```

## Servidor MCP (para agentes)

Expone 4 herramientas: `legal_search`, `legal_article`, `legal_related`, `legal_consult`.
Registrar en `mcp.json` / `.claude.json`:

```json
{
  "mcpServers": {
    "legal-memory-cr": {
      "command": "python",
      "args": ["-m", "legal_rag.mcp_server"],
      "cwd": "C:/Users/DEV/Documents/GitHub/legal knowledge & modus operandis"
    }
  }
}
```

## Arquitectura (5 capas)

1. **Corpus** (`markdown/`) — un `## Artículo N` por artículo, con frontmatter. Fiel al PDF.
2. **Conocimiento** — chunks por artículo + **grafo de concordancias** (refs internas,
   vecinos de capítulo) + temario como currículo.
3. **Recuperación** (`legal_rag/search.py`) — para responder, **solo artículos de código**
   (los temarios van por su stream de estudio). Pipeline: BM25 ⊕ semántico neuronal →
   **RRF** (recall) → **reranking cross-encoder** multilingüe (`jina-reranker-v2`, evalúa
   pregunta + artículo juntos = precisión) → **corte adaptativo** por margen de score.
   Degrada solo: sin reranker → RRF; sin fastembed → embedder stdlib tf-idf.
4. **Concordancias** (`legal_rag/graph.py`) — `related(art)` = cita + citado_por + misma materia.
5. **Asesoría** (`legal_rag/advisor.py`) — ensambla el bundle que el agente razona;
   `mcp_server.py` lo publica por MCP.

## Garantía de fidelidad

`scripts/verify_fidelity.py` compara PDF vs Markdown por **multiconjunto de palabras**
(acento-sensible) y **censo de comas/puntuación**. Resultado: **14/14 OK** — el cuerpo de
cada artículo es **verbatim**; solo se normaliza la marca de ordinal del encabezado
(`## Artículo 2` vs `2º`) y se quita paginación/ruido no legal. **No se usa NFKC** (alteraría
ordinales); solo deligadura tipográfica (`ﬁ`→`fi`).

## Principios de diseño

- **Anti-alucinación**: el agente cita artículo y código; todo sale del corpus indexado.
- **Vigencia (no cita norma muerta)**: ~409 artículos derogados se detectan, se **excluyen** de las respuestas y se marcan `⚠ DEROGADO` en el lookup exacto. `include_derogadas=True` para verlos a propósito.
- **N adaptativo**: nunca un tope fijo de artículos — devuelve todos los relevantes.
- **Relacionados primero**: un caso necesita la norma *y su red* (concordancias).
- **Formación**: los temarios son el currículo del examen de incorporación (CAACR).
- **Calidad primero (latencia secundaria)**: bi-encoder neuronal para *recall* +
  **reranker cross-encoder** para *precisión* (encuentra el artículo exacto: "homicidio
  culposo" → art. 117 #1; "responsabilidad por daño" → art. 1045 #1). Degradación elegante:
  sin reranker → RRF; sin fastembed → embedder stdlib de cero deps.
  Overrides: `LEGAL_EMBEDDER=stdlib|neural`, `LEGAL_RERANK=0`.

## Corpus

6 códigos (Civil, Penal, Procesal Civil/Penal/Familia, Familia) · 7 temarios 2025 ·
examen de incorporación CAACR. Fuentes oficiales (SCIJ/PGR) y Colegio de Abogados y
Abogadas de Costa Rica. **3.274 artículos**, 5.112 chunks, 1.946 concordancias.

## Roadmap

- Concordancias **cross-código** (sustantivo ↔ procesal).
- Mapa explícito temario→artículos para rutas de estudio.
- Modelo neuronal de máxima calidad (e5-large) como opción para despliegues con recursos.
