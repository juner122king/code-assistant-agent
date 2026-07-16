"""故意存在问题的示例应用，供 Agent 分析。"""

import os
import subprocess

# 风险：硬编码密钥
API_KEY = "sk-prod-abcdef1234567890"
DB_PASSWORD = "password123"


def get_user(user_id):
    # Bug：SQL 拼接注入风险（演示）
    query = "SELECT * FROM users WHERE id = '" + str(user_id) + "'"
    return query


def run_command(cmd):
    # 风险：shell=True 且未校验输入
    return subprocess.check_output(cmd, shell=True)


def load_config():
    # Bug：裸 except 吞掉所有错误
    try:
        with open("config/settings.json") as f:
            return f.read()
    except:
        return None


def divide(a, b):
    # Bug：未处理除零
    return a / b


if __name__ == "__main__":
    print("user:", get_user("1 OR 1=1"))
    print("config:", load_config())
    # print(divide(1, 0))
