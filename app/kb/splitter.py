"""文档加载与递归切分 —— 种子 Markdown → chunk 列表。

切分策略：RecursiveCharacterTextSplitter，Markdown 优先分隔符。
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

# Markdown 优先：标题 → 段落 → 句号 → 换行 → 空格
_MD_SEPARATORS = [
    "\n## ", "\n### ", "\n#### ",
    "\n\n", "\n",
    "。", "；", "，",
    " ", "",
]

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=600,
    chunk_overlap=80,
    separators=_MD_SEPARATORS,
    keep_separator=True,
)


@dataclass(frozen=True)
class DocChunk:
    """切分后的单条知识片段。"""
    chunk_id: str         # {source}-{idx:03d}
    content: str          # 切分后正文
    metadata: dict[str, str]  # knowledge_type, source, industry, city


def _parse_frontmatter(text: str) -> dict[str, str]:
    """读取 YAML 头部和历史 Markdown 注释中的 metadata。"""
    meta: dict[str, str] = {}
    if text.startswith("---"):
        _, _, remainder = text.partition("\n")
        frontmatter, separator, _ = remainder.partition("\n---")
        if separator:
            for line in frontmatter.splitlines():
                key, colon, value = line.partition(":")
                if colon and key.strip():
                    meta[key.strip()] = value.strip().strip('"')
    for line in text.split("\n"):
        m = re.match(r">\s*([^：:]+)[：:]\s*(.+)", line.strip())
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            # 归一化 key
            key_map = {
                "知识类型": "knowledge_type",
                "覆盖城市": "city",
                "适用场景": "scenario",
                "用途": "usage",
                "说明": "note",
            }
            meta[key_map.get(key, key)] = val
    return meta


def load_and_split(doc_dir: str) -> list[DocChunk]:
    """递归切分场景目录中的 Markdown，并继承目录和文档元数据。"""
    chunks: list[DocChunk] = []
    root = Path(doc_dir)
    for fpath in sorted(root.rglob("*.md")):
        relative_path = fpath.relative_to(root)
        if fpath.name == "README.md" or "archive" in relative_path.parts:
            continue
        with fpath.open(encoding="utf-8") as f:
            raw = f.read()
        meta = _parse_frontmatter(raw)
        if len(relative_path.parts) >= 3:
            meta.setdefault("domain", relative_path.parts[0])
            meta.setdefault("scenario_id", relative_path.parts[1])
        # 把 Markdown title (# xxx) 当作文档标题
        title_match = re.search(r"^#\s+(.+)", raw, re.MULTILINE)
        doc_title = title_match.group(1).strip() if title_match else fpath.stem
        meta.setdefault("source", doc_title)
        meta["document_title"] = doc_title
        meta["source_file"] = str(relative_path).replace("\\", "/")

        texts = _splitter.split_text(raw)
        base = str(relative_path.with_suffix(""))
        base = base.replace("\\", "_").replace("/", "_").replace(" ", "_")
        for idx, text in enumerate(texts):
            cid = f"{base}-{idx:03d}"
            chunks.append(DocChunk(
                chunk_id=cid,
                content=text.strip(),
                metadata=dict(meta),
            ))
    return chunks
