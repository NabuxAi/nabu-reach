"""Local-only, consent-ledger-backed campaign drafting. No live sending."""
from __future__ import annotations

import csv
import io
from contextlib import contextmanager
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

MAX_CSV_BYTES = 512 * 1024
MAX_CSV_ROWS = 1000
MAX_DRAFT_RECIPIENTS = 50
SUPPORTED_PROVIDERS = {"mock", "meta_cloud", "gowa", "evolution"}
_PHONE = re.compile(r"\+[1-9]\d{7,14}\Z")
_TAGS = re.compile(r"{{\s*([^{}]+?)\s*}}")


class ValidationError(ValueError):
    pass


def normalize_phone(phone: str) -> str:
    if not isinstance(phone, str):
        raise ValidationError("Phone must be an E.164 string")
    phone = phone.strip()
    if not _PHONE.fullmatch(phone):
        raise ValidationError("Phone must be in E.164 format, e.g. +15550100101")
    return phone


def validate_template(text: str) -> str:
    if not isinstance(text, str) or not text.strip() or len(text) > 2048:
        raise ValidationError("Message must be 1–2048 characters")
    tags = _TAGS.findall(text)
    if any(t.strip() not in {"name", "phone"} for t in tags):
        raise ValidationError("Only {{name}} and {{phone}} are supported")
    if "{{" in _TAGS.sub("", text) or "}}" in _TAGS.sub("", text):
        raise ValidationError("Invalid placeholder syntax")
    return text.strip()


def render_template(text: str, person: dict) -> str:
    return _TAGS.sub(lambda m: str(person[m.group(1).strip()]), text)


