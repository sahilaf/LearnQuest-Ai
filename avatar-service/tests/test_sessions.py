"""Sessions are freed as soon as the page that opened them goes away.

Regression: the video socket only sends, so a page closed while the face was
idle went unnoticed; the audio socket noticed but waited for the video one.
Four such zombie sessions filled MAX_SESSIONS and every new visitor was
refused video ("Refused: 4 sessions already open").

A real uvicorn server and real WebSocket clients, because the bug is in how
a network disconnect reaches the handlers - FastAPI's TestClient tears the
handler down on close, which hides it. No GPU needed: models load only when
the server is launched directly, and a session given no audio never uses them.

Run in the synctalk env:   python tests/test_sessions.py
"""

import asyncio
import os
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402
import uvicorn  # noqa: E402
import websockets  # noqa: E402

import avatar_server_ws as server  # noqa: E402


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = _free_port()
BASE = f"http://127.0.0.1:{PORT}"
WS = f"ws://127.0.0.1:{PORT}"


def _start_server() -> uvicorn.Server:
    srv = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=PORT, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(100):
        try:
            httpx.get(f"{BASE}/health", timeout=0.5)
            return srv
        except httpx.HTTPError:
            time.sleep(0.1)
    raise RuntimeError("test server did not start")


def _wait_closed(sid: str, timeout: float = 3.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        sess = server.sessions.get(sid)
        if sess is None or sess.closed.is_set():
            return True
        time.sleep(0.05)
    return False


async def _open_and_close_page(sid: str, *, only_video: bool = False) -> None:
    """What a browser tab does: open both sockets, sit idle, close."""
    audio = None if only_video else await websockets.connect(f"{WS}/ws/audio/{sid}")
    video = await websockets.connect(f"{WS}/ws/video/{sid}")
    await asyncio.sleep(0.3)  # idle: no audio, so nothing is ever sent
    await video.close()
    if audio is not None:
        await audio.close()


def test_closing_an_idle_page_frees_its_session():
    sid = httpx.post(f"{BASE}/session").json()["session_id"]
    asyncio.run(_open_and_close_page(sid))
    assert _wait_closed(sid), "an idle page's session stayed open after the page closed"


def test_a_dropped_video_socket_alone_frees_the_session():
    sid = httpx.post(f"{BASE}/session").json()["session_id"]

    async def page():
        audio = await websockets.connect(f"{WS}/ws/audio/{sid}")
        video = await websockets.connect(f"{WS}/ws/video/{sid}")
        await asyncio.sleep(0.3)
        await video.close()  # only the video socket goes
        await asyncio.sleep(1.0)
        closed = _wait_closed(sid, timeout=2.0)
        await audio.close()
        return closed

    assert asyncio.run(page()), "a dropped video socket did not free the session"


def test_closed_pages_make_room_for_new_visitors():
    for _ in range(server.MAX_SESSIONS + 2):
        response = httpx.post(f"{BASE}/session")
        assert response.status_code == 200, "a closed page's session was still counted against the limit"
        sid = response.json()["session_id"]
        asyncio.run(_open_and_close_page(sid))
        assert _wait_closed(sid)


if __name__ == "__main__":
    _start_server()
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print("PASS", name)
            except AssertionError as exc:
                failed += 1
                print("FAIL", name, "-", exc)
    sys.exit(1 if failed else 0)
