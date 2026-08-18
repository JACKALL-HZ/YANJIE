"""用户画像业务逻辑 —— 六维度画像 CRUD + 派生指标计算。

派生指标（净资产 / 现金跑道 / 月度盈余 / 可承受亏损）不落库，
每次读取时按当前字段实时算，供前端展示与 Agent 感知共用。
计算逻辑复用引擎层纯函数 `app.engine.profile_summary.compute_derived`，
保证「前端看到的指标」与「Agent 感知的指标」永远同源。
"""

from typing import Any

from sqlalchemy.orm import Session

from app.db.repository import ProfileRepo
from app.engine.profile_summary import compute_derived


class ProfileService:
    """用户画像管理服务。"""

    def __init__(self, db: Session) -> None:
        self.repo = ProfileRepo(db)
        self.db = db

    def get(self, user_id: str) -> dict[str, Any] | None:
        """获取画像，不存在返回 None。"""
        profile = self.repo.get(user_id)
        if profile is None:
            return None
        return _serialize(profile)

    def create(self, user_id: str) -> dict[str, Any]:
        """创建新画像（默认值）。"""
        profile = self.repo.create(user_id)
        self.db.commit()
        return _serialize(profile)

    def update(self, user_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        """更新画像字段。返回 None 表示画像不存在。"""
        profile = self.repo.update(user_id, **fields)
        if profile is None:
            return None
        self.db.commit()
        return _serialize(profile)

    def list_all(self) -> list[dict[str, Any]]:
        return [_serialize(p) for p in self.repo.list_all()]

    def list_by_user(self, user_id: str) -> list[dict[str, Any]]:
        return [_serialize(p) for p in self.repo.list_by_user(user_id)]

    def get_for_simulation(self, user_id: str) -> dict[str, Any]:
        """取画像供推演注入；无画像时返回空 dict（推演不阻断）。"""
        return self.get(user_id) or {}


def _serialize(profile) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": profile.id,
        "user_id": profile.user_id,
        # 1. 基本信息
        "age": profile.age,
        "gender": profile.gender,
        "city": profile.city,
        "education": profile.education,
        "marital_status": profile.marital_status,
        "dependents": profile.dependents,
        "family_burden": profile.family_burden,
        # 2. 职业与能力
        "occupation": profile.occupation,
        "industry": profile.industry,
        "years_experience": profile.years_experience,
        "skills": profile.skills or [],
        "certificates": profile.certificates or [],
        "career_history": profile.career_history,
        "strengths": profile.strengths,
        "weaknesses": profile.weaknesses,
        # 3. 财务状况
        "assets": profile.assets,
        "monthly_income": profile.monthly_income,
        "monthly_expense": profile.monthly_expense,
        "liabilities": profile.liabilities,
        "income_stability": profile.income_stability,
        "insurance": profile.insurance or [],
        # 4. 风险与决策
        "risk_appetite": profile.risk_appetite,
        "loss_tolerance": profile.loss_tolerance,
        "decision_style": profile.decision_style,
        "past_failures": profile.past_failures,
        # 5. 时间与资源
        "available_time": profile.available_time,
        "weekly_hours": profile.weekly_hours,
        "support_network": profile.support_network,
        # 6. 目标与约束
        "goals": profile.goals or [],
        "constraints": profile.constraints,
        "time_horizon": profile.time_horizon,
        "motivation": profile.motivation,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }
    data["derived"] = compute_derived(data)
    return data
