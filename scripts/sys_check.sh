#!/bin/bash
# ============================================================
# 系统资源巡检脚本
# 输出格式：标准 JSON（status/code/message/data）
# ============================================================

# ---------- 函数：输出标准 JSON 错误 ----------
output_error() {
    local err_msg="$1"
    local err_code="${2:-1}"
    cat <<EOF
{
  "status": "error",
  "code": $err_code,
  "message": "$err_msg",
  "data": null
}
EOF
    exit "$err_code"
}

# ---------- 函数：获取指标（带容错） ----------
get_cpu_usage() {
    local cpu_idle
    cpu_idle=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" 2>/dev/null)
    if [[ -z "$cpu_idle" ]]; then
        cpu_idle=0
    fi
    awk "BEGIN {printf \"%.2f\", 100 - $cpu_idle}" 2>/dev/null || echo "0.00"
}

get_mem_usage() {
    free | awk '/Mem/ {printf "%.2f", ($2-$7)/$2*100}' 2>/dev/null || echo "0.00"
}

get_disk_usage() {
    df -h / 2>/dev/null | awk 'NR==2 {print $5}' | sed 's/%//' 2>/dev/null || echo "0"
}

# ---------- 主逻辑 ----------
# 捕获全局错误（如管道中断）
set -o pipefail

# 获取数据
CPU_USAGE=$(get_cpu_usage)
MEM_USAGE=$(get_mem_usage)
DISK_USAGE=$(get_disk_usage)
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# 校验数据是否有效（全部为0或空字符串视为异常）
if [[ -z "$CPU_USAGE" || -z "$MEM_USAGE" || -z "$DISK_USAGE" ]]; then
    output_error "获取系统指标失败，请检查系统命令是否可用" 2
fi

# 如果三项全部为0，视为采集异常（极小概率，但做防御）
if [[ "$CPU_USAGE" == "0.00" && "$MEM_USAGE" == "0.00" && "$DISK_USAGE" == "0" ]]; then
    output_error "系统指标数据异常（全为0），请检查 top/free/df 命令输出" 3
fi

# ---------- 输出成功 JSON ----------
cat <<EOF
{
  "status": "success",
  "code": 0,
  "message": "系统资源采集成功",
  "data": {
    "timestamp": "$TIMESTAMP",
    "cpu_usage": $CPU_USAGE,
    "mem_usage": $MEM_USAGE,
    "disk_usage": $DISK_USAGE,
    "unit": "percent"
  }
}
EOF

exit 0