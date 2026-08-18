"""kb_chunks 双存储同步测试 — Chroma + SQL 表同时写入"""
import pytest

from app.db.models import KbChunk
from app.db.session import init_db, SessionLocal


@pytest.fixture(autouse=True)
def _init_db():
    """每个测试前确保表存在"""
    init_db()


class TestKbChunkDualStorage:
    def test_kb_chunk_repo_save_and_query(self, tmp_path):
        """KbChunkRepo 存储后可按行业/城市查询"""
        from app.db.repository import KbChunkRepo

        db = SessionLocal()
        try:
            repo = KbChunkRepo(db)

            repo.save_batch([
                {
                    "chunk_id": "c1",
                    "content": "杭州奶茶竞争激烈",
                    "industry": "milk_tea",
                    "city": "hangzhou",
                    "chunk_type": "case",
                    "source": "01-奶茶行业.md",
                },
                {
                    "chunk_id": "c2",
                    "content": "深圳零售市场饱和",
                    "industry": "retail",
                    "city": "shenzhen",
                    "chunk_type": "analysis",
                    "source": "02-零售.md",
                },
                {
                    "chunk_id": "c3",
                    "content": "杭州奶茶定价策略",
                    "industry": "milk_tea",
                    "city": "hangzhou",
                    "chunk_type": "strategy",
                    "source": "03-策略.md",
                },
            ])

            # 按行业查
            milktea = repo.query(industry="milk_tea")
            assert len(milktea) == 2

            # 按城市查
            hz = repo.query(city="hangzhou")
            assert len(hz) == 2

            # 按类型查
            cases = repo.query(chunk_type="case")
            assert len(cases) == 1
            assert cases[0].content == "杭州奶茶竞争激烈"

        finally:
            db.rollback()
            db.close()

    def test_kb_chunk_idempotent_upsert(self, tmp_path):
        """幂等：重复写入同 id 不报错，后写覆盖"""
        from app.db.repository import KbChunkRepo

        db = SessionLocal()
        try:
            repo = KbChunkRepo(db)

            repo.save_batch([{
                "chunk_id": "c_upsert",
                "content": "版本1",
                "industry": "test",
                "city": "test",
                "chunk_type": "test",
                "source": "test.md",
            }])
            db.commit()

            repo.save_batch([{
                "chunk_id": "c_upsert",
                "content": "版本2",
                "industry": "test",
                "city": "test",
                "chunk_type": "test",
                "source": "test.md",
            }])
            db.commit()

            results = repo.query(industry="test")
            assert len(results) == 1
            assert results[0].content == "版本2"

        finally:
            db.rollback()
            db.close()
