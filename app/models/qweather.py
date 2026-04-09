from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Weather(SQLModel, table=True):
    __tablename__ = "weather"

    id: int | None = Field(default=None, primary_key=True)
    # 数据观测时间
    obs_time: datetime = Field(unique=True)

    # 温度，默认单位：摄氏度
    temp: int | None
    # 体感温度，默认单位：摄氏度
    feels_like: int | None
    # 天气状况的图标代码，参考[天气图标项目](https://icons.qweather.com/)
    icon: str | None = Field(max_length=10)
    # 天气状况的文字描述，包括阴晴雨雪等天气状态的描述
    weather_text: str | None = Field(max_length=50)

    # 风向360角度
    wind_360: int | None
    # 风向
    wind_dir: str | None = Field(max_length=50)
    # 风力等级
    wind_scale: str | None = Field(max_length=10)
    # 风速，公里/小时
    wind_speed: int | None

    # 相对湿度，百分比数值
    humidity: int | None
    # 过去1小时降水量，默认单位：毫米
    precip: float | None
    # 大气压强，默认单位：百帕
    pressure: int | None
    # 能见度，默认单位：公里
    vis: int | None
    # 云量，百分比数值。可能为空
    cloud: int | None
    # 露点温度。可能为空
    dew: int | None

    # 创建时间
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), nullable=False
    )


class AirQuality(SQLModel, table=True):
    __tablename__ = "air_quality"

    id: int | None = Field(default=None, primary_key=True)

    # 空气质量指数的值
    aqi: int | None
    # 空气质量指数等级，可能为空
    aqi_level: int | None

    # 颗粒物（粒径小于等于2.5µm）
    pm25: float | None
    # 颗粒物（粒径小于等于10µm）
    pm10: float | None
    # 二氧化氮
    no2: float | None
    # 臭氧
    o3: float | None
    # 二氧化硫
    so2: float | None
    # 一氧化碳
    co: float | None

    # AQI相关联的监测站名称
    stations: str | None = Field(max_length=30)
    # 首要污染物的名字，可能为空
    primary_pollutant: str | None = Field(max_length=20)

    # 创建时间
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), nullable=False
    )
