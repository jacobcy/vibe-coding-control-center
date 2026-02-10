#!/usr/bin/env python3
"""测试 OpenAI API 连接"""

import os
import sys


def test_connection():
    # 1. 检查环境变量
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY 环境变量未设置")
        print("\n设置方法:")
        print('  export OPENAI_API_KEY="sk-proj-你的密钥"')
        return False

    print(f"✓ API Key 已设置 (前8位: {api_key[:8]}...)")

    # 2. 测试 API 连接
    try:
        from openai import OpenAI

        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "说'连接成功'"}],
            max_tokens=20,
        )
        reply = response.choices[0].message.content
        print(f"✓ API 连接成功")
        print(f"✓ 模型响应: {reply}")
        return True

    except ImportError:
        print("❌ openai 库未安装")
        print("\n安装方法:")
        print("  pip install openai")
        return False

    except Exception as e:
        print(f"❌ API 连接失败: {e}")
        return False


if __name__ == "__main__":
    print("=== OpenAI API 连接测试 ===\n")
    success = test_connection()
    print("\n" + ("测试通过 ✓" if success else "测试失败 ✗"))
    sys.exit(0 if success else 1)
