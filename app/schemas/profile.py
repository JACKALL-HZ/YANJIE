"""用户画像请求/响应 schema —— 六维度字段校验。

字段与 `app.db.models.UserProfile` 一一对应；派生指标由 ProfileService 计算。
"""

from pydantic import BaseModel, ConfigDict, Field

# ── 枚举取值（前后端共用口径，宽松校验：非法值不报错但摘要会降级为原文）──
EDUCATION_CHOICES = ("high_school", "college", "bachelor", "master", "phd", "other")
MARITAL_CHOICES = ("single", "married", "divorced", "widowed")
INCOME_STABILITY_CHOICES = ("stable", "fluctuating", "unstable")
RISK_APPETITE_CHOICES = ("conservative", "balanced", "aggressive")
DECISION_STYLE_CHOICES = ("analytical", "intuitive", "decisive", "consensus")
AVAILABLE_TIME_CHOICES = ("fulltime", "parttime", "spare", "weekend")


class ProfileCreateRequest(BaseModel):
    """创建画像 —— 归属恒为当前登录用户，无需任何字段。

    宽松忽略额外字段：老客户端仍会传 user_id，服务端一律以登录态为准。
    """

    model_config = ConfigDict(extra="ignore")


class ProfileUpdateRequest(BaseModel):
    """更新画像 —— 全字段可选，仅提交的字段会被写入。"""

    model_config = ConfigDict(extra="forbid")

    # ── 1. 基本信息 ──
    age: int | None = Field(None, ge=0, le=150, description="年龄")
    gender: str | None = Field(None, max_length=32, description="性别")
    city: str | None = Field(None, max_length=128, description="所在城市")
    education: str | None = Field(None, max_length=64, description="学历")
    marital_status: str | None = Field(None, max_length=32, description="婚姻状况")
    dependents: int | None = Field(None, ge=0, le=20, description="需抚养人数")
    family_burden: bool | None = Field(None, description="是否有家庭负担")

    # ── 2. 职业与能力 ──
    occupation: str | None = Field(None, max_length=128, description="当前职业")
    industry: str | None = Field(None, max_length=128, description="所在行业")
    years_experience: int | None = Field(None, ge=0, le=80, description="工作年限")
    skills: list[str] | None = Field(None, max_length=50, description="技能标签")
    certificates: list[str] | None = Field(
        None, max_length=30, description="资质/证书"
    )
    career_history: str | None = Field(None, max_length=5000, description="职业经历")
    strengths: str | None = Field(None, max_length=2000, description="个人优势")
    weaknesses: str | None = Field(None, max_length=2000, description="已知短板")

    # ── 3. 财务状况 ──
    assets: int | None = Field(None, ge=0, description="可支配资产（元）")
    monthly_income: int | None = Field(None, ge=0, description="月收入（元）")
    monthly_expense: int | None = Field(None, ge=0, description="月支出（元）")
    liabilities: int | None = Field(None, ge=0, description="负债总额（元）")
    income_stability: str | None = Field(
        None, max_length=32, description="收入稳定性"
    )
    insurance: list[str] | None = Field(
        None, max_length=20, description="已有保险覆盖"
    )

    # ── 4. 风险与决策 ──
    risk_appetite: str | None = Field(None, max_length=32, description="风险偏好")
    loss_tolerance: int | None = Field(
        None, ge=0, le=100, description="可承受最大亏损占资产比例（%）"
    )
    decision_style: str | None = Field(None, max_length=32, description="决策风格")
    past_failures: str | None = Field(
        None, max_length=3000, description="过往失败经历"
    )

    # ── 5. 时间与资源 ──
    available_time: str | None = Field(None, max_length=32, description="可投入时间")
    weekly_hours: int | None = Field(
        None, ge=0, le=168, description="每周可投入小时数"
    )
    support_network: str | None = Field(
        None, max_length=2000, description="可动用的人脉与资源"
    )

    # ── 6. 目标与约束 ──
    goals: list[str] | None = Field(None, max_length=20, description="核心目标")
    constraints: str | None = Field(
        None, max_length=2000, description="硬性约束（不可妥协项）"
    )
    time_horizon: int | None = Field(
        None, ge=1, le=50, description="时间视野（年）"
    )
    motivation: str | None = Field(
        None, max_length=2000, description="决策动机"
    )
