#!/opt/homebrew/bin/python3.14
"""Забрать googlevideo из открытой вкладки Chrome и скачать."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from youtube_downloader import FFMPEG, SUPPORT_DIR, chrome_youtube_media, _safe_name

LOG = SUPPORT_DIR / "last_run.log"
OUT_DIR = Path.home() / "Downloads"
HINT = sys.argv[1] if len(sys.argv) > 1 else "BEEvTpKOGnA"


def _log(line: str) -> None:
    print(line, flush=True)
    try:
        prev = LOG.read_text(encoding="utf-8") if LOG.exists() else ""
        LOG.write_text(prev + line + "\n", encoding="utf-8")
    except OSError:
        pass


def _curl(url: str, dest: Path, referer: str) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "/usr/bin/curl",
        "-L",
        "-C",
        "-",
        "--connect-timeout",
        "20",
        "--max-time",
        "900",
        "-A",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "-e",
        referer,
        "-o",
        str(dest),
        url,
    ]
    _log("$ " + " ".join(cmd[:8]) + " …")
    return subprocess.call(cmd)


def main() -> int:
    SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    LOG.write_text(f"chrome-grab {HINT}\n", encoding="utf-8")
    _log("Ищу поток в Chrome…")
    try:
        video, audio, title = chrome_youtube_media(HINT)
    except Exception as exc:
        _log(f"Chrome: {exc}")
        return 1
    name = _safe_name(title or HINT)
    _log(f"Название: {title}")
    video_path = OUT_DIR / f"{name}.mp4"
    referer = f"https://www.youtube.com/watch?v={HINT}" if len(HINT) == 11 else HINT
    code = _curl(video, video_path, referer)
    if code != 0:
        _log(f"curl video exit {code}")
        return code
    if audio:
        audio_path = OUT_DIR / f"{name}.audio.mp4"
        if _curl(audio, audio_path, referer) == 0 and audio_path.exists():
            merged = OUT_DIR / f"{name}-ok.mp4"
            ff = FFMPEG if Path(FFMPEG).exists() else "ffmpeg"
            merge = [ff, "-y", "-i", str(video_path), "-i", str(audio_path), "-c", "copy", str(merged)]
            _log("$ ffmpeg merge")
            if subprocess.call(merge) == 0 and merged.exists():
                video_path.unlink(missing_ok=True)
                audio_path.unlink(missing_ok=True)
                merged.rename(video_path)
    _log(f"Готово: {video_path} ({video_path.stat().st_size if video_path.exists() else 0})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
