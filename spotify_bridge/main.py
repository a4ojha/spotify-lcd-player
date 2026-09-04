"""
Spotify -> UART bridge
"""

import argparse
import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

import serial
from dotenv import load_dotenv
from unidecode import unidecode

CWD = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(CWD, ".env"))

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
REDIRECT_HOST = "127.0.0.1"
REDIRECT_PORT = 8888
REDIRECT_URI = f"http://{REDIRECT_HOST}:{REDIRECT_PORT}/callback"
SCOPE = "user-read-playback-state"
TOKEN_FILE = os.path.join(CWD, ".spotify_token.json")

SERIAL_PORT = os.environ.get("SPOTIFY_LCD_PORT", "COM3")
BAUD_RATE = 115200

POLL_SECONDS = 1
MAX_FIELD_LENGTH = 40

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
PLAYER_URL = "https://api.spotify.com/v1/me/player"

DEBUG = False

def log(msg):
    if DEBUG:
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --- auth --------------------------------------------------------------------
def _b64url(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

def _post_token(payload):
    body = urllib.parse.urlencode(payload).encode("ascii")
    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)

class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    result = {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != urllib.parse.urlparse(REDIRECT_URI).path:
            self.send_response(404)
            self.end_headers()
            return

        query = urllib.parse.parse_qs(parsed.query)
        _CallbackHandler.result = {k: v[0] for k, v in query.items()}

        ok = "code" in _CallbackHandler.result
        text = "Authorized. You can close this tab." if ok else "Authorization failed."
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(text.encode("utf-8"))

    def log_message(self, *args):  # silence the default stderr access log
        pass

def _authorize():
    """Run PKCE in a browser and return the token payload."""
    verifier = _b64url(secrets.token_bytes(48))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    state = _b64url(secrets.token_bytes(16))

    params = urllib.parse.urlencode(
        {
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE,
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
        }
    )
    url = f"{AUTH_URL}?{params}"

    server = http.server.HTTPServer((REDIRECT_HOST, REDIRECT_PORT), _CallbackHandler)
    threading.Thread(target=server.handle_request, daemon=True).start()

    print("opening browser for Spotify authorization", flush=True)
    print(f"  if it doesn't open, visit:\n  {url}\n", flush=True)
    webbrowser.open(url)

    deadline = time.time() + 300
    while not _CallbackHandler.result and time.time() < deadline:
        time.sleep(0.2)
    server.server_close()

    result = _CallbackHandler.result
    if not result:
        raise RuntimeError("timed out waiting for the Spotify redirect")
    if "error" in result:
        raise RuntimeError(f"authorization denied: {result['error']}")
    if result.get("state") != state:
        raise RuntimeError("state mismatch on the Spotify redirect")

    return _post_token(
        {
            "grant_type": "authorization_code",
            "code": result["code"],
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "code_verifier": verifier,
        }
    )

class TokenStore:
    """Holds the access/refresh pair, updates token when needed"""

    def __init__(self):
        self.access_token = None
        self.refresh_token = None
        self.expires_at = 0.0
        self._load()

    def _load(self):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return
        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token")
        self.expires_at = data.get("expires_at", 0.0)

