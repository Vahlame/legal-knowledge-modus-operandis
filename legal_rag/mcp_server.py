"""
Servidor MCP (Model Context Protocol) para la memoria legal CR.

JSON-RPC 2.0 newline-delimited sobre stdio, SIN dependencias (stdlib pura) — para
que cualquier agente MCP (Claude Code, etc.) consulte el corpus. Expone:

  - legal_search  : búsqueda híbrida (BM25+semántica), N adaptativo, citada
  - legal_article : texto verbatim de un artículo exacto
  - legal_related : concordancias (cita / citado por / misma materia)
  - legal_consult : bundle de asesoría (núcleo + relacionados + temario)

Registro (mcp.json / .claude.json):
  "legal-memory-cr": { "command": "python", "args": ["-m","legal_rag.mcp_server"],
                       "cwd": "<ruta del repo>" }

Requisito: índice construido (python -m legal_rag.index).
"""
import sys
import json
import pathlib

# Hacer importable el repo desde cualquier cwd (un cliente MCP puede lanzarlo
# desde otra carpeta), además de funcionar con `python -m legal_rag.mcp_server`.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from legal_rag import search, graph, advisor

PROTOCOL = "2024-11-05"

TOOLS = [
    {"name": "legal_search",
     "description": "Búsqueda híbrida (BM25 + semántica) en derecho costarricense. "
                    "Devuelve los artículos relevantes (cantidad adaptativa, sin tope fijo) "
                    "con su cita exacta. Para localizar la norma aplicable a un tema/caso.",
     "inputSchema": {"type": "object",
                     "properties": {"query": {"type": "string", "description": "consulta en lenguaje natural"},
                                    "code": {"type": "string", "description": "slug de código opcional, p.ej. codigo-civil-2026"}},
                     "required": ["query"]}},
    {"name": "legal_article",
     "description": "Texto VERBATIM de un artículo exacto (cita la fuente literal).",
     "inputSchema": {"type": "object",
                     "properties": {"article": {"type": "string", "description": "número, p.ej. 1045"},
                                    "code": {"type": "string", "description": "slug del código"}},
                     "required": ["article", "code"]}},
    {"name": "legal_related",
     "description": "Concordancias de un artículo: artículos que cita, que lo citan, y de su "
                    "misma materia (capítulo). Para traer 'artículos relacionados que ayudan al caso'.",
     "inputSchema": {"type": "object",
                     "properties": {"article": {"type": "string"}, "code": {"type": "string"}},
                     "required": ["article", "code"]}},
    {"name": "legal_consult",
     "description": "Bundle de asesoría para resolver una duda/caso: núcleo de artículos relevantes "
                    "+ relacionados por concordancia + entradas de temario. Todo citado. "
                    "El agente razona SOBRE esto sin inventar norma.",
     "inputSchema": {"type": "object",
                     "properties": {"question": {"type": "string"},
                                    "code": {"type": "string", "description": "slug de código opcional"}},
                     "required": ["question"]}},
]


def call_tool(name, args):
    if name == "legal_search":
        res = search.hybrid(args["query"], args.get("code"))
        return [{"citation": r["citation"], "structure": r["structure"],
                 "score": r["score"], "text": r["text"]} for r in res]
    if name == "legal_article":
        rows = search.get_article(args["article"], args.get("code"))
        return [{"citation": c, "structure": s, "text": t} for c, s, t in rows]
    if name == "legal_related":
        return graph.related(args["code"], args["article"])
    if name == "legal_consult":
        return advisor.consult(args["question"], args.get("code"))
    raise ValueError(f"herramienta desconocida: {name}")


def send(mid, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": mid}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    sys.stdout.buffer.write((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def main():
    # I/O binario explícito en UTF-8: evita que reconfigure() descarte la 1ª línea
    # y no depende de PYTHONIOENCODING (portátil).
    while True:
        raw = sys.stdin.buffer.readline()
        if not raw:
            break
        line = raw.decode("utf-8", "replace").lstrip("﻿").strip()  # tolera BOM
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        method, mid = msg.get("method"), msg.get("id")
        if method == "initialize":
            send(mid, result={"protocolVersion": PROTOCOL,
                              "capabilities": {"tools": {}},
                              "serverInfo": {"name": "legal-memory-cr", "version": "0.1.0"}})
        elif method == "tools/list":
            send(mid, result={"tools": TOOLS})
        elif method == "tools/call":
            p = msg.get("params", {})
            try:
                data = call_tool(p["name"], p.get("arguments", {}))
                text = json.dumps(data, ensure_ascii=False, indent=2)
                send(mid, result={"content": [{"type": "text", "text": text}]})
            except Exception as e:  # noqa: BLE001 — devolver el error al cliente MCP
                send(mid, result={"content": [{"type": "text", "text": f"ERROR: {e}"}],
                                  "isError": True})
        elif method is not None and mid is not None:
            send(mid, error={"code": -32601, "message": f"método no soportado: {method}"})
        # notifications (sin id), p.ej. notifications/initialized -> no se responde


if __name__ == "__main__":
    main()
