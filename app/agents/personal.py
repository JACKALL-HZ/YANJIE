from app.agents.base import StubAgent


class PersonalAgent(StubAgent):
    def __init__(self):
        super().__init__("personal", "个人智能体")
