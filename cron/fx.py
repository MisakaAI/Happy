#!/usr/bin/env python3

# https://fx.cmbchina.com/hq

# 外汇实时汇率
# python -m cron.fx

# CRON 每分钟执行一次
# * * * * * cd $(pwd) && PYTHONPATH=$(pwd) $(pwd)/.venv/bin/python -m cron.fx >> /dev/null 2>> $(pwd)/logs/error.log

import datetime as dt
import json
import os
import re
from zoneinfo import ZoneInfo

import psycopg
import requests
from dotenv import load_dotenv

load_dotenv()

DSN = os.getenv("DATABASE_URL", "").replace("+psycopg", "")
API_URL = "https://fx.cmbchina.com/api/v1/fx/rate"

# 表结构定义
SCHEMA = """
CREATE TABLE IF NOT EXISTS fx_rate (
    id       BIGSERIAL PRIMARY KEY,
    name     VARCHAR(20) NOT NULL,
    code     VARCHAR(20) NOT NULL,
    spot_bid NUMERIC(18, 6) NOT NULL,
    spot_ask NUMERIC(18, 6) NOT NULL,
    cash_bid NUMERIC(18, 6) NOT NULL,
    cash_ask NUMERIC(18, 6) NOT NULL,
    ts       TIMESTAMPTZ NOT NULL,
    CONSTRAINT unique_fx_rate UNIQUE (code, ts),
    CONSTRAINT chk_fx_rate_pos CHECK (
        spot_bid > 0 AND spot_ask > 0 AND cash_bid > 0 AND cash_ask > 0
    )
);

CREATE INDEX IF NOT EXISTS idx_fx_rate_latest
    ON fx_rate(code, ts DESC);
CREATE INDEX IF NOT EXISTS idx_fx_rate_ts
    ON fx_rate(ts);
"""


# 幂等创建当前程序所需的数据表和索引
def init_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(SCHEMA)


def fetch_fx_rates() -> list[dict]:
    headers = {
        "User-Agent": os.getenv("USER_AGENT", ""),
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

    body = data.get("body")
    if not isinstance(body, list):
        raise ValueError(f"Unexpected body: {json.dumps(body, ensure_ascii=False)}")
    return body


def parse_row_ts(row: dict) -> dt.datetime:
    raw_date = row.get("ratDat")
    raw_time = row.get("ratTim")
    if raw_date in (None, "") or raw_time in (None, ""):
        raise ValueError(
            f"Missing ratDat/ratTim: {json.dumps(row, ensure_ascii=False)}"
        )

    raw = f"{raw_date} {raw_time}"
    for fmt in ("%Y年%m月%d日 %H:%M:%S", "%Y年%m月%d日 %H:%M"):
        try:
            naive = dt.datetime.strptime(raw, fmt)
            # 接口时间按中国时区解释，写入 timestamptz。
            return naive.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
        except ValueError:
            pass
    raise ValueError(f"Unrecognized ratDat/ratTim format: {raw}")


def parse_pair_code(row: dict) -> str:
    eng = str(row.get("ccyNbrEng") or "").strip()
    m = re.search(r"\b([A-Z]{3})\b\s*$", eng)
    if m:
        return f"{m.group(1)}"

    # 兜底：直接用中文名称，避免整条记录丢弃
    name = str(row.get("ccyNbr") or "").strip()
    if name:
        return f"{name}"

    raise ValueError(f"Missing ccyNbrEng/ccyNbr: {json.dumps(row, ensure_ascii=False)}")


def insert_fx_rows(conn, rows: list[dict]) -> int:
    inserted = 0
    with conn.cursor() as cur:
        for row in rows:
            name = row.get("ccyNbr")
            if name in (None, ""):
                continue

            spot_bid_raw = row.get("rthBid")
            spot_ask_raw = row.get("rthOfr")
            cash_bid_raw = row.get("rtcBid")
            cash_ask_raw = row.get("rtcOfr")
            if any(
                v in (None, "")
                for v in (spot_bid_raw, spot_ask_raw, cash_bid_raw, cash_ask_raw)
            ):
                continue

            spot_bid = float(spot_bid_raw)
            spot_ask = float(spot_ask_raw)
            cash_bid = float(cash_bid_raw)
            cash_ask = float(cash_ask_raw)
            if min(spot_bid, spot_ask, cash_bid, cash_ask) <= 0:
                # fx_rate 表有正数约束，异常值直接跳过
                continue

            code = parse_pair_code(row)
            ts = parse_row_ts(row)

            cur.execute(
                """
                INSERT INTO fx_rate (name, code, spot_bid, spot_ask, cash_bid, cash_ask, ts)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (code, ts) DO NOTHING;
                """,
                (name, code, spot_bid, spot_ask, cash_bid, cash_ask, ts),
            )
            inserted += cur.rowcount

    return inserted


def main():
    # 检查数据库连接字符串
    if not DSN:
        raise RuntimeError("DATABASE_URL is not set in .env")

    rows = fetch_fx_rates()
    with psycopg.connect(DSN) as conn:
        init_schema(conn)
        count = insert_fx_rows(conn, rows)
        conn.commit()
        print(f"Inserted: fx_rate={count} row(s)")


if __name__ == "__main__":
    main()
