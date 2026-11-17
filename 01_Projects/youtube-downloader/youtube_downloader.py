#!/opt/homebrew/bin/python3.14
"""Программа для скачивания видео с YouTube и других сайтов (через yt-dlp)."""

from __future__ import annotations

import base64
import fcntl
import http.cookiejar
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import urllib.error
import urllib.request
from html import unescape
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urljoin, urlparse, urlunparse

APP_DIR = Path(__file__).resolve().parent
SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "SkachatVideo"
LOG_FILE = SUPPORT_DIR / "last_run.log"
DOWNLOADS = Path.home() / "Downloads"
YT_DLP = shutil.which("yt-dlp") or "/opt/homebrew/bin/yt-dlp"
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"


def _find_deno() -> str:
    candidates = [
        APP_DIR / "deno",
        Path.home() / "Desktop" / "deno",
        Path.home() / "Desktop" / "Скачать видео" / "deno",
        SUPPORT_DIR / "deno",
        Path("/opt/homebrew/bin/deno"),
        Path("/usr/local/bin/deno"),
    ]
    which = shutil.which("deno")
    if which:
        candidates.insert(0, Path(which))
    for p in candidates:
        if p.exists():
            return str(p.resolve())
    return "/opt/homebrew/bin/deno"


DENO = _find_deno()

QUALITIES = {
    "Лучшее качество": "bv*+ba/b",
    "1080p": "bv*[height<=1080]+ba/b[height<=1080]/b",
    "720p": "bv*[height<=720]+ba/b[height<=720]/b",
    "480p": "bv*[height<=480]+ba/b[height<=480]/b",
    "Только аудио (MP3)": None,
}

BROWSERS = ("chrome", "vivaldi", "safari", "firefox", "brave", "edge", "chromium")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)
WATCH_SLUG = re.compile(r"^https?://(?:www\.)?shemalestube\.com/watch-([^/?#]+)", re.I)
ASHEMALETUBE = re.compile(r"^https?://(?:www\.)?ashemaletube\.com/(?:videos|embed)/(\d+)", re.I)
ABTRANNY = re.compile(
    r"^https?://(?:www\.)?(?:abtranny\.com|gettranny\.com|vid-gt\.com|upornia\.com)/videos?/(\d+)",
    re.I,
)
ABTRANNY_ALPH = "АВСDЕFGHIJKLМNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,~"
ERKISS = re.compile(
    r"^https?://(?:[\w-]+\.)?erkiss\.(?:live|club|link|com|me|co|tv)/video/(\d+)/?(?:[?#].*)?$",
    re.I,
)
COOKIE_FILE = APP_DIR / ".erkiss.cookies"
ERKISS_Q = {
    "Лучшее качество": 5,
    "1080p": 5,
    "720p": 5,
    "480p": 4,
    "Только аудио (MP3)": 4,
}
HLS_SOURCE = re.compile(
    r"""<source[^>]+src=["']([^"']+)["'][^>]*type=["']application/x-mpegURL["']"""
    r"""|<source[^>]+type=["']application/x-mpegURL["'][^>]*src=["']([^"']+)["']""",
    re.I,
)
MP4_SOURCE = re.compile(
    r"""<source[^>]+src=["']([^"']+\.mp4[^"']*)["']""",
    re.I,
)
TITLE_RE = re.compile(r"<title>([^<]+)</title>", re.I)
OG_TITLE = re.compile(
    r"""<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']+)["']"""
    r"""|<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:title["']""",
    re.I,
)


def _clean_url(url: str) -> str:
    """Убрать tracking-параметры вроде ?ref=, из-за них pornsv не отдаёт плеер."""
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    if "youtube.com" in host or "youtu.be" in host:
        return url.strip()
    return urlunparse(parsed._replace(query="", fragment=""))


_CHROME_YT_JS = r"""
(() => {
  try { document.querySelector("video")?.play(); } catch (e) {}
  const gvs = [...performance.getEntries()]
    .map((e) => e.name)
    .filter((n) => n.includes("googlevideo.com") && n.includes("videoplayback"));
  const unique = [...new Set(gvs)];
  let vid = "";
  let aud = "";
  for (const u of unique) {
    let dec = u;
    try { dec = decodeURIComponent(u); } catch (e) {}
    const isVid = /mime=video|\bvideo\/(mp4|webm)/i.test(dec);
    const isAud = /mime=audio|\baudio\/(mp4|webm|mp4a)/i.test(dec);
    if (!vid && isVid) vid = u;
    if (!aud && isAud) aud = u;
  }
  if (!vid && unique[0]) vid = unique[0];
  const sd = (window.ytInitialPlayerResponse || {}).streamingData || {};
  const all = [...(sd.formats || []), ...(sd.adaptiveFormats || [])];
  const ready = all.filter((f) => f && f.url);
  ready.sort((a, b) => (b.height || 0) - (a.height || 0));
  const combo = ready.find((f) => f.audioQuality && (f.height || 0) <= 1080 && (f.height || 0) >= 360);
  const title = (document.title || "").replace(/ - YouTube$/, "");
  return JSON.stringify({
    title: title,
    n: unique.length,
    vid: vid,
    aud: aud,
    combo: combo ? combo.url : (ready[0] && ready[0].audioQuality ? ready[0].url : ""),
  });
})()
"""


def chrome_youtube_media(watch_hint: str = "") -> tuple[str, str, str]:
    """Прямые googlevideo URL из открытой вкладки Chrome (когда yt-dlp видит geo-block)."""
    js_path = SUPPORT_DIR / "chrome_yt.js"
    SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    js_path.write_text(_CHROME_YT_JS.strip() + "\n", encoding="utf-8")
    vid_m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", watch_hint or "")
    hint = (vid_m.group(1) if vid_m else (watch_hint or "")).replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
