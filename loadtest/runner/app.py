"""Load test runner for Kuulis (doc 18). Runs on its own server ("pc grande") so the load
generator never competes with the API for CPU.

- ``POST /api/runs`` starts k6 (``k6/kuulis.js``) with the given options, signs the synthetic
  admins in (2FA) for the admin scenario, samples the API server's CPU and memory from its
  node-exporter while it runs, and can send the push campaign in the middle of the test.
- ``GET /api/runs`` / ``GET /api/runs/{id}`` show progress and results; files are downloadable.
- ``POST /expo/push/send`` imitates Expo's push API: point the worker's EXPO_PUSH_URL here during
  the test so 5000 pushes go nowhere real.

Every ``/api`` call needs ``Authorization: Bearer $RUNNER_TOKEN``.
"""

import asyncio
import base64
import contextlib
import csv
import gzip
import hashlib
import hmac
import json
import os
import re
import secrets
import signal
import time
import uuid
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import httpx
import pyotp
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.routing import Route

RUNNER_TOKEN = os.environ.get("RUNNER_TOKEN", "")
BASE_URL = os.environ.get("BASE_URL", "https://kuulis-qa.top8.uk").rstrip("/")
PASSWORD = os.environ.get("LOADTEST_PASSWORD", "")
NODE_EXPORTER_URL = os.environ.get("NODE_EXPORTER_URL", "")
PUSH_LATENCY_MS = int(os.environ.get("PUSH_LATENCY_MS", "150"))
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
SCRIPT = Path(os.environ.get("K6_SCRIPT", Path(__file__).resolve().parent.parent / "k6/kuulis.js"))
DOMAIN = "loadtest.example.com"
CAMPAIGN_TITLE = "Prueba de carga Kuulis (ignorar)"  # apps/loadtest/services.py cleans these
ALLOWED_ENV = {
    "SCENARIOS",
    "SCALE",
    "DRIVERS",
    "RIDES",
    "BROWSERS",
    "DURATION",
    "RAMP",
    "LOCATION_S",
    "ARRIVE_S",
    "TRIP_S",
    "P_ACCOUNTS",
    "D_ACCOUNTS",
}

RUNS = DATA_DIR / "runs"
state: dict[str, Any] = {"run": None, "process": None, "tasks": []}
push_stats = {"requests": 0, "messages": 0, "first_at": None, "last_at": None, "per_second": {}}


def _authorized(request: Request) -> bool:
    header = request.headers.get("authorization", "")
    return bool(RUNNER_TOKEN) and hmac.compare_digest(header, f"Bearer {RUNNER_TOKEN}")


def _deny() -> JSONResponse:
    return JSONResponse({"error": "unauthorized"}, status_code=401)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _seconds(value: str | int | float) -> float:
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(s|m|h)?", str(value))
    if not match:
        raise ValueError(f"Bad duration {value!r}")
    return float(match[1]) * {"s": 1, "m": 60, "h": 3600}[match[2] or "s"]


# --- Clock -------------------------------------------------------------------------------------

# Seconds to add to this machine's clock to get the API server's. TOTP codes and the offer
# delivery times compare both clocks, and the load generator's may be off.
clock = {"offset": 0.0}


def server_time() -> float:
    return time.time() + clock["offset"]


async def measure_clock_offset(client: httpx.AsyncClient) -> float:
    """Polls the API until its ``Date`` header (whole seconds) ticks over: at that moment the
    server's clock is on the new second, which pins the offset to within the request time."""
    previous = None
    for _ in range(80):
        before = time.time()
        response = await client.get("/config/public")
        after = time.time()
        stamp = parsedate_to_datetime(response.headers["date"]).timestamp()
        if previous is not None and stamp > previous:
            clock["offset"] = round(stamp - (before + after) / 2, 3)
            return clock["offset"]
        previous = stamp
        await asyncio.sleep(0.05)
    clock["offset"] = round(previous - time.time() + 0.5, 3) if previous else 0.0
    return clock["offset"]


# --- Synthetic admins (same derivation as apps/loadtest/services.py) ---------------------------


def admin_totp_secret(n: int) -> str:
    digest = hmac.new(PASSWORD.encode(), f"kuulis-loadtest-admin-{n}".encode(), hashlib.sha256)
    return base64.b32encode(digest.digest()[:20]).decode()


