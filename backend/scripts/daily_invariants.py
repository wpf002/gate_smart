#!/usr/bin/env python3
"""
daily_invariants.py — Assert production is doing the right thing, not just that
it is up.

The regressions that cost the most never crashed. Production ran the losing pick
model for three days after an env var was reset outside the repo; an analysis
cache was warmed under a key nothing read for weeks; 517k junk rows entered the
form archive. Nothing raised, no health check went red, and each was found by
luck or by audit.

Runs after the nightly slate has settled and emails only when something is
actually wrong — an alert that fires on healthy days gets filtered, and then it
is not an alert.

Usage:
    cd backend
    python scripts/daily_invariants.py
    python scripts/daily_invariants.py --dry-run   # print, never email
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


async def main(dry_run: bool) -> int:
    from app.core import database as _db
    from app.services.invariants import CHECKS, run_invariants

    await _db.init_db()
    violations = await run_invariants()

    print(f"[daily_invariants] {len(CHECKS)} checks, {len(violations)} violation(s)")
    for label, detail in violations:
        print(f"  ✗ {label}: {detail}")
    if not violations:
        for label, _ in CHECKS:
            print(f"  ✓ {label}")
        return 0

    if not dry_run:
        try:
            from app.services.email_service import send_daily_report
            body = "\n".join(
                ["Production invariant violations:", ""]
                + [f"  - {label}: {detail}" for label, detail in violations]
                + ["", "These check that the system is doing the right thing, not",
                   "merely that it is up. Each corresponds to a regression that",
                   "previously reached production unnoticed."]
            )
            await send_daily_report(
                subject=f"[GateSmart] {len(violations)} invariant violation(s)",
                html_body="<pre>" + body.replace("<", "&lt;") + "</pre>",
                text_body=body,
            )
            print("  alert sent")
        except Exception as e:
            # Never let a mail failure hide the finding — the exit code still
            # carries it, and the log above already printed every violation.
            print(f"  !! alert send failed: {type(e).__name__}: {e}")
    return 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Assert production data invariants")
    ap.add_argument("--dry-run", action="store_true", help="print, never email")
    sys.exit(asyncio.run(main(ap.parse_args().dry_run)))
