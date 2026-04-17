import os
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import psycopg
from dotenv import load_dotenv

load_dotenv()
DSN = os.getenv("DATABASE_URL", "").replace("+psycopg", "")
primary_dir = Path(os.getenv("BACKUP_DIR", "/backup"))


# 确保目录存在且可写，成功返回该目录，失败则抛出异常
def ensure_writable_dir(path: Path) -> Path:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as err:
        raise OSError(f"无法创建目录 {path}") from err

    if not (path.is_dir() and os.access(path, os.W_OK)):
        raise PermissionError(f"目录 {path} 不是目录或不可写")
    return path


# 尝试确保主目录可用，失败则回退到 ~/backup
try:
    BACKUP_DIR = ensure_writable_dir(primary_dir)
except Exception as e:
    # 使用 from e 保留原始异常链
    print(f"警告: 无法使用主备份目录 {primary_dir}，原因: {e}")
    fallback_dir = Path.home() / "backup"
    try:
        BACKUP_DIR = ensure_writable_dir(fallback_dir)
        print(f"已切换到备用备份目录: {BACKUP_DIR}")
    except Exception as e2:
        # 抛出最终错误，同时链接两个原始异常（通过 from e2 或使用自定义消息）
        raise RuntimeError(
            f"无法创建或使用任何备份目录: "
            f"主目录 {primary_dir} 失败({e}), "
            f"备用目录 {fallback_dir} 失败({e2})"
        ) from e2  # 链接最后一个异常即可，完整的两个异常信息已包含在消息中

# 使用最终目录
print(f"备份目录: {BACKUP_DIR}")

# 基本信息
result = urlparse(DSN)
PG_USER = result.username
query = parse_qs(result.query)
PG_HOST = query.get("host", ["localhost"])[0]
PG_PORT = query.get("port", ["5432"])[0]

# 排除默认数据库
EXCLUDE_DBS = {"postgres", "template0", "template1"}


# 获取数据库列表
def get_databases():
    # 检查数据库连接字符串
    if not DSN:
        raise RuntimeError("DATABASE_URL is not set in .env")

    # 连接到 PostgreSQL 数据库
    with (
        psycopg.connect(DSN) as conn,
        conn.cursor() as cur,
    ):
        cur.execute("SELECT datname FROM pg_database;")
        dbs = [row[0] for row in cur.fetchall()]

        return dbs


# 执行备份
def backup_database(db_name):
    today = datetime.now().strftime("%Y%m%d")
    filename = f"{BACKUP_DIR}/{db_name}_{today}.sql.zst"

    cmd = [
        "pg_dump",
        "-h",
        PG_HOST,
        "-U",
        PG_USER,
        "-d",
        db_name,
        "--no-owner",
        "--compress=zstd",
        "--create",
        "--clean",
    ]

    print(f"- [{db_name}] -> {filename}")

    with open(filename, "wb") as f:
        subprocess.run(cmd, stdout=f, check=True)


def main():
    dbs = get_databases()

    for db in dbs:
        if db in EXCLUDE_DBS:
            continue

        backup_database(db)


if __name__ == "__main__":
    main()
