"""数据访问仓库层（DAO）。

提供与 SQLAlchemy Session 绑定的仓库类，隔离 engine 与 ORM 细节。
所有方法均不管理事务——事务边界由调用方（engine/api）控制。
"""

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import (
    AgentMemory,
    KbChunk,
    Scenario,
    SimulationEvent,
    SimulationMessage,
    SimulationSession,
    User,
    UserProfile,
)


# ── SimulationRepo ──────────────────────────────────────────


class SimulationRepo:
    """模拟会话 CRUD。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        session_id: str,
        scenario_id: str,
        decision_vars: dict[str, Any],
        world_state: dict[str, Any],
        user_id: str | None = None,
        owner_key: str | None = None,
        profile_id: str | None = None,
        phase: str = "simulating",
        user_profile: dict[str, Any] | None = None,
    ) -> str:
        """创建新会话行，返回 session_id。

        `user_profile` 是推演启动瞬间的画像快照——冻结存储，
        用户日后修改画像不会篡改历史推演的解释依据。
        """
        row = SimulationSession(
            id=session_id,
            scenario_id=scenario_id,
            user_id=user_id,
            owner_key=owner_key,
            profile_id=profile_id,
            user_profile=user_profile,
            phase=phase,
            current_year=0,
            decision_vars=decision_vars,
            world_state=world_state,
            timeline=[],
        )
        self.db.add(row)
        self.db.flush()
        return row.id

    # update() 允许的字段白名单
    _UPDATE_ALLOWED = frozenset({
        "current_year", "phase", "result", "score", "score_detail",
        "risks", "action_plan", "world_state", "timeline", "agent_states",
        "diary_tags", "diary_notes", "diary_archived",
        "actual_result", "actual_metrics", "calibration_score",
        "interventions", "decision_vars",
        "decision_history",
    })

    def update(self, session_id: str, **kwargs: Any) -> None:
        """增量更新会话字段（仅允许白名单内的字段）。"""
        row = self.db.query(SimulationSession).filter(
            SimulationSession.id == session_id
        ).one_or_none()
        if row is None:
            return
        for key, value in kwargs.items():
            if key not in self._UPDATE_ALLOWED:
                continue
            if hasattr(row, key):
                setattr(row, key, value)
        self.db.flush()

    def get(self, session_id: str) -> SimulationSession | None:
        return self.db.query(SimulationSession).filter(
            SimulationSession.id == session_id
        ).one_or_none()

    def list_by_scenario(self, scenario_id: str) -> list[SimulationSession]:
        return (
            self.db.query(SimulationSession)
            .filter(SimulationSession.scenario_id == scenario_id)
            .order_by(SimulationSession.created_at.desc())
            .all()
        )

    def list_all(self) -> list[SimulationSession]:
        return (
            self.db.query(SimulationSession)
            .order_by(SimulationSession.created_at.desc())
            .all()
        )

    def list_by_user(self, user_id: str) -> list[SimulationSession]:
        """返回指定用户的会话列表（按创建时间倒序）。"""
        return (
            self.db.query(SimulationSession)
            .filter(SimulationSession.user_id == user_id)
            .order_by(SimulationSession.created_at.desc())
            .all()
        )

    def list_by_owner_key(self, owner_key: str) -> list[SimulationSession]:
        return (
            self.db.query(SimulationSession)
            .filter(SimulationSession.owner_key == owner_key)
            .order_by(SimulationSession.created_at.desc())
            .all()
        )

    def append_decision(self, session_id: str, record: dict[str, Any]) -> None:
        row = self.get(session_id)
        if row is None:
            return
        history = list(row.decision_history or [])
        history.append(record)
        row.decision_history = history
        self.db.flush()

    def select_decision_branch(self, session_id: str, branch_id: str) -> None:
        row = self.get(session_id)
        if row is None:
            return
        history = [dict(record) for record in (row.decision_history or [])]
        for index in range(len(history) - 1, -1, -1):
            if history[index].get("selected_branch") is None:
                history[index] = {**history[index], "selected_branch": branch_id}
                break
        row.decision_history = history
        self.db.flush()


class MessageRepo:
    """推演会话消息持久化。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _stored_role(role: str, agent_id: str | None = None) -> str:
        """兼容现有表结构，在 role 中保留可选 Agent 标识。"""
        if agent_id and role == "agent":
            return f"agent:{agent_id}"
        return role

    @staticmethod
    def decode_role(stored_role: str) -> tuple[str, str | None]:
        """把历史 role 解码为接口使用的 role 与 agent_id。"""
        if stored_role.startswith("agent:"):
            return "agent", stored_role.removeprefix("agent:") or None
        if stored_role in {"market", "environment", "personal", "risk", "guide"}:
            return "agent", stored_role
        return stored_role, None

    def save(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        agent_id: str | None = None,
        year: int | None = None,
    ) -> SimulationMessage:
        latest_sequence = (
            self.db.query(func.max(SimulationMessage.sequence))
            .filter(SimulationMessage.session_id == session_id)
            .scalar()
        )
        row = SimulationMessage(
            session_id=session_id,
            sequence=(latest_sequence or 0) + 1,
            year=year,
            role=self._stored_role(role, agent_id),
            content=content,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def save_batch(
        self,
        session_id: str,
        messages: list[dict[str, Any]],
    ) -> None:
        for message in messages:
            content = str(message.get("content", "")).strip()
            role = str(message.get("role", "")).strip()
            if not content or role not in {"user", "agent", "system"}:
                continue
            self.save(
                session_id,
                role,
                content,
                agent_id=message.get("agent_id"),
                year=message.get("year"),
            )

    def list_by_session(self, session_id: str) -> list[SimulationMessage]:
        return (
            self.db.query(SimulationMessage)
            .filter(SimulationMessage.session_id == session_id)
            .order_by(
                SimulationMessage.sequence.asc().nullslast(),
                SimulationMessage.created_at.asc(),
                SimulationMessage.id.asc(),
            )
            .all()
        )


# ── EventRepo ────────────────────────────────────────────────


class EventRepo:
    """模拟事件写入。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def save(
        self,
        session_id: str,
        year: int,
        agent: str,
        action: str,
        state_diff: dict[str, Any],
        payload: dict[str, Any],
    ) -> SimulationEvent:
        row = SimulationEvent(
            session_id=session_id,
            year=year,
            agent=agent,
            action=action,
            state_diff=state_diff,
            payload=payload,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def save_batch(self, records: list[dict[str, Any]]) -> None:
        """批量写入事件（同一 session 同年多 Agent 动作）。"""
        for rec in records:
            self.save(**rec)

    def get_by_session(self, session_id: str) -> list[SimulationEvent]:
        return (
            self.db.query(SimulationEvent)
            .filter(SimulationEvent.session_id == session_id)
            .order_by(SimulationEvent.created_at.asc())
            .all()
        )


# ── ScenarioRepo ─────────────────────────────────────────────


class ScenarioRepo:
    """场景元数据 CRUD。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert(
        self,
        scenario_id: str,
        title: str,
        decision_source: dict[str, Any],
    ) -> Scenario:
        row = (
            self.db.query(Scenario)
            .filter(Scenario.scenario_id == scenario_id)
            .one_or_none()
        )
        if row is None:
            row = Scenario(
                scenario_id=scenario_id,
                title=title,
                decision_source=decision_source,
            )
            self.db.add(row)
        else:
            row.title = title
            row.decision_source = decision_source
        self.db.flush()
        return row

    def get(self, scenario_id: str) -> Scenario | None:
        return (
            self.db.query(Scenario)
            .filter(Scenario.scenario_id == scenario_id)
            .one_or_none()
        )

    def list_all(self) -> list[Scenario]:
        return (
            self.db.query(Scenario)
            .order_by(Scenario.created_at.desc())
            .all()
        )


# ── AgentMemoryRepo ──────────────────────────────────────────


class AgentMemoryRepo:
    """Agent 长期记忆存储。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def save(
        self,
        user_id: str,
        agent_id: str,
        domain: str,
        key: str,
        value: Any,
    ) -> AgentMemory:
        row = self.db.query(AgentMemory).filter(
            AgentMemory.user_id == user_id,
            AgentMemory.agent_id == agent_id,
            AgentMemory.domain == domain,
            AgentMemory.key == key,
        ).one_or_none()

        if row is None:
            row = AgentMemory(
                user_id=user_id,
                agent_id=agent_id,
                domain=domain,
                key=key,
                value=value,
            )
            self.db.add(row)
        else:
            row.value = value
        self.db.flush()
        return row

    def get(
        self,
        user_id: str,
        agent_id: str,
        domain: str,
        key: str,
    ) -> AgentMemory | None:
        return self.db.query(AgentMemory).filter(
            AgentMemory.user_id == user_id,
            AgentMemory.agent_id == agent_id,
            AgentMemory.domain == domain,
            AgentMemory.key == key,
        ).one_or_none()

    def delete_by_domain(
        self,
        user_id: str,
        agent_id: str,
        domain: str,
    ) -> int:
        """删除指定 domain 下所有记忆，返回删除行数。"""
        count = (
            self.db.query(AgentMemory)
            .filter(
                AgentMemory.user_id == user_id,
                AgentMemory.agent_id == agent_id,
                AgentMemory.domain == domain,
            )
            .delete()
        )
        self.db.flush()
        return count


# ── KbChunkRepo ────────────────────────────────────────────


class KbChunkRepo:
    """知识库分块 SQL 存储（与 Chroma 同步写入）。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def save_batch(self, records: list[dict[str, Any]]) -> None:
        """幂等批量写入（同 id 覆盖）。"""
        for rec in records:
            row = self.db.query(KbChunk).filter(
                KbChunk.id == rec["chunk_id"]
            ).one_or_none()
            if row is not None:
                row.content = rec["content"]
                row.industry = rec.get("industry")
                row.city = rec.get("city")
                row.type = rec["chunk_type"]
                row.tags = {"source": rec.get("source", "")}
            else:
                row = KbChunk(
                    id=rec["chunk_id"],
                    content=rec["content"],
                    industry=rec.get("industry"),
                    city=rec.get("city"),
                    type=rec["chunk_type"],
                    tags={"source": rec.get("source", "")},
                )
                self.db.add(row)
        self.db.flush()

    def query(
        self,
        industry: str | None = None,
        city: str | None = None,
        chunk_type: str | None = None,
    ) -> list[KbChunk]:
        """按行业/城市/类型筛选。"""
        q = self.db.query(KbChunk)
        if industry:
            q = q.filter(KbChunk.industry == industry)
        if city:
            q = q.filter(KbChunk.city == city)
        if chunk_type:
            q = q.filter(KbChunk.type == chunk_type)
        return q.order_by(KbChunk.created_at.desc()).all()


# ── ProfileRepo ────────────────────────────────────────────────


class ProfileRepo:
    """用户画像 CRUD。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: str) -> UserProfile | None:
        return self.db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).one_or_none()

    def create(self, user_id: str) -> UserProfile:
        """创建新的用户画像（默认值）。"""
        row = UserProfile(user_id=user_id)
        self.db.add(row)
        self.db.flush()
        return row

    def update(self, user_id: str, **kwargs: Any) -> UserProfile | None:
        """增量更新画像字段。"""
        row = self.db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).one_or_none()
        if row is None:
            return None
        for key, value in kwargs.items():
            if hasattr(row, key):
                setattr(row, key, value)
        self.db.flush()
        return row

    def list_all(self) -> list[UserProfile]:
        return (
            self.db.query(UserProfile)
            .order_by(UserProfile.created_at.desc())
            .all()
        )

    def list_by_user(self, user_id: str) -> list[UserProfile]:
        """返回指定用户的画像列表（正常每用户至多一条）。"""
        return (
            self.db.query(UserProfile)
            .filter(UserProfile.user_id == user_id)
            .order_by(UserProfile.created_at.desc())
            .all()
        )


# ── DiaryRepo ─────────────────────────────────────────────────


class DiaryRepo:
    """决策日记仓库 —— 标签/笔记/归档/校准。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def update_diary(
        self,
        session_id: str,
        tags: list[str] | None = None,
        notes: str | None = None,
        archived: bool | None = None,
    ) -> SimulationSession | None:
        row = self.db.query(SimulationSession).filter(
            SimulationSession.id == session_id
        ).one_or_none()
        if row is None:
            return None
        if tags is not None:
            row.diary_tags = tags
        if notes is not None:
            row.diary_notes = notes
        if archived is not None:
            row.diary_archived = archived
        self.db.flush()
        return row

    def list_diary(
        self,
        tag: str | None = None,
        archived: bool | None = None,
        user_id: str | None = None,
        owner_key: str | None = None,
    ) -> list[SimulationSession]:
        q = self.db.query(SimulationSession)
        if archived is not None:
            q = q.filter(SimulationSession.diary_archived == archived)
        if user_id is not None:
            q = q.filter(SimulationSession.user_id == user_id)
        elif owner_key is not None:
            q = q.filter(SimulationSession.owner_key == owner_key)
        q = q.order_by(SimulationSession.created_at.desc())
        results = q.all()
        if tag:
            results = [r for r in results if tag in (r.diary_tags or [])]
        return results

    def save_calibration(
        self,
        session_id: str,
        actual_result: str,
        actual_metrics: dict[str, Any] | None = None,
    ) -> SimulationSession | None:
        row = self.db.query(SimulationSession).filter(
            SimulationSession.id == session_id
        ).one_or_none()
        if row is None:
            return None
        row.actual_result = actual_result
        row.actual_metrics = actual_metrics or {}
        # 计算校准分数：simulated vs actual
        sim_result = row.result
        if sim_result == actual_result:
            row.calibration_score = 1.0
        elif sim_result and actual_result:
            row.calibration_score = 0.5  # 不同类型但有结果
        else:
            row.calibration_score = 0.0
        self.db.flush()
        return row

    def get_calibration(self, session_id: str) -> dict | None:
        row = self.db.query(SimulationSession).filter(
            SimulationSession.id == session_id
        ).one_or_none()
        if row is None:
            return None
        return {
            "session_id": row.id,
            "simulated_result": row.result,
            "actual_result": row.actual_result,
            "actual_metrics": row.actual_metrics,
            "calibration_score": row.calibration_score,
        }
