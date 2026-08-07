#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# 加载 .env 文件
def load_env():
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        print("未找到 .env 文件，请参考 .env.example 创建")
        sys.exit(1)
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            key, value = line.split('=', 1)
            os.environ[key.strip()] = value.strip()

# 加载环境变量
load_env()

# 导入 main 并运行
from main import run

if __name__ == "__main__":
    run()