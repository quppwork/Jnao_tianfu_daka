# 「问大宇 · 这份报告」iframe 嵌入说明

面向宿主页开发。对话由劲脑侧提供并维护；宿主只需嵌页面并传入已有账号与测评参数。

**嵌入页：**  
`https://jnaosoft.cn/static/dayu/html/report-talent-chat-embed.html`

账号仍走已有接口：`POST /api/partner/jinnao/register-parent`（拿到本系统 `user_id`，写入你们库的 `ai_user_id`）。**不必再接新的 ensure 接口。**

---

## 1. 怎么嵌

```html
<iframe
  src="https://jnaosoft.cn/static/dayu/html/report-talent-chat-embed.html?user_id=AI用户ID&token=登录令牌&dayu_test_result_id=测评结果ID"
  style="width:100%;height:100%;min-height:560px;border:0;border-radius:16px"
  allow="clipboard-write"
  title="问大宇 · 这份报告"
></iframe>
```

生产使用 **HTTPS**。`token` 由你们后端下发后拼进 URL，不要写死在前端，也不要把合作方 `X-Api-Key` 放到浏览器。

---

## 2. URL 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `user_id` | 是 | 本系统用户 ID（`ys_dayu_parent_user.ai_user_id`，register-parent 返回的 `user_id`） |
| `token` | 是 | 该用户登录 JWT（可存于 `ai_session_id`）；嵌入页读入后会从地址栏清除 |
| `dayu_test_result_id` | 是* | `ys_dayu_test_result.id`（成人测评）。打开时会自动关联报告，无需你们再同步 |
| `wx_user_id` | 否 | `ys_wx_member.id`；一般可不传（按 `ai_user_id` 反查） |
| `assessment_id` | 否 | 本系统报告 ID；若已有可直接传，则不必传 `dayu_test_result_id` |
| `talent` | 否 | 天赋名，如 `思者`（快捷提问兜底） |
| `theme` | 否 | 传 `lt` 为浅色 |

\* `dayu_test_result_id` 与 `assessment_id` 二选一即可（推荐前者，用你们库已有字段）。  
`access_token` / `test_result_id` 分别可代替 `token` / `dayu_test_result_id`。

---

## 3. 与宿主页的消息（可选）

嵌入页会向父页面 `postMessage`，`source` 固定为 `jnao-report-talent-chat`：

```js
window.addEventListener('message', (ev) => {
  const d = ev.data;
  if (!d || d.source !== 'jnao-report-talent-chat') return;
  // d.type:
  //   jnao-embed-ready  — 对话打开成功
  //   jnao-embed-error  — 缺参或鉴权失败（见 d.message）
  //   jnao-embed-close  — 用户点击关闭
  //   jnao-embed-cite   — 用户点击「§ 引用 · 章节」（见 d.section）
});
```

---

## 4. 职责划分

| 劲脑侧（我们） | 宿主侧（你们） |
|----------------|----------------|
| 嵌入页、对话、流式回答 | 报告页放置 iframe |
| 按 `dayu_test_result_id` 自动关联报告 | 传入 `user_id` + `token` + `dayu_test_result_id` |
| Agent / 知识库 / 后续扩展 | 账号仍用 register-parent；按需听 postMessage |

无需接入 Agent 内部实现，也无需持有模型密钥。

---

## 5. 联调自检

- iframe 能打开，参数正确时可看到开场白 / 历史  
- 提问有回复  
- 错误 `token` 会提示失败（或收到 `jnao-embed-error`）  
- `ai_user_id` 已指向 register-parent 返回的用户  

---