set js to read (POSIX file "{js_path}") as «class utf8»
tell application "Google Chrome"
  if (count of windows) is 0 then return "NO_CHROME"
  repeat with w in windows
    repeat with t in tabs of w
      set u to URL of t as text
      if u contains "youtube.com/watch" then
        if "{hint}" is "" or u contains "{hint}" then
          execute t javascript "try{{document.querySelector('video').play()}}catch(e){{}}"
          delay 3
          return execute t javascript js
        end if
      end if
    end repeat
  end repeat
  repeat with w in windows
    repeat with t in tabs of w
      if (URL of t as text) contains "youtube.com/watch" then
        execute t javascript "try{{document.querySelector('video').play()}}catch(e){{}}"
        delay 3
        return execute t javascript js
      end if
    end repeat
  end repeat
end tell
return "NO_TAB"
'''
    try:
        proc = subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=40,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Chrome: {exc}") from exc
    raw = (proc.stdout or "").strip()
    if proc.returncode != 0:
        err = (proc.stderr or "").strip() or raw or "osascript"
        raise RuntimeError(err)
    if raw in ("", "NO_CHROME", "NO_TAB", "missing value"):
        raise RuntimeError("Открой этот ролик во вкладке Chrome и нажми «Скачать» ещё раз.")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Chrome вернул не JSON") from exc
    title = str(data.get("title") or "").strip()
    combo = str(data.get("combo") or "").strip()
    vid = str(data.get("vid") or "").strip()
    aud = str(data.get("aud") or "").strip()
    if combo:
        return combo, "", title
    if vid:
        return vid, aud, title
    raise RuntimeError("В Chrome нет потока. Нажми Play на ролике и скачай ещё раз.")


def _safe_name(title: str, max_bytes: int = 120) -> str:
    safe = re.sub(r'[\\/:*?"<>|]+', "_", title or "video").strip(" .") or "video"
    encoded = safe.encode("utf-8")
    if len(encoded) <= max_bytes:
        return safe
    cut = encoded[:max_bytes]
    while True:
        try:
            return cut.decode("utf-8").rstrip(" .") + "…"
        except UnicodeDecodeError:
            cut = cut[:-1]


def _curl(url: str, *, referer: str = "", timeout: int = 25, cookies: bool = False) -> str:
    cmd = [
        "/usr/bin/curl",
        "-sSL",
        "-4",
        "--connect-timeout",
        "12",
        "--max-time",
        str(timeout),
        "-A",
        USER_AGENT,
        "-e",
        referer or url,
        "-H",
        "Accept: text/html,application/json,*/*",
    ]
    if cookies:
        cmd.extend(["-b", str(COOKIE_FILE), "-c", str(COOKIE_FILE)])
    cmd.append(url)
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        err = (proc.stderr or "").strip() or f"curl exit {proc.returncode}"
        raise RuntimeError(err)
    return proc.stdout


def _fetch_html(url: str) -> str:
    return _curl(url, timeout=25, cookies=False)


def _yt_python() -> str:
    """Python для curl_cffi. На Air yt-dlp — бинарник, не скрипт с shebang."""
    try:
        with open(YT_DLP, "rb") as fh:
            first = fh.readline()
        if first.startswith(b"#!"):
            return first[2:].decode("utf-8", errors="replace").strip() or sys.executable
    except OSError:
        pass
    return sys.executable


def _impersonate_html(url: str, *, timeout: int = 30, tries: int = 5) -> str:
    """HTML как Chrome: обычный curl на ashemaletube ловит Cloudflare 403."""
    payload = json.dumps({"url": url, "timeout": timeout, "tries": tries})
    script = (
        "import json,sys,time\n"
        "from curl_cffi import requests\n"
        "req=json.load(sys.stdin)\n"
        "url=req['url']\n"
        "host=url.split('/')[2]\n"
        "last=''\n"
        "for _ in range(int(req.get('tries') or 5)):\n"
        "    r=requests.get(url, impersonate='chrome', headers={"
        "'Accept':'text/html,application/xhtml+xml,*/*;q=0.8',"
        "'Accept-Language':'en-US,en;q=0.9',"
        "'Referer': url.split('/')[0]+'//'+host+'/'"
        "}, timeout=int(req.get('timeout') or 30))\n"
        "    last=r.text\n"
        "    if r.status_code==200 and 'Just a moment' not in last:\n"
        "        sys.stdout.write(last)\n"
        "        raise SystemExit(0)\n"
        "    time.sleep(1.2)\n"
        "sys.stdout.write(last)\n"
    )
    proc = subprocess.run(
        [_yt_python(), "-c", script],
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "").strip() or "не удалось открыть сайт как браузер")
    return proc.stdout


def _player_sources(html: str) -> str:
    match = re.search(r"sources:\s*(\{(?:[^{}]|\{[^{}]*\})*\})", html)
    if not match:
        return ""
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, dict):
        return ""
    for key in ("hlsAuto", "hls", "mp4", "video"):
        val = data.get(key)
        if isinstance(val, str) and val.startswith("http"):
            return val
    for val in data.values():
        if isinstance(val, str) and val.startswith("http"):
            return val
    return ""


def _looks_hls(url: str) -> bool:
    low = url.lower()
    return ".m3u8" in low or "/media/vp/" in low or "_tpl_" in low or "media=hls" in low


def _looks_direct(url: str) -> bool:
    if _looks_hls(url):
        return False
    path = url.lower().split("?")[0]
    host = urlparse(url).netloc.lower()
    return (
        path.endswith(".mp4")
        or "/get_file/" in path
        or bool(re.match(r"d\d+\.cdn3x\.com$", host))
    )


def resolve_ashemaletube(url: str) -> tuple[str, str, str]:
    html = _impersonate_html(url)
    if "Just a moment" in html:
        raise RuntimeError("Cloudflare не пустил. Нажми «Скачать» ещё раз.")
    media = _player_sources(html)
    if not media:
        raise RuntimeError("На странице ashemaletube нет потока плеера")
    title = _page_title(html)
    vid_match = ASHEMALETUBE.search(url)
    return media, title or (f"ashemaletube-{vid_match.group(1)}" if vid_match else "video"), url


def _impersonate_json(url: str, *, referer: str, params: dict[str, str] | None = None) -> object:
    """GET JSON как Chrome — обычный curl на tubeon отвечает пустым []."""
    payload = json.dumps({"url": url, "referer": referer, "params": params or {}})
    script = (
        "import json,sys\n"
        "from curl_cffi import requests\n"
        "req=json.load(sys.stdin)\n"
        "s=requests.Session(impersonate='chrome')\n"
        "if req.get('referer'):\n"
        "    s.get(req['referer'], timeout=20)\n"
        "r=s.get(req['url'], params=req.get('params') or None, headers={"
        "'Referer': req.get('referer') or req['url'],"
        "'Origin': req['url'].split('/')[0]+'//'+req['url'].split('/')[2],"
        "'X-Requested-With': 'XMLHttpRequest',"
        "'Accept': 'application/json, text/javascript, */*; q=0.01'"
        "}, timeout=20)\n"
        "sys.stdout.write(r.text)\n"
    )
    proc = subprocess.run(
        [_yt_python(), "-c", script],
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "").strip() or "не удалось открыть сайт как браузер")
    return json.loads(proc.stdout)


def _player_config_media(html: str, page_url: str) -> tuple[str, str] | None:
    if "player_config_json" not in html:
        return None
    vid_match = re.search(r"configData:\s*\{[^}]*?\bvid:\s*(\d+)", html) or re.search(
        r"/video/(\d+)/", page_url
    )
    if not vid_match:
        return None
    parsed = urlparse(page_url)
    api = f"{parsed.scheme}://{parsed.netloc}/player_config_json/"
    data = _impersonate_json(
        api,
        referer=page_url,
        params={
            "vid": vid_match.group(1),
            "aid": "0",
            "domain_id": "0",
            "embed": "0",
            "check_speed": "0",
        },
    )
    if not isinstance(data, dict):
        return None
    files = data.get("files") or {}
    media = ""
    for key in ("4k", "hq", "lq"):
        val = files.get(key)
        if isinstance(val, str) and val.startswith("http"):
            media = val
            break
    if not media:
        return None
    return media, str(data.get("title") or "")


def _page_title(html: str) -> str:
    match = OG_TITLE.search(html) or TITLE_RE.search(html)
    if not match:
        return ""
    raw = next((group for group in match.groups() if group), "")
    title = unescape(raw).split(" | ")[0].strip()
    return re.sub(r"\s+", " ", title)


def _hls_from_html(html: str, page_url: str) -> str:
    match = HLS_SOURCE.search(html)
    if not match:
        return ""
    src = next((group for group in match.groups() if group), "")
    return urljoin(page_url, unescape(src)) if src else ""


def _base164_decode(text: str) -> str:
    cleaned = re.sub(r"[^АВСЕМA-Za-z0-9.,~]", "", text)
    out: list[str] = []
    pos = 0
    length = len(cleaned)

    def take() -> int:
        nonlocal pos
        if pos >= length:
            return 64
        idx = ABTRANNY_ALPH.find(cleaned[pos])
        pos += 1
        return 64 if idx < 0 else idx

    while pos < length:
        first, second, third, fourth = take(), take(), take(), take()
        out.append(chr(((first << 2) | (second >> 4)) & 255))
        if third != 64:
            out.append(chr((((15 & second) << 4) | (third >> 2)) & 255))
        if fourth != 64:
            out.append(chr((((3 & third) << 6) | fourth) & 255))
    return "".join(out)


def resolve_abtranny(url: str, quality_label: str) -> tuple[str, str, str]:
    vid_match = ABTRANNY.search(url)
    if not vid_match:
        raise RuntimeError("Нет id видео abtranny")
    vid = int(vid_match.group(1))
    million = 1_000_000 * (vid // 1_000_000)
    thousand = 1_000 * (vid // 1_000)
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host == "vid-gt.com":
        host = "gettranny.com"
    hosts = [host]
    if host == "gettranny.com":
        hosts.append("vid-gt.com")
    title = f"video-{vid}"
    files = None
    page = ""
    last_error = "сайт не ответил"
    path_prefix = "/videos/" if "/videos/" in parsed.path.lower() else "/video/"
    for host in hosts:
        base = f"{parsed.scheme}://{host}"
        page = f"{base}{path_prefix}{vid}/"
        try:
            files = json.loads(
                _curl(
                    f"{base}/api/videofile.php?video_id={vid}&lifetime=8640000",
                    referer=page,
                    timeout=40,
                )
            )
        except (RuntimeError, json.JSONDecodeError, TypeError) as exc:
            last_error = str(exc)
            continue
        if isinstance(files, list) and files:
            try:
                meta = json.loads(
                    _curl(
                        f"{base}/api/json/video/86400/{million}/{thousand}/{vid}.json",
                        referer=page,
                        timeout=20,
                    )
                )
                title = str((meta.get("video") or {}).get("title") or title)
            except (RuntimeError, json.JSONDecodeError, TypeError, OSError):
                pass
            break
        files = None
    if not isinstance(files, list):
        raise RuntimeError(
            f"{last_error}. Если включён VPN — выключи его и нажми «Скачать» ещё раз."
        )
    prefer = ("_fhd.mp4", ".mp4", "_sd")
    if quality_label == "480p":
        prefer = (".mp4", "_sd", "_fhd.mp4")
    chosen = None
    for fmt in prefer:
        chosen = next((item for item in files if item.get("format") == fmt and item.get("video_url")), None)
        if chosen:
            break
    if not chosen:
        chosen = next((item for item in files if item.get("format") != "_tr.mp4" and item.get("video_url")), None)
    if not chosen:
        raise RuntimeError("На abtranny нет видеофайла")
    path = _base164_decode(str(chosen["video_url"]))
    if not path.startswith("/"):
        path = "/" + path
    return urljoin(base + "/", path.lstrip("/")), title, page


def resolve_erkiss(url: str, quality_label: str) -> tuple[str, str, str]:
    """Достать прямую mp4-ссылку с CDN, не читая всю страницу через yt-dlp."""
    html = _curl(url, referer=url, timeout=25, cookies=True)
    title = _page_title(html)
    sid_match = re.search(r'data-sid="([^"]+)"', html)
    vid_match = re.search(r'data-vid="(\d+)"', html) or ERKISS.search(url)
    if not sid_match or not vid_match:
        raise RuntimeError("На странице нет sid/vid плеера")
    sid = sid_match.group(1)
    vid = vid_match.group(1)
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    listing = json.loads(_curl(f"{base}/api/get_video_list?vid={vid}&sid={sid}", referer=url, cookies=True))
    available = {int(item[0]): item[1] for item in listing.get("files") or [] if item}
    if not available:
        raise RuntimeError("Сайт не отдал список качеств")
    wanted = ERKISS_Q.get(quality_label, 5)
    quality = wanted if wanted in available else max(available)

    parts = json.loads(
        _curl(f"{base}/api/get_video_file?vid={vid}&sid={sid}&q={quality}", referer=url, cookies=True)
    )
    if not isinstance(parts, list) or len(parts) < 7:
        raise RuntimeError("Сайт не отдал файл")
    media = (
        f"https://v{parts[0]}.erocdn.com/0/{parts[2]}/{parts[3]}/"
        f"{parts[6]}/{parts[1]}/{parts[5]}.mp4"
    )
    return media, title or f"erkiss-{vid}", url


def resolve_media(url: str, *, scrape: bool = False) -> tuple[str, str, str]:
    """Вернуть (ссылка_на_поток, название, referer)."""
    parsed = urlparse(url)
    slug_match = WATCH_SLUG.match(url)
    if slug_match:
        slug = slug_match.group(1)
        media = f"{parsed.scheme}://{parsed.netloc}/media/vp/{slug}/auto"
        title = slug.replace("---", " — ").replace("-", " ").strip()
        if not scrape:
            return media, title, url
        try:
            html = _fetch_html(url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return media, title, url
        return _hls_from_html(html, url) or media, _page_title(html) or title, url

    if not scrape:
        return url, "", url
    try:
        html = _fetch_html(url)
    except (urllib.error.URLError, TimeoutError, OSError, RuntimeError):
        html = ""
    title = _page_title(html)
    if not html or "Just a moment" in html or title.lower() in {"just a moment.", "just a moment"}:
        try:
            html = _impersonate_html(url)
            title = _page_title(html)
        except (RuntimeError, OSError, UnicodeDecodeError):
            return url, title, url
    sources = _player_sources(html)
    if sources:
        return sources, title, url
    hls = _hls_from_html(html, url)
    if hls:
        return hls, title, url
    try:
        cfg = _player_config_media(html, url)
    except (RuntimeError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        cfg = None
    if cfg:
        media, cfg_title = cfg
        return media, cfg_title or title, url
    kvs = _kvs_from_html(html, url)
    if kvs:
        return kvs, title, url
    mp4 = _mp4_from_html(html, url)
    if mp4:
        return mp4, title, url
    flow = _flowplayer_from_html(html)
    if flow:
        return flow, title, url
    vurl = _v_url_from_html(html)
    if vurl:
        return vurl, title, url
    embed = _embed_from_html(html, url)
    if embed:
        return embed, title, url
    return url, title, url


def _kvs_from_html(html: str, page_url: str) -> str:
    match = re.search(r"\bvideo_url:\s*'([^']+)'", html)
    if not match:
        return ""
    src = unescape(match.group(1)).strip()
    # KVS: function/0/https://… — хеш без лицензии даёт 404, пусть yt-dlp сам расшифрует страницу.
    if src.startswith("function/"):
        return ""
    if not src or "play-vva" in src or src.endswith("/play-vvap/") or src.endswith("/play-vvad/"):
        return ""
    return urljoin(page_url, src)


def _embed_from_html(html: str, page_url: str) -> str:
    """pornoland.baby и похожие: видео не на странице, а в iframe /embed/."""
    page = urlparse(page_url)
    page_key = (page.netloc.lower(), page.path.rstrip("/").lower())
    for match in re.finditer(
        r"""<iframe[^>]+(?:src|data-src)=["']([^"']+)["']""",
        html,
        re.I,
    ):
        src = unescape(match.group(1)).strip()
        if not src or src.startswith(("about:", "javascript:", "data:")):
            continue
        low = src.lower()
        if any(skip in low for skip in ("googletag", "doubleclick", "toplist", "adsystem", "exoclick")):
            continue
        abs_url = urljoin(page_url, src)
        parsed = urlparse(abs_url)
        path = parsed.path.lower()
        if "/embed/" not in path and not path.startswith("/embed"):
            continue
        if (parsed.netloc.lower(), path.rstrip("/")) == page_key:
            continue
        return abs_url
    return ""


def _mp4_from_html(html: str, page_url: str) -> str:
    match = MP4_SOURCE.search(html)
    if not match:
        return ""
    return urljoin(page_url, unescape(match.group(1)))


def _flowplayer_from_html(html: str) -> str:
    """xxxdan / cdn3x: sources.push({type:'video/mp4',src:'https://d02.cdn3x.com/...'}) без .mp4."""
    match = re.search(
        r"sources\.push\(\s*\{[^}]*?\bsrc:\s*['\"](https?://[^'\"]+)['\"]",
        html,
        re.I,
    )
    if match:
        return match.group(1)
    match = re.search(
        r"type:\s*['\"]video/mp4['\"][^}]*?\bsrc:\s*['\"](https?://[^'\"]+)['\"]",
        html,
        re.I,
    )
    return match.group(1) if match else ""


def _v_url_from_html(html: str) -> str:
    """besttrannytube и похожие: var V_URL = 'base64...'."""
    match = re.search(r"""\bV_URL\s*=\s*['"]([A-Za-z0-9+/=]+)['"]""", html)
    if not match:
        return ""
    try:
        decoded = base64.b64decode(match.group(1)).decode("utf-8", errors="replace").strip()
    except (ValueError, OSError):
        return ""
    return decoded if decoded.startswith("http") else ""


def _exit_country() -> str:
    """Страна, которую сейчас видит интернет (VPN или провайдер)."""
    try:
        req = urllib.request.Request(
            "https://ipinfo.io/country",
            headers={"User-Agent": USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            return resp.read().decode("utf-8", "replace").strip().upper()[:2]
    except OSError:
        return ""


def explain_error(text: str) -> str:
    error_lines = [
        line
        for line in text.splitlines()
        if line.lstrip().lower().startswith("error")
        or line.lstrip().lower().startswith("ошибка")
    ]
    low = "\n".join(error_lines).lower()
    if "sign in to confirm you're not a bot" in low or "not a bot" in low:
        return (
            "YouTube решил, что это бот. Включи «Cookies браузера», выбери Chrome "
            "и попробуй снова. Если включён VPN — выключи его."
        )
    if "requested format is not available" in low:
        return "Такого качества нет. Выбери «Лучшее качество» и скачай ещё раз."
    if "private video" in low:
        return "Видео приватное, скачать нельзя."
    if (
        "not made this video available in your country" in low
        or "not available in your country" in low
        or "video unavailable" in low
        or "this video is unavailable" in low
    ):
        country = _exit_country()
        if country and country != "RU":
            return (
                f"YouTube видит {country} — это VPN. Ролик в этой стране закрыт "
                "(российские сериалы часто только из РФ). "
                "Выключи Amnezia и нажми «Скачать» ещё раз."
            )
        if country == "RU":
            return (
                "YouTube закрыл этот ролик для России. Включи Amnezia "
                "(не Казахстан-датацентр) и нажми «Скачать» ещё раз."
            )
        return (
            "YouTube не отдаёт ролик по стране. Если VPN включён — выключи и попробуй снова. "
            "Если уже выключен — наоборот включи Amnezia."
        )
    if "http error 403" in low or "403: forbidden" in low:
        return "YouTube отклонил запрос (часто из‑за VPN). Выключи VPN или включи cookies Chrome."
    if "could not be decrypted" in low or "extracted 0 cookies" in low:
        return (
            "Chrome не отдал cookies (связка ключей). Закрой Chrome, в окне связки нажми Allow, "
            "либо в программе выбери Safari. Amnezia должна быть включена на весь трафик, не только браузер."
        )
    if "could not copy" in low or "could not find" in low and "cookie" in low:
        return (
            "Не удалось прочитать cookies браузера. Для Chrome нажми Allow в окне связки ключей. "
            "Для Safari дай Терминалу доступ к диску в Настройках → Конфиденциальность."
        )
    if "confirm your age" in low or "age-restricted" in low:
        return "Видео с ограничением по возрасту. Включи cookies браузера, где ты залогинен на YouTube."
    if "file name too long" in low or "errno 63" in low:
        return "Слишком длинное имя файла. Нажми «Скачать» ещё раз — имя теперь короче."
    if (
        "read timed out" in low
        or "operation timed out" in low
        or "connection timed out" in low
        or "curl exit 28" in low
    ):
        return (
            "Сайт не открывается с этого Мак (таймаут). "
            "Если включён VPN — выключи и нажми «Скачать» ещё раз."
        )
    if "connection refused" in low or "connection reset" in low or "bytes read" in low:
        return (
            "CDN оборвал качание. Нажми «Скачать» ещё раз — докачает с того же места. "
            "Если снова сбросит, выключи VPN."
        )
    if "extracted extension" in low or "unusual and will be skipped" in low:
        return "Сайт прячет файл за .php. Нажми «Скачать» ещё раз — теперь сохраняется как обычный MP4."
    if "unsupported url" in low:
        return "Этот сайт yt-dlp сам не знает. Если это страница с плеером — попробуй ещё раз, программа ищет поток на странице."
    if "ffmpeg" in low and ("not found" in low or "не найден" in low):
        return "Не найден ffmpeg. В терминале: brew install ffmpeg"
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped.lower().startswith("error"):
            return stripped
    return "Не получилось скачать. Текст ошибки — в логе внизу."


class YouTubeDownloader(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Скачать видео · 7")
        self.geometry("740x580")
        self.minsize(640, 480)

        self.url = tk.StringVar()
        self.folder = tk.StringVar(value=str(DOWNLOADS))
        self.quality = tk.StringVar(value="1080p")
        self.browser = tk.StringVar(value="chrome")
        self.use_cookies = tk.BooleanVar(value=True)
        self.whole_playlist = tk.BooleanVar(value=False)

        self._proc: subprocess.Popen[str] | None = None
        self._log_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._busy = False
        self._lines: list[str] = []
        self._log_count = 0

        self._build()
        self.after(80, self._drain_log)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self) -> None:
        pad = {"padx": 14, "pady": 6}
        root = ttk.Frame(self, padding=16)
        root.pack(fill=tk.BOTH, expand=True)

        ttk.Label(root, text="Скачать видео", font=("Helvetica", 16, "bold")).pack(
            anchor=tk.W, pady=(0, 10)
        )

        ttk.Label(root, text="Ссылка на видео или плейлист").pack(anchor=tk.W)
        url_row = ttk.Frame(root)
        url_row.pack(fill=tk.X, **pad)
        url_entry = ttk.Entry(url_row, textvariable=self.url)
        url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        url_entry.focus_set()
        ttk.Button(url_row, text="Вставить", command=self._paste).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(root, text="Папка сохранения").pack(anchor=tk.W)
        folder_row = ttk.Frame(root)
        folder_row.pack(fill=tk.X, **pad)
        ttk.Entry(folder_row, textvariable=self.folder).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(folder_row, text="Выбрать…", command=self._pick_folder).pack(side=tk.LEFT, padx=(8, 0))

        opts = ttk.Frame(root)
        opts.pack(fill=tk.X, **pad)

        ttk.Label(opts, text="Качество").pack(side=tk.LEFT)
        ttk.Combobox(
            opts,
            textvariable=self.quality,
            values=list(QUALITIES),
            state="readonly",
            width=22,
        ).pack(side=tk.LEFT, padx=(8, 18))

        ttk.Checkbutton(opts, text="Весь плейлист", variable=self.whole_playlist).pack(side=tk.LEFT)

        cookies = ttk.Frame(root)
        cookies.pack(fill=tk.X, **pad)
        ttk.Checkbutton(
            cookies,
            text="Cookies браузера (если YouTube просит войти)",
            variable=self.use_cookies,
        ).pack(side=tk.LEFT)
        ttk.Combobox(
            cookies,
            textvariable=self.browser,
            values=BROWSERS,
            state="readonly",
            width=10,
        ).pack(side=tk.LEFT, padx=(8, 0))

        btns = ttk.Frame(root)
        btns.pack(fill=tk.X, pady=(8, 8))
        self.download_btn = ttk.Button(btns, text="Скачать", command=self._start)
        self.download_btn.pack(side=tk.LEFT)
        self.cancel_btn = ttk.Button(btns, text="Стоп", command=self._cancel, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(btns, text="Открыть папку", command=self._open_folder).pack(side=tk.LEFT, padx=(8, 0))

        self.status = ttk.Label(root, text="Готово. Вставь ссылку и нажми «Скачать».")
        self.status.pack(anchor=tk.W, pady=(0, 6))

        self.progress = ttk.Progressbar(root, mode="determinate", maximum=100)
        self.progress.pack(fill=tk.X, pady=(0, 8))

        log_frame = ttk.Frame(root)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log = tk.Text(log_frame, height=14, wrap=tk.WORD, font=("Menlo", 11))
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set, state=tk.DISABLED)
        self.log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Label(
            root,
            text="YouTube, HLS-сайты вроде shemalestube и ещё ~1700 площадок. Скачивай только разрешённое.",
            foreground="#666",
        ).pack(anchor=tk.W, pady=(8, 0))

    def _paste(self) -> None:
        try:
            text = self.clipboard_get().strip()
        except tk.TclError:
            return
        if text:
            self.url.set(text)

    def _pick_folder(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.folder.get() or str(DOWNLOADS))
        if chosen:
            self.folder.set(chosen)

    def _open_folder(self) -> None:
        folder = Path(self.folder.get()).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["open", str(folder)])

    def _append(self, text: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self._log_count += 1
        if self._log_count > 250:
            self.log.delete("1.0", "80.0")
            self._log_count = 170
        self.log.insert(tk.END, text)
        if not text.endswith("\n"):
            self.log.insert(tk.END, "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _drain_log(self) -> None:
        try:
            for _ in range(80):
                kind, line = self._log_queue.get_nowait()
                if kind == "progress":
                    self._maybe_progress(line)
                else:
                    self._append(line)
                    self._maybe_progress(line)
        except queue.Empty:
            pass
        self.after(120, self._drain_log)

    def _maybe_progress(self, line: str) -> None:
        if "[download]" not in line or "%" not in line:
            return
        for part in line.replace("%", "% ").split():
            if part.endswith("%"):
                try:
                    value = float(part[:-1])
                except ValueError:
                    continue
                if 0 <= value <= 100:
                    self.progress["value"] = value
                    self.status.configure(text=line.replace("[download]", "").strip()[:90])
                    return

    def _start(self) -> None:
        url = self.url.get().strip()
        if not url:
            messagebox.showinfo("Нет ссылки", "Вставь ссылку на видео.")
            return
        if not Path(YT_DLP).exists():
            messagebox.showerror("Нет yt-dlp", "Не найден yt-dlp. Установи: brew install yt-dlp")
            return
        if not Path(FFMPEG).exists():
            messagebox.showerror("Нет ffmpeg", "Не найден ffmpeg. Установи: brew install ffmpeg")
            return

        folder = Path(self.folder.get()).expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Папка", f"Не удалось создать папку:\n{exc}")
            return

        self._set_busy(True)
        self.progress["value"] = 0
        self.status.configure(text="Скачиваю…")
        thread = threading.Thread(target=self._run, args=(url, folder), daemon=True)
        thread.start()

    def _build_command(
        self,
        url: str,
        folder: Path | str,
        *,
        use_cookies: bool,
        title: str = "",
        referer: str = "",
        is_hls: bool = False,
        is_direct: bool = False,
    ) -> list[str]:
        quality = self.quality.get()
        audio_only = QUALITIES.get(quality) is None
        folder = Path(folder).expanduser()
        if is_direct and not audio_only:
            output = str(folder / f"{_safe_name(title or 'video')}.mp4")
        elif title:
            output = str(folder / f"{_safe_name(title)}.%(ext)s")
        elif self.whole_playlist.get():
            output = str(folder / "%(playlist_index)03d - %(title).80B [%(id).40B].%(ext)s")
        else:
            output = str(folder / "%(title).80B [%(id).40B].%(ext)s")

        if is_direct:
            fmt = "b"
        elif is_hls:
            fmt = "b/bv*+ba"
        else:
            fmt = QUALITIES[quality]
        youtube = "youtube.com" in url.lower() or "youtu.be" in url.lower()
        cmd = [
            YT_DLP,
            "--no-color",
            "--newline",
            "--no-mtime",
            "--no-update",
            "--no-warnings",
            "--retries",
            "8",
            "--fragment-retries",
            "8",
            "--socket-timeout",
            "30",
            "--buffer-size",
            "32K",
            "--trim-filenames",
            "180",
            "--ffmpeg-location",
            str(Path(FFMPEG).parent),
            "-o",
            output,
        ]
        if not youtube:
            cmd.extend(["--force-ipv4", "--add-header", f"User-Agent:{USER_AGENT}"])
        if not is_direct:
            cmd.extend(["--concurrent-fragments", "16", "--http-chunk-size", "10M"])
        if referer:
            cmd.extend(["--referer", referer])
        if (
            is_direct
            or "erocdn.com" in url
            or "erkiss." in url
            or "abtranny.com" in url
            or "ashemaletube.com" in url
            or "cdn3x.com" in url
            or "cdnvideos.pro" in url
            or "gettranny.com" in url
            or "vid-gt.com" in url
            or "ahcdn.com" in url
            or "upornia.com" in url
        ):
            cmd.append("--no-check-certificate")
        if is_direct:
            cmd.extend(["--compat-options", "allow-unsafe-ext"])
        if youtube:
            cmd.extend(
                [
                    "--extractor-args",
                    "youtube:player_client=web,android,ios;player_skip=webpage",
                    "--impersonate",
                    "chrome",
                ]
            )
            if Path(DENO).exists():
                cmd.extend(["--js-runtimes", f"deno:{DENO}"])
        elif not is_direct:
            cmd.extend(["--impersonate", "chrome"])

        if self.whole_playlist.get():
            cmd.append("--yes-playlist")
        else:
            cmd.append("--no-playlist")

        if audio_only:
            cmd.extend(["-x", "--audio-format", "mp3", "--audio-quality", "0"])
        elif fmt:
            cmd.extend(["-f", fmt, "--merge-output-format", "mp4"])

        if use_cookies:
            cmd.extend(["--cookies-from-browser", self.browser.get()])

        cmd.append(url)
        return cmd

    def _run_once(self, cmd: list[str]) -> int:
        env = os.environ.copy()
        env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + env.get("PATH", "")
        self._log("\n$ " + " ".join(cmd))
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        assert self._proc.stdout is not None
        for line in self._proc.stdout:
            self._log(line.rstrip())
        code = self._proc.wait()
        self._proc = None
        return code

    def _log(self, line: str) -> None:
        self._lines.append(line)
        kind = "progress" if "[download]" in line and "%" in line else "line"
        self._log_queue.put((kind, line))

    def _run(self, url: str, folder: Path) -> None:
        self._lines = []
        is_hls = False
        is_direct = False
        try:
            url = _clean_url(url)
            self._log(url)
            media_url, title, referer = url, "", url
            scraped = False
            youtube = "youtube.com" in url.lower() or "youtu.be" in url.lower()
            if ERKISS.match(url):
                self._log("Достаю прямую ссылку с erkiss…")
                media_url, title, referer = resolve_erkiss(url, self.quality.get())
                is_direct = True
                self._log(f"Файл: {media_url}")
                if title:
                    self._log(f"Название: {title}")
            elif ABTRANNY.match(url):
                self._log("Достаю прямую ссылку…")
                media_url, title, referer = resolve_abtranny(url, self.quality.get())
                is_direct = True
                self._log(f"Файл: {media_url}")
                if title:
                    self._log(f"Название: {title}")
            elif ASHEMALETUBE.match(url):
                self._log("Обхожу Cloudflare и ищу поток ashemaletube…")
                media_url, title, referer = resolve_ashemaletube(url)
                self._log(f"Поток: {media_url}")
                if title:
                    self._log(f"Название: {title}")
            elif WATCH_SLUG.match(url):
                media_url, title, referer = resolve_media(url)
                if media_url != url:
                    self._log(f"Поток: {media_url}")
            elif "youtube.com" not in url.lower() and "youtu.be" not in url.lower():
                self._log("Ищу прямой файл на странице…")
                media_url, title, referer = resolve_media(url, scrape=True)
                scraped = True
                if media_url != url:
                    is_direct = _looks_direct(media_url)
                    self._log(f"Файл: {media_url}")
                    if title:
                        self._log(f"Название: {title}")

            is_hls = _looks_hls(media_url)
            cmd = self._build_command(
                media_url,
                folder,
                use_cookies=self.use_cookies.get(),
                title=title,
                referer=referer,
                is_hls=is_hls,
                is_direct=is_direct,
            )
            code = self._run_once(cmd)
            log_text = "\n".join(self._lines)
            if (
                code != 0
                and "unsupported url" in log_text.lower()
                and media_url == url
                and not scraped
            ):
                self._log("\nyt-dlp не знает сайт — ищу HLS/mp4 в HTML…")
                media_url, title, referer = resolve_media(url, scrape=True)
                if media_url != url:
                    is_hls = _looks_hls(media_url)
                    is_direct = _looks_direct(media_url)
                    cmd = self._build_command(
                        media_url,
                        folder,
                        use_cookies=self.use_cookies.get(),
                        title=title,
                        referer=referer,
                        is_hls=is_hls,
                        is_direct=is_direct,
                    )
                    code = self._run_once(cmd)
                    log_text = "\n".join(self._lines)
            if code != 0 and is_direct:
                self._log("\nCDN оборвал поток — докачиваю одним соединением…")
                self.after(0, lambda: self.status.configure(text="Докачиваю…"))
                code = self._curl_direct(media_url, folder, title, referer)
                log_text = "\n".join(self._lines)
            bot_block = "not a bot" in log_text.lower() or "http error 403" in log_text.lower()
            geo_block = (
                "video unavailable" in log_text.lower()
                or "not available in your country" in log_text.lower()
                or "not made this video available" in log_text.lower()
                or "use a vpn" in log_text.lower()
            )
            if code != 0 and (bot_block or geo_block):
                if not self.use_cookies.get():
                    self._log("\nYouTube не отдал ролик — повторяю с cookies Chrome…")
                    self.after(0, lambda: self.status.configure(text="Повтор с cookies Chrome…"))
                    self.after(0, lambda: self.use_cookies.set(True))
                    retry = self._build_command(
                        media_url,
                        folder,
                        use_cookies=True,
                        title=title,
                        referer=referer,
                        is_hls=is_hls,
                    )
                    code = self._run_once(retry)
                    log_text = "\n".join(self._lines)
                if code != 0 and (
                    "could not be decrypted" in log_text.lower()
                    or "extracted 0 cookies" in log_text.lower()
                ):
                    self._log("\nChrome не отдал cookies — пробую Safari…")
                    self.after(0, lambda: self.status.configure(text="Повтор с cookies Safari…"))
                    self.after(0, lambda: self.browser.set("safari"))
                    retry = self._build_command(
                        media_url,
                        folder,
                        use_cookies=True,
                        title=title,
                        referer=referer,
                        is_hls=is_hls,
                    )
                    code = self._run_once(retry)
                if code != 0 and youtube:
                    self._log("\nYouTube закрыл API — беру поток из открытого Chrome…")
                    self.after(0, lambda: self.status.configure(text="Забираю поток из Chrome…"))
                    try:
                        chrome_v, chrome_a, chrome_t = chrome_youtube_media(url)
                    except Exception as chrome_exc:
                        self._log(f"Chrome: {chrome_exc}")
                    else:
                        title = chrome_t or title
                        self._log(f"Chrome: {title or 'ролик'}")
                        cmd = self._build_command(
                            chrome_v,
                            folder,
                            use_cookies=False,
                            title=title,
                            referer=url,
                            is_direct=True,
                        )
                        code = self._run_once(cmd)
                        if code != 0:
                            code = self._curl_direct(chrome_v, folder, title, url)
                        if code == 0 and chrome_a:
                            self._log("Докачиваю звук из Chrome и склеиваю…")
                            audio_name = _safe_name((title or "video") + " audio")
                            audio_code = self._curl_direct(chrome_a, folder, audio_name, url)
                            video_path = Path(folder) / f"{_safe_name(title or 'video')}.mp4"
                            audio_path = Path(folder) / f"{audio_name}.mp4"
                            if audio_code == 0 and video_path.exists() and audio_path.exists():
                                merged = Path(folder) / f"{_safe_name(title or 'video')}-ok.mp4"
                                merge = [
                                    FFMPEG if Path(FFMPEG).exists() else "ffmpeg",
                                    "-y",
                                    "-i",
                                    str(video_path),
                                    "-i",
                                    str(audio_path),
                                    "-c",
                                    "copy",
                                    str(merged),
                                ]
                                self._log("$ " + " ".join(merge))
                                m = subprocess.run(merge, capture_output=True, text=True)
                                if m.returncode == 0 and merged.exists():
                                    video_path.unlink(missing_ok=True)
                                    audio_path.unlink(missing_ok=True)
                                    merged.rename(video_path)
        except Exception as exc:
            self._log(f"Ошибка: {exc}")
            self.after(0, lambda e=str(exc): self._finished(False, e))
            return
        finally:
            self._proc = None
            try:
                LOG_FILE.write_text("\n".join(self._lines), encoding="utf-8")
            except OSError:
                pass

        log_text = "\n".join(self._lines)
        if code == 0:
            self.after(0, lambda: self._finished(True, "Готово. Файл в выбранной папке."))
        elif code < 0:
            self.after(0, lambda: self._finished(False, "Остановлено."))
        else:
            message = explain_error(log_text)
            self.after(0, lambda m=message: self._finished(False, m))

    def _finished(self, ok: bool, text: str) -> None:
        self._set_busy(False)
        self.status.configure(text=text)
        if ok:
            self.progress["value"] = 100
            messagebox.showinfo("Скачано", text)
        elif "Остановлено" not in text:
            messagebox.showerror("Не скачалось", text)

    def _curl_direct(self, url: str, folder: Path, title: str, referer: str) -> int:
        dest = Path(folder) / f"{_safe_name(title or 'video')}.mp4"
        cmd = [
            "/usr/bin/curl",
            "-4",
            "-L",
            "-C",
            "-",
            "--connect-timeout",
            "20",
            "--max-time",
            "900",
            "--retry",
            "8",
            "--retry-delay",
            "3",
            "--retry-all-errors",
            "-A",
            USER_AGENT,
        ]
        if referer:
            cmd.extend(["-e", referer])
        cmd.extend(["-o", str(dest), url])
        return self._run_once(cmd)

    def _cancel(self) -> None:
        proc = self._proc
        if proc and proc.poll() is None:
            proc.terminate()
            self.status.configure(text="Останавливаю…")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.download_btn.configure(state=tk.DISABLED if busy else tk.NORMAL)
        self.cancel_btn.configure(state=tk.NORMAL if busy else tk.DISABLED)

    def _on_close(self) -> None:
        if self._busy:
            if not messagebox.askyesno("Скачивание", "Остановить скачивание и выйти?"):
                return
            self._cancel()
        self.destroy()


def _single_instance() -> object:
    """Одно окно: Desktop + Программы + Загрузки больше не открываются пачкой."""
    lock_dir = SUPPORT_DIR
    lock_dir.mkdir(parents=True, exist_ok=True)
    fh = open(lock_dir / "instance.lock", "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("Скачать видео", "Программа уже открыта. Оставь одно окно, лишние закрой.")
        root.destroy()
        raise SystemExit(0)
    fh.write(str(os.getpid()))
    fh.flush()
    return fh


def main() -> None:
    lock = _single_instance()
    app = YouTubeDownloader()
    app._instance_lock = lock
    app.mainloop()


if __name__ == "__main__":
    main()
