from app.agents.base import StubAgent


class EnvironmentAgent(StubAgent):
    def __init__(self):
        super().__init__("environment", "环境智能体")
