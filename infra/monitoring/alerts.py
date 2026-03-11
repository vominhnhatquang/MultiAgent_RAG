#!/usr/bin/env python3
"""
alerts.py — Webhook alerts when system RAM exceeds 9GB.
Usage:
    python3 infra/monitoring/alerts.py --webhook <URL> [--interval 60]
    ALERT_WEBHOOK_URL=https://... python3 infra/monitoring/alerts.py

Supports: Slack, Discord, generic webhooks.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from typing import Optional

# Thresholds
WARN_THRESHOLD_MB  = 8500   # 8.5GB — warning
CRIT_THRESHOLD_MB  = 9216   # 9GB   — critical, send alert

# Alert cooldown: don't spam if already alerted
ALERT_COOLDOWN_SEC = 300    # 5 minutes

_last_alert_time: Optional[float] = None
_last_alert_level: Optional[str]  = None


def get_total_ram_mb() -> float:
    """Get total used RAM across all rag containers via docker stats."""
    try:
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.Name}}\t{{.MemUsage}}"],
            capture_output=True, text=True, timeout=15
        )
        total = 0.0
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            name, mem_str = parts[0].strip(), parts[1].strip()
            if not name.startswith("rag_"):
                continue
            usage = mem_str.split(" / ")[0] if " / " in mem_str else mem_str
            total += parse_mem(usage)
        return total
    except Exception as e:
        print(f"[alerts] ERROR reading docker stats: {e}", file=sys.stderr)
        return 0.0


def parse_mem(mem_str: str) -> float:
    mem_str = mem_str.strip()
    if mem_str.endswith("GiB") or mem_str.endswith("GB"):
        return float(mem_str.rstrip("GiBgb")) * 1024
    elif mem_str.endswith("MiB") or mem_str.endswith("MB"):
        return float(mem_str.rstrip("MiBmb"))
    elif mem_str.endswith("KiB") or mem_str.endswith("KB"):
        return float(mem_str.rstrip("KiBkb")) / 1024
    return 0.0


def build_payload(level: str, used_mb: float, webhook_url: str) -> dict:
    emoji = "🔴" if level == "CRITICAL" else "🟡"
    color = 0xFF0000 if level == "CRITICAL" else 0xFFA500
    used_gb = used_mb / 1024

    # Auto-detect Slack vs Discord vs generic
    if "hooks.slack.com" in webhook_url:
        return {
            "text": f"{emoji} *RAG Chatbot — RAM {level}*",
            "attachments": [{
                "color": "#ff0000" if level == "CRITICAL" else "#ffa500",
                "fields": [
                    {"title": "RAM Used", "value": f"{used_gb:.2f} GB ({used_mb:.0f} MB)", "short": True},
                    {"title": "Threshold", "value": f"{CRIT_THRESHOLD_MB/1024:.1f} GB", "short": True},
                    {"title": "Timestamp", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "short": False},
                    {"title": "Action", "value": "Run `make health` to inspect containers.", "short": False},
                ],
            }],
        }
    elif "discord.com" in webhook_url:
        return {
            "embeds": [{
                "title": f"{emoji} RAG Chatbot — RAM {level}",
                "color": color,
                "fields": [
                    {"name": "RAM Used", "value": f"{used_gb:.2f} GB ({used_mb:.0f} MB)", "inline": True},
                    {"name": "Threshold", "value": f"{CRIT_THRESHOLD_MB/1024:.1f} GB", "inline": True},
                    {"name": "Timestamp", "value": datetime.now().isoformat(), "inline": False},
                ],
                "footer": {"text": "Run `make health` to inspect"},
            }]
        }
    else:
        # Generic JSON webhook
        return {
            "level": level,
            "service": "rag-chatbot",
            "message": f"RAM usage is {level}: {used_gb:.2f} GB ({used_mb:.0f} MB)",
            "used_mb": round(used_mb, 1),
            "threshold_mb": CRIT_THRESHOLD_MB,
            "timestamp": datetime.now().isoformat(),
        }


def send_webhook(webhook_url: str, payload: dict) -> bool:
    """Send JSON payload to webhook URL. Returns True on success."""
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status < 300
    except Exception as e:
        print(f"[alerts] Webhook send failed: {e}", file=sys.stderr)
        return False


def should_alert(level: str) -> bool:
    global _last_alert_time, _last_alert_level
    now = time.time()
    if _last_alert_time is None:
        return True
    # Alert again if level escalated or cooldown passed
    if level == "CRITICAL" and _last_alert_level == "WARNING":
        return True
    if now - _last_alert_time > ALERT_COOLDOWN_SEC:
        return True
    return False


def check_and_alert(webhook_url: str, verbose: bool = False) -> str:
    global _last_alert_time, _last_alert_level

    used_mb = get_total_ram_mb()

    if used_mb >= CRIT_THRESHOLD_MB:
        level = "CRITICAL"
    elif used_mb >= WARN_THRESHOLD_MB:
        level = "WARNING"
    else:
        level = "OK"

    ts = datetime.now().strftime("%H:%M:%S")
    if verbose or level != "OK":
        print(f"[{ts}] RAM: {used_mb:.0f} MB — {level}")

    if level != "OK" and should_alert(level):
        payload = build_payload(level, used_mb, webhook_url)
        success = send_webhook(webhook_url, payload)
        if success:
            print(f"[{ts}] Alert sent ({level}): {used_mb:.0f} MB")
            _last_alert_time = time.time()
            _last_alert_level = level
        else:
            print(f"[{ts}] Failed to send alert!", file=sys.stderr)

    return level


def main():
    parser = argparse.ArgumentParser(description="RAG Chatbot RAM Alert Monitor")
    parser.add_argument(
        "--webhook", "-w",
        default=os.environ.get("ALERT_WEBHOOK_URL", ""),
        help="Webhook URL (Slack/Discord/generic). Or set ALERT_WEBHOOK_URL env.",
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=60,
        help="Check interval in seconds (default: 60). Use 0 for one-shot.",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if not args.webhook:
        print("ERROR: --webhook or ALERT_WEBHOOK_URL is required.", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    print(f"[alerts] Starting RAM monitor (interval={args.interval}s)")
    print(f"[alerts] Warn threshold:  {WARN_THRESHOLD_MB} MB ({WARN_THRESHOLD_MB/1024:.1f} GB)")
    print(f"[alerts] Alert threshold: {CRIT_THRESHOLD_MB} MB ({CRIT_THRESHOLD_MB/1024:.1f} GB)")
    print(f"[alerts] Webhook: {args.webhook[:40]}...")

    if args.interval == 0:
        level = check_and_alert(args.webhook, verbose=True)
        sys.exit(0 if level == "OK" else 1)

    try:
        while True:
            check_and_alert(args.webhook, verbose=args.verbose)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[alerts] Monitor stopped.")


if __name__ == "__main__":
    main()
