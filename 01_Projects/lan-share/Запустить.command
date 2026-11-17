#!/bin/bash
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
exec /opt/homebrew/bin/python3.14 lan_share.py