class Admin:
    def __init__(self, client: httpx.AsyncClient, n: int) -> None:
        self.client = client
        self.n = n
        self.totp = pyotp.TOTP(admin_totp_secret(n))
        self.last_step = 0
        self.tokens: dict[str, str] = {}

    async def _code(self) -> str:
        """A code from a newer time step than the last one used (each works only once)."""
        wait = (self.last_step + 1) * 30 - server_time()
        if wait > 0:
            await asyncio.sleep(wait + 0.5)
        now = server_time()
        self.last_step = int(now) // 30
        return self.totp.at(now)

    async def login(self) -> dict[str, str]:
        email = f"lt-a{self.n:05d}@{DOMAIN}"
        step = await self.client.post(
            "/auth/admin/login", json={"email": email, "password": PASSWORD}
        )
        step.raise_for_status()
        body = step.json()
        if "access_token" not in body:  # 2FA on (always in QA)
            done = await self.client.post(
                "/auth/admin/totp",
                json={"challenge": body["challenge"], "code": await self._code()},
            )
            done.raise_for_status()
            body = done.json()
        self.tokens = {"access_token": body["access_token"], "refresh_token": body["refresh_token"]}
        return self.tokens

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens['access_token']}"}

    async def reauth(self) -> None:
        response = await self.client.post(
            "/auth/admin/reauth", json={"code": await self._code()}, headers=self.headers()
        )
        response.raise_for_status()


async def campaign(run_dir: Path, client: httpx.AsyncClient, delay: float, count: int) -> None:
    """Sends the push campaign (a broadcast to every user) ``delay`` seconds into the test. When
    broadcasts need a second approval, another synthetic admin approves it."""
    log = run_dir / "campaign.jsonl"

    def write(event: str, **data: Any) -> None:
        with log.open("a") as fh:
            fh.write(json.dumps({"at": _now(), "event": event, **data}) + "\n")

    await asyncio.sleep(delay)
    try:
        sender, approver = Admin(client, count + 1), Admin(client, count + 2)
        await sender.login()
        started = time.time()
        response = await client.post(
            "/notifications/send",
            json={"title": CAMPAIGN_TITLE, "body": "Mensaje de prueba, no hace falta hacer nada."},
            headers=sender.headers(),
        )
        write("sent", status=response.status_code, body=response.json())
        held = response.json().get("approval") if response.status_code == 202 else None
        if held:
            await approver.login()
            await approver.reauth()
            decided = await client.post(
                f"/admin/approvals/{held['id']}/approve",
                json={"note": "Prueba de carga"},
                headers=approver.headers(),
            )
            write("approved", status=decided.status_code)
        write("queued", seconds=round(time.time() - started, 2))
    except Exception as exc:  # recorded for the report; the load test keeps going
        write("error", error=repr(exc))


# --- API server metrics ------------------------------------------------------------------------


def _node_values(text: str) -> dict[str, float]:
    """CPU seconds per mode, memory, load and disk time from node-exporter's text format."""
    values: dict[str, float] = {"cpu_total": 0.0, "cpu_busy": 0.0, "cpu_iowait": 0.0}
    for line in text.splitlines():
        if line.startswith("node_cpu_seconds_total{"):
            mode = re.search(r'mode="(\w+)"', line)
            seconds = float(line.rsplit(" ", 1)[1])
            values["cpu_total"] += seconds
            if mode and mode[1] == "iowait":
                values["cpu_iowait"] += seconds
            elif mode and mode[1] != "idle":
                values["cpu_busy"] += seconds
        elif line.startswith("node_disk_io_time_seconds_total{"):
            values["disk_io"] = values.get("disk_io", 0.0) + float(line.rsplit(" ", 1)[1])
        else:
            for name in (
                "node_memory_MemTotal_bytes",
                "node_memory_MemAvailable_bytes",
                "node_load1",
                "node_procs_running",
                "node_procs_blocked",
            ):
                if line.startswith(name + " "):
                    values[name] = float(line.rsplit(" ", 1)[1])
    return values


