# 供 Windows「任务计划程序」调用：将当前 MySQL 库备份到本机。
# 前提：已安装 MySQL 客户端且 mysqldump 在 PATH；在 backend 配置了 .env。
#
# 操作：任务计划程序 → 创建任务 → 触发器「每天」→ 操作「启动程序」
#   程序:   powershell.exe
#   参数:   -NoProfile -ExecutionPolicy Bypass -File "D:\Study\test01\test\backend\scripts\backup_mysql_to_local.ps1"
#   起始于: D:\Study\test01\test\backend
#
$ErrorActionPreference = "Stop"
$BackendRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $BackendRoot
$Python = Join-Path $BackendRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}
& $Python "scripts\backup_mysql_to_local.py" @args
exit $LASTEXITCODE
