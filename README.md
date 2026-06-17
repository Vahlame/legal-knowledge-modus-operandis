# Memoria Legal CR — asesoría y formación jurídica para agentes de IA

Base de conocimiento de **derecho costarricense** (códigos + temarios) convertida a
Markdown **fiel y token-eficiente**, indexada para **recuperación híbrida** y expuesta
como **servidor MCP**, para que un agente de IA **asesore casos y forme abogados
citando SIEMPRE la fuente** — sin inventar norma.

> Encargo para despacho legal. Mismo ADN que un sistema de memoria híbrido (BM25 +
> semántico + RRF, *passage-first*), pero dedicado al dominio jurídico. **Portátil**:
> backend semántico neuronal (fastembed) por defecto, con fallback automático a un
> embedder stdlib de cero dependencias.

## 🤖 Instalar con un agente (lo más simple)

Clona el repo, ábrelo en **Claude Code** o **Codex** y dile:
> *«instala esto siguiendo AGENTS.md»*

El agente corre `pip install -e .` → `setup` → `register` y queda listo. Receta completa
en **[AGENTS.md](AGENTS.md)**. La instalación manual está más abajo.

## Estado — completo

| Fase | Qué | Estado |
|---|---|---|
| F1 | Conversión PDF → Markdown, **fidelidad probada** (cero pérdida de comas) | ✅ |
| F2 | Recuperación léxica FTS5 + citación | ✅ |
| F3 | Recuperación **híbrida** (BM25 + neuronal + **reranking** cross-encoder), **N adaptativo** | ✅ |
| F4 | **Grafo de concordancias** (cita / citado por / misma materia) | ✅ |
| F5 | Capa de **asesoría + formación** (núcleo + relacionados + temario) | ✅ |
| — | **Servidor MCP** (stdlib) para cualquier agente | ✅ |

## Instalación (1 comando)

Requisitos: **Python 3.11+** y git. Clona el repo y corre el instalador:

```powershell
# Windows (PowerShell)
git clone https://github.com/Vahlame/legal-knowledge-modus-operandis
cd legal-knowledge-modus-operandis ; ./install.ps1
```
```bash
# macOS / Linux
git clone https://github.com/Vahlame/legal-knowledge-modus-operandis
cd legal-knowledge-modus-operandis && ./install.sh
```

El instalador, a potencia completa: `pip install -e .` (motor neuronal + reranker),
construye el índice + cachea modelos, y registra el MCP en **Codex** y **Claude Code**.
Reinicia tu agente y listo.

Equivalente manual (todo vía `python -m legal_rag`, sin depender del PATH):

```powershell
pip install -e .                      # potencia completa (fastembed: neuronal + reranker)
python -m legal_rag setup             # índice + grafo + cachea modelos (~1.3 GB la 1ª vez)
python -m legal_rag register --all    # Codex + Claude Code (+ Cursor con --cursor)
python -m legal_rag doctor            # diagnóstico
```
> Si `fastembed` no instala en tu plataforma, el sistema cae solo al embedder stdlib
> (cero dependencias) — sigue funcionando, con menos recall semántico.

## Uso (CLI)

```powershell
python -m legal_rag consult "que pasa si no pago la pension alimentaria"
python -m legal_rag search  "prescripcion adquisitiva" --code codigo-civil-2026
python -m legal_rag article 1045 --code codigo-civil-2026   # VERBATIM + vigencia + reformas
python -m unittest discover -s tests                        # regresión (cero dependencias)
```
(Si el directorio *Scripts* de Python está en tu PATH, también sirve `legal-memory <cmd>`.)

## Agentes (MCP)

`register` deja el servidor `legal-memory-cr` (tools `legal_search`, `legal_article`,
`legal_related`, `legal_consult` — todas citan la fuente) listo en:

- **Codex** → `~/.codex/config.toml`
- **Claude Code** → `.mcp.json` del repo (in-project) y/o `~/.claude.json` (global)
- **Cursor** → `~/.cursor/mcp.json`  ·  cualquier otro cliente MCP usa la misma invocación.

Invocación robusta (sin depender del PATH; `<python>` = ruta absoluta del intérprete):

```toml
# Codex — ~/.codex/config.toml
[mcp_servers.legal-memory-cr]
command = "<python>"
args = ["-m", "legal_rag.mcp_server"]
```
```jsonc
// Claude Code / Cursor / genérico — dentro de "mcpServers"
"legal-memory-cr": { "command": "<python>", "args": ["-m", "legal_rag.mcp_server"] }
```
`python -m legal_rag register --dry-run --all` imprime exactamente qué escribirá en cada agente.

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
