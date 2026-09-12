# 前端对接 API 契约

> **读者**：重构前端的外部团队（**无需本仓库源码**）。  
> **约定**：本系统后端 HTTP 契约保持不变；前端可任意重写。  
> **范围**：现网产品前端实际使用的接口（含管理后台）。开发专用 `/api/dev/*` 仅附录说明。  
> **上游外呼**（豆包/百炼等）由后端完成，前端只调本契约；见同目录《外部接入与上游API》（若有）。  
> **版本基准**：JNAO API约 `0.3.0` · 整理日期 2026-09-03

---

## 1. 接入总则

### 1.1 Base URL

| 环境 | 建议 |
|------|------|
| 开发 | 前端同源请求 `/api/...`，由网关/开发服务器反代到后端（常见 `127.0.0.1:8012`） |
| 生产 | 同域反代 `/api`，或绝对 API 域名；须开启 CORS 且允许携带 Cookie |

### 1.2 鉴权（必读）

| 机制 | 说明 |
|------|------|
| Cookie（主路径） | 学生/家长：`jnao_session`；管理员：`jnao_admin_session`。HttpOnly，`Path=/`，默认 `SameSite=Lax`，生产 `Secure`，约 7 天 |
| Query `user_id` | **绝大多数业务接口必传**：当前登录用户数字 ID（学生/家长/管理员） |
| Header `X-Child-User-Id` | 与 `user_id` 等价备选 |
| Header `X-Session-Token` | 无 Cookie 场景备用；**生产默认不在登录 JSON 里回传** `session_token` |
| Header `X-Device-Id` | 短信/登录风控（可选） |
| Header `X-Request-Id` | 可选；响应会回写 |

**请求必须** `credentials: 'include'`（或等价携带 Cookie）。

| 标签 | 含义 |
|------|------|
| **none** | 无需登录 |
| **student** | 已登录学生（`role=student`，且已绑定家长） |
| **parent** | 已登录家长 |
| **admin** | 已登录管理员（读 `jnao_admin_session`） |
| **user** | 任意有效会话 |

登录成功：`Set-Cookie` 写入对应 cookie，并清理另一角色 cookie。登出：吊销会话并删除 cookie。

### 1.3 CORS

- `Access-Control-Allow-Credentials: true`
- Origin 白名单由服务端 `CORS_ORIGINS` 配置
- 允许方法：`GET, POST, PUT, DELETE, OPTIONS`
- 允许头：`Content-Type`, `X-Child-User-Id`, `X-Session-Token`, `X-Device-Id`, `X-Request-Id`

### 1.4 错误形态

```json
{ "detail": "中文短句或校验错误数组" }
```

| HTTP | 含义 |
|------|------|
| 401 | 未登录 / 会话失效 / 顶号 |
| 403 | 角色不符、学生未绑家长等 |
| 404 | 资源不存在 |
| 409 | 冲突 |
| 422 | 参数校验失败 |
| 429 | 限流 / 发码过频 |
| 500/502/503 | 服务或上游异常 |

### 1.5 SSE 流式格式

`Content-Type: text/event-stream`

```text
data: {"type":"token","content":"..."}\n\n
data: {"type":"done", ...}\n\n
data: {"type":"error","message":"..."}\n\n
data: [DONE]\n\n
```

### 1.6 登录成功共用体 `AuthResponse`

| 字段 | 类型 | 说明 |
|------|------|------|
| `child_user_id` | int | **后续业务 `user_id` 用此值**（家长登录时亦为家长账户 id） |
| `role` | string | `student` \| `parent` \| `admin` |
| `nickname` | string | |
| `parent_phone` | string\|null | |
| `login_name` | string\|null | 学生账号名 |
| `session_token` | string\|null | 生产常为 null，依赖 Cookie |
| `profile_complete` | bool | |
| `missing_fields` | string[] | |
| `account_ready` / `gate_passed` / `next_step` | — | 家长引导态 |
| `login_channel` | string | |
| `bind_ticket` | string\|null | 微信绑手机流程 |
| `must_change_password` | bool | |

