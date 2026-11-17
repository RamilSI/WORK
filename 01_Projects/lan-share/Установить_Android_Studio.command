#!/bin/bash
set -e
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
echo "Ставлю Android Studio через Homebrew…"
echo "Если спросит пароль — это нормально."
if ! brew info --cask android-studio >/dev/null 2>&1; then
  echo "Homebrew не видит cask. Проверь, что brew работает: brew -v"
  read -r _
  exit 1
fi
brew install --cask android-studio
echo
echo "Готово. Открой Android Studio из Программ и пройди мастер установки SDK."
open -a "Android Studio" || true
read -r -p "Нажми Enter, чтобы закрыть окно… "
