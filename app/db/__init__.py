"""Database layer (SQLAlchemy 2.0).

开发期用 SQLite，生产期切换连接串即可（schema 完全一致）。
本模块只依赖 SQLAlchemy，不得反向 import app.engine，避免循环导入。
"""

from app.db.models import Base
from app.db.session import SessionLocal, engine, init_db

__all__ = ["Base", "SessionLocal", "engine", "init_db"]
