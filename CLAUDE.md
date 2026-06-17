# Instalación con Claude Code

Esta herramienta se instala siguiendo **[AGENTS.md](AGENTS.md)** (mismos pasos para todo
agente). Si te pidieron "instala esto", ejecuta desde la raíz del repo:

```sh
python -m pip install -e .       # paquete + motor neuronal + reranker
python -m legal_rag setup        # índice + modelos (~1.3 GB la 1ª vez; NO abortes por la espera)
python -m legal_rag doctor       # verifica
```

- El servidor MCP de este proyecto ya está declarado en **`.mcp.json`** del repo: al abrir
  el proyecto, Claude Code te pedirá **aprobar** el servidor `legal-memory-cr`. Para
  registrarlo también global: `python -m legal_rag register --claude`.
- Mientras tanto (o sin MCP) úsalo por CLI: `python -m legal_rag consult "<pregunta>"`.
- Si `fastembed` no instala: `python -m pip install -e . --no-deps` → usa el embedder
  stdlib (cero dependencias). Todo lo demás funciona igual.

Reglas al asesorar: solo ley **vigente** (derogados excluidos), **cita** siempre la fuente,
temarios = estudio (no son la ley).
