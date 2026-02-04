import os
import threading
import time

import pytest
import requests
from werkzeug.serving import make_server

from stub_server.app import app, reset_store


class StubServerThread(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.server = make_server("127.0.0.1", 3000, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self) -> None:
        self.server.serve_forever()

    def stop(self) -> None:
        self.server.shutdown()
        self.ctx.pop()


def _wait_for_server(timeout: float = 5.0) -> None:
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get("http://127.0.0.1:3000/api/v2/auth/")
            if resp.status_code in {204, 401}:
                return
        except requests.ConnectionError:
            time.sleep(0.05)
            continue
    raise RuntimeError("Stub server failed to start")


@pytest.fixture(scope="session", autouse=True)
def stub_server() -> None:
    reset_store()
    server = StubServerThread()
    server.start()
    _wait_for_server()
    yield
    server.stop()
    server.join(timeout=2)


@pytest.fixture(scope="session", autouse=True)
def configure_env() -> None:
    os.environ["READWISE_TOKEN"] = "stub-token"
    os.environ["READWISE_READER_TOKEN"] = "stub-token"
    os.environ["READWISE_API_BASE_URL"] = "http://127.0.0.1:3000/api/v2"
    os.environ["READWISE_READER_API_BASE_URL"] = "http://127.0.0.1:3000/api/v3"


@pytest.fixture(autouse=True)
def fresh_store() -> None:
    reset_store()
    yield
