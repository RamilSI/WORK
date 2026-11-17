#!/bin/bash
# Ставит Homebrew, Python с окном, yt-dlp и ffmpeg, копирует программу в «Программы».
set -e
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
APP="$HOME/Applications/Скачать видео"

echo "=== Установка «Скачать видео» ==="
echo

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew не найден — ставлю (может спросить пароль)…"
  NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  if [ -x /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
    grep -q 'brew shellenv' "$HOME/.zprofile" 2>/dev/null || echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$HOME/.zprofile"
  elif [ -x /usr/local/bin/brew ]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
fi

echo "Ставлю Python 3.14, окно tkinter, yt-dlp и ffmpeg…"
brew install python@3.14 python-tk@3.14 yt-dlp ffmpeg

PY=""
for candidate in /opt/homebrew/bin/python3.14 /usr/local/bin/python3.14; do
  if [ -x "$candidate" ] && "$candidate" -c "import tkinter" 2>/dev/null; then
    PY="$candidate"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "Python с графическим окном не завёлся. Напиши мне — разберём."
  exit 1
fi

mkdir -p "$APP"
cp -f youtube_downloader.py Запустить.command Установить.command "$APP/"
chmod +x "$APP/Запустить.command" "$APP/Установить.command"
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true

echo
echo "Готово. Программа лежит в: $APP"
echo "Запускаю…"
open "$APP/Запустить.command"
sleep 2
