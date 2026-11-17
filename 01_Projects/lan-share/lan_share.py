#!/opt/homebrew/bin/python3.14
"""Локальный обмен файлами между Mac и телефоном в одной Wi‑Fi."""

from __future__ import annotations

import json
import os
import random
import secrets
import socket
import ssl
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 17890
HTTPS_PORT = 17891
SHARE_DIR = Path(os.environ.get("LAN_SHARE_DIR", str(Path.home() / "Downloads" / "Обмен"))).expanduser()
APK_PATH = SHARE_DIR / "Мой-плеер.apk"
WEB_DIR = Path(__file__).resolve().parent / "web"
PLAYER_ROUTES = {
    "/player": "player.html",
    "/player/": "player.html",
    "/player/manifest.webmanifest": "manifest.webmanifest",
    "/player/sw.js": "sw.js",
    "/player/icon.svg": "icon.svg",
}
MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".webmanifest": "application/manifest+json",
    ".svg": "image/svg+xml",
}
PIN = f"{random.randint(0, 9999):04d}"
TOKEN = secrets.token_hex(16)


def lan_ip() -> str:
    for iface in ("en0", "en1"):
        try:
            out = subprocess.check_output(["ipconfig", "getifaddr", iface], text=True).strip()
            if out:
                return out
        except (OSError, subprocess.CalledProcessError):
            pass
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("192.168.0.1", 80))
        ip = sock.getsockname()[0]
        sock.close()
        if not ip.startswith("127."):
            return ip
    except OSError:
        pass
    return "127.0.0.1"


def current_urls() -> tuple[str, str, str]:
    ip = lan_ip()
    return ip, f"http://{ip}:{PORT}", f"https://{ip}:{HTTPS_PORT}"


def ensure_cert(ip: str) -> tuple[Path, Path]:
    cert_dir = Path(__file__).resolve().parent / ".certs"
    cert_dir.mkdir(exist_ok=True)
    cert, key = cert_dir / "cert.pem", cert_dir / "key.pem"
    if cert.exists() and key.exists():
        return cert, key
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-sha256",
            "-days",
            "14",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-subj",
            f"/CN={ip}",
            "-addext",
            f"subjectAltName=IP:{ip},DNS:localhost",
        ],
        check=True,
        capture_output=True,
    )
    return cert, key


def safe_name(name: str) -> str:
    name = Path(name).name.replace("\x00", "").strip()
    if not name or name in {".", ".."}:
        raise ValueError("плохое имя файла")
    return name


