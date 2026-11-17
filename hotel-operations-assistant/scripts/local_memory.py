"""User-confirmed local preference/experience store. No network or model training."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import sys
import uuid

class MemoryStore:
    def __init__(self, directory=None):
        self.directory = Path(directory or os.environ.get("HOTEL_ASSISTANT_MEMORY_DIR") or Path.home() / "HotelOperationsMemory" / "hotel-operations-assistant").absolute()
        self.path = self.directory / "store.json"

    def check_paths(self):
        for path in [self.directory, *self.directory.parents, self.path, self.directory / ".write.lock"]:
            if path.exists() or path.is_symlink():
                info = path.lstat()
                if path.is_symlink() or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024):
                    raise ValueError("Refusing symlink/reparse-point memory path")

    def read(self):
        self.check_paths()
        if not self.path.exists():
            return {"version": 1, "records": []}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("records"), list):
            raise ValueError("Unknown or invalid store format; not resetting")
        ids = []
        for row in data["records"]:
            self.validate(row)
            if not isinstance(row.get("id"), str) or not row["id"]:
                raise ValueError("Invalid record ID")
            ids.append(row["id"])
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate record IDs")
        return data

    @staticmethod
    def validate(record):
        if not isinstance(record, dict) or record.get("kind") not in ("preference", "experience", "lesson"):
            raise ValueError("Invalid record kind")
        fields = ["title", "scope", "confirmation_quote"]
        if record["kind"] == "preference":
            fields += ["key", "value"]
        elif record["kind"] == "lesson":
            fields += ["problem", "outcome", "reason", "alternative", "limitations", "feedback_quote", "review_after"]
            if record.get("outcome") not in ("failed", "rejected", "expired"):
                raise ValueError("Lesson outcome must be failed/rejected/expired")
            from datetime import date
            date.fromisoformat(record.get("review_after", ""))
        else:
            fields += ["problem", "result", "verification", "limitations", "success_quote"]
            if not isinstance(record.get("steps"), list) or not record["steps"] or not all(isinstance(x, str) and x.strip() for x in record["steps"]):
                raise ValueError("Experience requires nonempty steps")
        if not all(isinstance(record.get(k), str) and record[k].strip() for k in fields):
            raise ValueError("Missing required content/confirmation")
        tags = record.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(x, str) for x in tags):
            raise ValueError("Invalid tags")
        allowed = {"kind", "title", "scope", "confirmation_quote", "key", "value", "problem", "steps", "result", "verification", "limitations", "success_quote", "tags", "id", "created_at", "updated_at", "outcome", "reason", "alternative", "feedback_quote", "review_after"}
        if set(record) - allowed:
            raise ValueError("Unknown record fields")

    @contextmanager
    def lock(self):
        self.check_paths()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.check_paths()
        lock = self.directory / ".write.lock"
        # Exclusive create prevents concurrent read-modify-write updates.
        with lock.open("x", encoding="utf-8") as stream:
            stream.write(str(os.getpid()))
        try:
            yield
        finally:
            lock.unlink()

    def write(self, data):
        self.check_paths()
        temporary = self.directory / (".store-" + uuid.uuid4().hex + ".tmp")
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def init(self):
        with self.lock():
            data = self.read()
            if not self.path.exists():
                self.write(data)
        return {"store": str(self.path), "records": len(data["records"])}

    def put(self, record, confirmed=False, replace_id=None):
        if not confirmed:
            raise ValueError("Explicit save confirmation required")
        self.validate(record)
        with self.lock():
            data = self.read()
            rows = data["records"]
            existing = next((x for x in rows if x["id"] == replace_id), None)
            if replace_id and not existing:
                raise ValueError("Replacement ID not found")
            if existing and existing["kind"] != record["kind"]:
                raise ValueError("Replacement kind mismatch")
            if record["kind"] == "preference" and any(x["kind"] == "preference" and x["scope"] == record["scope"] and x["key"] == record["key"] and x["id"] != replace_id for x in rows):
                raise ValueError("Preference exists; confirm replacement and specify ID")
            now = datetime.now(timezone.utc).isoformat()
            saved = dict(record)
            saved.update(id=replace_id or uuid.uuid4().hex, created_at=existing["created_at"] if existing else now, updated_at=now)
            if existing:
                rows[rows.index(existing)] = saved
            else:
                rows.append(saved)
            self.write(data)
        # Verify persistence using a fresh read.
        return self.get(saved["id"])

    def get(self, record_id):
        for row in self.read()["records"]:
            if row["id"] == record_id:
                return row
        raise ValueError("Record not found")

    def summaries(self, kind=None, query=None):
        result = []
        for row in self.read()["records"]:
            if kind and row["kind"] != kind:
                continue
            text = " ".join([row["title"], row["scope"], row.get("problem", ""), row.get("reason", ""), row.get("alternative", ""), *row.get("tags", [])]).casefold()
            if query and query.casefold() not in text:
                continue
            summary = {k: row[k] for k in ("id", "kind", "title", "scope", "updated_at")}
            if row["kind"] == "preference":
                summary.update(key=row["key"], value=row["value"])
            else:
                summary["tags"] = row.get("tags", [])
                if row["kind"] == "lesson":
                    summary.update(outcome=row["outcome"], review_after=row["review_after"])
            result.append(summary)
        return result

    def delete(self, record_id, confirmed=False):
        if not confirmed:
            raise ValueError("Explicit delete confirmation required")
        with self.lock():
            data = self.read()
            rows = data["records"]
            selected = [x for x in rows if x["id"] == record_id]
            if not selected:
                raise ValueError("Record not found")
            data["records"] = [x for x in rows if x["id"] != record_id]
            self.write(data)
        if any(x["id"] == record_id for x in self.read()["records"]):
            raise ValueError("Delete verification failed")
        return {"deleted_id": record_id}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", help="Directory for this user's hotel memory")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    for name in ("list", "search"):
        sub = commands.add_parser(name)
        sub.add_argument("--kind", choices=["preference", "experience", "lesson"])
        if name == "search":
            sub.add_argument("--query", required=True)
    commands.add_parser("get").add_argument("id")
    sub = commands.add_parser("put")
    sub.add_argument("--record", required=True)
    sub.add_argument("--confirmed", action="store_true")
    sub.add_argument("--replace-id")
    sub = commands.add_parser("delete")
    sub.add_argument("id")
    sub.add_argument("--confirmed", action="store_true")
    args = parser.parse_args()
    store = MemoryStore(args.store)
    try:
        if args.command == "init":
            result = store.init()
        elif args.command in ("list", "search"):
            result = {"store": str(store.path), "records": store.summaries(args.kind, getattr(args, "query", None))}
        elif args.command == "get":
            result = store.get(args.id)
        elif args.command == "put":
            record = json.loads(Path(args.record).read_text(encoding="utf-8-sig"))
            result = store.put(record, args.confirmed, args.replace_id)
        else:
            result = store.delete(args.id, args.confirmed)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True))
        return 2
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
