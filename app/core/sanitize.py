"""输入清洗 —— 防 LLM Prompt 注入。

根据 CLAUDE.md §5 安全红线：
- 用户输入回填前做清洗与脱敏
- RAG 检索结果回填前做清洗，屏蔽原生报错堆栈
- 所有外部内容在传入 LLM 前经过本模块处理

提供:
    sanitize_user_input(text)  — 清洗用户输入
    sanitize_rag_content(text) — 清洗 RAG/工具返回值
"""

import re

# 常见的 LLM prompt 注入/越狱模式（黑名单）
_INJECTION_PATTERNS: list[re.Pattern] = [
    # "ignore previous instructions" 及其变体
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above|your)\s+(instructions?|prompts?|rules?)", re.IGNORECASE),
    # "you are now DAN" / jailbreak role-switching
    re.compile(r"\byou\s+are\s+now\s+(\w+\s+)?(DAN|developer\s*mode|jailbreak)\b", re.IGNORECASE),
    # "system:" / "system message:" 伪装
    re.compile(r"<(system|instruction|prompt)\s*>", re.IGNORECASE),
    # "forget everything" / "disregard"
    re.compile(r"\b(forget|disregard|ignore)\s+(everything|all)\b", re.IGNORECASE),
    # 中文注入变体
    re.compile(r"(忽略|忘记|无视)(所有|之前|上面)(的)?(指令|提示|规则|要求)"),
    re.compile(r"你现在是\s*(DAN|开发者模式|越狱)"),
    # 强调标记覆盖（试图用 ~~~~ 或 ==== 创建"新 section"）
    re.compile(r"^[=~*#-]{10,}\s*(system|指令|规则|新规则)", re.IGNORECASE | re.MULTILINE),
]

# 控制字符（除换行和制表符外）
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

# Python traceback 模式（屏蔽原生报错堆栈）
_TRACEBACK_PATTERN = re.compile(
    r"Traceback\s*\(most recent call last\):.*?(?=\n\n|\Z)",
    re.DOTALL,
)
# File path pattern in errors
_FILE_PATH_PATTERN = re.compile(
    r'File\s+"[^"]*\.py",\s*line\s*\d+',
)


def sanitize_user_input(text: str, max_length: int = 2000) -> str:
    """清洗用户输入，阻止 Prompt 注入。

    - 去除控制字符
    - 检测注入模式，标记可疑内容
    - 截断超长输入

    Args:
        text: 原始用户输入
        max_length: 最大允许长度（超过部分截断）

    Returns:
        清洗后的安全文本
    """
    if not text:
        return ""

    # 截断
    if len(text) > max_length:
        text = text[:max_length]

    # 去除控制字符
    text = _CONTROL_CHARS.sub("", text)

    # 检测并中和注入模式
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            # 用占位符替换注入片段，保留其余内容
            text = pattern.sub("[内容已过滤]", text)

    return text.strip()


def sanitize_rag_content(text: str) -> str:
    """清洗 RAG/工具返回值，去除报错堆栈和内部路径。

    Args:
        text: 原始 RAG 检索或工具返回内容

    Returns:
        清洗后的安全文本
    """
    if not text:
        return ""

    # 屏蔽 Python traceback
    text = _TRACEBACK_PATTERN.sub("[内部错误信息已屏蔽]", text)

    # 屏蔽文件路径
    text = _FILE_PATH_PATTERN.sub("[内部路径已屏蔽]", text)

    # 去除控制字符
    text = _CONTROL_CHARS.sub("", text)

    return text.strip()