async def sample_node(run_dir: Path, every: float = 5.0) -> None:
    if not NODE_EXPORTER_URL:
        return
    previous: dict[str, float] | None = None
    async with httpx.AsyncClient(timeout=5) as client:
        while True:
            try:
                values = _node_values((await client.get(NODE_EXPORTER_URL)).text)
                row: dict[str, Any] = {"at": _now()}
                if previous and values["cpu_total"] > previous["cpu_total"]:
                    spent = values["cpu_total"] - previous["cpu_total"]
                    row["cpu_pct"] = round(
                        100 * (values["cpu_busy"] - previous["cpu_busy"]) / spent, 1
                    )
                    row["iowait_pct"] = round(
                        100 * (values["cpu_iowait"] - previous["cpu_iowait"]) / spent, 1
                    )
                    if "disk_io" in values and "disk_io" in previous:
                        # Busy seconds summed over disks per second of wall time.
                        row["disk_busy"] = round(
                            (values["disk_io"] - previous["disk_io"]) / every, 2
                        )
                total = values.get("node_memory_MemTotal_bytes")
                avail = values.get("node_memory_MemAvailable_bytes")
                if total and avail is not None:
                    row["mem_used_pct"] = round(100 * (1 - avail / total), 1)
                row["load1"] = values.get("node_load1")
                row["procs_running"] = values.get("node_procs_running")
                row["procs_blocked"] = values.get("node_procs_blocked")
                previous = values
                with (run_dir / "node.jsonl").open("a") as fh:
                    fh.write(json.dumps(row) + "\n")
            except Exception as exc:
                with (run_dir / "node.jsonl").open("a") as fh:
                    fh.write(json.dumps({"at": _now(), "error": repr(exc)}) + "\n")
            await asyncio.sleep(every)


def _node_summary(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "node.jsonl"
    if not path.exists():
        return None
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    cpu = sorted(r["cpu_pct"] for r in rows if "cpu_pct" in r)
    iowait = sorted(r["iowait_pct"] for r in rows if "iowait_pct" in r)
    mem = [r["mem_used_pct"] for r in rows if "mem_used_pct" in r]
    if not cpu:
        return {"samples": len(rows)}
    return {
        "samples": len(cpu),
        "cpu_avg": round(sum(cpu) / len(cpu), 1),
        "cpu_p95": cpu[min(len(cpu) - 1, int(0.95 * len(cpu)))],
        "cpu_max": cpu[-1],
        "mem_max": max(mem) if mem else None,
        "iowait_max": iowait[-1] if iowait else None,
    }


# --- Per endpoint and per minute numbers from k6's CSV ------------------------------------------


def _p(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    values.sort()
    return round(values[min(len(values) - 1, int(pct / 100 * len(values)))], 1)


def analyze_csv(run_dir: Path) -> dict[str, Any]:
    """p50/p95/p99 and errors per endpoint (k6 ``name`` tag) and per minute of the test, so the
    report can show where latency started to climb while the load ramped up."""
    path = run_dir / "metrics.csv.gz"
    if not path.exists():
        return {}
    endpoints: dict[str, dict[str, Any]] = {}
    minutes: dict[int, dict[str, Any]] = {}
    with gzip.open(path, "rt", newline="") as fh:
        for row in csv.DictReader(fh):
            metric = row["metric_name"]
            if metric not in ("http_req_duration", "ws_connect_ms", "driver_locations_sent"):
                continue
            minute = int(row["timestamp"]) // 60 * 60
            bucket = minutes.setdefault(
                minute,
                {"durations": [], "requests": 0, "errors_5xx": 0, "ws_connects": 0, "locations": 0},
            )
            if metric == "ws_connect_ms":
                bucket["ws_connects"] += 1
                continue
            if metric == "driver_locations_sent":
                bucket["locations"] += int(float(row["metric_value"]))
                continue
            value = float(row["metric_value"])
            status = row.get("status") or "0"
            name = row.get("name") or row.get("url") or "?"
            entry = endpoints.setdefault(name, {"durations": [], "statuses": {}})
            entry["durations"].append(value)
            entry["statuses"][status] = entry["statuses"].get(status, 0) + 1
            bucket["durations"].append(value)
            bucket["requests"] += 1
            if status == "0" or status.startswith("5"):
                bucket["errors_5xx"] += 1
    result = {
        "endpoints": {
            name: {
                "count": len(e["durations"]),
                "p50": _p(e["durations"], 50),
                "p95": _p(e["durations"], 95),
                "p99": _p(e["durations"], 99),
                "statuses": e["statuses"],
            }
            for name, e in sorted(endpoints.items(), key=lambda kv: -len(kv[1]["durations"]))
        },
        "timeline": [
            {
                "minute": datetime.fromtimestamp(minute, UTC).isoformat(timespec="minutes"),
                "req_per_s": round(b["requests"] / 60, 1),
                "p95_ms": _p(b["durations"], 95),
                "errors_5xx": b["errors_5xx"],
                "ws_connects": b["ws_connects"],
                "locations_per_s": round(b["locations"] / 60, 1),
            }
            for minute, b in sorted(minutes.items())
        ],
    }
    (run_dir / "analysis.json").write_text(json.dumps(result, indent=1))
    return result


# --- Runs --------------------------------------------------------------------------------------


def _meta(run_dir: Path) -> dict[str, Any]:
    return json.loads((run_dir / "meta.json").read_text())


def _save_meta(run_dir: Path, meta: dict[str, Any]) -> None:
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=1))


