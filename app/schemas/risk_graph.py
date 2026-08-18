"""风险传导图谱模型 —— RiskNode / RiskEdge / RiskChain / RiskDag。"""

from pydantic import BaseModel, Field


class RiskNode(BaseModel):
    metric: str = Field(description="指标名称")
    current_value: float = Field(description="当前值")
    severity: float = Field(ge=0, le=1, description="严重程度 0-1")
    message: str = Field(description="风险描述")


class RiskEdge(BaseModel):
    source: str = Field(description="源指标名称")
    target: str = Field(description="目标指标名称")
    cause: str = Field(description="传导原因描述")
    weight: float = Field(default=1.0, ge=0, le=1, description="传导强度 0-1")


class RiskChain(BaseModel):
    pathway: list[str] = Field(description="有序的指标传导路径")
    total_severity: float = Field(ge=0, le=1, description="综合严重程度")
    response_actions: list[str] = Field(description="应对措施列表")


class RiskDag(BaseModel):
    nodes: list[RiskNode] = Field(default_factory=list)
    edges: list[RiskEdge] = Field(default_factory=list)
    chains: list[RiskChain] = Field(default_factory=list)
