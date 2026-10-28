# 成人报告「问大宇」iframe 嵌入对接说明

> 版本：`prod-20261028-001` / commit `a1bc3c8`  
> 站点：`https://jnaosoft.cn`  
> 嵌入页：`/static/dayu/html/report-talent-chat-embed.html`

本文给**第三方宿主页**与**本方发版/联调**共用。走 iframe：**对方不必拷贝整站前端，也不必持有 Agent 密钥**。

---

## 1. 方案结论

| 项 | 说明 |
|----|------|
| 嵌入方式 | 宿主页用 `<iframe>` 打开本方嵌入页 |
| 对话能力 | 仍在本方域名执行（历史 / 流式 / 报告上下文） |
| 对方职责 | 拼 URL 参数：`assessment_id`、`user_id`、`token` |
| 本方职责 | 鉴权、Agent、知识库、落库记忆 |

---

## 2. 线上地址

| 用途 | URL |
|------|-----|
| 嵌入页 | `https://jnaosoft.cn/static/dayu/html/report-talent-chat-embed.html` |
| 本说明（静态） | `https://jnaosoft.cn/static/dayu/html/report-talent-chat-embed.md` |
| API 根 | `https://jnaosoft.cn`（iframe 内相对路径 `/api/...`） |

本机联调前端：`http://127.0.0.1:5185/static/dayu/html/report-talent-chat-embed.html`

---

## 3. iframe 示例

```html
<iframe
  id="jnao-report-chat"
  src="https://jnaosoft.cn/static/dayu/html/report-talent-chat-embed.html?assessment_id=123&user_id=456&token=JWT&talent=思者"
  style="width:100%;height:100%;min-height:560px;border:0;border-radius:16px"
  allow="clipboard-write"
  title="问大宇 · 这份报告"
></iframe>
```

生产须 **HTTPS 嵌 HTTPS**。`token` 由宿主后端下发拼进 URL，**勿写死在前端仓库**。

---

## 4. URL 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `assessment_id` | 是 | 该份成人测评报告 ID |
| `user_id` | 是 | 报告归属用户 ID |
| `token` | 是 | 该用户有效登录 JWT（页内读入后会从地址栏清除） |
| `talent` | 否 | 天赋名，如 `思者`（快捷问题兜底） |
| `theme` | 否 | 传 `lt` 为浅色主题 |

同义：`access_token` 可代替 `token`。

---

## 5. 后端接口（iframe 已接好；对方一般不用自调）

鉴权头（嵌入页已自动带）：

- `Authorization: Bearer <token>`
- `X-Session-Token: <token>`
- `X-Child-User-Id: <user_id>`
- Query：`user_id=<user_id>`

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/talent/assessment/{id}/chat` | 历史 + 开场白 + chips |
| `POST` | `/api/talent/assessment/{id}/chat` | 整段回复（流式失败时回退） |
| `POST` | `/api/talent/assessment/{id}/chat/stream` | SSE 流式 |

`POST` 体：`{ "content": "用户问题" }`

SSE 事件 `type`：`token` | `replace` | `status` | `done` | `error`，结束另有 `[DONE]`。

归属校验：只能打开**当前用户有权查看**的报告，否则 404。

---

## 6. 父页 postMessage（可选）

嵌入页 → 宿主：

```js
window.addEventListener('message', (ev) => {
  const d = ev.data;
  if (!d || d.source !== 'jnao-report-talent-chat') return;
  switch (d.type) {
    case 'jnao-embed-ready':  /* 打开成功：assessment_id, user_id, messages */ break;
    case 'jnao-embed-error':  /* message */ break;
    case 'jnao-embed-close':  /* 用户点 ✕ */ break;
    case 'jnao-embed-cite':   /* section：报告章节名，宿主可跳转 */ break;
  }
});
```

| `type` | 含义 |
|--------|------|
| `jnao-embed-ready` | 对话打开成功 |
| `jnao-embed-error` | 缺参 / 鉴权失败等 |
| `jnao-embed-close` | 用户关闭 |
| `jnao-embed-cite` | 点击「§ 引用 · 章节」 |

---

## 7. 交付清单

### 本方每次开报告需提供给宿主

1. `assessment_id`
2. `user_id`
3. 短时有效的 `token`
4. 嵌入页完整 URL（见 §2）

### 对方不需要

- 百炼 / 豆包 API Key、Agent 提示词、仓库私钥
- 整仓 `vue_fronted` 业务代码（iframe 已足够）

### 可选：只读参考源码（非嵌入必需）

| 文件 | 作用 |
|------|------|
| `vue_fronted/src/static/dayu/html/report-talent-chat-embed.html` | 嵌入页本体 |
| `vue_fronted/src/static/dayu/js/sse-post.js` | SSE 客户端 |
| `vue_fronted/src/static/dayu/js/guide-rich.js` | 富文本渲染 |
| `vue_fronted/src/static/dayu/html/report-v3.html`（`#tcHandle` / `bootTalentChat`） | 报告页内抽屉原实现 |

Vue 组件对照：`vue_fronted/src/components/report-talent-chat/report-talent-chat.vue`

---

## 8. 宝塔发版备忘（本方运维）

| 项 | 值 |
|----|-----|
| 域名 | `https://jnaosoft.cn`（`SITE_DOMAIN`） |
| 代码目录 | `/data/wwwroot/jnao_daka` |
| 分支 | `backend/dev` |
| 发版 tag | `prod-20261028-001` |
| commit | `a1bc3c8` |

宝塔终端：

```bash
cd /data/wwwroot/jnao_daka
git fetch origin --tags
git checkout backend/dev
git pull origin backend/dev

test -f .env.production && echo "env ok" || echo "缺少 .env.production"
sed -i 's/^JNAO_BUILD_ID=.*/JNAO_BUILD_ID=prod-20261028-001/' .env.production
grep '^JNAO_BUILD_ID=' .env.production

bash scripts/deploy-baota.sh
docker compose -f docker-compose.prod.yml ps
git log -1 --oneline
```

验收：

```bash
curl -sI "https://jnaosoft.cn/static/dayu/html/report-talent-chat-embed.html" | head -5
curl -sI "https://jnaosoft.cn/static/dayu/html/report-talent-chat-embed.md" | head -5
```

回退：`git checkout prod-上一稳定 tag` 后同样 `deploy-baota.sh`（保留现网 `.env.production`）。

---

## 9. 联调检查表

- [ ] 嵌入页 HTTP 200
- [ ] 带真实 `assessment_id` / `user_id` / `token` 能拉到历史
- [ ] 发送问题有流式或整段回复
- [ ] 错误 token 出现 `jnao-embed-error` 或横幅提示
- [ ] 宿主监听 `jnao-embed-close` / `jnao-embed-cite`（若需要）

---

## 10. 常见问题

**Q：对方一定要前端代码才能嵌吗？**  
A：不必。iframe + 参数即可。源码仅作 UI/协议参考。

**Q：token 放在 query 安全吗？**  
A：嵌入页读入后会 `replaceState` 清掉地址栏；仍建议短时 token，并由宿主后端签发，避免进前端仓库与长期日志。

**Q：引用章节点了没反应？**  
A：嵌入页通过 `jnao-embed-cite` 通知宿主；宿主报告页自行滚动到对应区块。