    def _save(self):
        data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
        }
        with open(TOKEN_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def _apply(self, payload):
        self.access_token = payload["access_token"]
        # Spotify only sometimes returns a new refresh token, keep the old one otherwise
        self.refresh_token = payload.get("refresh_token") or self.refresh_token
        self.expires_at = time.time() + payload.get("expires_in", 3600) - 60
        self._save()

    def token(self, force_refresh=False):
        if self.access_token and not force_refresh and time.time() < self.expires_at:
            return self.access_token

        if self.refresh_token:
            try:
                self._apply(
                    _post_token(
                        {
                            "grant_type": "refresh_token",
                            "refresh_token": self.refresh_token,
                            "client_id": CLIENT_ID,
                        }
                    )
                )
                return self.access_token
            except urllib.error.HTTPError as exc:
                log(f"refresh failed ({exc.code}), re-authorizing")
                self.refresh_token = None

        self._apply(_authorize())
        log("authorized")
        return self.access_token


# --- spotify polling ---------------------------------------------------------

def fetch_playback(tokens):
    for attempt in range(2):
        req = urllib.request.Request(
            PLAYER_URL,
            headers={"Authorization": f"Bearer {tokens.token(force_refresh=attempt > 0)}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 204:  # no active device
                    return None
                body = resp.read()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            if exc.code == 401 and attempt == 0:
                continue  # token went stale early; refresh and retry once
            if exc.code == 429:
                wait = int(exc.headers.get("Retry-After", "5")) + 1
                log(f"rate limited, sleeping {wait}s")
                time.sleep(wait)
                return None
            raise
    return None


# --- message building --------------------------------------------------------

_SUBSTITUTIONS = {
    "–": "-",
    "—": "-",
    "…": "...",
}

IDLE_MESSAGE = f"-|-|0|0\n"

def to_lcd_text(text):
    """Convert text to ASCII-only, suitable for the LCD."""
    for src, dst in _SUBSTITUTIONS.items():
        text = text.replace(src, dst)
    text = unidecode(text)
    # Keep printable ASCII only, replace '|' and everything else
    # with spaces so leftover junk can't break the message format.
    text = "".join(c if " " <= c <= "~" and c != "|" else " " for c in text)
    text = " ".join(text.split())[:MAX_FIELD_LENGTH]
    return text or "-"


def build_message(playback):
    item = playback.get("item") if playback else None
    if not item:
        return IDLE_MESSAGE

    title = to_lcd_text(item.get("name", ""))
    
    # TODO: handle podcasts
    if item.get("type") == "episode":
        artist = to_lcd_text(item.get("show", {}).get("name", ""))
    else:
        artist = to_lcd_text(", ".join(a["name"] for a in item.get("artists", [])))

    duration = item.get("duration_ms") or 0
    elapsed = playback.get("progress_ms") or 0
    progress = min(100, max(0, round(elapsed * 100 / duration))) if duration else 0

    is_playing = 1 if playback.get("is_playing") else 0
    return f"{title}|{artist}|{progress}|{is_playing}\n"


# --- uart --------------------------------------------------------------------

def open_uart():
    return serial.Serial(
        port=SERIAL_PORT,
        baudrate=BAUD_RATE,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
        timeout=1,
        write_timeout=2,
    )


# --- main loop ---------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="stream Spotify playback over UART COM3.")
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="prints data logs",
    )
    return parser.parse_args()


def main():
    global DEBUG
    DEBUG = parse_args().debug

    if not CLIENT_ID:
        sys.exit(
            f"No SPOTIFY_CLIENT_ID found. Put it in {os.path.join(CWD, '.env')}\n"
            f"Then add {REDIRECT_URI} to the app's Redirect URIs in the Spotify dashboard."
        )

    tokens = TokenStore()
    tokens.token()
    
    uart = None
    last_message = None

    log(f"polling every {POLL_SECONDS:g}s, writing to {SERIAL_PORT} @ {BAUD_RATE}")
    while True:
        try:
            if uart is None:
                uart = open_uart()
                log(f"{SERIAL_PORT} open")
                last_message = None

            try:
                message = build_message(fetch_playback(tokens))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                log(f"spotify poll failed: {exc}")
                time.sleep(POLL_SECONDS)
                continue

            if message != last_message:
                uart.write(message.encode("ascii"))
                uart.flush()
                last_message = message
                log(f"tx {message.rstrip()}")

        except serial.SerialException as exc:
            log(f"serial error: {exc}; retrying")
            if uart is not None:
                try:
                    uart.close()
                except serial.SerialException:
                    pass
                uart = None
                
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("stopped")
