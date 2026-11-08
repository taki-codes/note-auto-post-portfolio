"""Local note project records. No networking, login, purchases or publishing."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ["article_id", "theme", "url", "published_at", "access_type",
           "monitoring_status", "monitor_until"]
FILES = ["brief.md", "00_progress.md", "01_research.md", "02_article_plan.md",
         "03_free_article.md", "04_paid_article_plan.md", "05_paid_article_draft.md",
         "06_free_to_paid_link.md", "07_promotion_plan.md"]


def now() -> datetime:
    return datetime.now(JST)


def safe_id(value: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", value):
        raise ValueError("ID/slug must use 1-80 ASCII letters, digits, _ or -.")
    return value


def timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Timestamp requires a timezone, e.g. +09:00.")
    return result.astimezone(JST)


def publication(value: str) -> tuple[str, date]:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value, date.fromisoformat(value)
    result = timestamp(value)
    return result.isoformat(), result.date()


class Project:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.ledger = self.root / "published_articles.csv"

    def inside(self, path: Path) -> Path:
        path = path.resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise ValueError("Path must be a file inside this project.")
        return path

    def checkpoint(self, path: Path) -> Path:
        path = self.inside(path)
        if not path.is_file() or path.is_relative_to(self.root / ".history"):
            raise ValueError("Checkpoint requires an existing non-history file.")
        stamp = now().strftime("%Y%m%d-%H%M%S-%f") + "-" + uuid4().hex[:6]
        dest = self.root / ".history" / stamp / path.relative_to(self.root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        return dest

    def read(self) -> list[dict[str, str]]:
        if not self.ledger.exists():
            return []
        with self.ledger.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != COLUMNS:
                raise ValueError("Ledger columns differ from the required schema.")
            rows = list(reader)
        for row in rows:
            safe_id(row["article_id"])
            if row["monitoring_status"] not in {"active", "paused", "completed"}:
                raise ValueError("Invalid monitoring_status in ledger.")
            date.fromisoformat(row["monitor_until"])
            publication(row["published_at"])
        if len({r["article_id"] for r in rows}) != len(rows):
            raise ValueError("Duplicate article_id in ledger.")
        return rows

    def write(self, rows: list[dict[str, str]]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.ledger.exists():
            self.checkpoint(self.ledger)
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        temp = self.root / (".ledger-" + uuid4().hex + ".tmp")
        temp.write_text(output.getvalue(), encoding="utf-8-sig", newline="")
        temp.replace(self.ledger)

    def register(self, article_id: str, theme: str, url: str,
                 published_at: str, access_type: str) -> dict[str, str]:
        safe_id(article_id)
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "note.com" or "/n/" not in parsed.path:
            raise ValueError("Supply the public https://note.com/.../n/... article URL.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Use a canonical article URL without credentials or query parameters.")
        if not theme.strip() or theme.lstrip().startswith(("=", "+", "-", "@")):
            raise ValueError("Supply a plain text theme (no spreadsheet formula prefix).")
        if access_type not in {"free", "paid", "membership", "mixed"}:
            raise ValueError("Invalid access_type.")
        published_at, day = publication(published_at)
        if day > now().date():
            raise ValueError("Register only articles already published, not future plans.")
        rows = self.read()
        if any(r["article_id"] == article_id or r["url"] == url for r in rows):
            raise ValueError("Article ID or URL already registered; nothing changed.")
        row = dict(zip(COLUMNS, [article_id, theme, url, published_at, access_type,
                                 "active", (day + timedelta(days=90)).isoformat()]))
        rows.append(row)
        self.write(rows)
        return row

    def observe(self, article_id: str, source: str, method: str,
                likes: int | None = None, views: int | None = None,
                purchases: int | None = None, notes: str = "",
                observed_at: str | None = None, final: bool = False) -> Path:
        safe_id(article_id)
        rows = self.read()
        row = next((r for r in rows if r["article_id"] == article_id), None)
        if row is None:
            raise ValueError("Unknown article_id.")
        if row["monitoring_status"] == "completed":
            raise ValueError("Monitoring already completed; nothing changed.")
        if not source.strip() or not method.strip():
            raise ValueError("Record the source and collection method.")
        values = {"likes": likes, "views": views, "purchases": purchases}
        if any(v is not None and (not isinstance(v, int) or isinstance(v, bool) or v < 0)
               for v in values.values()):
            raise ValueError("Metrics must be non-negative integers or unavailable.")
        if all(v is None for v in values.values()) and not notes.strip():
            raise ValueError("Explain unavailability when all metrics are missing.")
        observed = timestamp(observed_at) if observed_at else now()
        if observed > now() + timedelta(minutes=5):
            raise ValueError("Do not record future observations.")
        if observed.date() < publication(row["published_at"])[1]:
            raise ValueError("Observation cannot predate publication.")
        expired = observed.date() >= date.fromisoformat(row["monitor_until"])
        if final and not expired:
            raise ValueError("Deadline has not arrived; final completion was not saved.")
        observation = {"article_id": article_id, "url": row["url"],
                       "observed_at": observed.isoformat(), "source": source,
                       "method": method, **values,
                       "unavailable_metrics": [k for k, v in values.items() if v is None],
                       "notes": notes, "is_final": expired,
                       "monitor_until": row["monitor_until"],
                       "completion_meaning": "観測終了であり、需要なしとは判断しない。" if expired else None}
        folder = self.inside(self.root / "monitoring" / article_id)
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / (observed.strftime("%Y%m%d-%H%M%S-%f") + "-" + uuid4().hex[:8] + ".json")
        with dest.open("x", encoding="utf-8") as handle:
            json.dump(observation, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        # Save the final record first. A failed ledger write can be safely resumed.
        if expired:
            row["monitoring_status"] = "completed"
            self.write(rows)
        return dest

    def set_status(self, article_id: str, status: str, reason: str) -> None:
        safe_id(article_id)
        if status not in {"active", "paused"} or not reason.strip():
            raise ValueError("Status must be active/paused with a reason; completion requires observe.")
        rows = self.read()
        row = next((r for r in rows if r["article_id"] == article_id), None)
        if row is None or row["monitoring_status"] == "completed":
            raise ValueError("Unknown or completed article; nothing changed.")
        folder = self.inside(self.root / "monitoring" / article_id)
        folder.mkdir(parents=True, exist_ok=True)
        event = folder / ("status-" + now().strftime("%Y%m%d-%H%M%S-%f") + "-" + uuid4().hex[:6] + ".json")
        event.write_text(json.dumps({"changed_at": now().isoformat(), "from": row["monitoring_status"],
                                     "to": status, "reason": reason}, ensure_ascii=False, indent=2), encoding="utf-8")
        row["monitoring_status"] = status
        self.write(rows)

    def due(self, as_of: date | None = None) -> list[dict[str, str]]:
        today = as_of or now().date()
        result = []
        for row in self.read():
            if row["monitoring_status"] == "completed":
                continue
            deadline = date.fromisoformat(row["monitor_until"])
            if today >= deadline:
                result.append({**row, "action": "final_observation_required"})
                continue
            if row["monitoring_status"] == "paused":
                continue
            dates = []
            for path in (self.root / "monitoring" / row["article_id"]).glob("*.json"):
                record = json.loads(path.read_text(encoding="utf-8"))
                if "observed_at" in record:
                    dates.append(timestamp(record["observed_at"]).date())
            published_day = publication(row["published_at"])[1]
            milestones = [min(published_day + timedelta(days=d), deadline) for d in (7, 14, 30, 60, 90)]
            remaining = [d for d in milestones if not dates or d > max(dates)]
            next_day = min(remaining) if remaining else deadline
            if today >= next_day:
                result.append({**row, "action": "observation_due", "due_at": next_day.isoformat()})
        return result

    def new_theme(self, slug: str, theme: str) -> Path:
        safe_id(slug)
        if not theme.strip():
            raise ValueError("Theme is required.")
        base = self.root / "themes" / (now().date().isoformat() + "_" + slug)
        folder = base
        counter = 2
        while folder.exists():
            folder = base.with_name(base.name + "-" + str(counter))
            counter += 1
        folder = self.inside(folder)
        folder.mkdir(parents=True)
        (folder / "evidence").mkdir()
        for name in FILES:
            template = self.root / "templates" / name
            text = template.read_text(encoding="utf-8")
            text = text.replace("{{theme}}", theme).replace("{{date}}", now().date().isoformat())
            (folder / name).write_text(text, encoding="utf-8")
        return folder


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("due", help="List due checks without accessing note or changing records.")
    checkpoint = commands.add_parser("checkpoint")
    checkpoint.add_argument("relative_path")
    theme = commands.add_parser("new-theme")
    theme.add_argument("--slug", required=True)
    theme.add_argument("--theme", required=True)
    register = commands.add_parser("register")
    for name in ("id", "theme", "url", "published-at"):
        register.add_argument("--" + name, required=True)
    register.add_argument("--access-type", choices=("free", "paid", "membership", "mixed"), required=True)
    register.add_argument("--confirmed-published", action="store_true", required=True,
                          help="Assert actual publication; this command does not publish.")
    observe = commands.add_parser("observe")
    for name in ("id", "source", "method"):
        observe.add_argument("--" + name, required=True)
    for name in ("likes", "views", "purchases"):
        observe.add_argument("--" + name, type=int)
    observe.add_argument("--notes", default="")
    observe.add_argument("--observed-at")
    observe.add_argument("--final", action="store_true")
    status = commands.add_parser("set-status")
    status.add_argument("--id", required=True)
    status.add_argument("--status", choices=("active", "paused"), required=True)
    status.add_argument("--reason", required=True)
    args = parser.parse_args()
    project = Project(ROOT)
    try:
        if args.command == "due":
            print(json.dumps(project.due(), ensure_ascii=False, indent=2))
        elif args.command == "checkpoint":
            print(project.checkpoint(ROOT / args.relative_path))
        elif args.command == "new-theme":
            print(project.new_theme(args.slug, args.theme))
        elif args.command == "register":
            print(json.dumps(project.register(args.id, args.theme, args.url, args.published_at, args.access_type), ensure_ascii=False, indent=2))
        elif args.command == "observe":
            print(project.observe(args.id, args.source, args.method, args.likes, args.views,
                                  args.purchases, args.notes, args.observed_at, args.final))
        elif args.command == "set-status":
            project.set_status(args.id, args.status, args.reason)
            print("Saved status change.")
    except (ValueError, OSError) as error:
        parser.exit(2, f"Error: {error}\n")


if __name__ == "__main__":
    main()