---

## 2. 基础设施

### `GET /api/ping` — none

**响应：** `{ ok, boot_id, force_relogin_on_boot, maintenance, maintenance_message, force_logout }`

### `GET /api/meta/version` — none

**响应：** `{ version, build_id, boot_id, force_relogin_on_boot, maintenance, maintenance_message, force_logout }`

用于发版热更新、维护遮罩、开发态进程重启强制重登。

---

## 3. 认证 `/api/auth`

### `GET /api/auth/captcha` — none

**响应：** `{ captcha_id, image_base64, image_format, expires_in }`

### `POST /api/auth/parent/phone-check` — none

**Body：** `phone`, `captcha_id`, `captcha_code`  
**响应：** `{ ok, message }`（防枚举，不暴露是否已注册）

### `POST /api/auth/sms/send` — none

**Body：** `phone`；`scene`=`login|register|bind`；`captcha_id?`, `captcha_code?`, `device_id?`  
**响应：** `{ ok, sent, message, hint?, expires_in, resend_after, debug_code? }`

### `POST /api/auth/sms/login` — none → Set-Cookie

**Body：** `phone`, `sms_code`；`device_id?` → **AuthResponse**（家长）

### `POST /api/auth/sms/register` — none → Set-Cookie

**Body：** `phone`, `sms_code`, `real_name`, `nickname`, `password`(≥8)；`device_id?`, `bind_ticket?` → **AuthResponse**

### `POST /api/auth/login` — none → Set-Cookie

| 角色 | Body |
|------|------|
| 家长 | `parent_phone`, `password`，建议 `role=parent` |
| 学生 | `login_name`, `password` |

→ **AuthResponse**。学生未绑家长 → **403**。

### `POST /api/auth/logout` — user

Query：`user_id` → `{ ok: true }` + 清 Cookie

### `GET /api/auth/siblings` — student

**响应：** `{ siblings: [{id, nickname, login_name, talent, account_status}], current: {id, nickname, login_name} }`

### `POST /api/auth/switch-child` — student → Set-Cookie

Query：`target_child_id`（必填）→ **AuthResponse**（切换后的孩子会话）

### 微信

| 方法 | 路径 | Auth | 说明 |
|------|------|------|------|
| GET | `/api/auth/wechat/config` | none | `{ configured, app_id?, bind_mobile_url?, ... }` |
| GET | `/api/auth/wechat/oauth-url` | none | Query `redirect?` → `{ url, configured }` |
| GET | `/api/auth/wechat/exchange` | none | Query `login_ticket` → AuthResponse + Cookie |
| GET | `/api/auth/wechat/callback` | none | **302** 回前端，非 JSON |
| POST | `/api/auth/wechat/send-bind-sms` | none | Body: `bind_ticket`, `phone` |
| POST | `/api/auth/wechat/bind-phone` | none | Body: `bind_ticket`, `phone`, `sms_code` → AuthResponse |
| POST | `/api/auth/wechat/complete-external-bind` | none | Body: `bind_ticket` → AuthResponse |

> 遗留 `POST /api/auth/register` 生产默认关闭；家长请用短信注册。

---

## 4. 家长 `/api/parent` — Auth: parent

`user_id` = 家长 ID。

| 方法 | 路径 | 入参 | 响应要点 |
|------|------|------|----------|
| GET | `/profile` | — | 资料：`id, parent_phone, nickname, real_name?, has_password, profile_complete, missing_fields, account_ready, next_step, ...` |
| PUT | `/profile` | `nickname?`, `real_name?`, `password?`, `old_password?` | 同上；改密可能刷新 Cookie |
| GET | `/quota` | — | `{ limit, used, remaining, can_add }` |
| GET | `/children` | — | `{ children: [{id, login_name?, nickname, talent?, training_days, checkins, grade?, age?, region?}] }` |
| POST | `/children` | `login_name`, `nickname`, `password`(≥8)；`grade?`, `age?`, `region?` | 单个 child 摘要 |
| PUT | `/children/{child_id}` | 可选 nickname/password/grade/age/region | 摘要 |
| DELETE | `/children/{child_id}` | — | `{ ok: true }` |

