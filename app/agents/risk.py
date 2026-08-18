from app.agents.base import StubAgent


class RiskAgent(StubAgent):
    def __init__(self):
        super().__init__("risk", "风险智能体")
