#!/usr/bin/env python3

# 天气 & 骑行建议
# python -m cron.cycling_tips
# CRON 周一至周五 7:40
# 40 7 * * 1-5 cd $(pwd) && PYTHONPATH=$(pwd) $(pwd)/.venv/bin/python -m cron.cycling_tips >> /dev/null 2>> $(pwd)/logs/error.log


import json
import os
import time
from datetime import datetime
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from tools.ai import AI
from tools.astrbot import message
from tools.qweather import fetch_weather_forecast, qweather_jwt

# 获取当前脚本所在目录的父目录（即项目根目录）
project_root = Path(__file__).parent.parent
prompt_file = project_root / "prompt.json"

# 读取并解析提示词 JSON
with open(prompt_file, encoding="utf-8") as f:
    prompt = json.load(f)

load_dotenv()

DSN = os.getenv("DATABASE_URL", "").replace("+psycopg", "")


def main():
    # 检查数据库连接字符串
    if not DSN:
        raise RuntimeError("DATABASE_URL is not set in .env")

    # 连接到 PostgreSQL 数据库
    with (
        psycopg.connect(DSN) as conn,
        conn.cursor(row_factory=psycopg.rows.dict_row) as cur,
    ):
        # 查询 weather 表的最新一条记录
        cur.execute("SELECT * FROM weather ORDER BY created_at DESC LIMIT 1")
        weather = cur.fetchone()  # 获取一条记录

        # 查询 air_quality 表的最新一条记录
        cur.execute("SELECT * FROM air_quality ORDER BY created_at DESC LIMIT 1")
        air_quality = cur.fetchone()  # 获取一条记录

    token = qweather_jwt()  # JWT
    hourly = fetch_weather_forecast(token)  # 24小时天气预报

    text = ""
    for i in prompt["cycling_tips"]:
        text += i
        text += "\n"

    text += f"Current weather data: {weather}\n"
    text += f"Current air Quality Data: {air_quality}\n"
    text += f"Weather data for the next hour: {hourly['hourly']}\n"

    start = time.time()
    bigmodel = AI()
    content = bigmodel.chat(text)
    end = time.time()
    elapsed = end - start

    message(
        f"【{datetime.now().strftime('%Y年%m月%d日')}】\n\n{content}\n\n本次思考用时: {elapsed:.3f}秒（{bigmodel.model}）"
    )


if __name__ == "__main__":
    main()
