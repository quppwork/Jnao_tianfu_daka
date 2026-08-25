# 百炼知识库 API 接入准备文档

> **用途**：明天接入 JNAO 项目知识库（优先引导页）前的速查手册  
> **前置配置**：[百炼知识库-阿里云前置配置.md](./百炼知识库-阿里云前置配置.md)（控制台、RAM、密钥、建库）  
> **完整架构**：[百炼知识库-完整RAG架构.md](./百炼知识库-完整RAG架构.md)（官方流水线代码结构）  
> **来源**：[阿里云百炼 · 知识库 API 指南](https://help.aliyun.com/zh/model-studio/rag-knowledge-base-api-guide)  
> **适用范围**：文档搜索类知识库 · 中国站华北2（北京）  
> **编写日期**：2026-08-24

---

## 一、接入目标（JNAO）

| 模块 | 现状 | 明天目标 |
|------|------|----------|
| **首页引导页** `/api/guide/chat` | 豆包 + 只读工具，**无 RAG** | 接入百炼 Retrieve，注入平台/训练/天赋类知识 |
| **学科答疑** `/api/qa/chat` | 已有 `tianfu_rag` 本地代理（8010） | 可先不动；后续可切百炼或让 tianfu_rag 转发 |
| **前端** `index.vue` | 已接 `/api/guide/chat/stream` | **无需改**，RAG 在后端透明完成 |

引导页人设是「教练引导、不解题」——知识库内容建议放：**平台说明、训练方法、天赋解读、FAQ**，与学科答疑知识库分开。

---

## 二、前置条件清单

> 控制台逐步操作见 **[百炼知识库-阿里云前置配置.md](./百炼知识库-阿里云前置配置.md)**。

### 2.1 阿里云控制台

- [ ] 开通百炼，地域选 **华北2（北京）**
- [ ] 子账号挂策略 **`AliyunBailianDataFullAccess`**，并加入业务空间
- [ ] 记录 **业务空间 ID**（`WORKSPACE_ID`，形如 `ws-xxxx`）与 **API Host**
- [ ] 准备待上传文档（docx/pdf/md 等）
- [ ] （可选）创建并**发布**知识检索 Agent，拿 `agent_id`（多库检索用 Search）

### 2.2 本地 / 服务器环境

```bash
# Python SDK
pip install alibabacloud_bailian20231229 requests

# 环境变量（Linux / .env 均可）
export ALIBABA_CLOUD_ACCESS_KEY_ID='你的AK'
export ALIBABA_CLOUD_ACCESS_KEY_SECRET='你的SK'
export WORKSPACE_ID='ws-xxxxxxxxxxxxxxxx'   # 业务空间 ID
export BAILIAN_API_HOST='ws-xxxxxxxx.cn-beijing.maas.aliyuncs.com'  # 控制台 API Host
export BAILIAN_INDEX_ID='idx_xxxxxxxx'      # 建库后填入
export DASHSCOPE_API_KEY='sk-xxxxxxxx'      # Search API 用（可选）
```

> JNAO 已确认：`WORKSPACE_ID=ws-0w5t66cmzttowdnw`，详见 [阿里云前置配置 §3.3](./百炼知识库-阿里云前置配置.md#33-jnao-当前业务空间已确认)。

### 2.3 SDK Client 初始化（所有 OpenAPI 共用）

```python
from alibabacloud_bailian20231229.client import Client as BailianClient
from alibabacloud_tea_openapi import models as open_api_models

def create_client() -> BailianClient:
    config = open_api_models.Config(
        access_key_id=os.environ["ALIBABA_CLOUD_ACCESS_KEY_ID"],
        access_key_secret=os.environ["ALIBABA_CLOUD_ACCESS_KEY_SECRET"],
    )
    # 公网
    config.endpoint = "bailian.cn-beijing.aliyuncs.com"
    # 同地域 VPC 内可用：bailian-vpc.cn-beijing.aliyuncs.com
    return BailianClient(config)
```

**鉴权方式**：OpenAPI 系列（建库、Retrieve 等）用 **AccessKey**；Search HTTP 用 **DashScope API Key（Bearer）**。

---

## 三、创建知识库（9 步流水线）

> **缺任何一步都会导致空库或失败**。`CreateIndex` 后必须调 `SubmitIndexJob`。

### 流程总览

```
ApplyFileUploadLease → PUT 上传文件 → AddFile → DescribeFile(轮询)
  → CreateIndex → SubmitIndexJob → GetIndexJobStatus(轮询 COMPLETED)
```

### 默认参数（文档示例）

| 参数 | 值 | 说明 |
|------|-----|------|
| `category_id` | `default` | 文件类目，全流程必须一致 |
| `parser` | `DASHSCOPE_DOCMIND` | 文档解析器 |
| `source_type` | `DATA_CENTER_FILE` | 数据来源类型 |
| `structure_type` | `unstructured` | 非结构化文档 |
| `sink_type` | `DEFAULT` | 向量存储类型 |

---

### 步骤 1：ApplyFileUploadLease — 申请上传租约

**SDK 方法**：`client.apply_file_upload_lease_with_options(category_id, workspace_id, request, headers, runtime)`

**请求体** `ApplyFileUploadLeaseRequest`：

```python
request = ApplyFileUploadLeaseRequest(
    file_name="平台训练说明.docx",   # 必须与实际文件名一致（含后缀）
    md_5=file_md5,                   # 文件 MD5（官方称当前不校验，但字段必填）
    size_in_bytes=file_size,         # 字节数
)
```

**响应关键字段**（下一步要用）：

| 字段 | 用途 |
|------|------|
| `Data.FileUploadLeaseId` | 租约 ID → AddFile |
| `Data.Param.Url` | 临时 PUT 上传地址 |
| `Data.Param.Headers["X-bailian-extra"]` | 上传请求头 |
| `Data.Param.Headers["Content-Type"]` | 上传请求头 |

租约有效期：**分钟级**，过期需重新申请。

---

### 步骤 2：PUT 上传文件到临时存储

**非 SDK 调用**，用 `requests` 直传：

```python
import requests

with open(file_path, "rb") as f:
    content = f.read()

upload_headers = {
    "X-bailian-extra": lease_headers["X-bailian-extra"],
    "Content-Type": lease_headers["Content-Type"],
}
resp = requests.put(upload_url, data=content, headers=upload_headers)
resp.raise_for_status()  # 必须成功，否则 AddFile 报 Access your uploaded file failed
```

---

### 步骤 3：AddFile — 注册文件到类目

**SDK 方法**：`client.add_file_with_options(workspace_id, request, headers, runtime)`

```python
request = AddFileRequest(
    lease_id=lease_id,
    parser="DASHSCOPE_DOCMIND",
    category_id="default",
)
# 响应：Data.file_id
```

---

### 步骤 4：DescribeFile — 轮询解析状态

**SDK 方法**：`client.describe_file_with_options(workspace_id, file_id, headers, runtime)`

| status | 含义 |
|--------|------|
| `INIT` | 待解析 |
| `PARSING` | 解析中 |
| `PARSE_SUCCESS` | ✅ 可继续建索引 |
| 其他 | 失败，联系支持 |

建议每 **5 秒** 轮询一次。

---

### 步骤 5：CreateIndex — 初始化知识库

**SDK 方法**：`client.create_index_with_options(workspace_id, request, headers, runtime)`

```python
request = CreateIndexRequest(
    name="JNAO-引导页知识库",
    structure_type="unstructured",
    source_type="DATA_CENTER_FILE",
    sink_type="DEFAULT",
    document_ids=[file_id],
)
# 响应：Data.id → index_id（知识库 ID，后续 Retrieve 必传）
```

---

### 步骤 6：SubmitIndexJob — 提交索引任务

**SDK 方法**：`client.submit_index_job_with_options(workspace_id, request, headers, runtime)`

```python
request = SubmitIndexJobRequest(index_id=index_id)
# 响应：Data.id → job_id
```

> ⚠️ **只 CreateIndex 不调 SubmitIndexJob = 空知识库**

---

### 步骤 7：GetIndexJobStatus — 轮询索引完成

**SDK 方法**：`client.get_index_job_status_with_options(workspace_id, request, headers, runtime)`

```python
request = GetIndexJobStatusRequest(index_id=index_id, job_id=job_id)
# status == "COMPLETED" 时建库完成
```

---

### 创建成功后的 ID 记录表

| ID | 来源接口 | 用途 |
|----|----------|------|
| `file_id` | AddFile | 更新/删文档 |
| `index_id` | CreateIndex | Retrieve、ListChunks |
| `job_id` | SubmitIndexJob | 查任务状态 |

控制台也可在「知识库」页面复制 `index_id`。

---

## 四、检索知识库

### 4.1 三种方式对比

| 方式 | 接口 | 返回 | JNAO 建议 |
|------|------|------|-----------|
| 百炼应用 | App API + `rag_options.index_id` | **模型生成的最终回答** | 暂不采用（已有豆包） |
| OpenAPI Retrieve | `Retrieve` | **文本切片** | ✅ 引导页首选，可控 |
| 知识检索 Search | HTTP Search | **文本切片**（跨多库） | 多库/多模态时用 |

JNAO 模式：**Retrieve 拿切片 → 注入豆包 system prompt → 豆包生成教练式回复**（与现有 QA RAG 模式一致）。

---

### 4.2 Retrieve — 单库检索（OpenAPI + AccessKey）

**SDK 方法**：`client.retrieve_with_options(workspace_id, request, headers, runtime)`

**最简请求**：

```python
from alibabacloud_bailian20231229 import models

request = models.RetrieveRequest(
    index_id="idx_xxxxxxxx",
    query="超脑阅读怎么练？",
)
resp = client.retrieve_with_options(workspace_id, request, {}, runtime)
# resp.body.data.nodes → 切片列表
```

**RetrieveRequest 全部 15 个字段**（SDK 2.14.3）：

| 字段 | 说明 |
|------|------|
| `index_id` | 知识库 ID（必填） |
| `query` | 检索问题（必填） |
| `dense_similarity_top_k` | 向量召回 Top-K |
| `sparse_similarity_top_k` | 稀疏召回 Top-K |
| `enable_reranking` | 是否重排序 |
| `rerank_top_n` | 重排后保留条数 |
| `rerank_min_score` | 最低相关性分数 |
| `rerank` | 重排模型配置 |
| `enable_rewrite` | 是否 Query 改写 |
| `rewrite` | 改写配置 |
| `query_history` | 多轮检索历史 |
| `search_filters` | 过滤条件 |
| `images` | 多模态图片 |
| `extra` | 扩展参数 |
| `save_retriever_history` | 是否保存检索历史 |

> 不含 `response_format`——JSON 输出需在**模型层**设置。

**推荐生产参数示例**：

```python
request = models.RetrieveRequest(
    index_id=index_id,
    query=query,
    dense_similarity_top_k=10,
    enable_reranking=True,
    rerank_top_n=3,
)
```

**响应 nodes 结构**（每条切片）：

```json
{
  "score": 0.92,
  "text": "切片正文…",
  "metadata": {
    "doc_id": "file_xxx",
    "doc_name": "文档名",
    "title": "标题",
    "content": "完整内容",
    "pipeline_id": "mymxbdxxxx",
    "_id": "chunk唯一ID"
  }
}
```

---

### 4.3 Search — 跨库检索（HTTP + DashScope Key，官方推荐）

**前置**：控制台创建并**发布**知识检索 Agent → 拿 `agent_id`。

**Endpoint**：

```
POST https://{workspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/indices/knowledge/search
Authorization: Bearer {DASHSCOPE_API_KEY}
Content-Type: application/json
```

**cURL 示例**：

```bash
curl -X POST "https://ws-xxxx.cn-beijing.maas.aliyuncs.com/api/v1/indices/knowledge/search" \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "aid-xxxxxxxxxxxxxxxx",
    "query": "请介绍一下超脑阅读训练方法。",
    "images": []
  }'
```

**Python 示例**：

```python
import os, requests

resp = requests.post(
    f"https://{workspace_id}.cn-beijing.maas.aliyuncs.com/api/v1/indices/knowledge/search",
    headers={
        "Authorization": f"Bearer {os.environ['DASHSCOPE_API_KEY']}",
        "Content-Type": "application/json",
    },
    json={
        "agent_id": agent_id,
        "query": user_query,
        "images": [],
    },
    timeout=30,
)
data = resp.json()
nodes = data.get("data", {}).get("nodes", [])
```

**响应示例**：

```json
{
  "code": "Success",
  "success": true,
  "data": {
    "total": 3,
    "nodes": [
      {
        "score": 0.9201,
        "text": "…切片正文…",
        "metadata": {
          "doc_name": "训练说明",
          "doc_id": "file_xxx",
          "_id": "chunk_xxx"
        }
      }
    ],
    "cost_time": 2629
  }
}
```

**限制**：默认 **25 QPS**；Agent 未发布会报错。

---

### 4.4 检索 + 大模型生成（JNAO 标准模式）

```python
# 1. 百炼 Retrieve
retrieve_req = models.RetrieveRequest(index_id=index_id, query=user_message)
retrieve_resp = client.retrieve_with_options(workspace_id, retrieve_req, {}, runtime)
context = "\n".join(n.text for n in retrieve_resp.body.data.nodes[:3])

# 2. 注入豆包（项目已有 doubao_client）
system = f"""你是张宇老师…
—— 知识库参考 ——
{context}
—— 知识库结束 ——"""
reply = await chat_completion(system_prompt=system, user_message=user_message, ...)
```

如需 JSON：在豆包/DashScope 层设 `response_format={"type": "json_object"}`，不在 Retrieve 层设。

---

## 五、更新知识库

文档类知识库**没有覆盖接口**，增量更新固定三步：

```
上传新文件（同创建 1-4 步）→ SubmitIndexAddDocumentsJob → DeleteIndexDocument(旧 file_id)
```

### SubmitIndexAddDocumentsJob

```python
request = SubmitIndexAddDocumentsJobRequest(
    index_id=index_id,
    document_ids=[new_file_id],
    source_type="DATA_CENTER_FILE",
)
resp = client.submit_index_add_documents_job_with_options(workspace_id, request, {}, runtime)
job_id = resp.body.data.id
# 轮询 GetIndexJobStatus 至 COMPLETED，任务完成前勿重复提交
```

### DeleteIndexDocument

```python
request = DeleteIndexDocumentRequest(
    index_id=index_id,
    document_ids=[old_file_id],
)
client.delete_index_document_with_options(workspace_id, request, {}, runtime)
```

**注意**：单次更新建议 **≤ 10 万** 文件；引用该库的应用会**实时生效**。

---

## 六、管理知识库

### ListIndices — 列出知识库

```python
request = ListIndicesRequest()
resp = client.list_indices_with_options(workspace_id, request, {}, runtime)
# resp.body.data → 知识库列表
```

### DeleteIndex — 永久删除

```python
request = DeleteIndexRequest(index_id=index_id)
client.delete_index_with_options(workspace_id, request, {}, runtime)
```

---

## 七、切片管理

| 操作 | SDK 方法 | 关键参数 |
|------|----------|----------|
| 列出 | `list_chunks_with_options` | `index_id`, `page_num`, `page_size` |
| 更新 | `update_chunk_with_options` | `pipeline_id`(=index_id), `data_id`, `chunk_id`, `content` |
| 删除 | `delete_chunk_with_options` | `pipeline_id`, `chunk_ids[]` |

```python
# 列出切片
req = ListChunksRequest(index_id=index_id, page_num=1, page_size=10)
result = client.list_chunks_with_options(workspace_id, req, {}, runtime)
for node in result.body.data.nodes or []:
    chunk_id = node.metadata["_id"]
    doc_id = node.metadata["doc_id"]
```

---

## 八、JNAO 后端接入方案（明天实施）

### 8.1 新增文件（建议）

```
backend/app/services/bailian_rag_client.py   # Retrieve / Search 封装
backend/app/services/guide_rag_router.py     # 何时触发 RAG（与 QA 分开）
```

### 8.2 修改文件

```
backend/app/agents/guide/runner.py           # run_chat / run_chat_stream 注入 rag_block
backend/app/agents/guide/runner.py           # build_chat_system_prompt 增加 rag_block 参数
backend/.env.example                         # 补充百炼配置项
backend/config/loader.py                     # （可选）加载百炼配置
```

### 8.3 .env 配置项（建议）

```bash
# 百炼知识库（业务空间已确认）
BAILIAN_WORKSPACE_ID=ws-0w5t66cmzttowdnw
BAILIAN_API_HOST=ws-0w5t66cmzttowdnw.cn-beijing.maas.aliyuncs.com
BAILIAN_INDEX_ID=                        # 建库后填
BAILIAN_AGENT_ID=                        # 可选，Search 用
DASHSCOPE_API_KEY=                       # Search 用；控制台左侧 API Key
GUIDE_RAG_ENABLED=1                      # 引导页开关
GUIDE_RAG_MODE=retrieve                  # retrieve | search
```

AccessKey 可与 OSS 共用 `ALIBABA_CLOUD_ACCESS_KEY_*`，也可单独 RAM 用户。

### 8.4 guide_rag_router 触发规则（建议）

**触发**（平台/训练/天赋类）：

- 「怎么练」「训练方法」「超脑阅读」「影像追忆」「天赋」「学者/思者/赢者/德者/行者」「打卡」「Tier」

**不触发**（交给学科答疑）：

- 具体学科题目、作业求解类

### 8.5 接入点（不改前端）

```
index.vue → POST /api/guide/chat/stream
         → guide_service.chat_stream()
         → guide/runner.run_chat_stream()
              ├─ [NEW] bailian_retrieve(query)  # 条件触发
              ├─ _gather_tools()                # 现有只读工具
              └─ doubao_client.chat_completion_stream(system + rag_block + tool_block)
```

bootstrap 欢迎语**暂不接 RAG**（靠 DB 情境 + 工具即可）。

---

## 九、明天执行 Checklist

### 上午：百炼侧

- [ ] 控制台上传 JNAO 平台/训练文档
- [ ] 跑通 9 步建库脚本，记录 `index_id`
- [ ] 用 Retrieve 测试 query：「超脑阅读怎么练」「学者天赋适合什么训练」
- [ ] 确认 `nodes` 返回 relevant 切片

### 下午：JNAO 后端

- [ ] `pip install alibabacloud_bailian20231229` 写入 requirements
- [ ] 实现 `bailian_rag_client.py`（Retrieve + 超时/降级）
- [ ] 实现 `guide_rag_router.py`
- [ ] 改 `guide/runner.py` 注入 rag_block
- [ ] `.env` 填 `BAILIAN_*`，设 `GUIDE_RAG_ENABLED=1`
- [ ] 重启后端，首页对话验证

### 验收标准

- [ ] 问平台/训练相关问题，回复含知识库事实（非编造）
- [ ] 问学科解题，仍引导去「学科答疑」
- [ ] RAG 失败时降级为纯豆包（不 500）
- [ ] `/api/health` 或 `/api/guide/debug` 可看到 rag 状态（可选）

---

## 十、常见错误速查

| 报错 | 原因 | 处理 |
|------|------|------|
| 知识库是空的 | 未 SubmitIndexJob | 补提交索引任务 |
| `Access your uploaded file failed` | PUT 上传失败就调了 AddFile | 确认租约 PUT 200 |
| `Access denied` / workspace 不存在 | endpoint 错或非空间成员 | 用北京 endpoint + 确认 WORKSPACE_ID |
| `Specified access key is not found` | AK 错或禁用 | 检查 RAM 密钥 |
| `Category is mismatched` | 租约与 AddFile 的 category_id 不一致 | 全程用同一 `default` |
| Agent 未发布 | Search 时 agent 未发布 | 控制台发布后再调 |
| 限流 | Search 超 25 QPS | 退避重试 |

---

## 十一、计费提醒

| 计费项 | 说明 |
|--------|------|
| 知识库规格 | 标准版/旗舰版按运行时长 |
| Embedding + Rerank | 建库、更新、检索时按 Token 计费 |

账户需保持余额充足，欠费会中断服务。

---

## 十二、API 速查表

| 场景 | API / 方法 | 鉴权 |
|------|------------|------|
| 申请上传租约 | `ApplyFileUploadLease` | AccessKey |
| 注册文件 | `AddFile` | AccessKey |
| 查文件解析 | `DescribeFile` | AccessKey |
| 建库 | `CreateIndex` | AccessKey |
| 提交索引 | `SubmitIndexJob` | AccessKey |
| 查索引任务 | `GetIndexJobStatus` | AccessKey |
| 检索（单库） | `Retrieve` | AccessKey |
| 检索（多库） | `POST .../knowledge/search` | DashScope Bearer |
| 追加文档 | `SubmitIndexAddDocumentsJob` | AccessKey |
| 删文档 | `DeleteIndexDocument` | AccessKey |
| 列知识库 | `ListIndices` | AccessKey |
| 删知识库 | `DeleteIndex` | AccessKey |
| 列/改/删切片 | `ListChunks` / `UpdateChunk` / `DeleteChunk` | AccessKey |

**官方 API 目录**：[知识库 API 参考](https://help.aliyun.com/zh/model-studio/developer-reference/api-bailian-2023-12-29-overview)

---

## 附录：完整建库 Python 骨架（可复制跑通）

```python
import hashlib, os, time, requests
from alibabacloud_bailian20231229 import models as m
from alibabacloud_bailian20231229.client import Client
from alibabacloud_tea_openapi import models as openapi
from alibabacloud_tea_util import models as util

WORKSPACE = os.environ["WORKSPACE_ID"]
CATEGORY = "default"

def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()

def client():
    cfg = openapi.Config(
        access_key_id=os.environ["ALIBABA_CLOUD_ACCESS_KEY_ID"],
        access_key_secret=os.environ["ALIBABA_CLOUD_ACCESS_KEY_SECRET"],
    )
    cfg.endpoint = "bailian.cn-beijing.aliyuncs.com"
    return Client(cfg)

def create_kb(file_path: str, name: str) -> str:
    c = client()
    rt = util.RuntimeOptions()
    fn = os.path.basename(file_path)
    size = os.path.getsize(file_path)

    lease = c.apply_file_upload_lease_with_options(
        CATEGORY, WORKSPACE,
        m.ApplyFileUploadLeaseRequest(file_name=fn, md_5=md5(file_path), size_in_bytes=size),
        {}, rt,
    ).body.data
    hdrs = lease.param.headers
    requests.put(
        lease.param.url, data=open(file_path, "rb").read(),
        headers={"X-bailian-extra": hdrs["X-bailian-extra"], "Content-Type": hdrs["Content-Type"]},
    ).raise_for_status()

    fid = c.add_file_with_options(
        WORKSPACE,
        m.AddFileRequest(lease_id=lease.file_upload_lease_id, parser="DASHSCOPE_DOCMIND", category_id=CATEGORY),
        {}, rt,
    ).body.data.file_id

    while True:
        st = c.describe_file_with_options(WORKSPACE, fid, {}, rt).body.data.status
        if st == "PARSE_SUCCESS": break
        if st not in ("INIT", "PARSING"): raise RuntimeError(st)
        time.sleep(5)

    iid = c.create_index_with_options(
        WORKSPACE,
        m.CreateIndexRequest(name=name, structure_type="unstructured",
                             source_type="DATA_CENTER_FILE", sink_type="DEFAULT", document_ids=[fid]),
        {}, rt,
    ).body.data.id

    jid = c.submit_index_job_with_options(
        WORKSPACE, m.SubmitIndexJobRequest(index_id=iid), {}, rt,
    ).body.data.id

    while True:
        st = c.get_index_job_status_with_options(
            WORKSPACE, m.GetIndexJobStatusRequest(index_id=iid, job_id=jid), {}, rt,
        ).body.data.status
        if st == "COMPLETED": break
        time.sleep(5)

    print(f"index_id={iid}")
    return iid

if __name__ == "__main__":
    create_kb("docs/平台训练说明.docx", "JNAO-引导页知识库")
```
