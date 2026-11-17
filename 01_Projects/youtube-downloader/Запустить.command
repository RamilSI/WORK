#!/bin/bash
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
# Deno рядом с программой (на Air его нет в Homebrew)
if [ -x "$PWD/deno" ]; then
  export PATH="$PWD:$PATH"
fi
if [ -x "$HOME/Desktop/deno" ]; then
  export PATH="$HOME/Desktop:$PATH"
  if [ -d /opt/homebrew/bin ] && [ ! -x /opt/homebrew/bin/deno ]; then
    cp "$HOME/Desktop/deno" /opt/homebrew/bin/deno 2>/dev/null || true
    chmod +x /opt/homebrew/bin/deno 2>/dev/null || true
  fi
fi

PY=""
for candidate in /opt/homebrew/bin/python3.14 /opt/homebrew/bin/python3.12 /usr/local/bin/python3.14 "$(command -v python3.14 2>/dev/null)"; do
  [ -n "$candidate" ] && [ -x "$candidate" ] || continue
  if "$candidate" -c "import tkinter" 2>/dev/null; then
    PY="$candidate"
    break
  fi
done

if [ -z "$PY" ]; then
  osascript -e 'display dialog "Сначала запусти «Установить.command» в этой же папке.\nНужны Python, yt-dlp и ffmpeg." buttons {"OK"} default button 1 with title "Скачать видео"'
  exit 1
fi

pkill -f "youtube_downloader.py" 2>/dev/null || true
sleep 0.3

exec "$PY" youtube_downloader.py
