#!/usr/bin/env python3
"""
天气、空气质量与资产行情 FastAPI 服务

启动:
    uvicorn web.app:app --reload
    python -m web.app

路由说明:
    GET /weather            无参数 -> 返回 weather.html；带 date -> 数据
    GET /air                同上，对应 air_quality 表
    GET /weather/now        最新一条天气
    GET /air/now            最新一条空气质量
    GET /weather/today      当天（系统时区）全部天气
    GET /air/today          当天（系统时区）全部空气质量

    GET /fx                 外汇页面；带 date 参数时返回外汇数据
    GET /fund               基金页面；带 date 参数时返回基金净值
    GET /gold               黄金页面；带 date 参数时返回黄金价格
    GET /{fx,gold}/now      每个品种的最新一条行情
    GET /{fx,gold}/today    当天全部行情
    GET /fund/now           每只基金的最新净值
    GET /fund/today         当天公布的基金净值
    GET /fund/recent        最近若干天的基金净值

    GET /weather?date=20260630                          2026-06-30 全部数据
    GET /weather?date=20260630&start=1000&end=1200      10:00 ~ 12:00 全部数据
    GET /weather?date=20260630&time=1000                最接近 10:00 的一条数据
"""

import os
from datetime import date as date_type
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse

load_dotenv()

DSN = os.getenv("DATABASE_URL", "").replace("+psycopg", "")
BASE_DIR = Path(__file__).parent
HTML_PATHS = {
    "weather": BASE_DIR / "weather.html",
    "fx": BASE_DIR / "fx.html",
    "fund": BASE_DIR / "fund.html",
    "gold": BASE_DIR / "gold.html",
}

# 系统本地时区，用于"当天"判定与时间格式化
LOCAL_TZ = datetime.now().astimezone().tzinfo

app = FastAPI(title="Happy Data API")

# 表名 -> (表名, 时间列)；weather 按观测时间，air_quality 按入库时间
TABLES = {
    "weather": ("weather", "obs_time"),
    "air": ("air_quality", "created_at"),
}

# 行情类型 -> (表名, 时间列)
MARKET_TABLES = {
    "fx": ("fx_rate", "ts"),
    "gold": ("gold", "ts"),
}


# --- 工具函数 ---


# 校验连接字符串
def _check_dsn() -> None:
    if not DSN:
        raise HTTPException(500, "DATABASE_URL 未配置")


# 解析 YYYYMMDD -> 本地时区当天零点（带时区）
def _parse_date(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y%m%d").replace(tzinfo=LOCAL_TZ)
    except ValueError:
        raise HTTPException(400, f"date 格式错误: {value}，应为 YYYYMMDD") from None


# 解析 HHMM -> datetime.time
def _parse_hhmm(value: str):
    try:
        return datetime.strptime(value, "%H%M").time()
    except ValueError:
        raise HTTPException(400, f"时间格式错误: {value}，应为 HHMM") from None


# 将行中的 datetime 转为本地时区字符串，便于 JSON 序列化
def _serialize(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = v.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(v, date_type):
            out[k] = v.isoformat()
        elif isinstance(v, Decimal):
            out[k] = float(v)
        else:
            out[k] = v
    return out


# 拼接本地时区的时间点：date(00:00) + HHMM
def _at(day: datetime, hhmm: str) -> datetime:
    return datetime.combine(day.date(), _parse_hhmm(hhmm), tzinfo=LOCAL_TZ)


# 查询 [start, end) 区间内的全部记录，按时间升序
def _query_range(table: str, ts_col: str, start: datetime, end: datetime) -> list[dict]:
    _check_dsn()
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT * FROM {table} "
            f"WHERE {ts_col} >= %s AND {ts_col} < %s ORDER BY {ts_col}",
            (start, end),
        )
        cols = [d[0] for d in cur.description]
        return [_serialize(dict(zip(cols, r, strict=True))) for r in cur.fetchall()]


# 查询最新一条记录
def _query_latest(table: str, ts_col: str) -> dict | None:
    _check_dsn()
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {table} ORDER BY {ts_col} DESC LIMIT 1")
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        return _serialize(dict(zip(cols, row, strict=True))) if row else None


# 查询最接近 target 的一条记录
def _query_closest(table: str, ts_col: str, target: datetime) -> dict | None:
    _check_dsn()
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT * FROM {table} "
            f"ORDER BY ABS(EXTRACT(EPOCH FROM ({ts_col} - %s))) ASC LIMIT 1",
            (target,),
        )
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        return _serialize(dict(zip(cols, row, strict=True))) if row else None


