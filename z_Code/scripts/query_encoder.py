"""Keep one Qwen query encoder resident while the local Elasticsearch is running."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

from support import CONTRACT, ROOT, es

URL = "http://127.0.0.1:8791"


def health(timeout=2):
    response = requests.get(URL + "/health", timeout=timeout)
    response.raise_for_status()
    result = response.json()
    if result["contract"] != CONTRACT:
        raise RuntimeError("The running query encoder uses a different model configuration.")
    return result


def query_vector(text):
    try:
        health(timeout=120)
        response = requests.post(URL + "/encode", json={"text": text}, timeout=120)
    except requests.ConnectionError as error:
        raise RuntimeError(
            "Start the query encoder first: python scripts/query_encoder.py --start"
        ) from error
    if not response.ok:
        raise RuntimeError(response.json()["error"])
    return response.json()["vector"]


def watch_elasticsearch(server, finished):
    failures = 0
    while not finished.wait(5):
        try:
            es("GET", "")
            failures = 0
        except requests.RequestException:
            failures += 1
            if failures == 3:
                server.shutdown()
                return


def serve():
    # Bind before loading the model so a second process cannot allocate another copy.
    server = HTTPServer(("127.0.0.1", 8791), Handler)
    try:
        es("GET", "")
        from encoder import Encoder, CONTRACT as encoder_contract

        if encoder_contract != CONTRACT:
            raise RuntimeError("Encoder settings do not match the source configuration.")
        server.encoder = Encoder()
        server.encoder.query("quiet accommodation")
        finished = threading.Event()

        threading.Thread(
            target=watch_elasticsearch, args=(server, finished), daemon=True
        ).start()
        print("Qwen query encoder ready at " + URL, flush=True)
        try:
            server.serve_forever()
        finally:
            finished.set()
    finally:
        server.server_close()


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body):
        data = json.dumps(body).encode()
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except ConnectionError:
            pass

    def do_GET(self):
        if self.path != "/health":
            return self.reply(404, {"error": "Unknown endpoint."})
        self.reply(200, {"contract": CONTRACT, "pid": os.getpid()})

    def do_POST(self):
        if self.path != "/encode":
            return self.reply(404, {"error": "Unknown endpoint."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1024 * 1024:
                raise ValueError("Query body must be between 1 byte and 1 MiB.")
            text = json.loads(self.rfile.read(length))["text"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Query text must be a non-empty string.")
            vector = self.server.encoder.query(text).tolist()
        except (ValueError, KeyError) as error:
            return self.reply(400, {"error": str(error)})
        except Exception as error:
            return self.reply(500, {"error": str(error)})
        self.reply(200, {"vector": vector})


def start():
    deadline = time.monotonic() + 600
    process = None
    log = ROOT / ".runtime/state/qwen.log"
    while time.monotonic() < deadline:
        try:
            return health()
        except requests.ReadTimeout:
            # The bound service may be loading or handling a long query. Wait
            # for it instead of failing or launching another model process.
            pass
        except (requests.ConnectionError, requests.Timeout):
            if process is None:
                es("GET", "")
                log.parent.mkdir(parents=True, exist_ok=True)
                with log.open("a", encoding="utf-8") as output:
                    process = subprocess.Popen(
                        [sys.executable, str(Path(__file__).resolve()), "--serve"],
                        stdin=subprocess.DEVNULL,
                        stdout=output,
                        stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    )
            elif process.poll() is not None:
                raise RuntimeError(f"Qwen startup failed. Check {log}.")
        time.sleep(1)
    if process is not None:
        process.terminate()
    raise RuntimeError(f"Qwen startup timed out. Check {log}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--start", action="store_true")
    mode.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    if args.start:
        print(f"Qwen query encoder ready (PID {start()['pid']}).")
    else:
        serve()
