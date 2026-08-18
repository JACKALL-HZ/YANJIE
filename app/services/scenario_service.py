"""场景业务逻辑 —— 场景列表、详情查询。"""

from app.core.logging import get_logger
from app.db.repository import ScenarioRepo
from app.schemas.decision_source import DecisionSource
from app.scenarios.loader import ScenarioLoader

logger = get_logger(__name__)


class ScenarioService:
    """场景 CRUD 业务编排。

    职责：从 DB 和文件系统获取场景列表与详情，负责降级兜底逻辑。
    """

    def __init__(self, loader: ScenarioLoader, repo: ScenarioRepo | None = None):
        self._loader = loader
        self._repo = repo

    def list_all(self) -> list[dict]:
        """返回本地已安装场景；MVP 以 scenarios 文件为唯一列表来源。"""
        ids = self._loader.list_all()
        result: list[dict] = []
        for sid in ids:
            try:
                source = self._loader.load(sid)
                result.append({"scenario_id": sid, "title": source.title})
            except FileNotFoundError:
                logger.info("scenario file not found, skipping: %s", sid)
            except Exception:
                logger.exception("failed to load scenario %s, skipping", sid)
        return result

    def get(self, scenario_id: str) -> DecisionSource:
        """返回单个场景（含完整决策变量和 Agent 定义）。"""
        return self._loader.load(scenario_id)

    def load_source(self, scenario_id: str) -> DecisionSource:
        """同 get，语义别名——供 SimulationService 调用。"""
        return self._loader.load(scenario_id)
