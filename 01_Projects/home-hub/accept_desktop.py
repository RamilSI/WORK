#!/usr/bin/env python3
"""Принять домашний Windows-десктоп в Syncthing и запомнить его адрес Tailscale."""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

HOME = Path.home()
CONF = HOME / "Library/Application Support/Syncthing/config.xml"
STATE = HOME / "Library/Application Support/Syncthing/home-hub-desktop.json"
IP_FILE = HOME / "Hub/Inbox/desktop-tailscale-ip.txt"
KDE_CONFIG = HOME / "Library/Preferences/kdeconnect/config"
TARGET = "DESKTOP-D6P4GIH"
GUI = "http://127.0.0.1:8384"


def apikey() -> str:
    return ET.parse(CONF).findtext("gui/apikey") or ""


def pending() -> dict:
    request = urllib.request.Request(
        GUI + "/rest/cluster/pending/devices",
        headers={"X-API-Key": apikey()},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)


def cli(*args: str) -> None:
    subprocess.run(["syncthing", "cli", *args], check=True, capture_output=True, text=True)


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {}


def save_state(data: dict) -> None:
    STATE.write_text(json.dumps(data), encoding="utf-8")


def wanted(info: dict) -> bool:
    name = str(info.get("name") or "")
    address = str(info.get("address") or "")
    return TARGET in name or address.startswith("192.168.0.12:")


def accept(device_id: str) -> None:
    try:
        cli(
            "config",
            "devices",
            "add",
            f"--device-id={device_id}",
            f"--name={TARGET}",
            "--auto-accept-folders",
        )
    except subprocess.CalledProcessError:
        pass
    try:
        cli("config", "folders", "inbox", "devices", "add", f"--device-id={device_id}")
    except subprocess.CalledProcessError:
        pass


def remember_kde(ip: str) -> None:
    if not KDE_CONFIG.exists():
        return
    text = KDE_CONFIG.read_text(encoding="utf-8")
    if f"customDevices=" in text and ip in text.split("customDevices=", 1)[1].splitlines()[0]:
        return
    lines = text.splitlines()
    found = False
    for index, line in enumerate(lines):
        if line.startswith("customDevices="):
            current = [part for part in line.split("=", 1)[1].split(",") if part]
            if ip not in current:
                current.append(ip)
            lines[index] = "customDevices=" + ",".join(current)
            found = True
            break
    if not found:
        lines.append(f"customDevices={ip}")
    KDE_CONFIG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    subprocess.run(["kdeconnect", "--refresh"], check=False, capture_output=True)


def pin_tailscale(device_id: str, pinned: str) -> str:
    if not IP_FILE.exists():
        return pinned
    ip = IP_FILE.read_text(encoding="utf-8").strip()
    if not ip.startswith("100.") or ip == pinned:
        return pinned
    try:
        cli("config", "devices", device_id, "addresses", "add", f"tcp://{ip}:22000")
    except subprocess.CalledProcessError:
        return pinned
    remember_kde(ip)
    return ip


def main() -> None:
    state = load_state()
    while True:
        try:
            device_id = state.get("device_id")
            if not device_id:
                for dev_id, info in pending().items():
                    if wanted(info):
                        accept(dev_id)
                        state["device_id"] = dev_id
                        save_state(state)
                        device_id = dev_id
                        break
            if device_id:
                pinned = pin_tailscale(device_id, state.get("pinned_ip", ""))
                if pinned != state.get("pinned_ip", ""):
                    state["pinned_ip"] = pinned
                    save_state(state)
        except (urllib.error.URLError, subprocess.CalledProcessError, OSError, json.JSONDecodeError, ET.ParseError):
            pass
        time.sleep(15)


if __name__ == "__main__":
    main()
