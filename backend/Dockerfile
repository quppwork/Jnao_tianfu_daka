FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements-prod.txt .
RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    -r requirements-prod.txt

COPY backend/ .
COPY docs/data/ /catalog_data/

ENV JNAO_HOST=0.0.0.0 \
    JNAO_PORT=8012 \
    TIANFU_RAG_MOCK=1 \
    CATALOG_DATA_DIR=/catalog_data

RUN mkdir -p /app/data

EXPOSE 8012

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8012"]
