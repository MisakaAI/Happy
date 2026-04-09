#!/usr/bin/env python3
import json
import os
import time
from datetime import datetime
from pathlib import Path

import jwt
import requests
from dotenv import load_dotenv

load_dotenv()

private_key_path = os.getenv("QWEATHER_PRIVATE_KEY")
private_key = Path(private_key_path).read_text(encoding="utf-8")
kid = os.getenv("QWEATHER_KID")
sub = os.getenv("QWEATHER_SUB")
url = os.getenv("QWEATHER_API_HOST")
lon = os.getenv("QWEATHER_DEFAULT_LON")
lat = os.getenv("QWEATHER_DEFAULT_LAT")


# JSON Web Token
def qweather_jwt(private_key: str = private_key, kid: str = kid, sub: str = sub) -> str:

    payload = {"iat": int(time.time()) - 30, "exp": int(time.time()) + 900, "sub": sub}
    headers = {"kid": kid}

    # Generate JWT
    encoded_jwt = jwt.encode(payload, private_key, algorithm="EdDSA", headers=headers)

    return encoded_jwt


# 实时天气
def fetch_weather_now(
    token: str, lon: str = lon, lat: str = lat, url: str = url
) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    params = {"location": f"{lon},{lat}"}
    api_url = url + "/v7/weather/now"

    session = requests.Session()
    session.trust_env = False
    r = session.get(api_url, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    return data


# 实时天气 格式化输出
def format_weather(data: dict) -> str:

    now = data.get("now")
    if not isinstance(now, dict):
        raise ValueError(
            f"Missing 'now' object: {json.dumps(data, ensure_ascii=False)}"
        )

    # 字段映射
    # key: 原字段,
    # value: 显示名称 + 单位
    mapping = {
        "obsTime": "数据观测时间",
        "temp": "温度: {} °C",
        "feelsLike": "体感温度: {} °C",
        "text": "天气: {}",
        "windDir": "风向: {}",
        "windScale": "风力: {} 级",
        "windSpeed": "风速: {} km/h",
        "humidity": "相对湿度: {}%",
        "precip": "降水量: {} mm",
        "pressure": "气压: {} hPa",
        "vis": "能见度: {} km",
        "cloud": "云量: {}%",
        "dew": "露点温度: {} °C",
    }

    lines = []

    for k, v in mapping.items():
        if k not in now or now[k] in ("", None):
            continue

        # 时间单独处理
        if k == "obsTime":
            dt = datetime.fromisoformat(now[k])
            formatted = dt.strftime("%Y年%m月%d日 %H:%M")
            lines.append(f"{v} {formatted}")
        else:
            if "{}" in v:
                lines.append(v.format(now[k]))
            else:
                lines.append(f"{v} {now[k]}")

    return "\n".join(lines)


# 实时空气质量
def fetch_air_quality(
    token: str, lon: str = lon, lat: str = lat, url: str = url
) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    api_url = url + f"/airquality/v1/current/{lat}/{lon}"

    session = requests.Session()
    session.trust_env = False
    r = session.get(api_url, headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()

    return data


# 实时空气质量 格式化输出
def format_air_quality(data: dict) -> str:
    lines = []

    # 空气质量指数
    aqi = data.get("indexes")[0].get("aqi")
    lines.append(f"空气质量指数（AQI）: {aqi}")

    # 首要污染物，可能为空
    primary = data.get("primaryPollutant")
    if primary is None:
        lines.append("首要污染物: 无")
    else:
        lines.append(f"首要污染物: {primary.get('fullName')}")

    # 污染物
    pollutants = data.get("pollutants")

    for i in pollutants:
        lines.append(
            f"{i['fullName']}: {i['concentration']['value']} {i['concentration']['unit']}"
        )

    stations = data.get("stations")[0].get("name")
    lines.append(f"监测站名称: {stations}")

    return "\n".join(lines)


# 逐小时天气预报
def fetch_weather_forecast(
    token: str, lon: str = lon, lat: str = lat, url: str = url
) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    params = {"location": f"{lon},{lat}"}
    api_url = url + "/v7/weather/24h"

    session = requests.Session()
    session.trust_env = False
    r = session.get(api_url, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    return data


# 逐小时天气预报 格式化输出
def format_weather_forecast(data: dict) -> str:
    # 字段映射
    hourly_mapping = {
        "fxTime": "预报时间",
        "temp": "温度: {} °C",
        "text": "天气: {}",
        "windDir": "风向: {}",
        "windScale": "风力: {} 级",
        "windSpeed": "风速: {} km/h",
        "humidity": "湿度: {}%",
        "precip": "降水量: {} mm",
        "pop": "降水概率: {}%",
        "pressure": "气压: {} hPa",
        "cloud": "云量: {}%",
        "dew": "露点: {} °C",
    }

    lines = []

    dt = datetime.fromisoformat(data["updateTime"])
    lines.append(f"更新时间: {dt.strftime('%Y年%m月%d日 %H:%M')}")

    # 处理 hourly 列表
    for h in data.get("hourly", []):
        for k, v in hourly_mapping.items():
            if k not in h or h[k] in ("", None):
                continue

            if k == "fxTime":
                dt = datetime.fromisoformat(h[k])
                lines.append(f"\n({dt.strftime('%m-%d %H:%M')})")
            else:
                lines.append(v.format(h[k]))

    return "\n".join(lines)


if __name__ == "__main__":
    token = qweather_jwt()  # JWT
    now = fetch_weather_now(token)  # 实时天气
    air = fetch_air_quality(token)  # 实时空气质量
    hourly = fetch_weather_forecast(token)  # 24小时天气预报

    print(f"QWeather JWT: {token}")
    print("-" * 30)
    print(f"[实时天气]\n{format_weather(now)}")
    print("-" * 30)
    print(f"[实时空气质量]\n{format_air_quality(air)}")
    print("-" * 30)
    print(f"[24小时天气预报]\n{format_weather_forecast(hourly)}")
