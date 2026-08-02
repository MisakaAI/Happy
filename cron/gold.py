#!/usr/bin/env python3

# https://www.sge.com.cn/cpfw/yqjyxq?pro_id=793740150630875136&parent_cplx=0&cplx=9
# https://m.cmbchina.com/goldratedetail.html?no=AUTD

# 采集黄金价格
# python -m cron.gold
# 跳过交易时段判断，强制采集
# python -m cron.gold --force

# CRON 每分钟执行，程序内部判断上海黄金交易所交易时段
# * * * * * cd $(pwd) && PYTHONPATH=$(pwd) $(pwd)/.venv/bin/python -m cron.gold >> /dev/null 2>> $(pwd)/logs/error.log

import argparse
import datetime as dt
import json
import os
from zoneinfo import ZoneInfo

import psycopg
import requests
from dotenv import load_dotenv

load_dotenv()

DSN = os.getenv("DATABASE_URL", "").replace("+psycopg", "")
API_URL = "https://m.cmbchina.com/api/rate/gold"
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

# 黄金价格表结构定义
SCHEMA = """
CREATE TABLE IF NOT EXISTS gold (
    id    BIGSERIAL PRIMARY KEY,
    code  VARCHAR(20) NOT NULL,
    price NUMERIC(12, 4) NOT NULL,
    ts    TIMESTAMPTZ NOT NULL,
    CONSTRAINT unique_gold UNIQUE (code, ts),
    CONSTRAINT chk_gold_price_pos CHECK (price > 0)
);

CREATE INDEX IF NOT EXISTS idx_gold_latest
    ON gold(code, ts DESC);
"""


# 幂等创建当前程序所需的数据表和索引
def init_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(SCHEMA)


# 判断是否处于交易时段（按分钟计算，结束分钟包含在内）
def is_trading_time(now: dt.datetime | None = None) -> bool:
    if now is None:
        now = dt.datetime.now(SHANGHAI_TZ)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=SHANGHAI_TZ)
    else:
        now = now.astimezone(SHANGHAI_TZ)

    weekday = now.weekday()  # 周一为 0，周日为 6
    minute = now.hour * 60 + now.minute

    # 日盘：周一至周五 09:00-11:30、13:30-15:30
    if weekday <= 4 and (9 * 60 <= minute <= 11 * 60 + 30):
        return True
    if weekday <= 4 and (13 * 60 + 30 <= minute <= 15 * 60 + 30):
        return True

    # 夜盘：周一至周五 19:50-23:59，次日（周二至周六）00:00-02:30
    if weekday <= 4 and minute >= 19 * 60 + 50:
        return True
    return 1 <= weekday <= 5 and minute <= 2 * 60 + 30


def fetch_gold_rates() -> tuple[dt.datetime, list[dict]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }
    session = requests.Session()
    session.trust_env = False
    r = session.get(API_URL, headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()

    if data.get("returnCode") != "SUC0000":
        raise RuntimeError(
            f"API error: returnCode={data.get('returnCode')}, msg={data.get('errorMsg')}"
        )

    body = data.get("body") or {}
    snapshot_time = body.get("time")
    rows = body.get("data")
    if snapshot_time in (None, "") or not isinstance(rows, list):
        raise ValueError(f"Unexpected body: {json.dumps(body, ensure_ascii=False)}")

    ts = parse_snapshot_time(snapshot_time)
    return ts, rows


def parse_snapshot_time(raw: str) -> dt.datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            naive = dt.datetime.strptime(raw, fmt)
            # 接口时间按中国时区解释，写入 timestamptz。
            return naive.replace(tzinfo=SHANGHAI_TZ)
        except ValueError:
            pass
    raise ValueError(f"Unrecognized body.time format: {raw}")


def insert_gold_rows(conn, ts: dt.datetime, rows: list[dict]) -> int:
    inserted = 0
    with conn.cursor() as cur:
        for row in rows:
            code = row.get("goldNo")
            cur_price = row.get("curPrice")
            if code in (None, "") or cur_price in (None, ""):
                continue

            price = float(cur_price)
            if price <= 0:
                # gold 表有 price > 0 约束，0 或负值直接跳过。
                continue

            cur.execute(
                """
                INSERT INTO gold (code, price, ts)
                VALUES (%s, %s, %s)
                ON CONFLICT (code, ts) DO NOTHING;
                """,
                (code, price, ts),
            )
            inserted += cur.rowcount

    return inserted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="采集招商银行黄金价格")
    parser.add_argument(
        "--force",
        action="store_true",
        help="跳过交易时段判断并强制执行采集",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.force and not is_trading_time():
        print("Skipped: outside gold trading hours")
        return

    # 检查数据库连接字符串
    if not DSN:
        raise RuntimeError("DATABASE_URL is not set in .env")

    ts, rows = fetch_gold_rates()
    with psycopg.connect(DSN) as conn:
        init_schema(conn)
        count = insert_gold_rows(conn, ts, rows)
        conn.commit()
        print(f"Inserted: gold={count} row(s)")


if __name__ == "__main__":
    main()
