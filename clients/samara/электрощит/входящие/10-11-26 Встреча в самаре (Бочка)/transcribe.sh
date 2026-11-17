#!/bin/bash
# Распознавание речи через whisper.cpp (локально, офлайн)
# Использование: ./transcribe.sh <путь-к-аудио>
set -euo pipefail

MODEL="/Users/ramil/.cache/whisper-cpp/ggml-large-v3-turbo.bin"
OUT_DIR="/Users/ramil/Documents/WORK"

# Файл задаётся wildcard'ом, чтобы обойти проблему
# юникод-нормализации имён файлов в macOS (NFC vs NFD)
if [ $# -ge 1 ]; then
  SRC=$(ls "$1")
else
  SRC=$(ls /Users/ramil/Downloads/Стандартная*2.mp3)
fi

echo ">>> Источник: $SRC"
echo ">>> Модель:   $MODEL"
echo ">>> Начало:   $(date '+%H:%M:%S')"

whisper-cli \
  -m "$MODEL" \
  -f "$SRC" \
  -l auto \
  -t 8 \
  -bs 5 \
  -pp \
  -np \
  -otxt \
  -osrt \
  -of "$OUT_DIR/транскрипция_$(basename "${SRC%.*}" | tr ' ' '_')"

echo ">>> Готово:   $(date '+%H:%M:%S')"
ls -lh "$OUT_DIR"/транскрипция_*
