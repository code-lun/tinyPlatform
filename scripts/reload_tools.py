#!/usr/bin/env python3
# ============================================================
# 脚本名称：重载工具注册表
# 输出格式：标准 JSON（status/code/message/data）
# ============================================================

import sys
import os
import json
import traceback

# ---------- 函数：输出标准 JSON 错误并退出 ----------
def output_error(err_msg, err_code=1):
    out = {
        "status": "error",
        "code": err_code,
        "message": err_msg,
        "data": None
    }
    # 仅输出 JSON，无额外文本
    print(json.dumps(out, ensure_ascii=False))
    sys.exit(err_code)

# ---------- 主逻辑 ----------
def main():
    try:
        # 动态计算 backend 路径（假设脚本位于 scripts/ 目录下）
        current_dir = os.path.dirname(os.path.abspath(__file__))
        target_path = os.path.abspath(os.path.join(current_dir, "../backend"))
        if target_path not in sys.path:
            sys.path.insert(0, target_path)

        # 导入注册表并执行重载
        from app.registry.registry import ToolRegistry
        r = ToolRegistry()
        r.reload()

        # 成功输出
        out = {
            "status": "success",
            "code": 0,
            "message": "工具注册表重载成功",
            "data": {
                "reloaded": True,
                "backend_path": target_path
            }
        }
        print(json.dumps(out, ensure_ascii=False))
        sys.exit(0)

    except ImportError as e:
        output_error(f"导入失败: {e}", 2)
    except Exception as e:
        # 将完整错误栈放入 message 方便调试（但保持 JSON 格式）
        error_msg = f"{e}\n{traceback.format_exc()}"
        output_error(error_msg, 3)

if __name__ == "__main__":
    main()