from app.agents.base import StubAgent


class MarketAgent(StubAgent):
    def __init__(self):
        super().__init__("market", "市场智能体")
