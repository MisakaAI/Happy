#!/usr/bin/env python3

# 采集实时天气
# python -m tools.save_weather weather

# CRON 每 10 分钟执行一次
# (60分钟/10分钟)*24小时*31天=4464次
# */10 * * * * cd $(pwd) && PYTHONPATH=$(pwd) $(pwd)/.venv/bin/python -m cron.save_weather weather >> /dev/null 2>> $(pwd)/logs/error.log

# 采集空气质量
# python -m tools.save_weather air

# CRON 每 30 分钟执行一次（避开整点）
# (60分钟/30分钟)*24小时*31天=1488次
# 15,45 * * * * cd $(pwd) && PYTHONPATH=$(pwd) $(pwd)/.venv/bin/python -m cron.save_weather air >> /dev/null 2>> $(pwd)/logs/error.log


import json
import os
import sys
from datetime import datetime

import psycopg
from dotenv import load_dotenv

from tools.qweather import fetch_air_quality, fetch_weather_now, qweather_jwt

load_dotenv()

DSN = os.getenv("DATABASE_URL", "").replace("+psycopg", "")


# 安全转换为整数，空值返回 None。
def to_int(v):
    if v in (None, ""):
        return None
    return int(v)


# 安全转换为浮点数，空值返回 None。
def to_float(v):
    if v in (None, ""):
        return None
    return float(v)


# 将实时天气数据写入 weather 表，并按 obs_time 去重
def insert_weather(conn, data: dict) -> int:
    now = data.get("now")
    if not isinstance(now, dict):
        raise ValueError(
            f"Missing 'now' object: {json.dumps(data, ensure_ascii=False)}"
        )

    obs_time = datetime.fromisoformat(now["obsTime"])

    row = (
        obs_time,
        to_int(now.get("temp")),  # 温度
        to_int(now.get("feelsLike")),  # 体感温度
        now.get("icon") or None,  # 天气图标代码
        now.get("text") or None,  # 天气描述
        to_int(now.get("wind360")),  # 风向角度
        now.get("windDir") or None,  # 风向文字
        now.get("windScale") or None,  # 风力等级
        to_int(now.get("windSpeed")),  # 风速 km/h
        to_int(now.get("humidity")),  # 湿度 %
        to_float(now.get("precip")),  # 降水量 mm
        to_int(now.get("pressure")),  # 气压 hPa
        to_int(now.get("vis")),  # 能见度 km
        to_int(now.get("cloud")),  # 云量 %
        to_int(now.get("dew")),  # 露点温度
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO weather (
                obs_time, temp, feels_like, icon, weather_text,
                wind_360, wind_dir, wind_scale, wind_speed,
                humidity, precip, pressure, vis, cloud, dew,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (obs_time) DO NOTHING;
            """,
            row,
        )
        return cur.rowcount


# 从 AQI 指数列表中优先选取(cn-mee)数据，否则取第一个
def pick_index(indexes: list[dict]) -> dict | None:
    for item in indexes:
        if item.get("code") == "cn-mee":
            return item
    return indexes[0] if indexes else None


# 从监测站列表中提取第一个有效站名，截断至30字符。
def pick_station_name(stations: list[dict]) -> str | None:
    for station in stations:
        name = station.get("name")
        if name not in (None, ""):
            return str(name)[:30]
    return None


# 将污染物列表转换为 {code: concentration} 映射
def pollutant_map(pollutants: list[dict]) -> dict[str, float]:
    values = {}
    for p in pollutants:
        code = p.get("code")
        concentration = p.get("concentration") or {}
        value = concentration.get("value")
        if code in (None, "") or value in (None, ""):
            continue
        values[str(code)] = float(value)
    return values


# 将空气质量数据写入 air_quality 表
def insert_air_quality(conn, payload: dict) -> int:
    index = pick_index(payload.get("indexes", []))
    if not index:
        raise ValueError(f"Empty indexes: {json.dumps(payload, ensure_ascii=False)}")

    pollutants = pollutant_map(payload.get("pollutants", []))
    station_name = pick_station_name(payload.get("stations", []))

    aqi = to_int(index.get("aqi"))
    level = to_int(index.get("level"))
    primary = (index.get("primaryPollutant") or {}).get("name")

    row = (
        aqi,
        level,
        to_float(pollutants.get("pm2p5")),  # PM2.5 浓度
        to_float(pollutants.get("pm10")),  # PM10 浓度
        to_float(pollutants.get("no2")),  # NO2 浓度
        to_float(pollutants.get("o3")),  # O3 浓度
        to_float(pollutants.get("so2")),  # SO2 浓度
        to_float(pollutants.get("co")),  # CO 浓度
        station_name,  # 监测站名称
        primary,  # 首要污染物
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO air_quality (
                aqi, aqi_level, pm25, pm10, no2, o3, so2, co, stations, primary_pollutant,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now());
            """,
            row,
        )
        return cur.rowcount


# 支持的采集任务类型
TASKS = {"weather": "fetch_weather_now", "air": "fetch_air_quality"}


def main():
    # 检查数据库连接字符串
    if not DSN:
        raise RuntimeError("DATABASE_URL is not set in .env")

    # 从命令行参数读取要执行的任务类型
    task = sys.argv[1] if len(sys.argv) > 1 else None
    if task not in TASKS:
        print(f"Usage: python -m tools.save_weather <{'|'.join(TASKS)}>")
        sys.exit(1)

    # 生成和风天气 API 鉴权 Token
    token = qweather_jwt()

    # 连接数据库并根据任务类型执行对应的采集与入库
    with psycopg.connect(DSN) as conn:
        if task == "weather":
            data = fetch_weather_now(token)  # 拉取实时天气数据
            count = insert_weather(conn, data)  # 写入 weather 表
            conn.commit()  # 提交事务
            print(f"Inserted: weather={count} row(s)")
        elif task == "air":
            data = fetch_air_quality(token)  # 拉取空气质量数据
            count = insert_air_quality(conn, data)  # 写入 air_quality 表
            conn.commit()  # 提交事务
            print(f"Inserted: air_quality={count} row(s)")


if __name__ == "__main__":
    main()
