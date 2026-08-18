"""Tavily Search 工具测试"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from app.tools.tavily_search import TavilySearchTool


class TestTavilySearchTool:
    def test_init_stores_api_key(self):
        tool = TavilySearchTool(api_key="tvly-test-key")
        assert tool._api_key == "tvly-test-key"

    def test_search_returns_formatted_results(self):
        """模拟 Tavily API 响应 → 格式化输出"""
        mock_response = {
            "results": [
                {
                    "title": "2025 Milk Tea Market Report",
                    "url": "https://example.com/report",
                    "content": "The milk tea market grew 15% in 2025 with Hangzhou leading.",
                },
                {
                    "title": "Tea Shop Regulations",
                    "url": "https://example.com/policy",
                    "content": "New food safety rules for tea shops in 2026.",
                },
            ],
            "answer": "The milk tea market is growing rapidly.",
        }

        with patch("httpx.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_response

            tool = TavilySearchTool(api_key="tvly-test-key")
            result = tool.search("奶茶市场 2025 趋势")

        assert "2025 Milk Tea Market Report" in result
        assert "Hangzhou" in result
        assert "15%" in result

    def test_search_empty_results(self):
        """空结果 → 返回提示"""
        mock_response = {"results": [], "answer": None}

        with patch("httpx.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_response

            tool = TavilySearchTool(api_key="tvly-test-key")
            result = tool.search("nonexistent query")

        assert "暂无" in result or "no result" in result.lower()

    def test_search_api_error_graceful(self):
        """API 错误 → 不抛异常，返回兜底"""
        with patch("httpx.post") as mock_post:
            mock_post.return_value.status_code = 500
            mock_post.return_value.text = "Internal Server Error"
            mock_post.return_value.raise_for_status.side_effect = Exception("500")

            tool = TavilySearchTool(api_key="tvly-test-key")
            result = tool.search("any query")

        assert "搜索暂时不可用" in result or "unavailable" in result.lower()

    def test_build_query_from_state(self):
        """从世界状态构建搜索查询"""
        tool = TavilySearchTool(api_key="tvly-test-key")
        query = tool.build_query(
            industry="milk_tea",
            city="hangzhou",
            year=2,
            world_state={"cash_flow": 150000, "competition_count": 50},
        )
        assert "milk" in query and "tea" in query  # replace("_", " ") splits
        assert "hangzhou" in query

    def test_format_results_max_limit(self):
        """超过 max_results 时截断（3 结果 × 3 行 = 最多 9 行）"""
        mock_response = {
            "results": [
                {"title": f"Result {i}", "url": f"https://example.com/{i}", "content": f"Content {i}"}
                for i in range(20)
            ],
            "answer": None,
        }

        with patch("httpx.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_response

            tool = TavilySearchTool(api_key="tvly-test-key", max_results=3)
            result = tool.search("test")

        # 每个结果 3 行（标题、内容、URL）
        lines = result.split("\n")
        result_lines = [l for l in lines if l.strip().startswith(("1.", "2.", "3.", "4."))]
        assert len(result_lines) <= 3  # 最多 3 个编号结果

    def test_result_truncation(self):
        """单条结果过长时截断 content"""
        long_content = "x" * 500
        mock_response = {
            "results": [
                {"title": "Long Result", "url": "https://example.com", "content": long_content},
            ],
            "answer": None,
        }

        with patch("httpx.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_response

            tool = TavilySearchTool(api_key="tvly-test-key", max_results=1)
            result = tool.search("test")

        assert len(result) < 500  # 截断后不应太长
