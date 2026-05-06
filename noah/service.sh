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

# 后台启动，让 init 能继续启动 nginx；端口 8080 匹配 nginx upstream
nohup /apps/svr/python3/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080 >> "$LOG_FILE" 2>&1 &