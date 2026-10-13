"""A tiny stand-in for a helpdesk inbox.

Replays data/tickets.json into a SQLite "helpdesk" in arrival order, the
way tickets would land in Zendesk, Intercom or a shared support inbox. The
gap finder then reads open tickets from that queue.

Set SUPABASE_URL and SUPABASE_SECRET_KEY (see .env.example) to use a
Supabase table instead of the local SQLite file. The table is created by
supabase/migrations/.

    python inbox.py replay              # one simulated week in about 20 seconds
    python inbox.py replay --speed 0    # load everything at once
    python inbox.py queue               # show what's waiting
"""

import argparse
import json
import os
import sqlite3
import time
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
DB = HERE / "data" / "helpdesk.db"
CHANNEL = {"email": "Email   ", "web_form": "Web form", "in_app": "In-app  "}
FIELDS = ["id", "received_at", "channel", "from_name", "from_email", "plan", "subject", "body", "status"]


def load_env():
    """Read .env.local or .env into os.environ, without overriding what's already set."""
    for name in (".env.local", ".env"):
        f = HERE / name
        if f.exists():
            for line in f.read_text().splitlines():
                k, sep, v = line.partition("=")
                if sep and not k.strip().startswith("#") and v.strip():
                    os.environ.setdefault(k.strip(), v.strip().strip('"'))


load_env()
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY", "")


def supabase(method: str, path: str, body=None, prefer: str = "") -> list:
    """Call the Supabase REST API for the tickets table."""
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": prefer},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read()
    return json.loads(text) if text else []


class SupabaseInbox:
    def clear(self):
        supabase("DELETE", "tickets?id=not.is.null")

    def add(self, t: dict):
        supabase("POST", "tickets", {k: t[k] for k in FIELDS}, prefer="resolution=merge-duplicates")

    def open_rows(self) -> list[dict]:
        return supabase("GET", "tickets?status=eq.new&order=received_at&select=*")


class SqliteInbox:
    def __init__(self):
        self.con = connect()

    def clear(self):
        self.con.execute("delete from tickets")

    def add(self, t: dict):
        self.con.execute("insert into tickets values (?,?,?,?,?,?,?,?,?)", tuple(t[k] for k in FIELDS))
        self.con.commit()

    def open_rows(self) -> list[dict]:
        self.con.row_factory = sqlite3.Row
        return [dict(r) for r in self.con.execute("select * from tickets where status='new' order by received_at")]


def inbox():
    return SupabaseInbox() if SUPABASE_URL and SUPABASE_KEY else SqliteInbox()


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.execute(
        """create table if not exists tickets (
            id text primary key, received_at text, channel text, from_name text,
            from_email text, plan text, subject text, body text, status text)"""
    )
    return con


def replay(speed: float):
    tickets = json.loads((HERE / "data" / "tickets.json").read_text())
    box = inbox()
    print(f"Inbox: {'Supabase' if isinstance(box, SupabaseInbox) else DB.name}\n")
    box.clear()
    prev = None
    for t in tickets:
        ts = datetime.fromisoformat(t["received_at"].rstrip("Z"))
        if speed and prev:
            # speed = simulated seconds per real second
            time.sleep(min((ts - prev).total_seconds() / speed, 1.5))
        prev = ts
        box.add(t)
        print(f"{ts:%a %H:%M}  {CHANNEL.get(t['channel'], t['channel'])}  {t['id']}  {t['subject'][:60]}")
    print(f"\n{len(tickets)} tickets in the queue")


def open_tickets() -> list[dict]:
    """Used by find_gaps.py. Falls back to the JSON file if the inbox is empty."""
    if SUPABASE_URL or DB.exists():
        rows = inbox().open_rows()
        if rows:
            return rows
    return json.loads((HERE / "data" / "tickets.json").read_text())


def show_queue():
    rows = open_tickets()
    by_channel = {}
    for r in rows:
        by_channel[r["channel"]] = by_channel.get(r["channel"], 0) + 1
    print(f"{len(rows)} open tickets  " + "  ".join(f"{k}: {v}" for k, v in by_channel.items()))
    for r in rows[-10:]:
        print(f"  {r['id']}  {r['received_at']}  {r['subject'][:70]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("replay")
    rp.add_argument("--speed", type=float, default=30000, help="simulated seconds per real second (0 = instant)")
    sub.add_parser("queue")
    args = ap.parse_args()
    replay(args.speed) if args.cmd == "replay" else show_queue()
