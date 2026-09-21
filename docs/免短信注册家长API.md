# 劲脑合作方 API — 免短信注册家长

> 版本：v1 · 更新：2026-09-10  
> 生产 Base URL：`https://jnaosoft.cn`  
> 鉴权：请求头 `X-Api-Key`（由 JNAO 侧单独下发，勿写入公开仓库）

---

## 1. 概述

劲脑侧已完成用户校验时，可通过本接口在 **JNAO 天赋打卡系统** 创建家长账号（**无需短信验证码**），并拿到本系统 `user_id` 做双向关联。

| 项 | 说明 |
|---|---|
| 来源标记 | `register_channel=jinnao`，`register_source=劲脑` |
| 必填参数 | 与站内短信注册一致：手机号、真实姓名、昵称、密码（去掉验证码） |
| 幂等 | 手机号已存在时 **不新建**，返回原 `user_id`，`created=false` |

---

## 2. 鉴权

所有合作方接口必须在 Header 携带：

```http
X-Api-Key: <JNAO 下发的密钥>
Content-Type: application/json
```

| HTTP | 含义 |
|------|------|
| 401 | Key 缺失或错误 |
| 503 | 服务端未配置合作 Key |

---

## 3. 注册家长

### 3.1 基本信息

| 项 | 值 |
|---|---|
| Method | `POST` |
| Path | `/api/partner/jinnao/register-parent` |
| 完整 URL | `https://jnaosoft.cn/api/partner/jinnao/register-parent` |

### 3.2 请求体

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| `phone` | string | 是 | 11～20 位 | 中国大陆手机号 |
| `real_name` | string | 是 | 2～20 字 | 家长真实姓名 |
| `nickname` | string | 是 | 2～20 字 | 展示昵称 |
| `password` | string | 是 | 8～128 位 | 登录密码（需满足强度策略） |
| `partner_ref` | string | 否 | ≤64 | 劲脑侧用户 ID，便于排查与回显 |

### 3.3 成功响应 `200`

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | int | **本系统家长账户 ID（关联请用此字段）** |
| `parent_phone` | string | 规范化后的手机号 |
| `nickname` | string | 昵称 |
| `register_channel` | string | 固定 `jinnao` |
| `register_source` | string | 固定 `劲脑` |
| `created` | bool | `true`=新注册；`false`=已存在，返回原账号 |
| `partner_ref` | string\|null | 请求里传入的侧标识回显 |

**新注册示例**

```json
{
  "user_id": 77,
  "parent_phone": "19900001122",
  "nickname": "劲脑联调",
  "register_channel": "jinnao",
  "register_source": "劲脑",
  "created": true,
  "partner_ref": "curl-smoke-001"
}
```

**已存在示例**

```json
{
  "user_id": 77,
  "parent_phone": "19900001122",
  "nickname": "劲脑联调",
  "register_channel": "jinnao",
  "register_source": "劲脑",
  "created": false,
  "partner_ref": "jinnao-user-10086"
}
```

### 3.4 错误响应

| HTTP | 场景 | `detail` 示例 |
|------|------|----------------|
| 400 | 参数校验失败 / 昵称或密码不合规 | 具体文案 |
| 401 | API Key 无效 | `无效的 API Key` |
| 429 | 同一手机号并发注册 | `注册处理中，请稍后再试` |
| 503 | 未配置 Key | `劲脑合作接口未配置（缺少 JINNAO_PARTNER_API_KEY）` |
| 422 | JSON 格式错误 | FastAPI 校验结构 |

---

## 4. 调用示例

### 4.1 curl

```bash
curl -X POST "https://jnaosoft.cn/api/partner/jinnao/register-parent" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: <请向 JNAO 索取>" \
  -d '{
    "phone": "13800138000",
    "real_name": "张三",
    "nickname": "张家长",
    "password": "YourPass123",
    "partner_ref": "jinnao-user-10086"
  }'
```

### 4.2 JavaScript (fetch)

```javascript
const res = await fetch('https://jnaosoft.cn/api/partner/jinnao/register-parent', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Api-Key': process.env.JNAO_PARTNER_API_KEY, // 仅服务端持有
  },
  body: JSON.stringify({
    phone: '13800138000',
    real_name: '张三',
    nickname: '张家长',
    password: 'YourPass123',
    partner_ref: 'jinnao-user-10086',
  }),
})
const data = await res.json()
if (!res.ok) throw new Error(data.detail || res.statusText)
// 持久化关联：data.user_id ↔ 劲脑侧用户
console.log(data.user_id, data.created)
```

### 4.3 Python (requests)

```python
import os
import requests

resp = requests.post(
    "https://jnaosoft.cn/api/partner/jinnao/register-parent",
    headers={
        "Content-Type": "application/json",
        "X-Api-Key": os.environ["JNAO_PARTNER_API_KEY"],
    },
    json={
        "phone": "13800138000",
        "real_name": "张三",
        "nickname": "张家长",
        "password": "YourPass123",
        "partner_ref": "jinnao-user-10086",
    },
    timeout=15,
)
resp.raise_for_status()
data = resp.json()
print(data["user_id"], data["created"])
```

---

## 5. 对接建议

1. **只存 `user_id`**：作为 JNAO 家长主键做关联；不要依赖昵称。
2. **服务端调用**：`X-Api-Key` 仅放服务端环境变量，勿下发 App/前端。
3. **先注册再业务**：拿到 `user_id` 后再写你们侧的绑定表。
4. **重复调用安全**：同一手机号多次调用只会得到同一个 `user_id`。
5. **密码**：用户后续可用该手机号 + 密码在 JNAO 家长端登录（与站内家长账号体系一致）。

---

## 6. 联调清单（给对接方）

JNAO 侧需提供：

- [ ] 生产 Base URL：`https://jnaosoft.cn`
- [ ] `X-Api-Key` 密钥（单独安全通道下发）
- [ ] 本接口文档

对接方需确认：

- [ ] 能 `200` 拿到 `user_id`
- [ ] 重复同一手机号得到 `created=false` 且 `user_id` 不变
- [ ] Key 错误得到 `401`
