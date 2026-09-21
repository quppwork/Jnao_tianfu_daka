# 百炼完整 RAG 架构（JNAO）

> 对齐官方：[知识库 API 指南](https://help.aliyun.com/zh/model-studio/rag-knowledge-base-api-guide)  
> 前置配置：[百炼知识库-阿里云前置配置.md](./百炼知识库-阿里云前置配置.md)  
> API 速查：[百炼知识库API接入准备.md](./百炼知识库API接入准备.md)  
> 更新日期：2026-08-25

---

## 一、与旧 RAG 的区别

| | 旧 `tianfu_rag`（enterprise_rag） | 现 **百炼完整 RAG** |
|--|--|--|
| 知识库 | 自建服务黑盒 `/chat` | 阿里云文档搜索类知识库（控制台/API 可管） |
| 检索 | 服务内部完成，只返回 `answer` | 官方 **Retrieve / Search** 返回切片 `nodes` |
| 生成 | 上游模型写死 | **切片 + 豆包**（项目可控） |
| 运维 | 依赖内网 8010 | 北京公网 OpenAPI / MaaS Host |
| 引导页 | 未接 | ✅ `GUIDE_RAG_ENABLED=1` |
| 学科答疑 | 仍走 tianfu_rag（遗留） | 待独立学科库后再切 |

官方三种用法中，JNAO 采用的是：

> **API 检索切片 → 自有大模型生成**（不是百炼应用里挂 `rag_options`）

---

## 二、完整流水线

```
用户问题（引导页）
    │
    ├─ guide_rag_router：是否查库（天赋/训练类；解题类跳过）
    │
    ▼
Bailian RAG（app/services/bailian）
    │
    ├─ mode=retrieve（默认）
    │     OpenAPI Retrieve
    │     endpoint: bailian.cn-beijing.aliyuncs.com
    │     鉴权: AccessKey（可复用 OSS_*）
    │     参数: dense_top_k / enable_reranking / rerank_top_n / enable_rewrite
    │
    └─ mode=search（可选）
          HTTP Search
          https://{BAILIAN_API_HOST}/api/v1/indices/knowledge/search
          鉴权: Bearer DASHSCOPE_API_KEY
          需控制台发布知识检索 Agent → BAILIAN_AGENT_ID
    │
    ▼
RagResult（nodes / score / sources / rag_block）
    │
    ▼
guide/runner：注入 system prompt「知识库参考」
    │
    ▼
豆包 Ark 生成教练式回复（流式/非流式）
```

---

## 三、代码结构

```
backend/app/services/bailian/
  config.py      # 环境变量 → BailianConfig
  client.py      # OpenAPI Client 工厂
  models.py      # RagNode / RagResult
  retrieve.py    # Retrieve 官方接口
  search.py      # Search HTTP + ListIndices
  __init__.py    # rag_query / guide_rag_query / bailian_status

backend/app/services/bailian_rag_client.py   # 兼容旧导入
backend/app/services/guide_rag_router.py     # 引导页触发条件
backend/tools/bailian_rag_verify.py          # 配置/检索冒烟
```

---

## 四、环境变量（完整）

```bash
BAILIAN_WORKSPACE_ID=ws-0w5t66cmzttowdnw
BAILIAN_API_HOST=ws-0w5t66cmzttowdnw.cn-beijing.maas.aliyuncs.com
BAILIAN_INDEX_ID=x1micrdmjq
DASHSCOPE_API_KEY=...                 # Search 用
BAILIAN_AGENT_ID=                     # Search 用（控制台发布后填）

GUIDE_RAG_ENABLED=1
GUIDE_RAG_MODE=retrieve               # retrieve | search

# Retrieve 调参（可选）
BAILIAN_RETRIEVE_TOP_N=3
BAILIAN_DENSE_TOP_K=6
BAILIAN_ENABLE_RERANKING=1
BAILIAN_ENABLE_REWRITE=0

# AccessKey：优先 ALIBABA_CLOUD_*，否则 OSS_*
# ALIBABA_CLOUD_ACCESS_KEY_ID=
# ALIBABA_CLOUD_ACCESS_KEY_SECRET=
```

当前已确认：`index_id=x1micrdmjq`（Jinao 天赋知识库）。

---

## 五、验证

```bash
cd backend
python tools/bailian_rag_verify.py --query "学者天赋是什么"
```

或：`GET /api/health` → `integrations.bailian_rag`  
`GET /api/guide/debug` → `bailian_rag`

---

## 六、后续（学科答疑）

1. 控制台再建 **学科教学法** 知识库，或 Search Agent 挂多库  
2. `qa/runner` 将 `qa_rag_client.rag_chat` 换为 `bailian.rag_query`  
3. 下线 `TIANFU_RAG_URL` 依赖  

引导页已不再依赖旧 RAG。
