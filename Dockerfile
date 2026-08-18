# 衍界 YanJie AI · 后端生产镜像
# 构建上下文：项目根目录
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# pg_isready 用于启动脚本等待数据库；libpq 供 psycopg 链接
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先拷贝依赖清单并安装（利用层缓存，仅在依赖变更时重建）
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install ".[dev]"

# 拷贝源码与运行所需数据
COPY app ./app
COPY scenarios ./scenarios
COPY "文档种子数据" "./文档种子数据"
COPY deploy/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# 向量库持久化目录（运行时挂卷）
RUN mkdir -p /app/chroma_data

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]
