from app.kb.classify_scene import select_scenario
from app.scenarios.loader import ScenarioLoader


def test_general_entrepreneurship_routes_to_general_startup():
    assert select_scenario("我想创业做一个项目", "entrepreneurship") == "general_startup"


def test_specialized_entrepreneurship_keeps_specific_template():
    assert select_scenario("我准备开一家奶茶店", "entrepreneurship") == "milktea_startup"
    assert select_scenario("我想做 SaaS 软件创业", "entrepreneurship") == "saas_startup"


def test_general_startup_source_is_valid():
    source = ScenarioLoader("scenarios").load("general_startup")

    assert source.title == "通用创业"
    assert {item.name for item in source.decision_vars} >= {"budget", "city", "industry"}
