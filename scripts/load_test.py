"""Load test of the containerised forecast service; writes results/load_test.json.

Starts the image built by ``docker build -t be-power-forecast .`` twice:

* ``normal``: the LEAR forecasts and the prices (data/cache/prices_BE.parquet);
* ``degraded``: the LEAR forecasts cannot be read, so every answer is the naive fallback.

For each, 1, 10 and 50 concurrent clients send ``POST /forecast`` requests for random
delivery days of the served range (fixed seed) during 30 s each. Client and server run on
the same machine; latencies include the local network round trip.
Usage: python scripts/load_test.py [--duration 30] [--clients 1 10 50]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import subprocess
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

from be_power_forecast.config import SEED

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "be-power-forecast"
SCENARIOS = {
    "normal": {},
    "degraded": {"BE_FORECAST_DIR": "/nonexistent"},  # forecasts unreadable: naive fallback
}


def start(name: str, port: int, env: dict) -> None:
    cmd = ["docker", "run", "-d", "--rm", "--name", name, "-p", f"{port}:8000"]
    cmd += ["-v", f"{ROOT / 'data' / 'cache'}:/data:ro"]
    for k, v in env.items():
        cmd += ["-e", f"{k}={v}"]
    subprocess.run([*cmd, IMAGE], check=True, capture_output=True)


def wait_ready(url: str, timeout: float = 60) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        try:
            return httpx.get(f"{url}/health", timeout=2).json()
        except httpx.HTTPError:
            time.sleep(0.5)
    raise RuntimeError(f"{url} did not start")


async def client(http, url, days, rng, stop_at, records) -> None:
    while time.perf_counter() < stop_at:
        day = days[rng.integers(len(days))]
        t0 = time.perf_counter()
        r = await http.post(f"{url}/forecast", json={"delivery_day": day})
        ms = 1000 * (time.perf_counter() - t0)
        model = r.json().get("model") if r.status_code == 200 else None
        records.append((ms, r.status_code, model))


async def run_level(url: str, days: list[str], n_clients: int, duration: float) -> dict:
    records: list = []
    limits = httpx.Limits(max_connections=n_clients)
    async with httpx.AsyncClient(limits=limits, timeout=30) as http:
        await http.get(f"{url}/health")  # warm-up
        start_t = time.perf_counter()
        stop_at = start_t + duration
        rngs = np.random.default_rng(SEED).spawn(n_clients)
        await asyncio.gather(*(client(http, url, days, rng, stop_at, records) for rng in rngs))
        elapsed = time.perf_counter() - start_t
    ms = np.array([r[0] for r in records])
    ok = [r for r in records if r[1] == 200]
    return {
        "clients": n_clients,
        "requests": len(records),
        "throughput_rps": len(records) / elapsed,
        "p50_ms": float(np.percentile(ms, 50)),
        "p95_ms": float(np.percentile(ms, 95)),
        "p99_ms": float(np.percentile(ms, 99)),
        "errors": len(records) - len(ok),
        "fallback_share": sum(r[2] == "naive_fallback" for r in ok) / max(len(ok), 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--clients", type=int, nargs="+", default=[1, 10, 50])
    args = parser.parse_args()

    image = subprocess.run(
        ["docker", "image", "inspect", IMAGE, "--format", "{{.Id}} {{.Size}}"],
        check=True, capture_output=True, text=True,
    ).stdout.split()  # fmt: skip
    docker = subprocess.run(
        ["docker", "info", "--format", "{{.ServerVersion}} {{.NCPU}} {{.MemTotal}}"],
        check=True, capture_output=True, text=True,
    ).stdout.split()  # fmt: skip
    out: dict = {
        "setup": {
            "image_id": image[0][:19],
            "image_size_MB": int(image[1]) / 1e6,
            "docker_version": docker[0],
            "docker_cpus": int(docker[1]),
            "docker_memory_GB": int(docker[2]) / 1e9,
            "host": f"{platform.system()} {platform.machine()}",
            "duration_s": args.duration,
            "uvicorn_workers": 1,
        },
        "scenarios": {},
    }
    for i, (name, env) in enumerate(SCENARIOS.items()):
        port, container = 8100 + i, f"bpf-load-{name}"
        url = f"http://127.0.0.1:{port}"
        start(container, port, env)
        try:
            health = wait_ready(url)
            days = [str(d.date()) for d in pd.date_range(health["first_day"], health["last_day"])]
            levels = [asyncio.run(run_level(url, days, n, args.duration)) for n in args.clients]
        finally:
            subprocess.run(["docker", "stop", container], capture_output=True)
        out["scenarios"][name] = {"health": health, "levels": levels}
        for lv in levels:
            print(name, json.dumps(lv), flush=True)
    path = ROOT / "results" / "load_test.json"
    path.write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
