#!/bin/bash
# ============================================================
# 获取当前时间脚本
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

# ---------- 主逻辑 ----------
CURRENT_TIME=$(date "+%Y-%m-%d %H:%M:%S" 2>/dev/null)

if [[ -z "$CURRENT_TIME" ]]; then
    output_error "获取系统时间失败" 2
fi

# 额外获取时间戳（毫秒级，方便前端排序）
TIMESTAMP_MS=$(date "+%s%3N" 2>/dev/null)
if [[ -z "$TIMESTAMP_MS" ]]; then
    # 若系统不支持 %3N（如 macOS），退化为秒级
    TIMESTAMP_MS=$(date "+%s" 2>/dev/null)"000"
fi

cat <<EOF
{
  "status": "success",
  "code": 0,
  "message": "获取时间成功",
  "data": {
    "datetime": "$CURRENT_TIME",
    "timestamp_ms": $TIMESTAMP_MS,
    "timezone": "$(date "+%Z" 2>/dev/null || echo "Unknown")"
  }
}
EOF

exit 0