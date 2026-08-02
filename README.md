# HAPPY

**H**ome **A**I **P**latform with **Py**thon

- [x] [通过 Astrbot 推送消息](./tools/astrbot.py)
- [x] [调用 LLM 对话](./tools/llm.py)
- [x] [和风天气 API](./tools/qweather.py)

## 定时任务

```sh
# 自动安装定时任务
bash cron/install_cron.sh
```

- [x] [安装](./cron/install_cron.sh)
- [x] [骑行建议](./cron/cycling_tips.py)
- [x] [和风天气](./cron/qweather.py)
- [x] [黄金](./cron/gold.py)
- [x] [基金](./cron/fund.py)
- [x] [汇率](./cron/fx.py)

## Web 数据看板与 API

Web 服务读取定时任务写入 PostgreSQL 的数据，提供天气、外汇、基金和黄金看板。配置 `.env` 中的 `DATABASE_URL` 后启动：

```sh
uv run uvicorn web.app:app --host 0.0.0.0 --port 8000 --reload
```

页面入口：

| 页面 | 地址 | 数据来源 |
| --- | --- | --- |
| 天气与空气质量 | <http://localhost:8000/weather> | `cron/qweather.py` |
| 外汇实时牌价 | <http://localhost:8000/fx> | `cron/fx.py` |
| 基金净值 | <http://localhost:8000/fund> | `cron/fund.py` |
| 贵金属实时行情 | <http://localhost:8000/gold> | `cron/gold.py` |
| OpenAPI 文档 | <http://localhost:8000/docs> | FastAPI 自动生成 |

外汇和贵金属页面展示全部品种的最新行情及所选品种的当日曲线；基金页面展示每只基金的最新净值及最近 180 天净值曲线。贵金属行情中 `AGTD` 为白银，单位是元/千克；其他品种为黄金，单位是元/克。页面使用 Vue 3 与 ECharts CDN，浏览器需要能访问 jsDelivr。

### 行情 API

| 接口 | 说明 |
| --- | --- |
| `GET /fx/now` | 每个币种的最新牌价；传 `code` 时返回该币种单条数据 |
| `GET /fx/today` | 当天全部外汇牌价；支持 `code` 过滤 |
| `GET /gold/now` | 每个贵金属品种的最新价格；传 `code` 时返回该品种单条数据 |
| `GET /gold/today` | 当天全部贵金属价格；支持 `code` 过滤 |
| `GET /fund/now` | 每只基金的最新净值；传 `code` 时返回该基金单条数据 |
| `GET /fund/today` | 当天公布的基金净值；支持 `code` 过滤 |
| `GET /fund/recent` | 最近 90 天净值；支持 `days=1..3660` 和 `code` |

`/fx` 和 `/gold` 在带 `date=YYYYMMDD` 时返回数据而不是 HTML 页面，并兼容天气接口的时间查询方式：`start=HHMM&end=HHMM` 查询闭合到结束分钟的区间，`time=HHMM` 查询最接近指定时间的记录。未传 `code` 时，`time` 返回每个品种最接近该时间的记录。`/fund` 带 `date=YYYYMMDD` 时返回当日净值，也支持 `code`。

示例：

```text
GET /fx?date=20260802&code=USD
GET /fx?date=20260802&start=0900&end=1130&code=JPY
GET /gold?date=20260802&time=1030&code=AUTD
GET /fund?date=20260801&code=017641
GET /fund/recent?days=180&code=017641
```

天气与空气质量接口继续提供 `/weather/now`、`/weather/today`、`/air/now` 和 `/air/today`；`/weather`、`/air` 带 `date` 时支持同样的日期和时间参数。

## 📝 开源协议

[DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE](https://www.wtfpl.net/txt/copying/)
