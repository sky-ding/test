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

# 注入 Noah 环境文件中的 PM_* 等变量。
# 仅导出非空值，避免 app.env 里的空模板覆盖平台已注入的真实机密配置。
if [ -f "$APP_DIR/noah/env/app.env" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    # 去掉首尾空白
    trimmed=$(printf '%s' "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    # 跳过空行与注释
    [ -z "$trimmed" ] && continue
    case "$trimmed" in
      \#*) continue ;;
    esac
    # 仅处理 KEY=VALUE 格式
    case "$trimmed" in
      *=*)
        key=${trimmed%%=*}
        val=${trimmed#*=}
        key=$(printf '%s' "$key" | sed 's/[[:space:]]*$//')
        val=$(printf '%s' "$val" | sed 's/^[[:space:]]*//')
        # 值为空时不覆盖已有环境变量
        [ -z "$val" ] && continue
        export "$key=$val"
        ;;
      *)
        ;;
    esac
  done < "$APP_DIR/noah/env/app.env"
fi

# 后台启动，让 init 能继续启动 nginx；端口 8080 匹配 nginx upstream
nohup /apps/svr/python3/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080 >> "$LOG_FILE" 2>&1 &