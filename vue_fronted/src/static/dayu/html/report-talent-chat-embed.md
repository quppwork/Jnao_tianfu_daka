# 「问大宇 · 这份报告」iframe 嵌入说明

面向宿主页开发。对话由 **jnaosoft（本系统）** 提供并维护；宿主只需嵌页面并传入账号与测评参数。

孩子/家长首页 AI、学科答疑、天赋学院、家长在线咨询等整页能力请对方自研前端，接口见同目录 **`partner-ai-modules-api.md`**（登录与主数据以对方库表为准）。

**唯一嵌入页（请勿改用其它报告页）：**  
`https://jnaosoft.cn/static/dayu/html/report-talent-chat-embed.html`

**不要打开** `report-v3.html` / 其它 dayu 报告页——那是本站完整报告 UI，不是给你们嵌对话用的；错用常会出现「测评记录不存在」。

---

## 0. 你们库 vs 必须调接口

| 你们直接读自己库即可 | 必须调本系统接口 |
|----------------------|------------------|
| `ys_dayu_test_result.id`（成人测评结果） | `POST /api/partner/jinnao/register-parent` → 拿本系统 `user_id`，写回你们库 `ys_dayu_parent_user.ai_user_id` |
| 已保存的 `ai_user_id`、`ai_session_id`（token） | 浏览器里的对话 / 历史由嵌入页自动调本系统 API（需 JWT） |
| 微信侧用户 id（可选，作 `wx_user_id`） | （可选）`POST /api/partner/jinnao/ensure-report-chat`：一次拿到 token + 本系统 `assessment_id` + `embed_url` |

说明：

- 测评正文、天赋结果**不用推给我们**；嵌入页打开时会按 `dayu_test_result_id` **自动关联**到本系统报告。
- **不要**把 `ys_dayu_test_result.id` 填进参数名 `assessment_id`。`assessment_id` 是本系统报告 ID（仅当你们已通过 ensure 等方式拿到时才用）。
- 账号仍走已有 `register-parent` 即可；**不必**为嵌对话再接 ensure（ensure 只是可选快捷方式）。

---

## 1. 怎么嵌

`user_id`、`token`、报告 id（见下）**三者都要有**，缺一会无法对话。

```html
<iframe
  src="https://jnaosoft.cn/static/dayu/html/report-talent-chat-embed.html?user_id=AI用户ID&token=登录令牌&dayu_test_result_id=测评结果ID"
  style="width:100%;height:100%;min-height:560px;border:0;border-radius:16px"
  allow="clipboard-write"
  title="问大宇 · 这份报告"
></iframe>
```

生产使用 **HTTPS**。`token` 由你们**后端**下发后拼进 URL，不要写死在前端，也不要把合作方 `X-Api-Key` 放到浏览器。

若已调 ensure，可直接把返回的 `embed_url` 作为 iframe 的 `src`。

---

## 2. URL 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `user_id` | **是** | 本系统用户 ID（`ys_dayu_parent_user.ai_user_id` = register-parent 返回的 `user_id`） |
| `token` | **是** | 该用户登录 JWT（可存于 `ai_session_id`）；嵌入页读入后会从地址栏清除 |
| `dayu_test_result_id` | **是\*** | 你们库 `ys_dayu_test_result.id`（**仅成人测评**）。打开时自动关联本系统报告 |
| `wx_user_id` | 否 | `ys_wx_member.id`；一般可不传（按 `ai_user_id` 反查） |
| `assessment_id` | 否\* | **本系统**报告 ID；仅当已有时传，此时不必再传 `dayu_test_result_id` |
| `talent` | 否 | 天赋名，如 `思者`（快捷提问兜底） |
| `theme` | 否 | 传 `lt` 为浅色 |

\* `dayu_test_result_id` 与 `assessment_id` **二选一**（推荐前者，用你们库已有字段）。  
别名：`access_token` ≈ `token`；`test_result_id` ≈ `dayu_test_result_id`。

常见错误 → 「测评记录不存在」：登录用户与报告所有者不一致，或把你们的测评 id 当成了 `assessment_id`。

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

| 本系统（jnaosoft） | 宿主侧（你们） |
|--------------------|----------------|
| 嵌入页、对话、流式回答、对话存档 | 报告页放置上述 iframe（或 ensure 的 `embed_url`） |
| 按 `dayu_test_result_id` 自动关联本库报告 | 传入 `user_id` + `token` + `dayu_test_result_id` |
| Agent / 知识库 | `register-parent` 并回写 `ai_user_id`；按需听 postMessage |

无需接入 Agent 内部实现，也无需持有模型密钥；无需直连本系统数据库。

---

## 5. 联调自检

- iframe 的 URL 必须是 `report-talent-chat-embed.html`，不是 `report-v3.html`
- 参数齐全时可看到开场白 / 历史，并能提问得到回复
- 错误 `token` 会失败（或 `jnao-embed-error`）
- `ai_user_id` 已指向 register-parent 返回的用户
- 「测评记录不存在」→ 检查是否误传 `assessment_id`、或 `user_id`/`token` 与该测评绑定人不一致

---
