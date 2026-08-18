"""业务编排层 —— 连接 API 与 Engine/Agents/DB，不调 LLM，不做判定。

每个 Service 是一组无状态函数 + 依赖注入组合。
"""
