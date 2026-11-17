#!/bin/bash
set -euo pipefail
ROOT="/Users/ramil/Documents/WORK/01_Projects/Tonaly_Site"
HOST="root@46.173.19.173"

scp \
  "$ROOT/backend/main.py" \
  "$ROOT/backend/object_match.py" \
  "$ROOT/backend/eleveight.py" \
  "$ROOT/backend/kite_requests.py" \
  "$HOST:/root/tonal/backend/"

scp \
  "$ROOT/backend/templates/brochure_0607hs_velesgard.html" \
  "$ROOT/backend/templates/compare_0607hs_izolep.html" \
  "$ROOT/backend/templates/applications.html" \
  "$ROOT/backend/templates/guide.html" \
  "$ROOT/backend/templates/object.html" \
  "$ROOT/backend/templates/object_card.html" \
  "$ROOT/backend/templates/object_results.html" \
  "$ROOT/backend/templates/not_found.html" \
  "$ROOT/backend/templates/product.html" \
  "$ROOT/backend/templates/base.html" \
  "$HOST:/root/tonal/backend/templates/"

scp \
  "$ROOT/frontend/css/style.css" \
  "$HOST:/var/www/tonal/frontend/css/style.css"

scp \
  "$ROOT/frontend/docs/brochure-0607hs-velesgard.pdf" \
  "$ROOT/frontend/docs/brochure-0607hs-velesgard.html" \
  "$ROOT/frontend/docs/compare-0607hs-izolep.pdf" \
  "$HOST:/var/www/tonal/frontend/docs/"

ssh "$HOST" 'systemctl restart tonal && systemctl is-active tonal && echo OK'
echo "https://rml-s.ru/brochure/rem-pox-0607-hs-velesgard"
echo "https://rml-s.ru/docs/brochure-0607hs-velesgard.pdf"
echo "https://rml-s.ru/applications"
