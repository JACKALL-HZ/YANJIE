"""决策拆解助手测试 —— 自然语言 → 结构化变量提取。"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.breakdown_service import BreakdownService


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def service():
    return BreakdownService()


class TestBreakdownStub:
    """Stub 模式规则匹配测试。"""

    def test_extract_budget_from_chinese(self, service):
        result = service.breakdown("在杭州开奶茶店，预算20万")
        assert result.extracted_vars.get("budget") == 200000

    @pytest.mark.parametrize("query", [
        "可用预算 200,000 元 所在城市 上海 所属行业 咖啡 推演年数 2",
        "预算20 万元",
        "预算 200000 元",
    ])
    def test_extract_budget_accepts_common_amount_formats(self, service, query):
        result = service.breakdown(query, scenario_id="general_startup")
        assert result.extracted_vars.get("budget") == 200000
        assert "budget" not in result.invalid_vars

    def test_extract_city(self, service):
        result = service.breakdown("在上海开咖啡店")
        assert result.extracted_vars.get("city") == "上海"

    def test_extract_changsha_city(self, service):
        result = service.breakdown("在长沙买房，预算200万")

        assert result.scenario_id == "house_purchase"
        assert result.extracted_vars.get("city") == "长沙"

    def test_extract_industry(self, service):
        result = service.breakdown("想开一家餐饮店")
        assert "industry" in result.extracted_vars

    def test_out_of_range_span_years_is_reported_for_correction(self, service):
        result = service.breakdown("推演5年看看效果", scenario_id="milktea_startup")
        assert "span_years" not in result.extracted_vars
        assert result.invalid_vars["span_years"] == "推演年数不能高于 3"

    def test_multiple_extractions(self, service):
        result = service.breakdown("在成都开奶茶店，预算30万，推演3年")
        assert result.extracted_vars.get("budget") == 300000
        assert result.extracted_vars.get("city") == "成都"
        assert result.extracted_vars.get("span_years") == 3

    def test_missing_required_reported(self, service):
        """未识别场景时不应偷偷套用创业必填字段。"""
        result = service.breakdown("随便看看")
        assert result.scenario_id == ""
        assert result.missing_required == []
        assert "考研" in result.suggestions

    def test_scenario_id_auto_resolved(self, service):
        result = service.breakdown("开奶茶店")
        assert result.scenario_id == "milktea_startup"

    def test_food_business_is_routed_to_restaurant_startup(self, service):
        result = service.breakdown("你好我要开一家牛肉面店")

        assert result.scenario_id == "restaurant_startup"

    def test_parameter_followup_cannot_switch_an_existing_scene(self, service):
        with patch("app.services.breakdown_service.classify_scene", return_value="housing"):
            result = service.breakdown(
                "你好我要开一家牛肉面店。预算300000，在济南，推演2年",
                scenario_id="restaurant_startup",
                latest_query="预算300000，在济南，推演2年",
            )

        assert result.scenario_id == "restaurant_startup"
        assert result.extracted_vars["budget"] == 300000
        assert result.extracted_vars["city"] == "济南"
        assert result.extracted_vars["span_years"] == 2

    def test_milktea_description_does_not_fabricate_required_values(self, service):
        result = service.breakdown("我要开一家独立品牌奶茶店，叫做浩哥果味鲜")

        assert result.scenario_id == "milktea_startup"
        assert "budget" not in result.extracted_vars
        assert "city" not in result.extracted_vars
        assert "budget" in result.missing_required
        assert "city" in result.missing_required

    def test_generic_startup_requires_user_supplied_values(self, service):
        result = service.breakdown("创业")

        assert result.scenario_id == "general_startup"
        assert result.extracted_vars == {}
        assert set(result.missing_required) == {"budget", "city", "industry"}

    def test_generic_startup_extracts_user_named_industry(self, service):
        result = service.breakdown("北京，开铁锅炖", scenario_id="general_startup")

        assert result.scenario_id == "general_startup"
        assert result.extracted_vars["city"] == "北京"
        assert result.extracted_vars["industry"] == "铁锅炖"
        assert "budget" in result.missing_required

    def test_grad_exam_query_uses_grad_exam_fields(self, service):
        result = service.breakdown("目标清华大学，备考八个月")

        assert result.scenario_id == "grad_exam"
        assert result.extracted_vars["target_school"] == "清华大学"
        assert result.extracted_vars["prep_months"] == 8
        assert "city" not in result.missing_required
        assert "industry" not in result.missing_required

    def test_study_abroad_query_uses_only_study_fields(self, service):
        result = service.breakdown(
            "去美国留学，专业计算机，预算100万",
            scenario_id="study_abroad",
        )

        assert result.extracted_vars["target_country"] == "美国"
        assert result.extracted_vars["target_major"] == "计算机"
        assert result.extracted_vars["budget"] == 1000000
        assert "city" not in result.extracted_vars
        assert "industry" not in result.extracted_vars
        assert not result.missing_required

    @pytest.mark.parametrize(
        ("query", "scenario_id"),
        [
            ("申请英国计算机硕士", "study_abroad"),
            ("准备秋招找产品经理工作", "job_hunting"),
            ("我想从高级工程师晋升技术经理", "career_advance"),
            ("杭州买房，月供压力怎么算", "house_purchase"),
            ("我有十万想定投基金", "investment"),
        ],
    )
    def test_scene_specific_queries_select_the_matching_scenario(
        self, service, query, scenario_id
    ):
        assert service.breakdown(query).scenario_id == scenario_id

    def test_explicit_scenario_id_used(self, service):
        result = service.breakdown("创业", scenario_id="milktea_startup")
        assert result.scenario_id == "milktea_startup"

    def test_generic_query_is_marked_as_unresolved_scene(self, service):
        result = service.breakdown("你好")

        assert result.domain == "general"
        assert result.scenario_id == ""

    def test_explicit_stale_scenario_switches_when_query_names_new_scene(self, service):
        result = service.breakdown(
            "你好。我要考研，北京大学",
            scenario_id="milktea_startup",
            latest_query="我要考研，北京大学",
        )

        assert result.scenario_id == "grad_exam"
        assert result.extracted_vars["target_school"] == "北京大学"
        assert "budget" not in result.missing_required
        assert "city" not in result.missing_required
        assert "industry" not in result.missing_required


class TestBreakdownLLM:
    """Mock LLM 模式测试。"""

    def test_llm_response_parsed(self):
        """LLM 返回有效 JSON 应正确解析。"""
        from pathlib import Path
        from unittest.mock import patch
        import json
        from app.schemas.decision_source import DecisionSource

        source_json = json.loads(
            Path("scenarios/milktea_startup.json").read_text(encoding="utf-8")
        )
        source = DecisionSource.model_validate(source_json)

        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = '{"budget": 250000, "city": "杭州", "industry": "milk_tea"}'
        mock_llm.invoke.return_value = mock_resp

        service = BreakdownService()
        service._llm = mock_llm
        result = service.breakdown("在杭州开奶茶店预算25万")
        assert result.extracted_vars.get("budget") == 250000
        assert result.extracted_vars.get("city") == "杭州"

    def test_llm_garbage_response_fallback(self):
        """LLM 返回垃圾 JSON → 正常 fallback。"""
        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = "gibberish no json here"
        mock_llm.invoke.return_value = mock_resp

        service = BreakdownService()
        service._llm = mock_llm
        result = service.breakdown("测试查询")
        # 不应崩溃，返回空提取 + missing
        assert result.scenario_id == ""


    def test_llm_extraction_fills_high_confidence_city_when_model_omits_it(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="{}")

        service = BreakdownService()
        service._llm = mock_llm
        result = service.breakdown("在长沙买房，预算200万")

        assert result.extracted_vars["city"] == "长沙"
        assert result.extracted_vars["budget"] == 2000000

    def test_llm_schema_defaults_are_not_treated_as_user_input(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=(
            '{"budget":300000,"span_years":3,"city":"北京","industry":"铁锅炖"}'
        ))

        service = BreakdownService()
        service._llm = mock_llm
        result = service.breakdown("北京，开铁锅炖", scenario_id="general_startup")

        assert result.extracted_vars["city"] == "北京"
        assert result.extracted_vars["industry"] == "铁锅炖"
        assert "budget" not in result.extracted_vars
        assert "span_years" not in result.extracted_vars
        assert "budget" in result.missing_required

    def test_llm_out_of_range_value_is_not_returned_as_recognized_input(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content='{"city":"长沙","budget":2000000,"income":0}'
        )

        service = BreakdownService()
        service._llm = mock_llm
        result = service.breakdown("长沙买房，预算200万")

        assert result.scenario_id == "house_purchase"
        assert result.extracted_vars["city"] == "长沙"
        assert result.extracted_vars["budget"] == 2000000
        assert "income" not in result.extracted_vars
        assert "income" in result.missing_required
        assert "income" not in result.invalid_vars

    def test_llm_breakdown_prompt_is_bound_to_selected_scene(self):
        from unittest.mock import MagicMock

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content='{"target_country":"美国", "target_major":"计算机"}'
        )

        service = BreakdownService()
        service._llm = mock_llm
        service.breakdown(
            "去美国留学，专业计算机",
            scenario_id="study_abroad",
        )

        system_prompt = mock_llm.invoke.call_args.args[0][0].content
        assert "留学决策推演" in system_prompt
        assert "目标专业" in system_prompt
        assert "奶茶" not in system_prompt


class TestBreakdownAPI:
    """API 端点测试。"""

    def test_endpoint_returns_structured(self, client):
        resp = client.post("/api/assistant/breakdown", json={
            "query": "在杭州开奶茶店预算20万",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "scenario_id" in data
        assert "extracted_vars" in data
        assert "missing_required" in data
        assert "suggestions" in data

    def test_endpoint_with_scenario_id(self, client):
        resp = client.post("/api/assistant/breakdown", json={
            "query": "在杭州开奶茶店",
            "scenario_id": "milktea_startup",
        })
        assert resp.status_code == 200
        assert resp.json()["scenario_id"] == "milktea_startup"

    def test_endpoint_switches_stale_scene_from_latest_query(self, client):
        resp = client.post("/api/assistant/breakdown", json={
            "query": "你好。我要考研，北京大学",
            "scenario_id": "milktea_startup",
            "latest_query": "我要考研，北京大学",
        })

        assert resp.status_code == 200
        assert resp.json()["scenario_id"] == "grad_exam"
