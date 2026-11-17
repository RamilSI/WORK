#!/bin/bash
# Второй Mac. Запускать в своём окне Терминала: пароль администратора спросит macOS.
set -euo pipefail
export HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_ENV_HINTS=1

if ! command -v brew >/dev/null; then
  echo "Сначала поставьте Homebrew: https://brew.sh"
  exit 1
fi

brew install syncthing
brew install --cask kde-connect

pkg="$HOME/Downloads/Tailscale-1.104.7-macos.pkg"
curl -fL -o "$pkg" "https://pkgs.tailscale.com/stable/Tailscale-1.104.7-macos.pkg"
sudo /usr/sbin/installer -pkg "$pkg" -target /

mkdir -p "$HOME/Hub/Inbox"
brew services start syncthing
sleep 2
syncthing cli config folders add --id=inbox --label=Inbox --path="$HOME/Hub/Inbox" --type=sendreceive || true
open -a "KDE Connect"
open -a Tailscale

echo
echo "Syncthing ID этого Mac:"
syncthing --device-id
echo "Его нужно добавить на Windows в папку Inbox."
echo "В Tailscale войдите тем же аккаунтом, что и на десктопе."
