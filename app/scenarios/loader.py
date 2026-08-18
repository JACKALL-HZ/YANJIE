import json
import os
import time
from pathlib import Path
import re

from app.core.errors import (
    InvalidScenarioIdError,
    ScenarioIdMismatchError,
    ScenarioNotFoundError,
)
from app.schemas.decision_source import DecisionSource


_SCENARIO_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")

# 缓存 TTL（秒），可通过 SCENARIO_CACHE_TTL 环境变量覆盖，默认 300s
_SCENARIO_CACHE_TTL = int(os.getenv("SCENARIO_CACHE_TTL", "300"))


class ScenarioLoader:
    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()
        self._cache: dict[str, tuple[DecisionSource, float]] = {}

    def load(self, scenario_id: str) -> DecisionSource:
        if not isinstance(scenario_id, str) or not _SCENARIO_ID_PATTERN.fullmatch(
            scenario_id
        ):
            raise InvalidScenarioIdError(scenario_id)

        now = time.time()
        cached = self._cache.get(scenario_id)
        if cached is not None:
            source, ts = cached
            if _SCENARIO_CACHE_TTL <= 0 or (now - ts) < _SCENARIO_CACHE_TTL:
                return source
            # TTL 过期，重新加载
            del self._cache[scenario_id]

        path = (self.root / f"{scenario_id}.json").resolve()
        if path.parent != self.root or not path.is_file():
            raise ScenarioNotFoundError(scenario_id)

        payload = json.loads(path.read_text(encoding="utf-8"))
        payload_scenario_id = payload.get("scenario_id")
        if payload_scenario_id != scenario_id:
            raise ScenarioIdMismatchError(scenario_id, payload_scenario_id)
        source = DecisionSource.model_validate(payload)
        self._cache[scenario_id] = (source, now)
        return source

    def list_all(self) -> list[str]:
        """返回所有已安装的场景 ID 列表。"""
        ids: list[str] = []
        for f in self.root.glob("*.json"):
            sid = f.stem
            if _SCENARIO_ID_PATTERN.fullmatch(sid):
                ids.append(sid)
        return sorted(ids)
