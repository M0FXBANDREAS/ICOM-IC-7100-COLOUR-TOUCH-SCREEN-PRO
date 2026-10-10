#!/usr/bin/env bash
# Fresh installation for Raspberry Pi / Debian. Run as your normal desktop user.
set -euo pipefail
cd "$(dirname "$0")"
if [ "$(id -u)" -eq 0 ]; then
  echo 'Run this installer as your normal user, not with sudo.' >&2
  exit 1
fi
if ! command -v apt-get >/dev/null 2>&1; then
  echo 'This installer requires Debian or Raspberry Pi OS with apt-get.' >&2
  exit 1
fi
printf '\nInstalling HamTech M0FXB Modification — IC-7100 Photo Console\n\n'
sudo apt-get update
sudo apt-get install -y python3 python3-venv libportaudio2 chromium unzip
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
chmod +x start-panel.sh install-and-start.sh
if ! id -nG "$USER" | tr ' ' '\n' | grep -qx dialout; then
  sudo usermod -aG dialout "$USER"
  printf '\nSerial permission added. Log out and back in before controlling the radio.\n'
fi
python3 - <<'PY'
from pathlib import Path
import os
root=Path.cwd()
# A desktop menu entry launches a terminal so radio errors remain visible.
def quoted(value):
    return '"'+str(value).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')+'"'
folder=Path.home()/'.local/share/applications'
folder.mkdir(parents=True,exist_ok=True)
entry=folder/'hamtech-ic7100.desktop'
entry.write_text('[Desktop Entry]\nType=Application\nName=HamTech IC-7100 Console\nComment=HamTech M0FXB Modification\nExec=/usr/bin/bash '+quoted(root/'start-panel.sh')+'\nTerminal=true\nCategories=Utility;\n')
entry.chmod(0o755)
PY
printf '\nInstallation complete.\nStart: bash start-panel.sh\nOpen on this Pi: http://127.0.0.1:7100\nRadio settings: CI-V 19200 baud / address 88h\n'
