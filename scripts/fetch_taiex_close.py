#!/usr/bin/env python3
"""Fetch TWSE TAIEX daily close prices and export to CSV."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://www.twse.com.tw/indicesReport/MI_5MINS"
DEFAULT_START = dt.date(2000, 1, 1)
DEFAULT_END = dt.date(2025, 12, 31)
USER_AGENT = "Mozilla/5.0 (compatible; TAIEXCloseFetcher/1.0)"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch Taiwan Stock Exchange (TAIEX) daily close prices "
            "and export to CSV."
        )
    )
    parser.add_argument(
        "--start",
        type=str,
        default=DEFAULT_START.isoformat(),
        help="Start date (YYYY-MM-DD). Default: 2000-01-01",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=DEFAULT_END.isoformat(),
        help="End date (YYYY-MM-DD). Default: 2025-12-31",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="taiex_close.csv",
        help="Output CSV path. Default: taiex_close.csv",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.3,
        help="Sleep seconds between requests. Default: 0.3",
    )
    return parser.parse_args()


def daterange(start: dt.date, end: dt.date) -> list[dt.date]:
    if end < start:
        raise ValueError("End date must be >= start date")
    days = (end - start).days
    return [start + dt.timedelta(days=offset) for offset in range(days + 1)]


def fetch_day_close(day: dt.date) -> float | None:
    params = {
        "response": "json",
        "date": day.strftime("%Y%m%d"),
    }
    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"[warn] {day} fetch failed: {exc}", file=sys.stderr)
        return None

    if payload.get("stat") != "OK":
        return None

    rows = payload.get("data") or []
    if not rows:
        return None

    fields = payload.get("fields") or []
    target_index = None
    for idx, field in enumerate(fields):
        if "發行量加權股價指數" in field:
            target_index = idx
            break
    if target_index is None:
        target_index = 1 if len(rows[-1]) > 1 else 0

    raw_value = rows[-1][target_index]
    if raw_value in ("--", "---", ""):
        return None

    return float(str(raw_value).replace(",", ""))


def main() -> int:
    args = parse_args()
    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    dates = daterange(start, end)

    with open(args.output, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["date", "taiex_close"])

        for day in dates:
            close = fetch_day_close(day)
            if close is not None:
                writer.writerow([day.isoformat(), close])
            time.sleep(args.sleep)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