async def _run(run_dir: Path, env: dict[str, str], options: dict[str, Any]) -> None:
    meta = _meta(run_dir)
    client = httpx.AsyncClient(base_url=f"{BASE_URL}/api/v1", timeout=30)
    try:
        meta["clock_offset_s"] = await measure_clock_offset(client)
        env["CLOCK_OFFSET_MS"] = str(int(clock["offset"] * 1000))
        admins = int(options.get("admins", 5))
        tokens = []
        for n in range(1, admins + 1):
            tokens.append(await Admin(client, n).login())
        env["ADMIN_TOKENS"] = json.dumps(tokens)
        state["tasks"] = [asyncio.create_task(sample_node(run_dir))]
        if options.get("campaign_at"):
            state["tasks"].append(
                asyncio.create_task(
                    campaign(run_dir, client, _seconds(options["campaign_at"]), admins)
                )
            )
        meta["started_at"] = _now()
        meta["status"] = "running"
        _save_meta(run_dir, meta)
        with (run_dir / "k6.log").open("wb") as log:
            process = await asyncio.create_subprocess_exec(
                "k6",
                "run",
                "--quiet",
                "--out",
                f"csv={run_dir / 'metrics.csv.gz'}",
                str(SCRIPT),
                env={
                    **os.environ,
                    **env,
                    "PASSWORD": PASSWORD,
                    "BASE_URL": BASE_URL,
                    "SUMMARY_PATH": str(run_dir / "summary.json"),
                },
                stdout=log,
                stderr=asyncio.subprocess.STDOUT,
            )
            state["process"] = process
            code = await process.wait()
        meta["exit_code"] = code
        meta["status"] = "finished" if code in (0, 99) else "failed"  # 99: thresholds crossed
    except Exception as exc:
        meta["status"] = "failed"
        meta["error"] = repr(exc)
    finally:
        for task in state["tasks"]:
            task.cancel()
        await client.aclose()
        meta["finished_at"] = _now()
        meta["node"] = _node_summary(run_dir)
        meta["push"] = {k: v for k, v in push_stats.items() if k != "per_second"}
        try:
            await asyncio.to_thread(analyze_csv, run_dir)
        except Exception as exc:
            meta["analysis_error"] = repr(exc)
        _save_meta(run_dir, meta)
        state["process"] = None
        state["run"] = None


async def start_run(request: Request) -> Response:
    if not _authorized(request):
        return _deny()
    if state["run"]:
        return JSONResponse({"error": "a run is in progress", "run": state["run"]}, 409)
    if not PASSWORD:
        return JSONResponse({"error": "LOADTEST_PASSWORD is not set"}, 500)
    options = await request.json() if await request.body() else {}
    env = {k: str(v) for k, v in (options.get("env") or {}).items() if k in ALLOWED_ENV}
    run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True)
    push_stats.update(requests=0, messages=0, first_at=None, last_at=None, per_second={})
    _save_meta(
        run_dir,
        {
            "id": run_id,
            "status": "starting",
            "created_at": _now(),
            "base_url": BASE_URL,
            "env": env,
            "options": {k: v for k, v in options.items() if k != "env"},
        },
    )
    state["run"] = run_id
    asyncio.get_running_loop().create_task(_run(run_dir, env, options))
    return JSONResponse({"id": run_id}, 201)