---

## 5. 用户资料 `/api/user` — Auth: student

| 方法 | 路径 | 入参 | 响应要点 |
|------|------|------|----------|
| GET | `/profile` | — | `child_user_id, nickname, jnao_uid, profile_json, training_level, 天赋相关字段...` |
| PUT | `/profile` | `nickname?`, `jnao_uid?`, `profile_json?`, `training_level?` | 同 GET |
| PUT | `/learner-profile` | `age?`, `grade?`, `school_stage?`(`primary_low\|primary_high\|junior\|senior`), `subject_pref?` | 同 profile |
| POST | `/talent/resolve-conflict` | `action`=`keep_old\|use_new` | `{ action, talent_primary, plans_reset }` |

`profile_json` 为扩展对象，前端按已有字段读写即可，勿假设全部键稳定。

---

## 6. 首页引导 `/api/guide` — Auth: student

| 方法 | 路径 | 入参 | 响应要点 |
|------|------|------|----------|
| GET | `/session` | — | `{ session_id, messages[] }` |
| GET | `/sessions` | — | `{ items: [{id, title, message_count, updated_at?, created_at?}] }` |
| GET | `/sessions/{id}` | — | `{ session_id, title, messages }` |
| DELETE | `/sessions/{id}` | — | `{ ok: true }` |
| POST | `/bootstrap` | `{ force?: false, use_llm?: true }` | 欢迎语、`situation`, `next_action`, `actions?` 等 |
| POST | `/clear` | — | `{ cleared }` |
| POST | `/confirm` | `{ write_op, args? }` | 受控写确认 |
| POST | `/chat` | `{ message` (1–4000), `session_id? }` | `{ session_id, reply, actions[], situation?, next_action?, tools_used?, blocks? }` |
| POST | `/chat/stream` | 同 chat | **SSE**（§1.5） |

`actions` 常见：`{ type: "navigate"|"confirm_write", target?, label?, ... }`，由前端执行跳转/弹窗。

---

## 7. 学科答疑 `/api/qa` + 语音 — Auth: student

| 方法 | 路径 | 入参 | 响应要点 |
|------|------|------|----------|
| GET | `/sessions` | — | `{ items: [{id, title, subject, created_at?}] }` |
| POST | `/sessions` | `{ subject? }` | `{ id, subject }` |
| GET | `/sessions/{id}` | — | `{ session_id, messages }` |
| DELETE | `/sessions/{id}` | — | `{ ok: true }` |
| POST | `/chat` | `{ message, session_id?, subject?, image_id?, use_rag? }` | `{ session_id, reply, ... }` |
| POST | `/chat/stream` | 同 chat | **SSE** |
| POST | `/upload-image` | **multipart** 字段 `file` | `{ image_id, url }` |
| GET | `/images/{image_id}` | Query 带 `user_id` | **图片二进制**（非 JSON） |

### `POST /api/voice/asr` — student，multipart

字段 `audio` → `{ text }` 或 `{ error }`。未开通语音时可能返回错误文案。  
`POST /api/voice/tts` 当前 **501**，勿依赖。

---

## 8. 天赋测评 `/api/talent` — Auth: student

