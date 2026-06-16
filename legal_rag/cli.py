"""
CLI unificado de la memoria legal CR.

  legal-memory setup       -> construye el índice + cachea modelos (potencia completa)
  legal-memory register    -> registra el MCP en Codex y Claude Code (y Cursor)
  legal-memory mcp         -> arranca el servidor MCP por stdio (= legal-memory-mcp)
  legal-memory doctor      -> diagnóstico (deps, índice, modelos, entry points)
  legal-memory search "…"  -> búsqueda híbrida
  legal-memory consult "…" -> bundle de asesoría
  legal-memory article N --code <slug>
"""
import sys
import json
import argparse
import pathlib

from legal_rag import paths

MCP_NAME = "legal-memory-cr"
MCP_BIN = "legal-memory-mcp"


def _mcp_invocation():
    """Invocación robusta del servidor MCP: el intérprete actual (ruta absoluta) +
    el módulo. Funciona sin depender de que el directorio Scripts esté en PATH.
    Devuelve (command, args)."""
    return sys.executable, ["-m", "legal_rag.mcp_server"]


def _has_fastembed() -> bool:
    try:
        import fastembed  # noqa: F401
        return True
    except Exception:
        return False


# ------------------------------------------------------------------ doctor
def cmd_doctor(_args):
    md = len(list(paths.MD_DIR.glob("*.md"))) if paths.MD_DIR.exists() else 0
    print(f"HOME            : {paths.HOME}")
    print(f"corpus markdown : {'OK' if md else 'FALTA'} ({md} docs)")
    print(f"índice (db)     : {'OK' if paths.DB.exists() else 'FALTA -> legal-memory setup'}")
    print(f"vectores (npy)  : {'OK (neuronal)' if paths.VEC.exists() else 'no (modo stdlib)'}")
    print(f"fastembed       : {'sí (neuronal + reranker)' if _has_fastembed() else 'no (embedder stdlib)'}")
    cmd, cargs = _mcp_invocation()
    print(f"comando MCP     : {cmd} {' '.join(cargs)}")


# ------------------------------------------------------------------ setup
def cmd_setup(args):
    from legal_rag import index, embed
    print("1) Construyendo índice (BM25 + semántico + grafo)…")
    index.build()
    if not args.no_warm and embed.neural_available():
        print("2) Cacheando modelos neuronales (descarga ~1.3 GB la 1ª vez)…")
        try:
            embed.neural_encode(["calentando el modelo"])
            if embed.reranker_enabled():
                embed.rerank_scores("calentar", ["texto de prueba"])
            print("   modelos listos.")
        except Exception as e:  # noqa: BLE001
            print(f"   aviso: no se cachearon los modelos ({e}); se bajarán al primer uso.")
    print("\nListo. Ahora:  legal-memory register --all")


# ------------------------------------------------------------------ register
def _reg_codex(command, cargs, dry):
    cfg = pathlib.Path.home() / ".codex" / "config.toml"
    section = f"[mcp_servers.{MCP_NAME}]"
    args_toml = ", ".join(f"'{a}'" for a in cargs)
    block = f"\n{section}\ncommand = '{command}'\nargs = [{args_toml}]\n"
    existing = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
    if section in existing:
        print(f"  Codex     : ya estaba registrado ({cfg})")
        return
    if dry:
        print(f"\n  # append a {cfg}{block}")
    else:
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(existing + block, encoding="utf-8")
        print(f"  Codex     : añadido a {cfg}")


def _reg_json(label, cfg, command, cargs, dry):
    data = {}
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data.setdefault("mcpServers", {})[MCP_NAME] = {"command": command, "args": cargs}
    if dry:
        entry = json.dumps({MCP_NAME: data["mcpServers"][MCP_NAME]}, ensure_ascii=False)
        print(f"  {label}: {cfg}\n              mcpServers += {entry}")
    else:
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {label}: escrito {cfg}")


def cmd_register(args):
    targets = [t for t, on in (("codex", args.codex), ("claude", args.claude),
                               ("cursor", args.cursor)) if on or args.all]
    if not targets:
        targets = ["codex", "claude"]          # primarios por defecto
    command, cargs = _mcp_invocation()
    print(f"Registrando '{MCP_NAME}'  ({command} {' '.join(cargs)})"
          + ("   [DRY-RUN]" if args.dry_run else ""))
    for t in targets:
        if t == "codex":
            _reg_codex(command, cargs, args.dry_run)
        elif t == "claude":
            _reg_json("Claude Code (global ~/.claude.json)",
                      pathlib.Path.home() / ".claude.json", command, cargs, args.dry_run)
        elif t == "cursor":
            _reg_json("Cursor (global)",
                      pathlib.Path.home() / ".cursor" / "mcp.json", command, cargs, args.dry_run)
    print("\n(Claude Code en ESTE proyecto ya queda cubierto por el .mcp.json del repo.)")
    if not args.dry_run:
        print("Reinicia el agente para que cargue el servidor.")


# ------------------------------------------------------------------ pasarelas
def cmd_mcp(_args):
    from legal_rag import mcp_server
    mcp_server.main()


def cmd_search(args):
    from legal_rag import search
    sys.stdout.reconfigure(encoding="utf-8")
    res = search.hybrid(" ".join(args.query), args.code)
    print(f"{len(res)} artículos de ley relevantes:")
    for r in res:
        print(f"  [{r['rama']}] {r['citation']}")


def cmd_consult(args):
    from legal_rag import advisor
    sys.stdout.reconfigure(encoding="utf-8")
    print(advisor.format_consult(advisor.consult(" ".join(args.question), args.code)))


def cmd_article(args):
    from legal_rag import search
    sys.stdout.reconfigure(encoding="utf-8")
    rows = search.get_article(args.num, args.code)
    for cite, struct, text, vig, reformas in rows or []:
        print(f"\n### {cite}{'' if vig else '  ⚠ DEROGADO'}")
        print(text)
        if reformas:
            print(f"   ↳ historia: {reformas}")
    if not rows:
        print("(sin resultados)")


def main():
    ap = argparse.ArgumentParser(prog="legal-memory", description="Memoria legal CR (RAG)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="diagnóstico").set_defaults(func=cmd_doctor)

    sp = sub.add_parser("setup", help="construye índice + cachea modelos")
    sp.add_argument("--no-warm", action="store_true", help="no descargar/cachear modelos")
    sp.set_defaults(func=cmd_setup)

    rp = sub.add_parser("register", help="registra el MCP en los agentes")
    for flag in ("codex", "claude", "cursor", "all"):
        rp.add_argument(f"--{flag}", action="store_true")
    rp.add_argument("--dry-run", action="store_true", help="solo imprime, no escribe")
    rp.set_defaults(func=cmd_register)

    sub.add_parser("mcp", help="arranca el servidor MCP (stdio)").set_defaults(func=cmd_mcp)

    q = sub.add_parser("search", help="búsqueda híbrida")
    q.add_argument("query", nargs="+")
    q.add_argument("--code")
    q.set_defaults(func=cmd_search)

    c = sub.add_parser("consult", help="bundle de asesoría")
    c.add_argument("question", nargs="+")
    c.add_argument("--code")
    c.set_defaults(func=cmd_consult)

    a = sub.add_parser("article", help="artículo exacto")
    a.add_argument("num")
    a.add_argument("--code")
    a.set_defaults(func=cmd_article)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