class Store:
    def __init__(self, db_path: str):
        self.path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS contacts (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  phone TEXT UNIQUE NOT NULL,
                  name TEXT NOT NULL DEFAULT '',
                  consent_status TEXT NOT NULL CHECK(consent_status IN ('opt_in','opt_out')),
                  consent_source TEXT NOT NULL DEFAULT '',
                  consent_at TEXT NOT NULL DEFAULT '',
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS accounts (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  label TEXT NOT NULL UNIQUE,
                  provider TEXT NOT NULL,
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS campaigns (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  account_id INTEGER NOT NULL REFERENCES accounts(id),
                  template TEXT NOT NULL,
                  status TEXT NOT NULL CHECK(status = 'draft'),
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  action TEXT NOT NULL,
                  details TEXT NOT NULL,
                  at TEXT NOT NULL
                );
            """)

    @contextmanager
    def _db(self):
        con = sqlite3.connect(self.path, timeout=8)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=8000")
        con.execute("PRAGMA foreign_keys=ON")
        try:
            with con:
                yield con
        finally:
            con.close()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    def _audit(self, db, action, details):
        db.execute("INSERT INTO audit_events(action,details,at) VALUES(?,?,?)", (action, details, self._now()))

    def summary(self):
        with self._db() as db:
            contact = db.execute("SELECT consent_status, COUNT(*) AS n FROM contacts GROUP BY consent_status").fetchall()
            counts = {r["consent_status"]: r["n"] for r in contact}
            return {
                "accounts": db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0],
                "contacts": sum(counts.values()),
                "opted_in": counts.get("opt_in", 0),
                "opted_out": counts.get("opt_out", 0),
                "drafts": db.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0],
                "sending_enabled": False,
            }

    def accounts(self):
        with self._db() as db:
            return [dict(r) for r in db.execute("SELECT id,label,provider,status,created_at FROM accounts ORDER BY id DESC")]

    def add_account(self, label, provider):
        if not isinstance(label, str) or not label.strip() or len(label) > 80:
            raise ValidationError("Account label must be 1–80 characters")
        if provider not in SUPPORTED_PROVIDERS:
            raise ValidationError("Unknown provider")
        status = "mock_ready" if provider == "mock" else "setup_required"
        with self._db() as db:
            try:
                cur = db.execute("INSERT INTO accounts(label,provider,status,created_at) VALUES(?,?,?,?)",
                                 (label.strip(), provider, status, self._now()))
            except sqlite3.IntegrityError as exc:
                raise ValidationError("Account label already exists") from exc
            self._audit(db, "account_created", provider)
            return {"id": cur.lastrowid, "label": label.strip(), "provider": provider, "status": status}

    def contacts(self):
        with self._db() as db:
            return [dict(r) for r in db.execute(
                "SELECT phone,name,consent_status,consent_source,consent_at FROM contacts ORDER BY id DESC LIMIT 200")]

    def import_csv(self, content: bytes):
        if not isinstance(content, bytes) or len(content) > MAX_CSV_BYTES:
            raise ValidationError("CSV exceeds 512 KiB limit")
        try:
            text = content.decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValidationError("CSV must be UTF-8") from exc
        try:
            reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
            required = {"phone", "name", "consent", "consent_source", "consent_at"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValidationError("CSV columns required: phone,name,consent,consent_source,consent_at")
            rows = list(reader)
        except csv.Error as exc:
            raise ValidationError(f"Malformed CSV: {exc}") from exc
        if len(rows) > MAX_CSV_ROWS:
            raise ValidationError("CSV exceeds 1000-row limit")
        result = {"imported": 0, "skipped": 0, "errors": []}
        with self._db() as db:
            for n, row in enumerate(rows, start=2):
                try:
                    if None in row:
                        raise ValidationError("Incorrect column count")
                    phone = normalize_phone(row.get("phone", ""))
                    name = (row.get("name") or "").strip()
                    if len(name) > 120:
                        raise ValidationError("Name too long")
                    consent_raw = (row.get("consent") or "").strip().lower()
                    if consent_raw in {"true", "yes", "1", "opt_in"}:
                        status = "opt_in"
                    elif consent_raw in {"false", "no", "0", "opt_out"}:
                        status = "opt_out"
                    else:
                        raise ValidationError("Consent must be yes/no or true/false")
                    source = (row.get("consent_source") or "").strip()
                    stamp = (row.get("consent_at") or "").strip()
                    if len(source) > 160:
                        raise ValidationError("Consent source too long")
                    if status == "opt_in":
                        if not source or not stamp:
                            raise ValidationError("Opt-in requires documented source and timestamp")
                        try:
                            dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                        except ValueError as exc:
                            raise ValidationError("Invalid consent_at ISO timestamp") from exc
                        if not dt.tzinfo or dt.astimezone(timezone.utc) > datetime.now(timezone.utc):
                            raise ValidationError("Consent timestamp must have a timezone and not be in the future")
                    previous = db.execute("SELECT consent_status FROM contacts WHERE phone=?", (phone,)).fetchone()
                    if previous and previous["consent_status"] == "opt_out" and status == "opt_in":
                        result["skipped"] += 1
                        result["errors"].append({"row": n, "reason": "Existing opt-out cannot be overridden by CSV"})
                        continue
                    db.execute("""INSERT INTO contacts(phone,name,consent_status,consent_source,consent_at,created_at)
                                  VALUES(?,?,?,?,?,?) ON CONFLICT(phone) DO UPDATE SET
                                  name=excluded.name, consent_status=excluded.consent_status,
                                  consent_source=excluded.consent_source, consent_at=excluded.consent_at""",
                               (phone, name, status, source, stamp, self._now()))
                    result["imported"] += 1
                except ValidationError as exc:
                    result["skipped"] += 1
                    if len(result["errors"]) < 25:
                        result["errors"].append({"row": n, "reason": str(exc)})
            self._audit(db, "csv_import", f"imported={result['imported']}; skipped={result['skipped']}")
        return result

    def opt_out(self, phone: str):
        phone = normalize_phone(phone)
        with self._db() as db:
            cur = db.execute("UPDATE contacts SET consent_status='opt_out' WHERE phone=?", (phone,))
            if cur.rowcount == 0:
                raise ValidationError("Contact not found")
            self._audit(db, "opt_out", "Contact opted out")
        return {"phone": phone, "consent_status": "opt_out"}

    def preview(self, message: str):
        message = validate_template(message)
        with self._db() as db:
            count = db.execute("SELECT COUNT(*) FROM contacts WHERE consent_status='opt_in'").fetchone()[0]
            recipients = [dict(r) for r in db.execute(
                "SELECT phone,name FROM contacts WHERE consent_status='opt_in' ORDER BY id LIMIT ?", (MAX_DRAFT_RECIPIENTS,))]
        return {
            "eligible": count,
            "draft_limit": MAX_DRAFT_RECIPIENTS,
            "within_draft_limit": min(count, MAX_DRAFT_RECIPIENTS),
            "examples": [{"phone": r["phone"], "message": render_template(message, r)} for r in recipients[:5]],
            "sending_enabled": False,
            "notice": "Preview only. No messages are sent.",
        }

    def campaigns(self):
        with self._db() as db:
            return [dict(r) for r in db.execute(
                """SELECT c.id,c.name,c.template,c.status,c.created_at,a.label AS account_label
                   FROM campaigns c JOIN accounts a ON a.id=c.account_id ORDER BY c.id DESC LIMIT 100""")]

    def add_draft(self, name, account_id, message):
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise ValidationError("Campaign name must be 1–120 characters")
        message = validate_template(message)
        if not isinstance(account_id, int) or isinstance(account_id, bool):
            raise ValidationError("Valid account required")
        with self._db() as db:
            account = db.execute("SELECT id FROM accounts WHERE id=?", (account_id,)).fetchone()
            if not account:
                raise ValidationError("Unknown account")
            cur = db.execute("INSERT INTO campaigns(name,account_id,template,status,created_at) VALUES(?,?,?,'draft',?)",
                             (name.strip(), account_id, message, self._now()))
            self._audit(db, "campaign_draft_created", f"id={cur.lastrowid}")
            return {"id": cur.lastrowid, "status": "draft", "sending_enabled": False}