| 方法 | 路径 | 入参 | 响应要点 |
|------|------|------|----------|
| POST | `/report` | `answer`（35 位 0/1 串）, `uid`, `type`(0 成人/1 孩子) | `{ code:1, data, assessment_id, talent_conflict?, ... }`；失败常见 502 |
| GET | `/assessment/history` | `limit?` | `{ items: [{id, talent_primary, talent_tag, assessed_at?}] }` |
| GET | `/assessment/latest` | — | 最新测评摘要；无则 404 |
| GET | `/assessment/{id}` | — | `{ code:1, data, assessment_id, talent_primary, ... }` |
| DELETE | `/assessment/{id}` | — | `{ deleted, assessment_id }` |

`data` 为测评报告大对象（上游结构），前端按现有报告页字段消费。

---

## 9. 今日训练 `/api/training` — Auth: student（另有注明）

### 9.1 今日方案核心字段（`TrainingTodayResponse` 摘要）

- `plan_id`, `plan_date`, `status`, `report_text?`
- `items[]`：`id, title, audio_url, video_url, duration_min, checkin_status, watch_progress, ...`
- `overall_tier`, `day_locked`, `planned_minutes`, `media_exhausted`, `can_customize_plan`
- `optional_offers[]` 等

`audio_url` / `video_url` 常为带签名的 **stream** 路径，供 `<audio>`/`<video>` 直接播放（支持 Range）。

### 9.2 接口表

| 方法 | 路径 | 入参 | 说明 |
|------|------|------|------|
| GET | `/entry` | — | 进页状态（是否需测评、日锁、天赋冲突等） |
| GET | `/today` | `plan_date?`, `skip_ai?=0\|1` | 今日训练方案 |
| POST | `/schedule` | Body `{ planned_minutes }`（约 20–480） | 按分钟生成/调整方案 |
| GET | `/report/today` | `force?=0\|1` | 刷新今日报告文案 |
| POST | `/plan/customize` | `{ plan_id, skills: string[] }` | 自定义技能 |
| POST | `/plan/media-exhausted` | `{ plan_date? }` | 标记媒体耗尽 |
| POST | `/plan/elective-toggle` | `{ plan_id, skill, action: add\|remove }` | 选修开关 |
| GET | `/progress` | — | 进度摘要 |
| POST | `/checkin` | `{ plan_id, item_id?, content?, result?, note?, time_spent?, cards?, ... }` | 打卡 → `{ record_id, plan_status, ... }` |
| GET | `/checkin/today` | `plan_date?` | 今日打卡列表 |
| PUT | `/checkin/{id}` | 可更新字段 | 改打卡 |
| DELETE | `/checkin/{id}` | — | 删打卡 |
| GET | `/history` | `limit?`, `exclude_today?` | 历史 |
| GET | `/elective/list` | `planned_minutes?`, `overall_tier?` | 选修列表（**当前无学生鉴权**） |
| POST | `/elective` | `{ plan_id, skill, cards? }` | 选修打卡 |
| POST | `/window` | `{ start_time, end_time }`（`HH:MM`） | 设置时段 |
| DELETE | `/window` | — | 清除时段 |
| POST | `/items/{item_id}/watch-progress` | `{ watched_sec, duration_sec?, media? }` | 观看进度 |
| GET | `/video/talent` | — | 天赋视频元数据（Auth: user） |
| GET | `/video/talent/stream` | — | **视频流** |
| GET | `/items/{item_id}/stream` | `media=audio\|video`，及签名参数 | **音/视频流** |

---

