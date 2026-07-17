#!/usr/bin/env bash
# Deploy ScamCheck lên VM target team6-scamcheck.exe.xyz.
# Chạy TRÊN VM target (qua SSH). Yêu cầu: sudo passwordless.
#
#   bash deploy/deploy.sh
#
# Idempotent: chạy lại nhiều lần vẫn an toàn (update code + restart).
set -euo pipefail

REPO_URL="https://hackathon-project.int.exe.xyz/Sharing-hackathon-2026/team6-scamcheck.git"
INSTALL_DIR="/opt/scamcheck"
VENV="$INSTALL_DIR/backend/.venv"
ENV_FILE="/etc/scamcheck.env"

echo "==> [1/6] Clone/update repo"
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "    repo đã có, git pull..."
  sudo git -C "$INSTALL_DIR" fetch --all -q
  sudo git -C "$INSTALL_DIR" reset --hard origin/main -q
else
  sudo rm -rf "$INSTALL_DIR"
  sudo git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi
sudo chown -R "$USER":"$USER" "$INSTALL_DIR"

echo "==> [2/6] Tạo venv + cài dependencies"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$INSTALL_DIR/backend/requirements.txt"

echo "==> [3/6] Chạy test (phải xanh mới tiếp tục)"
( cd "$INSTALL_DIR/backend" && "$VENV/bin/pytest" -q )

echo "==> [4/6] Cấu hình env (GEMINI_API_KEY từ /etc/scamcheck.env)"
if [ ! -f "$ENV_FILE" ]; then
  echo "    ! Chưa có $ENV_FILE. Tạo mẫu để điền key:" >&2
  echo "    sudo tee $ENV_FILE <<EOF" >&2
  cat "$INSTALL_DIR/.env.example" >&2
  echo "EOF" >&2
  echo "    Sau đó chạy lại deploy.sh" >&2
  exit 1
fi
sudo chown root:"$USER" "$ENV_FILE"
sudo chmod 640 "$ENV_FILE"
# Public edge cung cấp full SSL ở origin không port; QR phải trỏ tới URL final-user này,
# không phải cổng Nginx nội bộ 8000.
PUBLIC_BASE_URL="https://team6-scamcheck.exe.xyz/"
if sudo grep -q '^BASE_URL=' "$ENV_FILE"; then
  sudo sed -i "s|^BASE_URL=.*|BASE_URL=$PUBLIC_BASE_URL|" "$ENV_FILE"
else
  printf '\nBASE_URL=%s\n' "$PUBLIC_BASE_URL" | sudo tee -a "$ENV_FILE" >/dev/null
fi
SQLITE_PATH="/var/lib/scamcheck/scamcheck.sqlite3"
if sudo grep -q '^SQLITE_PATH=' "$ENV_FILE"; then
  sudo sed -i "s|^SQLITE_PATH=.*|SQLITE_PATH=$SQLITE_PATH|" "$ENV_FILE"
else
  printf 'SQLITE_PATH=%s\n' "$SQLITE_PATH" | sudo tee -a "$ENV_FILE" >/dev/null
fi
if ! sudo grep -q '^ADMIN_AUTH_ORIGIN=' "$ENV_FILE"; then
  printf 'ADMIN_AUTH_ORIGIN=https://team6-scamcheck.exe.xyz:8001\n' | sudo tee -a "$ENV_FILE" >/dev/null
fi
if ! sudo grep -q '^ADMIN_PROXY_PORT=' "$ENV_FILE"; then
  printf 'ADMIN_PROXY_PORT=8001\n' | sudo tee -a "$ENV_FILE" >/dev/null
fi
if ! sudo grep -q '^ADMIN_ALLOWED_EMAILS=' "$ENV_FILE"; then
  printf 'ADMIN_ALLOWED_EMAILS=\n' | sudo tee -a "$ENV_FILE" >/dev/null
fi
if sudo grep -q '^ADMIN_ALLOWED_EMAILS=$' "$ENV_FILE"; then
  echo "    ! ADMIN_ALLOWED_EMAILS đang rỗng: admin login sẽ fail closed cho tới khi cấu hình email." >&2
fi

echo "==> [5/6] Cài systemd backend + nginx"
sudo cp "$INSTALL_DIR/deploy/scamcheck-backend.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable scamcheck-backend >/dev/null
sudo systemctl restart scamcheck-backend

# Cấu hình nginx: phục vụ frontend/ + proxy /api/* -> 127.0.0.1:5000.
NGINX_SITE="/etc/nginx/sites-available/scamcheck"
sudo tee "$NGINX_SITE" >/dev/null <<'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    listen 8000;
    listen [::]:8000;
    listen 8001;
    listen [::]:8001;

    root /opt/scamcheck/frontend;
    index index.html;
    server_name _;

    client_max_body_size 64k;

    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        # Preserve :8001 so Flask only trusts exe.dev auth headers on admin origin.
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 45s;
    }

    location /assets/ {
        expires 1h;
        add_header Cache-Control "public";
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
NGINX
sudo ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/scamcheck
# Gỡ site default (tránh xung đột default_server trên port 80/8000).
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable nginx >/dev/null
sudo systemctl restart nginx

echo "==> [6/6] Kiểm tra sức khoẻ"
health=""
for attempt in $(seq 1 15); do
  if health=$(curl -fsS --max-time 3 http://127.0.0.1:5000/api/health 2>/dev/null); then
    break
  fi
  sleep 1
done
if [ -z "$health" ] || ! printf '%s' "$health" | "$VENV/bin/python" -c \
  'import json,sys; value=json.load(sys.stdin); raise SystemExit(not (value.get("ok") is True and value.get("ready") is True))'; then
  echo "    ! Backend không healthy/ready sau deploy: ${health:-không có phản hồi}" >&2
  sudo systemctl status scamcheck-backend --no-pager >&2 || true
  exit 1
fi
echo "    backend health: $health"
qr_svg=$(curl -fsS --max-time 5 http://127.0.0.1:5000/api/share/qr.svg)
if ! printf '%s' "$qr_svg" | grep -Fq 'Mã QR dẫn tới https://team6-scamcheck.exe.xyz/' \
  || printf '%s' "$qr_svg" | grep -Fq ':8000'; then
  echo "    ! QR chưa trỏ tới public origin không port." >&2
  exit 1
fi
echo "    share QR: public origin không port"
admin_status=$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' \
  -H 'Host: team6-scamcheck.exe.xyz:8001' http://127.0.0.1:5000/api/ai-logs?scope=all)
if [ "$admin_status" != "401" ]; then
  echo "    ! Admin log API phải yêu cầu exe.dev login (nhận HTTP $admin_status)." >&2
  exit 1
fi
sudo test -f /var/lib/scamcheck/scamcheck.sqlite3
echo "    SQLite + admin auth gate: sẵn sàng"
echo "    frontend:"; curl -fsS --max-time 5 -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8000/
echo "    library:"; curl -fsS --max-time 5 -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8000/library.html
echo "    practice:"; curl -fsS --max-time 5 -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8000/practice.html
echo "    history:"; curl -fsS --max-time 5 -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8000/history.html
echo
echo "✓ Deploy xong. Public: https://team6-scamcheck.exe.xyz/"
