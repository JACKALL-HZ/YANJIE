"""数据库会话管理。

开发期用 SQLite 文件库（零部署）；生产期仅改 DATABASE_URL 环境变量。
本模块单向 import app.db.models（不反向 import engine），避免循环导入。
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.models import Base

_settings = get_settings()
_connect_args: dict = {}
if _settings.database_url.startswith("sqlite"):
    # SQLite：check_same_thread=False 允许跨线程访问（FastAPI/SSE 场景）
    _connect_args = {"check_same_thread": False}

if _settings.database_url in ("sqlite://", "sqlite:///:memory:"):
    # 内存库必须用 StaticPool，否则每个连接是独立的一次性库，
    # init_db() 建表的连接与查询连接不在同一库，导致 no such table。
    engine = create_engine(
        _settings.database_url,
        connect_args=_connect_args,
        poolclass=StaticPool,
        future=True,
    )
else:
    engine = create_engine(
        _settings.database_url,
        connect_args=_connect_args,
        future=True,
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


# 幂等迁移清单：{表名: {列名: 列类型 DDL}}
# create_all 只建表不改表，旧库靠这里补列。新增字段时在此登记即可。
_ADD_COLUMNS: dict[str, dict[str, str]] = {
    "users": {
        "password_hash": "VARCHAR(255)",
    },
    "simulation_sessions": {
        "user_profile": "JSON",
        "owner_key": "VARCHAR(64)",
        "decision_history": "JSON",
    },
    "simulation_messages": {
        "sequence": "INTEGER",
    },
    "user_profiles": {
        # 1. 基本信息
        "gender": "VARCHAR(32)",
        "city": "VARCHAR(128)",
        "education": "VARCHAR(64)",
        "marital_status": "VARCHAR(32)",
        "dependents": "INTEGER",
        # 2. 职业与能力
        "occupation": "VARCHAR(128)",
        "industry": "VARCHAR(128)",
        "years_experience": "INTEGER",
        "certificates": "JSON",
        "strengths": "TEXT",
        "weaknesses": "TEXT",
        # 3. 财务状况
        "monthly_income": "INTEGER",
        "monthly_expense": "INTEGER",
        "liabilities": "INTEGER",
        "income_stability": "VARCHAR(32)",
        "insurance": "JSON",
        # 4. 风险与决策
        "loss_tolerance": "INTEGER",
        "decision_style": "VARCHAR(32)",
        "past_failures": "TEXT",
        # 5. 时间与资源
        "weekly_hours": "INTEGER",
        "support_network": "TEXT",
        # 6. 目标与约束
        "goals": "JSON",
        "constraints": "TEXT",
        "time_horizon": "INTEGER",
        "motivation": "TEXT",
    },
}

# 幂等索引清单：{索引名: (表名, 列名)}
_ADD_INDEXES: dict[str, tuple[str, str]] = {
    "ix_simulation_sessions_user_id": ("simulation_sessions", "user_id"),
    "ix_simulation_sessions_owner_key": ("simulation_sessions", "owner_key"),
    "ix_user_profiles_user_id": ("user_profiles", "user_id"),
}


def _migrate() -> None:
    """开发期幂等迁移：为已存在表补齐新列与索引（create_all 不会改旧表）。"""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table, columns in _ADD_COLUMNS.items():
            if table not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table)}
            for column, ddl_type in columns.items():
                if column in present:
                    continue
                conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}")
                )

        for index_name, (table, column) in _ADD_INDEXES.items():
            if table not in existing_tables:
                continue
            present_idx = {i["name"] for i in inspector.get_indexes(table)}
            if index_name in present_idx:
                continue
            conn.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS {index_name} "
                    f"ON {table} ({column})"
                )
            )


def init_db() -> None:
    """幂等建表（开发期替代 Alembic）。"""
    Base.metadata.create_all(bind=engine)
    _migrate()
