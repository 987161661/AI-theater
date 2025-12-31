# 诊断测试脚本
# 用于测试 WorldBuilder 和 CastingLogic 的基本功能

import pandas as pd
from openai import OpenAI

# 测试数据
test_df = pd.DataFrame({
    "Time": ["T1", "T2"],
    "Event": ["事件1", "事件2"],
    "Goal": ["目标1", "目标2"]
})

print("=== 测试 1: DataFrame.to_markdown ===")
try:
    markdown = test_df.to_markdown(index=False)
    print("✅ Success:")
    print(markdown)
except Exception as e:
    print(f"❌ Error: {e}")

print("\n=== 测试 2: OpenAI Client 创建 ===")
try:
    # 这里需要你的实际配置
    # client = OpenAI(api_key="your_key", base_url="your_url")
    print("⚠️ Skipped (需要实际配置)")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n=== 测试 3: JSONParser 导入 ===")
try:
    from core.utils.json_parser import JSONParser, WorldBibleModel, PersonaModel
    print("✅ JSONParser 导入成功")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n=== 测试完成 ===")
print("如果测试1失败,说明 tabulate 库有问题")
print("如果测试3失败,说明 json_parser.py 有问题")
