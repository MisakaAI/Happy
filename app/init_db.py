from sqlmodel import SQLModel

from app.database import engine
from app.models.qweather import AirQuality, Weather  # noqa: F401

# 初始化数据库
# python -m app.init_db


def init_db():
    SQLModel.metadata.create_all(engine)


if __name__ == "__main__":
    init_db()
