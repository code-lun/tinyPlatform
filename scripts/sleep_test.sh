#!/bin/bash
# ============================================================
# 脚本名称：睡眠测试工具,用于测试线程池
# 输出格式：标准 JSON（status/code/message/data）
# 功能描述：让系统睡眠指定时长（默认 5 分钟/300 秒），用于测试任务挂起或后台调度
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

# ---------- 参数处理 ----------
# 默认睡眠 300 秒 (5 分钟)
SLEEP_SECONDS=${1:-60}

# 验证参数是否为数字
if ! [[ "$SLEEP_SECONDS" =~ ^[0-9]+$ ]]; then
    output_error "参数错误：睡眠时长必须是正整数（单位：秒）" 1
fi

# 验证参数范围
if [[ "$SLEEP_SECONDS" -le 0 ]]; then
    output_error "参数错误：睡眠时长必须大于 0" 1
fi

# ---------- 记录开始时间 ----------
START_TIME=$(date "+%Y-%m-%d %H:%M:%S" 2>/dev/null)
if [[ -z "$START_TIME" ]]; then
    output_error "获取系统时间失败" 2
fi

# 获取开始时间戳（毫秒级）
START_TIMESTAMP_MS=$(date "+%s%3N" 2>/dev/null)
if [[ -z "$START_TIMESTAMP_MS" ]] || ! [[ "$START_TIMESTAMP_MS" =~ ^[0-9]+$ ]]; then
    # macOS 兼容回退
    START_TIMESTAMP_MS=$(date "+%s" 2>/dev/null)"000"
fi

# ---------- 执行核心逻辑 ----------
sleep "$SLEEP_SECONDS" 2>/dev/null
SLEEP_EXIT_CODE=$?

# 检查 sleep 命令执行状态
if [[ $SLEEP_EXIT_CODE -ne 0 ]]; then
    output_error "睡眠命令执行失败 (exit code: $SLEEP_EXIT_CODE)" 2
fi

# ---------- 记录结束时间 ----------
END_TIME=$(date "+%Y-%m-%d %H:%M:%S" 2>/dev/null)
if [[ -z "$END_TIME" ]]; then
    output_error "获取系统时间失败" 2
fi

END_TIMESTAMP_MS=$(date "+%s%3N" 2>/dev/null)
if [[ -z "$END_TIMESTAMP_MS" ]] || ! [[ "$END_TIMESTAMP_MS" =~ ^[0-9]+$ ]]; then
    END_TIMESTAMP_MS=$(date "+%s" 2>/dev/null)"000"
fi

# 计算实际睡眠时长
ACTUAL_DURATION_MS=$((END_TIMESTAMP_MS - START_TIMESTAMP_MS))

# ---------- 输出成功结果 ----------
cat <<EOF
{
  "status": "success",
  "code": 0,
  "message": "睡眠测试完成",
  "data": {
    "sleep_seconds": $SLEEP_SECONDS,
    "start_time": "$START_TIME",
    "end_time": "$END_TIME",
    "duration_ms": $ACTUAL_DURATION_MS,
    "timezone": "$(date "+%Z" 2>/dev/null || echo "Unknown")"
  }
}
EOF

exit 0