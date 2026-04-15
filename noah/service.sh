#!/bin/sh

APP_DIR="/apps/dat/web/working/ipd-pmo.vip.vip.com"
LOG_DIR="/apps/logs/log_receiver/ipd-pmo.vip.vip.com"
LOG_FILE="$LOG_DIR/backend.log"

mkdir -p "$LOG_DIR"

cd "$APP_DIR" || exit 1

# 异步启动，并将标准输出/错误统一写入指定日志文件
nohup /apps/svr/python3/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080 >> "$LOG_FILE" 2>&1 &

echo "Started uvicorn in background, pid=$!, log=$LOG_FILE"