def _fetch_all(query: str, params: tuple = ()) -> list[dict]:
    """执行固定 SQL 并返回可 JSON 序列化的字典列表。"""
    _check_dsn()
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute(query, params)
        cols = [d[0] for d in cur.description]
        return [_serialize(dict(zip(cols, row, strict=True))) for row in cur.fetchall()]


def _market_range(
    kind: str, start: datetime, end: datetime, code: str | None = None
) -> list[dict]:
    table, ts_col = MARKET_TABLES[kind]
    code_sql = " AND code = %s" if code else ""
    params = (start, end, code) if code else (start, end)
    return _fetch_all(
        f"SELECT * FROM {table} "
        f"WHERE {ts_col} >= %s AND {ts_col} < %s{code_sql} "
        f"ORDER BY {ts_col}, code",
        params,
    )


def _market_latest(kind: str, code: str | None = None) -> dict | list[dict] | None:
    table, ts_col = MARKET_TABLES[kind]
    if code:
        rows = _fetch_all(
            f"SELECT * FROM {table} WHERE code = %s ORDER BY {ts_col} DESC LIMIT 1",
            (code,),
        )
        return rows[0] if rows else None

    return _fetch_all(
        f"SELECT * FROM ("
        f"SELECT DISTINCT ON (code) * FROM {table} ORDER BY code, {ts_col} DESC"
        f") AS latest ORDER BY code"
    )


def _market_closest(
    kind: str, target: datetime, code: str | None = None
) -> dict | list[dict] | None:
    table, ts_col = MARKET_TABLES[kind]
    if code:
        rows = _fetch_all(
            f"SELECT * FROM {table} WHERE code = %s "
            f"ORDER BY ABS(EXTRACT(EPOCH FROM ({ts_col} - %s))) LIMIT 1",
            (code, target),
        )
        return rows[0] if rows else None

    return _fetch_all(
        f"SELECT * FROM ("
        f"SELECT DISTINCT ON (code) * FROM {table} "
        f"ORDER BY code, ABS(EXTRACT(EPOCH FROM ({ts_col} - %s)))"
        f") AS closest ORDER BY code",
        (target,),
    )


def _market_by_date(
    kind: str,
    date: str,
    start: str | None,
    end: str | None,
    t: str | None,
    code: str | None,
) -> dict | list | None:
    day = _parse_date(date)
    if t is not None:
        return _market_closest(kind, _at(day, t), code)

    if start is not None or end is not None:
        if start is None or end is None:
            raise HTTPException(400, "start 与 end 必须同时提供，格式 HHMM")
        lo = _at(day, start)
        hi = _at(day, end) + timedelta(minutes=1)
        return _market_range(kind, lo, hi, code)

    return _market_range(kind, day, day + timedelta(days=1), code)


FUND_SELECT = """
SELECT f.code, f.name, f.manager, n.nav_date, n.net_value
FROM fund_nav AS n
JOIN fund AS f ON f.id = n.fund_id
"""


def _fund_range(
    start: date_type, end: date_type, code: str | None = None
) -> list[dict]:
    code_sql = " AND f.code = %s" if code else ""
    params = (start, end, code) if code else (start, end)
    return _fetch_all(
        FUND_SELECT
        + f"WHERE n.nav_date >= %s AND n.nav_date < %s{code_sql} "
        + "ORDER BY n.nav_date, f.code",
        params,
    )


def _fund_latest(code: str | None = None) -> dict | list[dict] | None:
    if code:
        rows = _fetch_all(
            FUND_SELECT + "WHERE f.code = %s ORDER BY n.nav_date DESC LIMIT 1",
            (code,),
        )
        return rows[0] if rows else None

    return _fetch_all(
        "SELECT * FROM ("
        "SELECT DISTINCT ON (f.code) f.code, f.name, f.manager, "
        "n.nav_date, n.net_value "
        "FROM fund_nav AS n JOIN fund AS f ON f.id = n.fund_id "
        "ORDER BY f.code, n.nav_date DESC"
        ") AS latest ORDER BY code"
    )


# 按日期参数查询：返回单条（time）或列表（全天 / start-end）
def _by_date(
    table: str,
    ts_col: str,
    date: str,
    start: str | None,
    end: str | None,
    t: str | None,
) -> dict | list:
    day = _parse_date(date)

    # time：返回最接近的一条
    if t is not None:
        return _query_closest(table, ts_col, _at(day, t))

    # start/end：必须同时提供，区间为 [start, end+1min)（end 分钟闭区间）
    if start is not None or end is not None:
        if start is None or end is None:
            raise HTTPException(400, "start 与 end 必须同时提供，格式 HHMM")
        lo = _at(day, start)
        hi = _at(day, end) + timedelta(minutes=1)
        return _query_range(table, ts_col, lo, hi)

    # 仅 date：当天全天 [00:00, 次日 00:00)
    return _query_range(table, ts_col, day, day + timedelta(days=1))


