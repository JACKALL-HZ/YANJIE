class ScenarioError(Exception):
    """Base class for scenario loading failures."""


class InvalidScenarioIdError(ScenarioError):
    def __init__(self, scenario_id: object):
        self.scenario_id = scenario_id
        super().__init__(f"invalid scenario id: {scenario_id!r}")


class ScenarioNotFoundError(ScenarioError):
    def __init__(self, scenario_id: str):
        self.scenario_id = scenario_id
        super().__init__(f"scenario not found: {scenario_id}")


class ScenarioIdMismatchError(ScenarioError):
    def __init__(self, expected: str, actual: str):
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"scenario id mismatch: expected {expected!r}, got {actual!r}"
        )
