"""Minimal localhost HTTP server for Nabu Reach MVP. No live messaging API."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .core import Store, ValidationError, MAX_CSV_BYTES

WEB = Path(__file__).resolve().parent / "web"
MAX_JSON_BYTES = 16 * 1024


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Deliberately avoids logging contact payloads.
        print("[Nabu Reach] " + (fmt % args))

    def respond(self, status, data, content_type="application/json; charset=utf-8"):
        if isinstance(data, (dict, list)):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        elif isinstance(data, str):
            body = data.encode("utf-8")
        else:
            body = data
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; base-uri 'none'; object-src 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        route = urlparse(self.path).path
        try:
            if route in {"/", "/app.css", "/app.js"}:
                filename = {"/": "index.html", "/app.css": "app.css", "/app.js": "app.js"}[route]
                ct = {"/": "text/html; charset=utf-8", "/app.css": "text/css; charset=utf-8", "/app.js": "text/javascript; charset=utf-8"}[route]
                return self.respond(200, (WEB / filename).read_bytes(), ct)
            if route == "/healthz":
                return self.respond(200, {"status": "ok", "mode": "draft_only"})
            routes = {"/api/summary": self.server.store.summary,
                      "/api/accounts": self.server.store.accounts,
                      "/api/contacts": self.server.store.contacts,
                      "/api/campaigns": self.server.store.campaigns}
            if route in routes:
                return self.respond(200, routes[route]())
            return self.respond(404, {"error": "Not found"})
        except Exception:
            return self.respond(500, {"error": "Internal error"})

    def do_POST(self):
        route = urlparse(self.path).path
        # Reject cross-origin browser writes; no cookies or CORS support.
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if origin and origin not in {"http://" + host, "https://" + host}:
            return self.respond(403, {"error": "Cross-origin write blocked"})
        if route not in {"/api/accounts", "/api/contacts/import", "/api/contacts/opt-out", "/api/campaigns/preview", "/api/campaigns"}:
            return self.respond(404, {"error": "Not found"})
        try:
            size = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            size = -1
        cap = MAX_CSV_BYTES if route == "/api/contacts/import" else MAX_JSON_BYTES
        if size < 0 or size > cap:
            return self.respond(413, {"error": "Missing or oversized payload"})
        ctype = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if ctype != ("text/csv" if route == "/api/contacts/import" else "application/json"):
            return self.respond(415, {"error": "Unsupported content type"})
        body = self.rfile.read(size)
        try:
            if route == "/api/contacts/import":
                result = self.server.store.import_csv(body)
            else:
                payload = json.loads(body)
                if not isinstance(payload, dict):
                    raise ValidationError("JSON object required")
                if route == "/api/accounts":
                    result = self.server.store.add_account(payload.get("label"), payload.get("provider"))
                elif route == "/api/contacts/opt-out":
                    result = self.server.store.opt_out(payload.get("phone"))
                elif route == "/api/campaigns/preview":
                    result = self.server.store.preview(payload.get("message"))
                else:
                    result = self.server.store.add_draft(payload.get("name"), payload.get("account_id"), payload.get("message"))
        except (ValidationError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            return self.respond(400, {"error": str(exc)})
        except Exception:
            return self.respond(500, {"error": "Internal error"})
        return self.respond(200, result)


def make_server(host="127.0.0.1", port=8787, db_path="data/reach.sqlite3"):
    server = ThreadingHTTPServer((host, port), Handler)
    server.store = Store(db_path)
    return server


def main():
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8787"))
    db = os.environ.get("DB_PATH", "data/reach.sqlite3")
    if host not in {"127.0.0.1", "localhost", "::1"}:
        print("WARNING: no authentication is built in. Bind the published Docker port to localhost only.")
    server = make_server(host, port, db)
    print(f"Nabu Reach MVP (draft-only) on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
