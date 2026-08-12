# 现有脚本/接口改造为规范工具 Skill

## 技能目标

将一个已有的脚本或接口改造为符合统一 JSON 输出规范的工具，并注册到后端工具注册表中。改造后的脚本应具备健壮的错误处理、兼容性考虑以及严格的 JSON 输出。

---

## 标准脚本模板（推荐直接复用）

以下是一个符合规范的脚本模板，可作为改造的起点：

```bash
#!/bin/bash
# ============================================================
# 脚本名称：获取当前时间
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
# 1. 检查依赖命令是否存在（如需要）
# if ! command -v some_command &> /dev/null; then
#     output_error "命令不可用: some_command" 2
# fi

# 2. 执行核心逻辑
CURRENT_TIME=$(date "+%Y-%m-%d %H:%M:%S" 2>/dev/null)
if [[ -z "$CURRENT_TIME" ]]; then
    output_error "获取系统时间失败" 2
fi

# 3. 额外获取时间戳（毫秒级，方便前端排序）
TIMESTAMP_MS=$(date "+%s%3N" 2>/dev/null)
if [[ -z "$TIMESTAMP_MS" ]]; then
    # 若系统不支持 %3N（如 macOS），退化为秒级
    TIMESTAMP_MS=$(date "+%s" 2>/dev/null)"000"
fi

# 4. 输出成功结果
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
```

### 模板要点说明

- **函数封装错误输出**：`output_error` 统一输出错误 JSON 并退出，避免重复代码。
- **使用 heredoc 输出 JSON**：多行 JSON 更易读，且无需担心转义问题（但需确保变量内容不含特殊 JSON 字符）。
- **命令错误重定向**：`2>/dev/null` 避免错误信息混入 JSON 输出。
- **空值检查**：关键变量赋值后检查是否为空，防止输出无效数据。
- **兼容性回退**：对 `%3N` 不支持的系统（如 macOS）回退到秒级时间戳。
- **错误码语义化**：命令执行失败使用 `2`，数据异常使用 `3`。

---

## 改造流程

### 第 1 步：分析现有脚本/接口

明确现有脚本或接口的：

- **输入**：是否需要参数，格式如何。
- **输出**：当前输出格式。
- **依赖**：依赖哪些命令或服务。
- **核心逻辑**：主要功能。
- **失败场景**：哪些情况会导致失败。

### 第 2 步：设计输出结构

所有输出统一为：

```json
{
  "status": "success|error",
  "code": 0,
  "message": "描述信息",
  "data": { }
}
```

错误码约定：

| code | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 通用错误 |
| 2 | 命令不可用 |
| 3 | 数据异常 |

### 第 3 步：改造脚本

#### 场景 A：现有脚本为 Shell 脚本

在原有逻辑基础上，添加 `output_error` 函数，将原有输出替换为 JSON 输出，并增加必要的错误检查。

**示例改造步骤：**

1. 在脚本开头定义 `output_error` 函数（可直接复制模板）。
2. 将原有命令执行结果赋值给变量，并检查是否为空或命令是否成功。
3. 将原本的 `echo` 输出替换为 `cat <<EOF ... EOF` 输出的 JSON。
4. 确保所有输出均为 JSON，不混入调试信息。

#### 场景 B：现有接口为 HTTP/其他服务

编写一个 Shell 脚本调用该接口，并将返回结果包装成统一 JSON。

**示例：**

```bash
#!/bin/bash
# api_wrapper.sh

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

# 调用接口
response=$(curl -s -X GET "http://example.com/api/status")
if [ $? -ne 0 ]; then
    output_error "接口调用失败" 2
fi

if [ -z "$response" ]; then
    output_error "接口返回数据异常" 3
fi

# 包装为统一格式
cat <<EOF
{
  "status": "success",
  "code": 0,
  "message": "调用成功",
  "data": $response
}
EOF

exit 0
```

**注意：** 如果接口返回的不是 JSON，需先进行转换或解析，确保 `data` 字段是有效的 JSON 对象。

### 第 4 步：添加执行权限

```bash
chmod +x scripts/your_tool.sh
```

### 第 5 步：注册到 `tools.yaml`

编辑 `backend/app/registry/tools.yaml`，在 `tools:` 下新增工具定义。

```yaml
tools:
  - name: get_time
    display_name: 获取系统时间
    description: 获取当前系统时间，包含日期时间、毫秒时间戳和时区信息
    script: get_time.sh
    category: 系统信息
    params: []
    timeout: 10
    enabled: true
    tags:
      - 时间
      - 系统
```

字段说明同前。

### 第 6 步：热重载或重启后端

```bash
python3 -c "from app.registry import tool_registry; tool_registry.reload()"
```

或重启容器。

### 第 7 步：验证

```bash
bash scripts/your_tool.sh
```

检查输出是否为合法 JSON，且字段齐全。通过后端接口调用确认工具已注册且可正常使用。

---

## 检查清单

- [ ] 脚本已包含 `output_error` 函数，统一错误输出。
- [ ] 所有输出均使用 heredoc 或 echo 输出合法 JSON，无多余文本。
- [ ] 关键变量已检查是否为空，避免输出无效数据。
- [ ] 依赖命令已检查是否存在（若需要）。
- [ ] 错误码使用符合规范：0/1/2/3。
- [ ] 脚本已添加执行权限。
- [ ] `tools.yaml` 中已添加/更新工具定义，`script` 字段与文件名一致。
- [ ] 已执行热重载或重启后端。
- [ ] 工具调用返回结果正常。

---

## 注意事项

- **保留核心逻辑**：改造只调整输出和错误处理，不改变原有功能。
- **JSON 转义**：若 `data` 中包含变量，确保变量内容不含特殊字符（引号、换行等），必要时使用 `jq` 等工具生成 JSON。
- **超时设置**：根据脚本实际执行时间合理设置 `timeout`。
- **兼容性**：考虑不同系统的命令差异（如 macOS 的 `date` 不支持 `%3N`），提供回退方案。