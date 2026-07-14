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

    root /opt/scamcheck/frontend;
    index index.html;
    server_name _;

    client_max_body_size 64k;

    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
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
sleep 2
echo "    backend health:"; curl -fsS http://127.0.0.1:5000/api/health || echo "    ! backend chưa sẵn sàng" >&2
echo
echo "    frontend :"; curl -fsS -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8000/
echo
echo "✓ Deploy xong. Public: https://team6-scamcheck.exe.xyz:8000/"
