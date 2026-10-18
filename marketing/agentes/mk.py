#!/usr/bin/env python3
"""Command line client of the marketing registry (MK5 API) for the agents and for people.

Only the standard library, so it runs in any Claude session or laptop with Python 3.11+:

    export KUULIS_API=https://kuulis-qa.top8.uk/api/v1   # default
    export KUULIS_MK_TOKEN=kst_...                       # service token (admin panel > Tokens de servicio)
    python3 marketing/agentes/mk.py list --status guion
    python3 marketing/agentes/mk.py upload K-2026-11-04-A out/K-2026-11-04-A/tiktok.mp4 --role final

Every command prints JSON on stdout; errors go to stderr with the API error code and exit 1.
Pieces can be named by id or by code (K-AAAA-MM-DD-X). Full contract: docs/api/marketing.md.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API = os.environ.get("KUULIS_API", "https://kuulis-qa.top8.uk/api/v1").rstrip("/")
TOKEN = os.environ.get("KUULIS_MK_TOKEN", "")
# Cloudflare in front of the API and of S3 rejects Python's default User-Agent.
USER_AGENT = "Mozilla/5.0 (compatible; kuulis-mk/1.0)"
CODE_RE = re.compile(r"^K-\d{4}-\d{2}-\d{2}-[A-Z]+$")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: Any = None):
        super().__init__(f"{status} {code}: {message}")
        self.status, self.code, self.details = status, code, details


def call(
    method: str, path: str, body: Any = None, *, query: dict | None = None, auth: bool = True
) -> Any:
    url = API + path
    if query:
        clean = {k: v for k, v in query.items() if v not in (None, "")}
        if clean:
            url += "?" + urllib.parse.urlencode(clean)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if auth:
        if not TOKEN:
            raise SystemExit("Falta KUULIS_MK_TOKEN (token de servicio del panel, rol marketing).")
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            err = json.loads(raw)["error"]
        except (ValueError, KeyError, TypeError):
            raise ApiError(exc.code, "http_error", raw[:300].decode(errors="replace")) from exc
        raise ApiError(
            exc.code, err.get("code", "?"), err.get("message", ""), err.get("details")
        ) from exc
    return json.loads(raw) if raw else None


def put_file(url: str, path: Path, headers: dict[str, str]) -> None:
    data = path.read_bytes()
    req = urllib.request.Request(
        url, data=data, method="PUT", headers={"User-Agent": USER_AGENT, **headers}
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        if resp.status >= 300:
            raise ApiError(resp.status, "upload_failed", f"S3 answered {resp.status}")


def content_id(ref: str) -> str:
    """A piece id, or its code looked up in the registry."""
    if not CODE_RE.match(ref):
        return ref
    page = call("GET", "/admin/marketing/contents", query={"q": ref, "limit": 5})
    for item in page["items"]:
        if item["code"] == ref:
            return item["id"]
    raise ApiError(404, "not_found", f"No hay pieza con código {ref}")


def load_json(arg: str) -> Any:
    """Inline JSON, a path to a .json file, or '-' for stdin."""
    if arg == "-":
        return json.load(sys.stdin)
    if arg.lstrip().startswith(("{", "[")):
        return json.loads(arg)
    return json.loads(Path(arg).read_text())


def media_size(path: Path) -> dict[str, Any]:
    """Width/height of PNG and JPEG files without extra libraries (videos: leave them empty)."""
    head = path.open("rb").read(64 * 1024)
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return {
            "width": int.from_bytes(head[16:20], "big"),
            "height": int.from_bytes(head[20:24], "big"),
        }
    if head[:2] == b"\xff\xd8":
        i = 2
        while i < len(head) - 9:
            if head[i] != 0xFF:
                break
            marker, length = head[i + 1], int.from_bytes(head[i + 2 : i + 4], "big")
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                return {
                    "height": int.from_bytes(head[i + 5 : i + 7], "big"),
                    "width": int.from_bytes(head[i + 7 : i + 9], "big"),
                }
            i += 2 + length
    return {}


def upload(
    cid: str, path: Path, role: str, source: str, extra: dict[str, Any] | None = None
) -> dict:
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    body = {
        "filename": path.name,
        "content_type": content_type,
        "size": path.stat().st_size,
        "role": role,
        "source": source,
        **media_size(path),
        **(extra or {}),
    }
    created = call("POST", f"/admin/marketing/contents/{cid}/assets", body)
    put_file(created["upload_url"], path, created.get("headers") or {"Content-Type": content_type})
    return call("POST", f"/admin/marketing/contents/{cid}/assets/{created['asset']['id']}/confirm")


# ---- Commands -------------------------------------------------------------------------------------


def cmd_site(_: argparse.Namespace) -> Any:
    return call("GET", "/public/site", auth=False)


def cmd_list(a: argparse.Namespace) -> Any:
    query = {"status": a.status, "q": a.q, "from": a.desde, "to": a.hasta, "limit": a.limit}
    return call("GET", "/admin/marketing/contents", query=query)


def cmd_show(a: argparse.Namespace) -> Any:
    return call("GET", f"/admin/marketing/contents/{content_id(a.ref)}")


def cmd_create(a: argparse.Namespace) -> Any:
    return call("POST", "/admin/marketing/contents", load_json(a.json))


def cmd_update(a: argparse.Namespace) -> Any:
    return call("PATCH", f"/admin/marketing/contents/{content_id(a.ref)}", load_json(a.json))


def cmd_status(a: argparse.Namespace) -> Any:
    return call(
        "POST", f"/admin/marketing/contents/{content_id(a.ref)}/status", {"status": a.status}
    )


def cmd_variant(a: argparse.Namespace) -> Any:
    """Create the platform version, or update it when the piece already has one."""
    cid = content_id(a.ref)
    body = load_json(a.json)
    piece = call("GET", f"/admin/marketing/contents/{cid}")
    current = next((v for v in piece["variants"] if v["platform"] == body.get("platform")), None)
    if current is None:
        return call("POST", f"/admin/marketing/contents/{cid}/variants", body)
    body.pop("platform", None)
    return call("PATCH", f"/admin/marketing/contents/{cid}/variants/{current['id']}", body)


def cmd_upload(a: argparse.Namespace) -> Any:
    extra = {
        k: v for k, v in {"model": a.model, "prompt": a.prompt, "rights": a.rights}.items() if v
    }
    if a.credits is not None:
        extra["credits_used"] = a.credits
    if a.cost is not None:
        extra["cost_usd"] = a.cost
    return upload(content_id(a.ref), Path(a.file), a.role, a.source, extra)


def cmd_upload_render(a: argparse.Namespace) -> Any:
    """Upload a Remotion render (out/<codigo>/manifest.json) and attach each file to its platform version.

    Videos and carousel slides are `final`, `Portada` stills are `portada`. A version gets the first final
    file of its platform as `asset_id` and its cover as `cover_asset_id` (versions must exist already).
    """
    cid = content_id(a.ref)
    folder = Path(a.folder)
    manifest = json.loads((folder / "manifest.json").read_text())
    uploaded: list[dict[str, Any]] = []
    for item in manifest["archivos"]:
        role = "portada" if item["plantilla"] == "Portada" else "final"
        asset = upload(cid, folder / item["archivo"], role, "remotion")
        uploaded.append(
            {"red": item["red"], "role": role, "asset_id": asset["id"], "archivo": item["archivo"]}
        )
    piece = call("GET", f"/admin/marketing/contents/{cid}")
    attached = []
    for variant in piece["variants"]:
        mine = [u for u in uploaded if u["red"] == variant["platform"]]
        final = next((u["asset_id"] for u in mine if u["role"] == "final"), None)
        cover = next((u["asset_id"] for u in mine if u["role"] == "portada"), None)
        patch = {k: v for k, v in {"asset_id": final, "cover_asset_id": cover}.items() if v}
        if patch and not a.no_attach:
            call("PATCH", f"/admin/marketing/contents/{cid}/variants/{variant['id']}", patch)
            attached.append({"platform": variant["platform"], **patch})
    return {"uploaded": uploaded, "attached": attached}


def cmd_approve(a: argparse.Namespace) -> Any:
    return call("POST", f"/admin/marketing/contents/{content_id(a.ref)}/approve")


def cmd_changes(a: argparse.Namespace) -> Any:
    return call(
        "POST", f"/admin/marketing/contents/{content_id(a.ref)}/request-changes", {"note": a.note}
    )


def cmd_queue(a: argparse.Namespace) -> Any:
    return call("GET", "/admin/marketing/queue", query={"day": a.day})


def cmd_metric(a: argparse.Namespace) -> Any:
    return call(
        "POST", f"/admin/marketing/publications/{a.publication_id}/metrics", load_json(a.json)
    )


def cmd_performance(a: argparse.Namespace) -> Any:
    query = {
        "platform": a.platform,
        "pillar": a.pillar,
        "format": a.format,
        "from": a.desde,
        "to": a.hasta,
    }
    return call("GET", "/admin/marketing/performance", query=query)


def cmd_learnings(_: argparse.Namespace) -> Any:
    return call("GET", "/admin/marketing/learnings")


def cmd_learn(a: argparse.Namespace) -> Any:
    body = load_json(a.json)
    if a.id:
        return call("PATCH", f"/admin/marketing/learnings/{a.id}", body)
    return call("POST", "/admin/marketing/learnings", body)


def cmd_spend(a: argparse.Namespace) -> Any:
    return call("GET", "/admin/marketing/spend", query={"month": a.month})


def cmd_accounts(_: argparse.Namespace) -> Any:
    return call("GET", "/admin/marketing/accounts")


def cmd_raw(a: argparse.Namespace) -> Any:
    return call(a.method.upper(), a.path, load_json(a.json) if a.json else None)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mk", description="Registro de marketing de Kuulis (API MK5).")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser(
        "site", help="Valores vivos de /public/site (cuota, meses gratis, pagos)"
    ).set_defaults(fn=cmd_site)

    s = sub.add_parser("list", help="Piezas del registro")
    s.add_argument("--status")
    s.add_argument("--q")
    s.add_argument("--desde", help="scheduled_for desde AAAA-MM-DD")
    s.add_argument("--hasta", help="scheduled_for hasta AAAA-MM-DD")
    s.add_argument("--limit", type=int, default=50)
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("show", help="Una pieza con versiones, archivos y estados permitidos")
    s.add_argument("ref")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("create", help="Crear pieza: JSON (inline, archivo o -)")
    s.add_argument("json")
    s.set_defaults(fn=cmd_create)

    s = sub.add_parser("update", help="Editar campos de una pieza")
    s.add_argument("ref")
    s.add_argument("json")
    s.set_defaults(fn=cmd_update)

    s = sub.add_parser(
        "status", help="Mover de estado (idea, guion, revisado, producido, archivado, descartado)"
    )
    s.add_argument("ref")
    s.add_argument("status")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser(
        "variant", help="Crear o actualizar la versión de una red (JSON con platform)"
    )
    s.add_argument("ref")
    s.add_argument("json")
    s.set_defaults(fn=cmd_variant)

    s = sub.add_parser("upload", help="Subir un archivo a S3 y registrarlo")
    s.add_argument("ref")
    s.add_argument("file")
    s.add_argument("--role", choices=["original", "final", "portada", "fuente"], default="final")
    s.add_argument("--source", default="remotion", help="remotion, higgsfield, buzzy, captura…")
    s.add_argument("--model")
    s.add_argument("--prompt")
    s.add_argument("--rights")
    s.add_argument("--credits", type=float)
    s.add_argument("--cost", help="USD con dos decimales")
    s.set_defaults(fn=cmd_upload)

    s = sub.add_parser(
        "upload-render", help="Subir out/<codigo>/ de Remotion y enlazarlo a las versiones"
    )
    s.add_argument("ref")
    s.add_argument("folder")
    s.add_argument("--no-attach", action="store_true")
    s.set_defaults(fn=cmd_upload_render)

    s = sub.add_parser("approve", help="Aprobar (solo tras el OK de Carlos)")
    s.add_argument("ref")
    s.set_defaults(fn=cmd_approve)

    s = sub.add_parser("changes", help="Pedir cambios con una nota (vuelve a revisado)")
    s.add_argument("ref")
    s.add_argument("note")
    s.set_defaults(fn=cmd_changes)

    s = sub.add_parser("queue", help="Tarjetas de publicación de un día")
    s.add_argument("--day")
    s.set_defaults(fn=cmd_queue)

    s = sub.add_parser("metric", help="Instantánea de métricas de una publicación")
    s.add_argument("publication_id")
    s.add_argument("json")
    s.set_defaults(fn=cmd_metric)

    s = sub.add_parser("performance", help="Una fila por publicación con su última instantánea")
    for flag in ("--platform", "--pillar", "--format", "--desde", "--hasta"):
        s.add_argument(flag)
    s.set_defaults(fn=cmd_performance)

    sub.add_parser("learnings", help="Aprendizajes").set_defaults(fn=cmd_learnings)

    s = sub.add_parser("learn", help="Crear (o con --id, editar) un aprendizaje")
    s.add_argument("json")
    s.add_argument("--id")
    s.set_defaults(fn=cmd_learn)

    s = sub.add_parser("spend", help="Gasto de un mes")
    s.add_argument("--month")
    s.set_defaults(fn=cmd_spend)

    sub.add_parser("accounts", help="Cuentas en redes").set_defaults(fn=cmd_accounts)

    s = sub.add_parser("raw", help="Llamada libre: METHOD /ruta [json]")
    s.add_argument("method")
    s.add_argument("path")
    s.add_argument("json", nargs="?")
    s.set_defaults(fn=cmd_raw)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = args.fn(args)
    except ApiError as exc:
        print(
            json.dumps(
                {
                    "error": exc.code,
                    "status": exc.status,
                    "message": str(exc),
                    "details": exc.details,
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
