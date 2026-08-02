#!/usr/bin/env python3

# https://fund.cmbchina.com/OpenFundDetail?Channel=Summary&FundID=017641

# 采集基金净值
# python -m cron.fund 017641

# CRON 每天 17:00 执行一次
# 0 17 * * * cd $(pwd) && PYTHONPATH=$(pwd) $(pwd)/.venv/bin/python -m cron.fund 017641 >> /dev/null 2>> $(pwd)/logs/error.log

import datetime as dt
import json
import os
import sys

import psycopg
import requests
from dotenv import load_dotenv

load_dotenv()

DSN = os.getenv("DATABASE_URL", "").replace("+psycopg", "")
API_URL = "https://fund.cmbchina.com/api/v1/fund/buy?code={code}"

# 基金及基金净值表结构定义
SCHEMA = """
CREATE TABLE IF NOT EXISTS fund (
    id      BIGSERIAL PRIMARY KEY,
    code    VARCHAR(20) NOT NULL UNIQUE,
    name    VARCHAR(60) NOT NULL,
    manager VARCHAR(30)
);

CREATE TABLE IF NOT EXISTS fund_nav (
    id        BIGSERIAL PRIMARY KEY,
    fund_id   BIGINT NOT NULL REFERENCES fund(id) ON DELETE CASCADE,
    nav_date  DATE NOT NULL,
    net_value NUMERIC(12, 6) NOT NULL,
    CONSTRAINT unique_fund_nav UNIQUE (fund_id, nav_date),
    CONSTRAINT chk_nav_pos CHECK (net_value > 0)
);

CREATE INDEX IF NOT EXISTS idx_fund_nav_date
    ON fund_nav(nav_date);
CREATE INDEX IF NOT EXISTS idx_fund_nav_fund_date_desc
    ON fund_nav(fund_id, nav_date DESC);
"""


# 幂等创建当前程序所需的数据表和索引
def init_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(SCHEMA)


def fetch_fund_buy(code: str) -> dict:
    url = API_URL.format(code=code)
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "Accept": "*/*",
    }
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()

    if data.get("returnCode") != "SUC0000":
        raise RuntimeError(
            f"API error: returnCode={data.get('returnCode')}, msg={data.get('errorMsg')}"
        )

    body = data.get("body") or {}
    # 必要字段校验
    for k in ("code", "name", "latestNetValue", "updateTime"):
        if body.get(k) in (None, ""):
            raise ValueError(
                f"Missing field '{k}' in body: {json.dumps(body, ensure_ascii=False)}"
            )

    return body


def parse_nav_date(update_time_str: str) -> dt.date:
    """
    API: "2026-02-26 00:00:00" -> date(2026,2,26)
    """
    # 兼容可能出现的格式变化
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(update_time_str, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Unrecognized updateTime format: {update_time_str}")


def upsert_fund_and_nav(
    conn,
    code: str,
    name: str,
    manager: str | None,
    nav_date: dt.date,
    net_value: float,
) -> int:
    """
    写入：
      - fund(code unique)
      - fund_nav(fund_id, nav_date unique)
    """
    with conn.cursor() as cur:
        # 1) fund：不存在则插入，存在则更新 name/manager（防止基金信息变更）
        cur.execute(
            """
            INSERT INTO fund (code, name, manager)
            VALUES (%s, %s, %s)
            ON CONFLICT (code) DO UPDATE
              SET name = EXCLUDED.name,
                  manager = EXCLUDED.manager
            RETURNING id;
            """,
            (code, name, manager),
        )
        fund_id = cur.fetchone()[0]

        # 2) fund_nav：按 (fund_id, nav_date) 去重
        cur.execute(
            """
            INSERT INTO fund_nav (fund_id, nav_date, net_value)
            VALUES (%s, %s, %s)
            ON CONFLICT (fund_id, nav_date) DO NOTHING;
            """,
            (fund_id, nav_date, net_value),
        )
        return cur.rowcount


def main():
    # 检查数据库连接字符串
    if not DSN:
        raise RuntimeError("DATABASE_URL is not set in .env")

    # 从命令行读取基金代码，未指定时采集默认基金
    code = sys.argv[1] if len(sys.argv) > 1 else "017641"

    body = fetch_fund_buy(code)
    fund_code = body["code"]
    fund_name = body["name"]
    fund_manager = body.get("manager")
    nav_date = parse_nav_date(body["updateTime"])
    net_value = float(body["latestNetValue"])

    with psycopg.connect(DSN) as conn:
        init_schema(conn)
        count = upsert_fund_and_nav(
            conn, fund_code, fund_name, fund_manager, nav_date, net_value
        )
        conn.commit()
        print(f"Inserted: fund_nav={count} row(s)")


if __name__ == "__main__":
    main()
