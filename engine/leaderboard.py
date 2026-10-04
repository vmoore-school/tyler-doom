"""Global leaderboard client (Supabase REST). Requests never block the game loop: each call returns a
Request whose .status goes "pending" -> "ok" / "error"; poll it each frame.

Desktop uses urllib on a background thread. In the browser (pygbag) neither works, so requests go
through the page's own fetch() via a small JavaScript helper, and Python polls for the answer."""
import json
import os
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request

from . import leaderboard_config as config

WEB = sys.platform == "emscripten"
TIMEOUT = 8  # seconds
NAME_MAX = 12

_JS = """
window.lb_results = window.lb_results || {};
window.lb_fetch = function (id, url, method, headers, body) {
  window.lb_results[id] = "";
  fetch(url, {method: method, headers: JSON.parse(headers), body: body || undefined})
    .then(r => r.text().then(t => { window.lb_results[id] = JSON.stringify({status: r.status, text: t}); }))
    .catch(e => { window.lb_results[id] = JSON.stringify({status: 0, text: String(e)}); });
};
window.lb_take = function (id) {
  const r = window.lb_results[id] || "";
  if (r) delete window.lb_results[id];
  return r;
};
"""


def clean_name(name):
    """What gets submitted: printable, trimmed, at most NAME_MAX characters."""
    return "".join(c for c in name if c.isprintable()).strip()[:NAME_MAX]


class Request:
    def __init__(self):
        self.status, self.result, self.error = "pending", None, None

    def _finish(self, code, text):
        if 200 <= code < 300:
            try:
                self.result = json.loads(text) if text else None
                self.status = "ok"
                return
            except ValueError:
                text = "bad response"
        self.error = f"HTTP {code}: {text[:80]}" if code else "can't reach the leaderboard"
        self.status = "error"


class Leaderboard:
    def __init__(self):
        # Environment overrides are for local testing against a mock server (desktop only).
        self.url = os.environ.get("LEADERBOARD_URL", config.SUPABASE_URL).rstrip("/")
        self.key = os.environ.get("LEADERBOARD_KEY", config.SUPABASE_KEY)
        self.enabled = bool(self.url and self.key)
        self._web_pending = {}  # request id -> Request
        self._next_id = 0
        if WEB and self.enabled:
            import platform  # pygbag's bridge to the page's JavaScript
            platform.window.eval(_JS)

    def submit(self, name, wave, kills):
        body = json.dumps({"name": clean_name(name), "wave": int(wave), "kills": int(kills)})
        return self._request("POST", "/rest/v1/scores", body, {"Prefer": "return=minimal"})

    def fetch_top(self, n=10):
        query = urllib.parse.urlencode({"select": "name,wave,kills",
                                        "order": "wave.desc,kills.desc,created_at.asc", "limit": n})
        return self._request("GET", f"/rest/v1/scores?{query}")

    def poll(self):
        """Collect finished browser requests. Call once per frame (does nothing on desktop)."""
        if not self._web_pending:
            return
        import platform
        for rid, req in list(self._web_pending.items()):
            raw = platform.window.lb_take(rid)
            if raw:
                del self._web_pending[rid]
                answer = json.loads(raw)
                req._finish(answer["status"], answer["text"])

    def _request(self, method, path, body=None, extra=None):
        req = Request()
        if not self.enabled:
            req.status, req.error = "error", "leaderboard not set up"
            return req
        headers = {"apikey": self.key, "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        headers.update(extra or {})
        url = self.url + path
        if WEB:
            import platform
            self._next_id += 1
            rid = f"r{self._next_id}"
            self._web_pending[rid] = req
            platform.window.lb_fetch(rid, url, method, json.dumps(headers), body or "")
        else:
            threading.Thread(target=self._desktop, args=(req, method, url, body, headers), daemon=True).start()
        return req

    @staticmethod
    def _desktop(req, method, url, body, headers):
        data = body.encode() if body else None
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data, headers, method=method),
                                        timeout=TIMEOUT) as r:
                req._finish(r.status, r.read().decode())
        except urllib.error.HTTPError as e:
            req._finish(e.code, e.read().decode(errors="replace"))
        except Exception:  # offline, DNS, timeout...
            req._finish(0, "")
