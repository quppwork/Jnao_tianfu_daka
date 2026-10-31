FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements-prod.txt .
RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    -r requirements-prod.txt

COPY backend/ .
# 目录数据由运行时挂载提供（docker-compose.prod.yml: ./docs/data:/catalog_data）
# 构建阶段不 COPY docs/data，避免服务器缺目录时 build 失败
RUN mkdir -p /catalog_data /app/data

ENV JNAO_HOST=0.0.0.0 \
    JNAO_PORT=8012 \
    TIANFU_RAG_MOCK=1 \
    CATALOG_DATA_DIR=/catalog_data

EXPOSE 8012

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8012"]