## 10. 成长 `/api/growth` — Auth: student

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/badges` | `{ items: [{name, icon, cond, earned, ...}] }` |
| GET | `/timeline` | 成长时间线 |
| GET | `/calendar` | 日历打点 |
| GET | `/tier` | 段位：`overall_tier`/`level`（同一）、`duan_label`、`honor_level`、`title`、`skills[]`… |
| GET | `/console` | **中央电脑**一页汇总：`tier`、`xp`、`lcd`、`locks`、`ladder`（本机榜）；`skills_wall` 第一期为 `null` |
| GET | `/summary` | 汇总卡片数据 |
| GET | `/milestones` | 里程碑 |
| GET | `/share` | `{ title, text, highlights[] }` |
| GET | `/academic-plan` | 学业规划报告；Query `refresh=true` 强制重新生成 AI 文案 |

学业规划响应摘要：`generated_at`, `student`, `score_projection`, `goal_stages`, `report_content`, `sections`, `ai_generated`。首次生成可能较慢（数十秒），宜做加载态；结果有服务端缓存。

---

## 11. 管理后台 `/api/admin`

| 方法 | 路径 | Auth | 说明 |
|------|------|------|------|
| POST | `/login` | none | Body `login_name`, `password` → AuthResponse + **admin Cookie** |
| POST | `/logout` | admin | `{ ok: true }` |
| GET/PUT | `/settings` | admin | 登录设备数策略等 |
| GET/POST | `/parents` | admin | 列表 / 创建 |
| GET | `/parents/removed` | admin | 已删家长 |
| PUT/DELETE | `/parents/{id}` | admin | 更新 / 删除 |
| POST | `/parents/{id}/restore` | admin | 恢复 |
| POST | `/parents/restore-by-phone` | admin | 按手机恢复 |
| GET | `/parents/{id}/detail` | admin | 详情（含孩子、会话等） |
| POST | `/parents/{id}/reconcile` | admin | 对账修复 |
| GET/POST | `/children` | admin | 列表 / 创建 |
| PUT/DELETE | `/children/{id}` | admin | 更新 / 删除 |
| POST | `/children/{id}/restore` | admin | 恢复 |
| POST/DELETE | `/children/{id}/bind` | admin | 绑定/解绑家长 |
| GET | `/children/{id}/detail` | admin | 孩子详情 |
| GET/PUT | `/children/{id}/talent-quota` | admin | 测评额度 |
| POST | `/children/talent-quota/batch` | admin | 批量额度 |
| GET | `/children/{id}/talent-assessments` | admin | 测评列表 |
| GET | `/blacklist` | admin | 黑名单 |
| DELETE | `/blacklist/{kind}/{value}` | admin | 移除 |

管理端 `user_id` 传**管理员** id，Cookie 用 `jnao_admin_session`。

---

## 12. 不在生产前端范围

| 路径 | 说明 |
|------|------|
| `/api/dev/*` | 仅 `JNAO_DEV_MODE=1`；重置训练/模拟日切等 |
| `/api/guide/debug*` | 调试探测；生产默认关闭 |
| `/docs` OpenAPI | 仅调试开关开启时可用 |

---

## 13. 对接检查清单（给前端负责人）

1. 所有 API 请求携带 Cookie（`credentials: 'include'`），业务 URL 带 `user_id=`。  
2. 登录后持久化 `AuthResponse.child_user_id` 作为当前身份 id。  
3. **不要**依赖响应里的 `session_token`（生产常为空）。  
4. 学生/家长与管理员会话隔离（两套 Cookie）。  
5. 训练媒体用返回的 stream URL 播放，勿自拼无签名地址。  
6. Guide/QA 流式按 SSE `token` / `done` / `error` 解析。  
7. 轮询或进页读取 `/api/meta/version`，处理 `maintenance` / `force_logout` / `boot_id`。  
8. 跨域时确保前端 Origin 已加入服务端 CORS 白名单。

---

## 14. 联调联系方式 / 环境（由交付方填写）

| 项 | 值 |
|----|-----|
| API Base（测试） | _待填_ |
| API Base（生产） | _待填_ |
| CORS 已放行 Origin | _待填_ |
| 测试学生账号 | _待填_ |
| 测试家长手机号 | _待填_ |
| 管理员账号 | _待填_ |
| 接口变更联系人 | _待填_ |

字段以联调环境实际响应为准；标为扩展/大对象的结构勿写死全部键名。若契约变更，应由后端提供变更说明与兼容窗口。
