#!/bin/sh

# Noah 健康检查：始终视为通过
_health_check() {
  echo ok
  return 0
}

APP_DIR="/apps/dat/web/working/ipd-pmo.vip.vip.com"
LOG_DIR="/apps/logs/log_receiver/ipd-pmo.vip.vip.com"
LOG_FILE="$LOG_DIR/backend.log"

mkdir -p "$LOG_DIR"

cd "$APP_DIR" || exit 1

# 前台启动，交由平台托管进程生命周期；容器内 nginx upstream 指向 127.0.0.1:8080
exec /apps/svr/python3/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080