def _summary(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "summary.json"
    if not path.exists():
        return None
    metrics = json.loads(path.read_text()).get("metrics", {})
    picked = {}
    for name, metric in metrics.items():
        values = metric.get("values", {})
        keep = {
            k: round(v, 2) if isinstance(v, float) else v
            for k, v in values.items()
            if k in ("count", "rate", "p(95)", "p(99)", "med", "max", "avg", "passes", "fails")
        }
        thresholds = metric.get("thresholds")
        if thresholds:
            keep["thresholds"] = {k: v.get("ok") for k, v in thresholds.items()}
        picked[name] = keep
    return picked


async def list_runs(request: Request) -> Response:
    if not _authorized(request):
        return _deny()
    runs = [_meta(d) for d in sorted(RUNS.glob("*"), reverse=True) if (d / "meta.json").exists()]
    return JSONResponse({"active": state["run"], "runs": runs})


async def get_run(request: Request) -> Response:
    if not _authorized(request):
        return _deny()
    run_dir = RUNS / Path(request.path_params["run_id"]).name
    if not (run_dir / "meta.json").exists():
        return JSONResponse({"error": "not found"}, 404)
    log = run_dir / "k6.log"
    tail = log.read_text(errors="replace")[-4000:] if log.exists() else ""
    node = run_dir / "node.jsonl"
    last_node = node.read_text().strip().splitlines()[-1:] if node.exists() else []
    return JSONResponse(
        {
            **_meta(run_dir),
            "summary": _summary(run_dir),
            "node_now": json.loads(last_node[0]) if last_node else None,
            "node_summary": _node_summary(run_dir),
            "push_now": {k: v for k, v in push_stats.items() if k != "per_second"},
            "log_tail": tail,
            "files": sorted(p.name for p in run_dir.iterdir()),
        }
    )


async def get_file(request: Request) -> Response:
    if not _authorized(request):
        return _deny()
    run_dir = RUNS / Path(request.path_params["run_id"]).name
    path = run_dir / Path(request.path_params["name"]).name
    if not path.is_file():
        return JSONResponse({"error": "not found"}, 404)
    return FileResponse(path)


async def stop_run(request: Request) -> Response:
    if not _authorized(request):
        return _deny()
    process = state["process"]
    if process is None:
        return JSONResponse({"error": "nothing running"}, 409)
    with contextlib.suppress(ProcessLookupError):
        process.send_signal(signal.SIGINT)  # k6 stops gracefully and still writes the summary
    asyncio.get_running_loop().create_task(_force_stop(process))
    return JSONResponse({"stopping": state["run"]})


async def _force_stop(process: asyncio.subprocess.Process) -> None:
    # Iterations blocked on sockets can keep k6 waiting after the first signal; a second one
    # makes it stop at once (the summary is still written).
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(process.wait(), timeout=60)
        return
    with contextlib.suppress(ProcessLookupError):
        process.send_signal(signal.SIGINT)


# --- Fake Expo push ----------------------------------------------------------------------------


async def expo_push(request: Request) -> Response:
    """Same answer shape as https://exp.host/--/api/v2/push/send, after a realistic delay."""
    messages = await request.json()
    messages = messages if isinstance(messages, list) else [messages]
    now = time.time()
    second = str(int(now))
    push_stats["requests"] += 1
    push_stats["messages"] += len(messages)
    push_stats["first_at"] = push_stats["first_at"] or _now()
    push_stats["last_at"] = _now()
    push_stats["per_second"][second] = push_stats["per_second"].get(second, 0) + len(messages)
    if state["run"]:
        with (RUNS / state["run"] / "push.jsonl").open("a") as fh:
            fh.write(json.dumps({"t": round(now, 3), "messages": len(messages)}) + "\n")
    await asyncio.sleep(PUSH_LATENCY_MS / 1000)
    return JSONResponse({"data": [{"status": "ok", "id": str(uuid.uuid4())} for _ in messages]})


async def push_stats_view(request: Request) -> Response:
    if not _authorized(request):
        return _deny()
    return JSONResponse(push_stats)


async def healthz(_: Request) -> Response:
    return JSONResponse({"ok": True, "active": state["run"], "base_url": BASE_URL})


async def home(_: Request) -> Response:
    return HTMLResponse(
        "<!doctype html><meta charset=utf-8><title>Kuulis carga</title>"
        "<body style='font-family:system-ui;max-width:40rem;margin:2rem auto'>"
        "<h1>Kuulis · pruebas de carga</h1><p>API con token: <code>GET /api/runs</code>, "
        "<code>POST /api/runs</code>, <code>GET /api/runs/{id}</code>.</p>"
    )


app = Starlette(
    routes=[
        Route("/", home),
        Route("/healthz", healthz),
        Route("/expo/push/send", expo_push, methods=["POST"]),
        Route("/api/push", push_stats_view),
        Route("/api/runs", list_runs),
        Route("/api/runs", start_run, methods=["POST"]),
        Route("/api/runs/{run_id}", get_run),
        Route("/api/runs/{run_id}/stop", stop_run, methods=["POST"]),
        Route("/api/runs/{run_id}/files/{name}", get_file),
    ]
)
RUNS.mkdir(parents=True, exist_ok=True)
