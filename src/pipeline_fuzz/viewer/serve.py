"""Tiny static server for the spec-fuzz viewer.

Usage:
    python -m src.pipeline_fuzz.viewer.serve --workspace workspace_fuzz [--port 8765]

Serves:
    /            → viewer/index.html
    /ws/...      → files under <workspace>/pipeline_fuzz/
    /ws/_index.json → auto-generated task index (findings counts per task)
"""
from __future__ import annotations

import argparse
import http.server
import json
import socketserver
from collections import Counter
from pathlib import Path

VIEWER_DIR = Path(__file__).parent


def build_index(fuzz_root: Path) -> dict:
    tasks = []
    if not fuzz_root.is_dir():
        return {"tasks": tasks}
    for task_dir in sorted(p for p in fuzz_root.iterdir() if p.is_dir()):
        findings_path = task_dir / "findings.json"
        cases_path = task_dir / "cases.json"
        counts: Counter = Counter()
        if findings_path.is_file():
            try:
                for f in json.loads(findings_path.read_text()):
                    counts[f.get("verdict", "OK")] += 1
            except Exception:
                pass
        if cases_path.is_file():
            try:
                cases = json.loads(cases_path.read_text())
                counts["TOTAL"] = len(cases)
                for c in cases:
                    v = c.get("verdict")
                    if v and v not in ("INCORRECTNESS", "INCOMPLETENESS"):
                        counts[v] += 1
            except Exception:
                pass
        tasks.append({"task": task_dir.name, "counts": dict(counts)})
    return {"tasks": tasks}


def make_handler(fuzz_root: Path):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path in ("/", "/index.html"):
                self.path = "/index.html"
                self.directory = str(VIEWER_DIR)
                return self._serve_file(VIEWER_DIR / "index.html", "text/html")
            if self.path == "/ws/_index.json":
                data = json.dumps(build_index(fuzz_root)).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if self.path.startswith("/ws/"):
                rel = self.path[len("/ws/"):].split("?", 1)[0]
                target = (fuzz_root / rel).resolve()
                try:
                    target.relative_to(fuzz_root.resolve())
                except ValueError:
                    self.send_error(403); return
                if not target.is_file():
                    self.send_error(404); return
                ctype = "application/json" if target.suffix == ".json" else "text/plain; charset=utf-8"
                return self._serve_file(target, ctype)
            self.send_error(404)

        def _serve_file(self, path: Path, ctype: str):
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a, **kw):  # quiet
            return
    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True, help="Workspace dir containing pipeline_fuzz/")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    fuzz_root = Path(args.workspace) / "pipeline_fuzz"
    if not fuzz_root.is_dir():
        print(f"[warn] {fuzz_root} does not exist yet — viewer will show empty index")
    handler = make_handler(fuzz_root)
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as httpd:
        print(f"spec-fuzz viewer: http://127.0.0.1:{args.port}/  (serving {fuzz_root})")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
