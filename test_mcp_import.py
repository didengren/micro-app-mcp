#!/usr/bin/env python3
"""测试mcp模块导入"""

print("测试mcp模块导入...")

try:
    import mcp
    print("✅ 成功导入mcp模块")
except Exception as e:
    print(f"❌ 导入mcp模块失败: {e}")

try:
    from mcp import types
    print("✅ 成功从mcp导入types")
except Exception as e:
    print(f"❌ 从mcp导入types失败: {e}")

try:
    import mcp.types
    print("✅ 成功导入mcp.types模块")
except Exception as e:
    print(f"❌ 导入mcp.types模块失败: {e}")

print("测试完成！")
