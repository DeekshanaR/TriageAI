"""Batch 'master script': processes a CSV of incoming tickets end-to-end.

For every row it creates a ticket (guard, AI classification, policy, correlation).
Tickets the policy marks AUTO are worked through the lifecycle automatically
(IN_PROGRESS -> RESOLVED -> CLOSED); the others are left for a human.
Designed to run from a Linux terminal or a cron job. Exit code 1 if any row failed.

Usage:  python -m scripts.master_runner --input data/incoming_tickets.csv
"""
import argparse
import csv
import logging
import sys

from app import service

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("master_runner")


def run(input_path: str, auto_close: bool = True) -> dict:
    summary = {"processed": 0, "failed": 0, "auto_closed": 0, "awaiting_approval": 0, "manual_review": 0}
    with open(input_path, newline="", encoding="utf-8") as f:
        for line_no, row in enumerate(csv.DictReader(f), start=2):
            try:
                t = service.create_ticket(row["title"], row["description"])
                log.info("Ticket #%s | %s | %s | policy=%s | status=%s | team=%s", t["id"], t["category"],
                         t["priority"], t["autonomy"], t["status"], t["assignee"])
                summary["processed"] += 1
                if t["autonomy"] == "AUTO" and t["status"] == "ASSIGNED":
                    if auto_close:
                        for status in ("IN_PROGRESS", "RESOLVED", "CLOSED"):
                            service.transition(t["id"], status, "Automated by master_runner")
                        summary["auto_closed"] += 1
                elif t["autonomy"] == "APPROVAL":
                    summary["awaiting_approval"] += 1
                else:
                    summary["manual_review"] += 1
            except Exception as exc:
                summary["failed"] += 1
                log.error("Row %s failed: %s", line_no, exc)
    log.info("SUMMARY %s", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="CSV with columns: title,description")
    parser.add_argument("--no-close", action="store_true", help="leave AUTO tickets assigned")
    args = parser.parse_args()
    sys.exit(1 if run(args.input, auto_close=not args.no_close)["failed"] else 0)
