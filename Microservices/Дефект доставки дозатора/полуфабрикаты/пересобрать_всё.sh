#!/bin/bash
# Полная пересборка готовых материалов из исходного фото.
# Запуск:  bash пересобрать_всё.sh
set -e
cd "$(dirname "$0")"
PHOTO="../1794635603887.jpg"
OUT="../готовые"
mkdir -p "$OUT" кропы

echo "== 1/6. Слои визуализации (снятие плёнки, рельеф, края) =="
bash сделать_усиление.sh >/dev/null

echo "== 2/6. Поиск и трассировка трещины (black-hat) =="
swift crack_detect.swift "$PHOTO" кропы/overlay_crack.png | tail -12
swift trace_crack.swift "$PHOTO" 2740 1760 300 700 crack_points.json кропы/mask_region.png

echo "== 3/6. Кадры: выноска, макро ×4, кадры для ролика =="
swift compose.swift "$PHOTO" crack_points.json "$OUT"
mkdir -p кадры_ролика
mv -f "$OUT/03_кадр_макро_1080.png" "$OUT/04_кадр_с_выноской_1080.png" кадры_ролика/

echo "== 4/6. Ролик с выноской (13,4 с) =="
ffmpeg -y -loglevel error -loop 1 -t 4 -i "кадры_ролика/04_кадр_с_выноской_1080.png" -i "$PHOTO" \
  -loop 1 -t 5 -i "кадры_ролика/03_кадр_макро_1080.png" \
  -filter_complex "[0:v]scale=1080:1440,setsar=1,fps=30,format=yuv420p[v0];\
[1:v]zoompan=z='1+(7.84-1)*on/180':x='max(0,min(iw-iw/zoom,2876-iw/zoom/2))':y='max(0,min(ih-ih/zoom,1951-ih/zoom/2))':d=180:s=1080x1440:fps=30,setsar=1,format=yuv420p[v1];\
[2:v]scale=1080:1440,setsar=1,fps=30,format=yuv420p[v2];\
[v0][v1]xfade=transition=fade:duration=0.8:offset=3.2[x1];\
[x1][v2]xfade=transition=fade:duration=0.8:offset=8.4,fade=t=in:st=0:d=0.5,fade=t=out:st=12.9:d=0.5,format=yuv420p[out]" \
  -map "[out]" -c:v libx264 -preset medium -crf 20 -movflags +faststart "$OUT/05_ролик_с_выноской.mp4"

echo "== 5/6. PDF-приложение (2 страницы A4) =="
TMP=$(mktemp -d)
sips -Z 1800 "$OUT/01_трещина_на_кадре_с_выноской.png" --out "$TMP/p1.png" >/dev/null
sips -Z 1800 "$OUT/02_макро_трещина_x4.png" --out "$TMP/p2.png" >/dev/null
swift pdf.swift "$OUT/06_приложение_к_претензии.pdf" "$TMP/p1.png" "$TMP/p2.png" >/dev/null
rm -rf "$TMP"

echo "== 6/6. Автономный визуализатор (все фото внутри) =="
python3 сделать_офлайн.py | tail -2

echo
echo "Готово. Результаты: $(cd "$OUT" && pwd)"
ls -1 "$OUT"
