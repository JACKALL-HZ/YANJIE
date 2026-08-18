"""SQLAlchemy 2.0 declarative models.

字段严格对齐 PRD 7.3.1 DDL（PostgreSQL 生产目标）；开发期用 SQLite 自动建表。
- 主键用 String(36) + uuid4() 字符串（避免 SQLite 下 Uuid(CHAR(32)) 截断 36 位 uuid 的问题）
- JSON 列用 sqlalchemy.JSON（SQLite 下存 TEXT，完全可用）；kb_chunks.embedding 以 JSON 占位（开发期 Chroma 等价，不引 pgvector）
- 时间戳 DateTime(timezone=True) + Python default（SQLite 下比 server_default 更稳）
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    password_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scenario_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    cover_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(64), nullable=True)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    intro: Mapped[str | None] = mapped_column(Text, nullable=True)
    background: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_source: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("scenario_id", "kind", "ref_id", name="uq_asset_triple"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scenario_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    ref_id: Mapped[str] = mapped_column(String(255), nullable=False)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class KbChunk(Base):
    __tablename__ = "kb_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scenario_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("scenarios.id", ondelete="SET NULL"),
        nullable=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 开发期 Chroma 等价：embedding 以 JSON 占位（维度信息存 list），不引 pgvector
    embedding: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    tags: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class SimulationSession(Base):
    __tablename__ = "simulation_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # MVP-0 简化：直接存 scenario_id 字符串（FK 到 scenarios.scenario_id 唯一列），允许为空
    scenario_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("scenarios.scenario_id"),
        nullable=True,
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    owner_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    profile_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user_profiles.id"), nullable=True
    )
    # 推演开始时冻结的画像快照：用户后续改画像不影响历史推演的可复盘性
    user_profile: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    phase: Mapped[str] = mapped_column(String(32), default="input", nullable=False)
    current_year: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    decision_vars: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    world_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    agent_states: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    decision_history: Mapped[list[Any]] = mapped_column(JSON, default=list)
    timeline: Mapped[list[Any]] = mapped_column(JSON, default=list)
    interventions: Mapped[list[Any]] = mapped_column(JSON, default=list)
    result: Mapped[str | None] = mapped_column(String(64), nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_detail: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    risks: Mapped[list[Any]] = mapped_column(JSON, default=list)
    advice: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_plan: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    compare_pair_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # ── 决策日记（v1.2 新增）──
    diary_tags: Mapped[list[Any]] = mapped_column(JSON, default=list)
    diary_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    diary_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    # ── 现实校准（v1.2 新增）──
    actual_result: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actual_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    calibration_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class SimulationMessage(Base):
    __tablename__ = "simulation_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("simulation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 会话内的稳定写入顺序；旧数据允许为空并回退到时间排序。
    sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class SimulationEvent(Base):
    __tablename__ = "simulation_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("simulation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    agent: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    state_diff: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class UserProfile(Base):
    """用户决策画像 —— 六维度输入，直接决定 Agent 推演时对"你是谁"的感知。

    维度：基本信息 / 职业能力 / 财务状况 / 风险与决策 / 时间与资源 / 目标与约束。
    派生指标（净资产、现金跑道、月度盈余、投入占比）在 service 层计算，不落库。
    """

    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, unique=True, index=True
    )

    # ── 1. 基本信息 ──
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(32), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    education: Mapped[str | None] = mapped_column(String(64), nullable=True)
    marital_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dependents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    family_burden: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── 2. 职业与能力 ──
    occupation: Mapped[str | None] = mapped_column(String(128), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    skills: Mapped[list[Any]] = mapped_column(JSON, default=list)
    certificates: Mapped[list[Any]] = mapped_column(JSON, default=list)
    career_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    strengths: Mapped[str | None] = mapped_column(Text, nullable=True)
    weaknesses: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── 3. 财务状况 ──
    assets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_income: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_expense: Mapped[int | None] = mapped_column(Integer, nullable=True)
    liabilities: Mapped[int | None] = mapped_column(Integer, nullable=True)
    income_stability: Mapped[str | None] = mapped_column(String(32), nullable=True)
    insurance: Mapped[list[Any]] = mapped_column(JSON, default=list)

    # ── 4. 风险与决策 ──
    risk_appetite: Mapped[str] = mapped_column(String(32), default="balanced")
    loss_tolerance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decision_style: Mapped[str | None] = mapped_column(String(32), nullable=True)
    past_failures: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── 5. 时间与资源 ──
    available_time: Mapped[str] = mapped_column(String(32), default="fulltime")
    weekly_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    support_network: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── 6. 目标与约束 ──
    goals: Mapped[list[Any]] = mapped_column(JSON, default=list)
    constraints: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_horizon: Mapped[int | None] = mapped_column(Integer, nullable=True)
    motivation: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class AgentMemory(Base):
    __tablename__ = "agent_memories"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "agent_id", "domain", "key", name="uq_agent_memory"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


# 9 张表名（供测试断言）
TABLE_NAMES: list[str] = [
    "users",
    "scenarios",
    "assets",
    "kb_chunks",
    "simulation_sessions",
    "simulation_messages",
    "simulation_events",
    "user_profiles",
    "agent_memories",
]