def file_list() -> list[dict]:
    SHARE_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for path in sorted(SHARE_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.name.startswith(".") or not path.is_file():
            continue
        items.append(
            {
                "name": path.name,
                "size": path.stat().st_size,
                "url": "/files/" + urllib.parse.quote(path.name) + "?t=" + TOKEN,
            }
        )
    return items


PAGE = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Обмен с телефоном</title>
<style>
  :root {
    --bg: #0f1412;
    --card: #1a211e;
    --line: #2c3833;
    --text: #eef4f0;
    --muted: #93a39a;
    --acc: #3dd68c;
    --acc2: #1f8f5b;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: ui-rounded, "SF Pro Text", system-ui, sans-serif;
    background: radial-gradient(1200px 600px at 10% -10%, #1c3a2c, var(--bg));
    color: var(--text);
    min-height: 100dvh;
  }
  main { max-width: 880px; margin: 0 auto; padding: 24px 16px 48px; }
  h1 { font-size: 1.5rem; margin: 0 0 6px; }
  .sub { color: var(--muted); margin-bottom: 20px; }
  .grid { display: grid; gap: 16px; }
  @media (min-width: 800px) { .grid.top { grid-template-columns: 280px 1fr; } }
  .card {
    background: color-mix(in srgb, var(--card) 92%, black);
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: 16px;
  }
  #qr, #qr-player { width: 220px; height: 220px; background: #fff; border-radius: 12px; padding: 8px; }
  .qrs { display: flex; flex-wrap: wrap; gap: 16px; }
  .pin { font-size: 2rem; letter-spacing: .2em; font-weight: 700; color: var(--acc); }
  .url { word-break: break-all; color: var(--acc); }
  .drop {
    border: 1.5px dashed var(--line);
    border-radius: 16px;
    padding: 28px 16px;
    text-align: center;
    background: #121916;
  }
  .drop.over { border-color: var(--acc); background: #163323; }
  button, .btn {
    appearance: none;
    border: 0;
    border-radius: 12px;
    background: var(--acc);
    color: #062113;
    font-weight: 700;
    padding: 12px 16px;
    cursor: pointer;
    text-decoration: none;
    display: inline-block;
  }
  button.ghost { background: #26352e; color: var(--text); }
  input[type=file] { display: none; }
  .row { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; }
  .file {
    display: flex; justify-content: space-between; gap: 12px; align-items: center;
    padding: 10px 0; border-bottom: 1px solid var(--line);
  }
  .file:last-child { border-bottom: 0; }
  .name { overflow-wrap: anywhere; }
  .meta { color: var(--muted); font-size: .85rem; }
  progress { width: 100%; height: 10px; }
  #gate { max-width: 420px; margin: 12vh auto; padding: 16px; }
  input[type=password], input[type=text] {
    width: 100%; padding: 12px; border-radius: 12px; border: 1px solid var(--line);
    background: #101613; color: var(--text); font-size: 1.2rem; letter-spacing: .2em; text-align: center;
  }
  .err { color: #ff8d8d; }
</style>
</head>
<body>
<main>
  <div id="gate" class="card" hidden>
    <h1>Код с экрана Mac</h1>
    <p class="sub">4 цифры, которые видны на компьютере</p>
    <input id="pin" inputmode="numeric" maxlength="4" autocomplete="one-time-code">
    <p><button id="unlock">Войти</button></p>
    <p class="err" id="pin-err"></p>
  </div>
  <div id="app" hidden>
    <h1>Обмен с телефоном</h1>
    <p class="sub">Samsung: тот же Wi‑Fi, <b>выключи мобильный интернет и VPN</b>.
      Лучше Chrome, не Samsung Internet. Если камера не открывает http — введи ссылку руками.
      <a href="/player/" style="color:#3dd68c">Плеер</a></p>
    <div class="grid top">
      <div class="card" id="pair">
        <div class="qrs">
          <div>
            <div id="qr-player"></div>
            <p><b>HTTPS</b> — камера Samsung, потом «Дополнительно → перейти»</p>
          </div>
          <div>
            <div id="qr"></div>
            <p class="meta">HTTP, если HTTPS не пустит</p>
          </div>
        </div>
        <p>Код обмена: <span class="pin">__PIN__</span></p>
        <p class="url" id="lan-url">__URL__/?p=__PIN__</p>
        <p class="url">HTTPS для Samsung: __HTTPS__/?p=__PIN__</p>
      </div>
      <div class="card">
        <div class="drop" id="drop">
          <p>Перетащи файлы сюда или выбери с устройства</p>
          <div class="row">
            <label class="btn">Выбрать файлы<input id="picker" type="file" multiple></label>
            <button class="ghost" id="refresh">Обновить список</button>
          </div>
          <p><progress id="bar" value="0" max="100" hidden></progress></p>
          <p class="meta" id="status"></p>
        </div>
      </div>
    </div>
    <div class="card" style="margin-top:16px">
      <h2 style="margin:0 0 8px;font-size:1.1rem">Файлы в папке «Обмен»</h2>
      <div id="files"></div>
    </div>
  </div>
</main>
<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
<script>
const PIN_Q = new URLSearchParams(location.search).get("p") || "";

function pretty(n) {
  if (n < 1024) return n + " Б";
  if (n < 1048576) return (n/1024).toFixed(1) + " КБ";
  if (n < 1073741824) return (n/1048576).toFixed(1) + " МБ";
  return (n/1073741824).toFixed(2) + " ГБ";
}

async function api(path, opt) {
  const res = await fetch(path, Object.assign({ credentials: "same-origin" }, opt));
  if (res.status === 401) throw new Error("need-pin");
  if (!res.ok) throw new Error(await res.text());
  const ct = res.headers.get("content-type") || "";
  return ct.includes("json") ? res.json() : res.text();
}

async function loadFiles() {
  const data = await api("/api/files");
  const box = document.getElementById("files");
  if (!data.length) { box.innerHTML = '<p class="meta">Пока пусто</p>'; return; }
  box.innerHTML = data.map(f => `
    <div class="file">
      <div>
        <div class="name">${f.name}</div>
        <div class="meta">${pretty(f.size)}</div>
      </div>
      <a class="btn" href="${f.url}">Скачать</a>
    </div>`).join("");
}

function sendFiles(files) {
  if (!files.length) return;
  const fd = new FormData();
  [...files].forEach(f => fd.append("files", f, f.name));
  const bar = document.getElementById("bar");
  const status = document.getElementById("status");
  bar.hidden = false; bar.value = 0;
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/upload");
  xhr.withCredentials = true;
  xhr.upload.onprogress = e => {
    if (e.lengthComputable) {
      bar.value = Math.round(e.loaded / e.total * 100);
      status.textContent = pretty(e.loaded) + " из " + pretty(e.total);
    }
  };
  xhr.onload = () => {
    status.textContent = xhr.status === 200 ? "Готово" : "Ошибка загрузки";
    loadFiles().catch(() => {});
  };
  xhr.onerror = () => { status.textContent = "Сеть оборвалась"; };
  xhr.send(fd);
}

async function enter(pin) {
  await api("/api/auth", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({pin})
  });
  document.getElementById("gate").hidden = true;
  document.getElementById("app").hidden = false;
  const local = location.hostname === "127.0.0.1" || location.hostname === "localhost";
  document.getElementById("pair").style.display = local ? "" : "none";
  const url = "__HTTPS__/?p=__PIN__";
  const httpUrl = "__URL__/?p=__PIN__";
  if (window.QRCode) {
    new QRCode(document.getElementById("qr-player"), {text: url, width: 204, height: 204});
    new QRCode(document.getElementById("qr"), {text: httpUrl, width: 204, height: 204});
  }
  await loadFiles();
}

document.getElementById("unlock").onclick = () => {
  enter(document.getElementById("pin").value.trim()).catch(() => {
    document.getElementById("pin-err").textContent = "Неверный код";
  });
};
document.getElementById("picker").onchange = e => sendFiles(e.target.files);
document.getElementById("refresh").onclick = () => loadFiles();
const drop = document.getElementById("drop");
["dragenter","dragover"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave","drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", e => sendFiles(e.dataTransfer.files));

(async () => {
  try {
    await api("/api/files");
    await enter("");
  } catch {
    if (PIN_Q) {
      try { await enter(PIN_Q); return; } catch {}
    }
    document.getElementById("gate").hidden = false;
  }
})();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "LanShare/1.0"

    def log_message(self, fmt: str, *args) -> None:
        ua = self.headers.get("User-Agent", "")[:90]
        sys.stderr.write("%s - %s [%s]\n" % (self.address_string(), fmt % args, ua))

    def _authed(self) -> bool:
        cookie = self.headers.get("Cookie", "")
        if f"lan_share={TOKEN}" in cookie:
            return True
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        return qs.get("t", [""])[0] == TOKEN

    def _send_file(self, file_path: Path, download_name: str) -> None:
        size = file_path.stat().st_size
        start, end, status = 0, size - 1, 200
        rng = self.headers.get("Range", "")
        if rng.startswith("bytes=") and size:
            spec = rng.split("=", 1)[1].split(",", 1)[0].strip()
            left, _, right = spec.partition("-")
            try:
                if left:
                    start = int(left)
                if right:
                    end = int(right)
            except ValueError:
                start, end = 0, size - 1
            if start < 0 or start >= size or end < start:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            end = min(end, size - 1)
            status = 206
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header(
            "Content-Disposition",
            f"attachment; filename*=UTF-8''{urllib.parse.quote(download_name)}",
        )
        self.end_headers()
        if getattr(self, "_omit_body", False):
            return
        with file_path.open("rb") as fh:
            fh.seek(start)
            left = length
            while left > 0:
                chunk = fh.read(min(256 * 1024, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    def _json(self, data, status: int = 200, extra_headers: list[tuple[str, str]] | None = None) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        for key, value in extra_headers or []:
            self.send_header(key, value)
        self.end_headers()
        if not getattr(self, "_omit_body", False):
            self.wfile.write(raw)

    def _text(self, body: str, status: int = 200, content_type: str = "text/html; charset=utf-8") -> None:
        raw = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if not getattr(self, "_omit_body", False):
            self.wfile.write(raw)

    def do_HEAD(self) -> None:
        # Samsung DownloadManager сначала шлёт HEAD; без этого отвечает 501.
        self._omit_body = True
        try:
            self.do_GET()
        finally:
            self._omit_body = False

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)
        if path == "/":
            _ip, http_url, https_url = current_urls()
            html = (
                PAGE.replace("__PIN__", PIN)
                .replace("__URL__", http_url)
                .replace("__HTTPS__", https_url)
            )
            self._text(html)
            return
        if path in {"/apk", "/MyPlayer.apk"}:
            if not APK_PATH.is_file():
                self._text("APK ещё нет", 404, "text/plain; charset=utf-8")
                return
            size = APK_PATH.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.android.package-archive")
            self.send_header("Content-Length", str(size))
            self.send_header("Content-Disposition", "attachment; filename=MyPlayer.apk")
            self.end_headers()
            if getattr(self, "_omit_body", False):
                return
            with APK_PATH.open("rb") as fh:
                while True:
                    chunk = fh.read(256 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            return
        if path in PLAYER_ROUTES:
            file_path = WEB_DIR / PLAYER_ROUTES[path]
            raw = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", MIME.get(file_path.suffix, "application/octet-stream"))
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            if not getattr(self, "_omit_body", False):
                self.wfile.write(raw)
            return
        if path == "/api/files":
            if not self._authed():
                self._json({"error": "pin"}, 401)
                return
            self._json(file_list())
            return
        if path.startswith("/files/"):
            if not self._authed():
                self._text("Нужен код", 401, "text/plain; charset=utf-8")
                return
            name = safe_name(path[len("/files/") :])
            file_path = SHARE_DIR / name
            if not file_path.is_file():
                self._text("Нет файла", 404, "text/plain; charset=utf-8")
                return
            self._send_file(file_path, name)
            return
        self._text("Нет такой страницы", 404, "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/auth":
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length)
            try:
                pin = str(json.loads(raw.decode() or "{}").get("pin", "")).strip()
            except json.JSONDecodeError:
                pin = ""
            if pin != PIN and not (pin == "" and self._authed()):
                self._json({"error": "bad pin"}, 401)
                return
            self._json(
                {"ok": True},
                extra_headers=[
                    ("Set-Cookie", f"lan_share={TOKEN}; Path=/; SameSite=Lax"),
                ],
            )
            return
        if parsed.path == "/api/upload":
            if not self._authed():
                self._json({"error": "pin"}, 401)
                return
            try:
                saved = self._save_uploads()
            except Exception as exc:
                self._json({"error": str(exc)}, 400)
                return
            self._json({"saved": saved})
            return
        self._text("Нет", 404, "text/plain; charset=utf-8")

    def _save_uploads(self) -> list[str]:
        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            raise RuntimeError("нужен multipart")
        boundary = ""
        for part in ctype.split(";"):
            part = part.strip()
            if part.lower().startswith("boundary="):
                boundary = part.split("=", 1)[1].strip().strip('"')
        if not boundary:
            raise RuntimeError("нет boundary")
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length)
        sep = b"--" + boundary.encode()
        saved: list[str] = []
        SHARE_DIR.mkdir(parents=True, exist_ok=True)
        for chunk in body.split(sep):
            if not chunk or chunk in {b"--\r\n", b"--"}:
                continue
            if chunk.startswith(b"\r\n"):
                chunk = chunk[2:]
            header_blob, _, data = chunk.partition(b"\r\n\r\n")
            if not data:
                continue
            if data.endswith(b"\r\n"):
                data = data[:-2]
            headers = header_blob.decode("utf-8", "replace")
            if "filename=" not in headers:
                continue
            match = None
            for line in headers.split("\r\n"):
                if "filename=" in line:
                    match = line
                    break
            if not match:
                continue
            raw_name = match.split("filename=", 1)[1].strip().strip('"')
            name = safe_name(urllib.parse.unquote(raw_name))
            dest = unique_path(SHARE_DIR / name)
            dest.write_bytes(data)
            saved.append(dest.name)
        return saved


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix, parent = path.stem, path.suffix, path.parent
    for idx in range(2, 1000):
        candidate = parent / f"{stem} ({idx}){suffix}"
        if not candidate.exists():
            return candidate
    return parent / f"{stem}-{secrets.token_hex(4)}{suffix}"


def main() -> None:
    SHARE_DIR.mkdir(parents=True, exist_ok=True)
    ip, http_url, https_url = current_urls()
    try:
        cert, key = ensure_cert(ip)
        tls = ThreadingHTTPServer(("0.0.0.0", HTTPS_PORT), Handler)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=str(cert), keyfile=str(key))
        tls.socket = ctx.wrap_socket(tls.socket, server_side=True)
        threading.Thread(target=tls.serve_forever, daemon=True).start()
        print(f"HTTPS: {https_url}/?p={PIN}")
    except Exception as exc:
        print(f"HTTPS не поднялся: {exc}")
        https_url = http_url
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"HTTP:  {http_url}/?p={PIN}")
    print(f"Папка: {SHARE_DIR}")
    print(f"Код: {PIN}")
    threading.Timer(0.4, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}/?p={PIN}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nСтоп")


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent)
    main()
