#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
project_dir="$(pwd -P)"

if [[ ! -f .env ]]; then
  echo "缺少 .env；请先把本机的 .env 安全上传到 $project_dir/.env" >&2
  exit 1
fi

if ! python3 -m venv .venv; then
  echo "请先运行：sudo apt update && sudo apt install -y python3-venv" >&2
  exit 1
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
chmod 600 .env

if [[ $(id -u) -eq 0 ]]; then
  sudo_cmd=()
else
  sudo_cmd=(sudo)
fi

cat <<EOF | "${sudo_cmd[@]}" tee /etc/systemd/system/nailong.service >/dev/null
[Unit]
Description=Nailong QQ Bot
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$(id -un)
WorkingDirectory=$project_dir
Environment=PYTHONUNBUFFERED=1
ExecStart=$project_dir/.venv/bin/python $project_dir/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

"${sudo_cmd[@]}" systemctl daemon-reload
"${sudo_cmd[@]}" systemctl enable --now nailong.service
"${sudo_cmd[@]}" systemctl --no-pager status nailong.service
