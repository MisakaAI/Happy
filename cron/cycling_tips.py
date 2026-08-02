#!/usr/bin/env python3

# 天气 & 骑行建议
# python -m cron.cycling_tips
# CRON 周一至周五 7:40
# 40 7 * * 1-5 cd $(pwd) && PYTHONPATH=$(pwd) $(pwd)/.venv/bin/python -m cron.cycling_tips >> /dev/null 2>> $(pwd)/logs/error.log


import os
import time
from datetime import datetime

import psycopg
from dotenv import load_dotenv

from tools.astrbot import message
from tools.llm import DEEPSEEK, chat
from tools.qweather import fetch_weather_forecast, qweather_jwt

load_dotenv()

DSN = os.getenv("DATABASE_URL", "").replace("+psycopg", "")

model = DEEPSEEK

prompt = """
你是天气分析与骑行通勤助手。
根据输入的天气数据，生成简洁的通勤建议。
只输出纯文本，不解释分析过程，不重复输入中的具体参数。

请严格按以下格式输出，段落之间空一行：

天气情况
用一段话总结未来24小时天气变化，包括天气状况、温度范围、降雨情况、风力变化。不超过120字。

穿衣建议
根据气温、体感温度、降雨、风力，给出一句日常穿衣建议。

骑行建议
结合以下通勤规则判断交通工具：
- 通勤距离约10km，沿海道路。
- 上班方向约202°，下班方向约22°，根据天气风向判断顺风或逆风。
- 早晚天气不同，以全天较差天气作为统一选择依据。

交通工具优先级：
1. 公交/打车：
暴雨、雷暴、台风、极端大风、能见度极低等危险天气。
2. 电动自行车：
中到大雨、明显逆风、较强风力影响骑行、路面湿滑，或气温高于26℃（但未达到公交/打车条件）。
3. 公路自行车：
无明显降雨、无恶劣天气、风力适中，且气温≤26℃。
晚上轻微逆风时可适当放宽推荐公路车，但气温仍需≤26℃。

若推荐公路自行车：
根据风况估算速度和耗时：
无风：20km/h
顺风：25km/h
轻微逆风：16km/h
明显逆风：13km/h

输出推荐交通工具、建议速度和预计耗时。
若不是公路车，只说明推荐交通工具和原因，不需要估算速度。

要求：
- 只输出“天气情况”“穿衣建议”“骑行建议”四个段落。
- 语言自然、简洁，适合手机查看。
- 不使用 Markdown、序号、表格。
"""


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

    text = f"{prompt}\n"

    text += f"Current weather data: {weather}\n"
    text += f"Current air quality Data: {air_quality}\n"
    text += f"Weather forecast for the next 24 hours: {hourly['hourly']}\n"

    start = time.time()
    content = chat(text, api=model)
    end = time.time()
    elapsed = end - start

    message(
        f"【{datetime.now().strftime('%Y年%m月%d日')}】\n\n{content}\n\n本次思考用时: {elapsed:.3f}秒（{model.model}）"
    )


if __name__ == "__main__":
    main()
