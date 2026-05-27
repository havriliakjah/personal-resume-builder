"""
desktop.py  --  PHASE 6: the Synthesis Workbench as a desktop app
==================================================================
This is the launcher. It does two things:

  1. starts the Flask server (server.py) on a background thread
  2. opens the workbench in its own native window, via pywebview

The result: the app runs in its own window -- no browser, no
localhost address to type. The three-tier app underneath is
unchanged (window -> server.py -> data.py -> synthesis.db);
pywebview just replaces the browser tab with a real app window.

HOW TO RUN:
    python desktop.py
or just double-click  "Synthesis Workbench.bat"  in this folder.

Run the desktop app OR `python server.py` -- not both at once;
they would both try to use port 5000.
"""

import socket
import threading
import time
from pathlib import Path

import webview

from server import app  # the Flask app -- the same one server.py runs

HERE = Path(__file__).resolve().parent
ICON = HERE / "synthesis.ico"   # a .ico -- Windows rejects a .png here
HOST, PORT = "127.0.0.1", 5000


def valid_icon(path):
    """True only if `path` is a real Windows .ico file.

    Windows builds the window with .NET, and .NET's icon loader will
    take ONLY a true .ico -- a .png, a truncated copy, or a missing
    file makes it throw, and on Windows that unhandled exception
    aborts the whole process (not just the window). So we check the
    file's first 4 bytes -- a real .ico always starts 00 00 01 00 --
    and hand the window an icon only when it is genuinely safe.
    """
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"\x00\x00\x01\x00"
    except OSError:
        return False


def run_server():
    """Run the Flask app on this (background) thread.

    debug and the reloader are OFF on purpose: the reloader spawns a
    second process and would fight the thread model used here. This is
    the packaged app, not the dev server. `threaded=True` lets the
    workbench's parallel fetches all be answered at once.
    """
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False,
            threaded=True)


def wait_for_server(timeout=15):
    """Block until the server is accepting connections.

    Without this, the window could open and try to load the page
    before Flask is listening -- and show a connection error. We poll
    the port until it answers, then let the window open.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((HOST, PORT), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.15)
    return False


if __name__ == "__main__":
    print("Starting Synthesis Workbench...")

    # The server runs on a DAEMON thread -- "daemon" means it shuts
    # down with the app when the window closes, so nothing is left
    # running in the background afterwards.
    threading.Thread(target=run_server, daemon=True).start()

    if not wait_for_server():
        print("The server did not start. Is port 5000 already in use "
              "(another 'python server.py' running)? Close it and retry.")
        raise SystemExit(1)

    webview.create_window("Synthesis Workbench", f"http://{HOST}:{PORT}",
                          width=1280, height=900, min_size=(900, 640))
    # private_mode=False keeps the browser engine's storage across
    # launches. It is harmless either way now -- the app keeps all of
    # its data in the database, nothing in the browser.
    icon = str(ICON) if valid_icon(ICON) else None
    if icon is None:
        print("Note: no valid synthesis.ico found -- launching without "
              "a custom window icon (the app still works fine).")
    webview.start(icon=icon, private_mode=False)
