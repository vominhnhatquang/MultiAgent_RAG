#!/usr/bin/env python3
"""
check_ram.py — Per-process RAM monitoring for RAG Chatbot containers.
Usage: python3 infra/monitoring/check_ram.py [--json] [--interval N]
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# Memory budgets in MB (from docker-compose.yml)
MEMORY_BUDGETS = {
    "rag_backend":      700,
    "rag_frontend":     200,
    "rag_postgres":     800,
    "rag_qdrant":       800,
    "rag_redis":        300,
    "rag_ollama":      6100,
    "rag_celery":       200,
    "rag_celery_beat":  100,
}

TOTAL_BUDGET_MB = 9200
WARN_THRESHOLD_MB = 9000   # > 9GB → warning
CRIT_THRESHOLD_MB = 9500   # > 9.5GB → webhook alert + OOM risk

# ANSI colors
GREEN  = "\033[0;32m"
YELLOW = "\033[1;33m"
RED    = "\033[0;31m"
CYAN   = "\033[0;36m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


@dataclass
class ContainerStats:
    name: str
    mem_usage_mb: float
    mem_limit_mb: float
    mem_pct: float
    status: str


def get_container_stats() -> list[ContainerStats]:
    """Pull live stats from docker stats command."""
    try:
        result = subprocess.run(
            [
                "docker", "stats", "--no-stream",
                "--format",
                "{{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except FileNotFoundError:
        print(f"{RED}ERROR: docker not found in PATH{RESET}", file=sys.stderr)
        return []
    except subprocess.TimeoutExpired:
        print(f"{RED}ERROR: docker stats timed out{RESET}", file=sys.stderr)
        return []

    stats = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue

        name = parts[0].strip()
        mem_str = parts[1].strip()    # e.g. "123MiB / 300MiB"
        pct_str = parts[2].strip()    # e.g. "41.00%"

        try:
            usage, limit = mem_str.split(" / ")
            mem_usage_mb = parse_mem(usage)
            mem_limit_mb = parse_mem(limit)
            mem_pct = float(pct_str.rstrip("%"))
        except (ValueError, AttributeError):
            continue

        budget = MEMORY_BUDGETS.get(name, mem_limit_mb)
        if mem_usage_mb > budget * 0.9:
            status = "CRITICAL"
        elif mem_usage_mb > budget * 0.75:
            status = "WARNING"
        else:
            status = "OK"

        stats.append(ContainerStats(
            name=name,
            mem_usage_mb=mem_usage_mb,
            mem_limit_mb=mem_limit_mb,
            mem_pct=mem_pct,
            status=status,
        ))

    return stats


def parse_mem(mem_str: str) -> float:
    """Parse memory string like '123MiB', '1.2GiB', '500MB' to MB."""
    mem_str = mem_str.strip()
    if mem_str.endswith("GiB") or mem_str.endswith("GB"):
        return float(mem_str.rstrip("GiBgb")) * 1024
    elif mem_str.endswith("MiB") or mem_str.endswith("MB"):
        return float(mem_str.rstrip("MiBmb"))
    elif mem_str.endswith("KiB") or mem_str.endswith("KB"):
        return float(mem_str.rstrip("KiBkb")) / 1024
    elif mem_str.endswith("B"):
        return float(mem_str.rstrip("Bb")) / (1024 * 1024)
    return 0.0


def color_for_status(status: str) -> str:
    return {
        "OK": GREEN,
        "WARNING": YELLOW,
        "CRITICAL": RED,
    }.get(status, RESET)


def send_alert(message: str) -> None:
    """Send alert to Discord/Slack webhook if ALERT_WEBHOOK_URL is set."""
    webhook_url = os.environ.get("ALERT_WEBHOOK_URL", "")
    print(f"\n  {RED}🚨 ALERT: {message}{RESET}")
    if not webhook_url:
        return
    try:
        import urllib.request
        payload = json.dumps({"content": message}).encode()
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as exc:
        print(f"  {YELLOW}Webhook delivery failed: {exc}{RESET}", file=sys.stderr)


def print_table(stats: list[ContainerStats]) -> int:
    """Print a formatted table. Returns exit code (0=ok, 1=warning, 2=critical)."""
    print(f"\n{BOLD}{CYAN}RAG Chatbot — RAM Monitor  [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]{RESET}")
    print("─" * 72)
    print(f"{'Container':<20} {'Used (MB)':>10} {'Budget (MB)':>12} {'%Used':>7}  {'Status':<10}")
    print("─" * 72)

    total_used = 0.0
    exit_code = 0

    for s in stats:
        budget = MEMORY_BUDGETS.get(s.name, s.mem_limit_mb)
        pct_of_budget = (s.mem_usage_mb / budget * 100) if budget > 0 else 0
        c = color_for_status(s.status)
        print(
            f"{c}{s.name:<20} {s.mem_usage_mb:>10.1f} {budget:>12.0f} {pct_of_budget:>6.1f}%  {s.status}{RESET}"
        )
        total_used += s.mem_usage_mb
        if s.status == "CRITICAL":
            exit_code = max(exit_code, 2)
        elif s.status == "WARNING":
            exit_code = max(exit_code, 1)

    print("─" * 72)
    total_color = RED if total_used > CRIT_THRESHOLD_MB else YELLOW if total_used > WARN_THRESHOLD_MB else GREEN
    print(f"{total_color}{'TOTAL':<20} {total_used:>10.1f} {TOTAL_BUDGET_MB:>12.0f} {total_used/TOTAL_BUDGET_MB*100:>6.1f}%{RESET}")
    print()

    if total_used > CRIT_THRESHOLD_MB:
        send_alert(f"⚠️ RAM CRITICAL: {total_used:.0f}MB / {CRIT_THRESHOLD_MB}MB — OOM risk!")
        exit_code = 2
    elif total_used > WARN_THRESHOLD_MB:
        print(f"{YELLOW}⚠ WARNING: Total RAM {total_used:.0f}MB > {WARN_THRESHOLD_MB}MB — approaching limit.{RESET}")
        exit_code = max(exit_code, 1)

    return exit_code


def print_json(stats: list[ContainerStats]) -> int:
    total_used = sum(s.mem_usage_mb for s in stats)
    output = {
        "timestamp": datetime.now().isoformat(),
        "total_used_mb": round(total_used, 1),
        "total_budget_mb": TOTAL_BUDGET_MB,
        "status": "CRITICAL" if total_used > CRIT_THRESHOLD_MB else "WARNING" if total_used > WARN_THRESHOLD_MB else "OK",
        "containers": [
            {
                "name": s.name,
                "used_mb": round(s.mem_usage_mb, 1),
                "budget_mb": MEMORY_BUDGETS.get(s.name, s.mem_limit_mb),
                "pct": round(s.mem_pct, 1),
                "status": s.status,
            }
            for s in stats
        ],
    }
    print(json.dumps(output, indent=2))
    return 0 if output["status"] == "OK" else 1


def main():
    parser = argparse.ArgumentParser(description="RAG Chatbot RAM Monitor")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--interval", type=int, default=0,
                        help="Refresh interval in seconds (0 = run once)")
    args = parser.parse_args()

    if args.interval > 0:
        import time
        try:
            while True:
                stats = get_container_stats()
                if args.json:
                    print_json(stats)
                else:
                    print("\033[2J\033[H", end="")  # clear screen
                    print_table(stats)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nMonitor stopped.")
        return 0
    else:
        stats = get_container_stats()
        if not stats:
            print("No running containers found. Is Docker running?", file=sys.stderr)
            return 1
        if args.json:
            return print_json(stats)
        return print_table(stats)


if __name__ == "__main__":
    sys.exit(main())