# --- 路由 ---


@app.get("/")
def root():
    return RedirectResponse(url="/weather")


# GET /weather, GET /air
def _serve(
    kind: str, date: str | None, start: str | None, end: str | None, t: str | None
):
    # 无 date 参数 -> 返回页面
    if date is None:
        return FileResponse(HTML_PATHS["weather"])
    table, ts_col = TABLES[kind]
    return _by_date(table, ts_col, date, start, end, t)


@app.get("/weather")
def weather(
    date: str | None = Query(default=None, description="YYYYMMDD"),
    start: str | None = Query(default=None, description="HHMM"),
    end: str | None = Query(default=None, description="HHMM"),
    time: str | None = Query(default=None, description="HHMM"),
):
    return _serve("weather", date, start, end, time)


@app.get("/air")
def air(
    date: str | None = Query(default=None, description="YYYYMMDD"),
    start: str | None = Query(default=None, description="HHMM"),
    end: str | None = Query(default=None, description="HHMM"),
    time: str | None = Query(default=None, description="HHMM"),
):
    return _serve("air", date, start, end, time)


@app.get("/weather/now")
def weather_now():
    return _query_latest(*TABLES["weather"])


@app.get("/air/now")
def air_now():
    return _query_latest(*TABLES["air"])


@app.get("/weather/today")
def weather_today():
    day = datetime.now(LOCAL_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return _query_range(*TABLES["weather"], day, day + timedelta(days=1))


@app.get("/air/today")
def air_today():
    day = datetime.now(LOCAL_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return _query_range(*TABLES["air"], day, day + timedelta(days=1))


# --- 外汇与黄金 ---


def _serve_market(
    kind: str,
    date: str | None,
    start: str | None,
    end: str | None,
    t: str | None,
    code: str | None,
):
    if date is None:
        return FileResponse(HTML_PATHS[kind])
    return _market_by_date(kind, date, start, end, t, code)


@app.get("/fx")
def fx(
    date: str | None = Query(default=None, description="YYYYMMDD"),
    start: str | None = Query(default=None, description="HHMM"),
    end: str | None = Query(default=None, description="HHMM"),
    time: str | None = Query(default=None, description="HHMM"),
    code: str | None = Query(default=None, description="币种代码，如 USD"),
):
    return _serve_market("fx", date, start, end, time, code)


@app.get("/gold")
def gold(
    date: str | None = Query(default=None, description="YYYYMMDD"),
    start: str | None = Query(default=None, description="HHMM"),
    end: str | None = Query(default=None, description="HHMM"),
    time: str | None = Query(default=None, description="HHMM"),
    code: str | None = Query(default=None, description="黄金品种代码，如 Au(T+D)"),
):
    return _serve_market("gold", date, start, end, time, code)


@app.get("/fx/now")
def fx_now(code: str | None = Query(default=None)):
    return _market_latest("fx", code)


@app.get("/gold/now")
def gold_now(code: str | None = Query(default=None)):
    return _market_latest("gold", code)


@app.get("/fx/today")
def fx_today(code: str | None = Query(default=None)):
    day = datetime.now(LOCAL_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return _market_range("fx", day, day + timedelta(days=1), code)


@app.get("/gold/today")
def gold_today(code: str | None = Query(default=None)):
    day = datetime.now(LOCAL_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return _market_range("gold", day, day + timedelta(days=1), code)


# --- 基金 ---


@app.get("/fund")
def fund(
    date: str | None = Query(default=None, description="YYYYMMDD"),
    code: str | None = Query(default=None, description="基金代码"),
):
    if date is None:
        return FileResponse(HTML_PATHS["fund"])
    day = _parse_date(date).date()
    return _fund_range(day, day + timedelta(days=1), code)


@app.get("/fund/now")
def fund_now(code: str | None = Query(default=None)):
    return _fund_latest(code)


@app.get("/fund/today")
def fund_today(code: str | None = Query(default=None)):
    day = datetime.now(LOCAL_TZ).date()
    return _fund_range(day, day + timedelta(days=1), code)


@app.get("/fund/recent")
def fund_recent(
    days: int = Query(default=90, ge=1, le=3660),
    code: str | None = Query(default=None),
):
    today = datetime.now(LOCAL_TZ).date()
    return _fund_range(
        today - timedelta(days=days - 1), today + timedelta(days=1), code
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("web.app:app", host="0.0.0.0", port=8000, reload=True)
