#!/bin/bash
# Готовит «усиленные» копии фото дефекта для визуального разбора трещины.
# Требуется ffmpeg (brew install ffmpeg). Запуск:  bash сделать_усиление.sh
set -e
cd "$(dirname "$0")"
SRC="../1794635603887.jpg"
OUT="."

echo "== 1. Усиление рельефа (контраст + unsharp) =="
ffmpeg -y -loglevel error -i "$SRC" -frames:v 1 \
  -vf "eq=contrast=1.12:brightness=0.02:saturation=0.85,unsharp=7:7:1.5:7:7:0.5" \
  "$OUT/01_усиление_рельефа.png"

echo "== 2. Краевая карта (трещины/царапины как линии) =="
ffmpeg -y -loglevel error -i "$SRC" -frames:v 1 \
  -vf "format=gray,edgedetect=low=0.02:high=0.09" \
  "$OUT/02_краевая_карта.png"

echo "== 3. Виртуальное «снятие плёнки»: подавление блика (гомоморфное деление) =="
ffmpeg -y -loglevel error -i "$SRC" -frames:v 1 \
  -vf "curves=all='0/0 0.45/0.46 0.7/0.70 0.85/0.78 1/0.86',eq=contrast=1.22:saturation=0.85,unsharp=5:5:1.2:5:5:0.3" \
  "$OUT/03_снятие_плёнки_подавление_блика.png"

echo "== 3b. Рельеф (high-pass / «оттиск» поверхности) =="
ffmpeg -y -loglevel error -i "$SRC" -frames:v 1 \
  -filter_complex "[0:v]format=gray,split[a][b];[b]gblur=sigma=8[c];[a][c]blend=all_mode=subtract,lutyuv=y='clip(val+128,0,255)',eq=contrast=2.6" \
  "$OUT/07_рельеф_highpass.png"

echo "== 4. Зона-кандидат по описанию претензии (справа и выше центра, край аппарата) =="
ffmpeg -y -loglevel error -i "$SRC" -frames:v 1 \
  -vf "crop=1500:1500:1520:820,scale=1500:1500,eq=contrast=1.1,unsharp=7:7:1.3:7:7:0.4" \
  "$OUT/04_зона_кандидат_верх_справа.png"

echo "== 5. Полный размер, уменьшенная копия для отчёта =="
ffmpeg -y -loglevel error -i "$SRC" -frames:v 1 -vf "scale=1400:-1" "$OUT/05_обзор_1400.png"

echo "Готово. Файлы в: $(pwd)"
ls -1 "$OUT"
