# 前端-后端 API 文档

> 最后更新：2026-07-02
> 按前端页面编排，请求/响应格式 + 后端业务逻辑
> **API 覆盖率：45/45 前端核心调用 + 家长端 9 个端点 + 训练 v2.0 新增端点**

---

## 目录

1. [全局约定](#全局约定)
2. [用户注册引导 (onboarding)](#用户注册引导-onboarding)
3. [首页引导对话](#首页引导对话)
4. [天赋测试](#天赋测试)
5. [天赋报告](#天赋报告)
6. [今日训练](#今日训练)
7. [学科答疑](#学科答疑)
8. [成长里程碑](#成长里程碑)
9. [语音服务](#语音服务)
10. [开发者工具](#开发者工具)

---

## 全局约定

| 项 | 值 |
|---|---|
| 后端地址 | `http://127.0.0.1:8012` |
| 用户标识 | Query `?user_id=` 或 Header `X-Child-User-Id` |
| 数据库 | SQLite（开发）/ MySQL（生产） |
| AI 模型 | 火山引擎豆包 `doubao-seed-1-6-250615` |
| 内容目录 | `docs/data/xet_*.json` → 启动时自动灌入 `content_item` 表（511 条） |

---

## 用户注册引导 (onboarding)

**前端页面**: `vue_fronted/src/pages/login/onboarding/index.vue`
**后端 API**: `app/api/auth.py`、`app/api/user.py`

### 流程图

```
孩子登录 → 未完成 onboarding？→ 完善信息页
  Step1 选新/老学员
  Step2 开始天赋测试（新/老统一，不再自选五者）
    → 天赋测试页 → 报告页
    → 新学员：报告后进入首页（onboarding 完成）
    → 老学员：报告后回到 Step4 补录训练历史 → Step100 → 首页
```

**说明**：孩子账号由家长分配，注册环节不再进入 onboarding；信息填写在**首次登录后**进行。

### API 列表

#### 注册

```
POST /api/auth/register
```

| 参数 | 类型 | 说明 |
|------|------|------|
| parent_phone | string | 家长手机号 |
| nickname | string | 昵称 |

**响应**:
```json
{
  "child_user_id": 1,
  "nickname": "小明",
  "parent_phone": "13900000001"
}
```

**后端工作**: `auth_service.register_child()` → INSERT `child_user` → 返回 user_id

#### 登录

```
POST /api/auth/login
```

| 参数 | 类型 | 说明 |
|------|------|------|
| parent_phone | string | 家长手机号 |
| nickname | string | 昵称 |

**后端工作**: SELECT `child_user` WHERE parent_phone → 不存在返回 404

#### 读取用户信息

```
GET /api/user/profile?user_id={uid}
```

**响应**:
```json
{
  "child_user_id": 1,
  "parent_phone": "13900000001",
  "nickname": "小明",
  "profile_json": { "onboarding": { ... } },
  "training_level": "初级",
  "talent_code": 1
}
```

#### 保存引导信息（核心）

```
PUT /api/user/profile
```

| 参数 | 类型 | 说明 |
|------|------|------|
| profile_json | object | 含 `onboarding` 字段的 JSON blob |
| nickname | string | 可选，更新昵称 |
| training_level | string | 可选，训练等级 |

**`profile_json.onboarding` 完整结构**:
```json
{
  "student_type": "returning",
  "completed_at": "2026-06-29T10:00:00.000Z",

  "self_reported_talent": "学者",
  "self_reported_talent_code": 1,
  "talent_unknown": false,

  "first_training_date": "2025年3月",
  "total_training_sessions": 120,

  "prior_abilities": ["超脑阅读", "影像追忆"],
  "prior_training_data": {
    "超脑阅读": {
      "firstDate": "2025年3月",
      "totalCount": 30,
      "lastTime": "20",
      "lastResult": "85",
      "note": "中途停过两个月"
    }
  }
}
```

**字段详解**:

| 字段 | 类型 | 步骤 | 校验规则 |
|------|------|------|----------|
| `student_type` | string | Step 1 | `"new"` / `"returning"` |
| `self_reported_talent` | string | Step 2（已废弃自选） | 现统一走天赋测评，不再自选五者 |
| `self_reported_talent_code` | int | — | 由测评结果写入 `child_user.talent_code` |
| `talent_unknown` | bool | Step 2 | 恒为 true（待测评） |
| `talent_test_done` | bool | 测评后 | 天赋测试已完成 |
| `first_training_date` | string\|null | Step 4 | 全局初次训练日期（年月选择器，如 "2025年3月"），可空 |
| `total_training_sessions` | int\|null | Step 4 | 全局训练总次数（纯数字，`parseInt` 转换），可空 |
| `prior_abilities` | string[] | Step 4 | 做过的训练项目名（12 选多） |
| `prior_training_data` | object | Step 5+ | key=项目名，value=该项目详情；所有字段可空 |

**`prior_training_data.<项目>` 字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `firstDate` | string | 该项目第一次打卡时间（年月选择器） |
| `totalCount` | int | 该项目打卡次数（纯数字） |
| `lastTime` | string | 最近一次时长（分钟） |
| `lastResult` | string | 最近一次正确率（%） |
| `note` | string | 备注，自由文本 |

**前端校验规则**:
- Step 2：点击「开始天赋测试」进入测评（新/老学员相同）
- Step 4：至少选 1 个训练项目，否则 toast "请至少选择一项"
- Step 5+：所有字段选填，可跳过，可留空

**保存时机**:
| 时机 | 触发函数 | 保存内容 |
|------|----------|----------|
| Step 2 进入天赋测试前 | `startTalentTest()` → `persistOnboarding()` | 学员类型 + `talent_unknown:true` |
| 天赋报告返回（新学员） | `report/goBack` | `talent_test_done` + `completed_at` |
| 天赋报告返回（老学员） | `report/goBack` | `talent_test_done`，跳转 resume Step 4 |
| Step 100 "开始训练" | `goHome()` → `persistOnboarding({finalize})` | 完整 JSON（老学员含训练历史） |

**后端工作**:
1. `user_service.update_profile()` → 写入 `child_user.profile_json` 字段（JSON blob，不解析内部结构）
2. `sync_child_user_talent()` → 从 `onboarding.self_reported_talent_code` 同步到 `child_user.talent_code` + `child_user.training_level`
   - 优先级：JNAO 测评 > 自选天赋 > 无
   - `talent_unknown: true` 时跳过自选天赋

> **注意**: Step 4 和 Step 5+ **不发后端请求**，纯前端本地状态。Step 3 已保存天赋，Step 100 保存全量覆盖更新。

#### 更新学员档案

```
PUT /api/user/learner-profile
```

| 参数 | 类型 | 说明 |
|------|------|------|
| age | int | 年龄 (5-25) |
| grade | string | 年级 |
| school_stage | string | 学段：primary_low / primary_high / junior / senior |
| subject_pref | string | 学科偏好 |

---

## 首页引导对话

**前端**: `vue_fronted/src/pages/index.vue`
**后端**: `app/api/guide.py`、`app/api/chat.py`

```
POST /api/guide/chat?user_id={uid}
{ "message": "你好" }
→ { "reply": "你好！我是张宇老师..." }

GET  /api/guide/session?user_id={uid}
→ { "messages": [...] }

GET  /api/guide/debug
→ 显示豆包原始回复（仅开发环境）

POST /api/chat       # 通用对话（不含引导人设）
POST /api/chat/stream # SSE 流式对话
```

**后端工作**: 调用豆包 LLM → 引导人设注入（张宇老师） → 返回回复。**当前为静态人设**；读用户画像做个性化引导为预留能力（见 [数据闭环与预留说明.md](数据闭环与预留说明.md)）。

---

## 天赋测试

**前端**: `vue_fronted/src/pages/talent/index.vue`
**后端**: `app/api/talent.py`

### 提交流程（一步完成）

```
POST /api/talent/report
```

| 参数 | 类型 | 说明 |
|------|------|------|
| answer | string | 35 位 "1"/"0" 答案串 |
| uid | int | JNAO 用户 ID |
| type | int | 0=成人 1=儿童 |
| child_user_id | int | **必传**，否则不落库 |

**响应**:
```json
{
  "code": 1,
  "data": { "talent": "学者", "check_talent": "学者", ... },
  "assessment_id": 1,
  "talent_conflict": false,
  "talent_locked": false,
  "lock_message": null
}
```

**后端工作**:
1. `jnao_submit(answer, uid, type)` → 提交到 m.jnao.com
2. `jnao_get_report(record_id)` → 获取 JNAO 报告 JSON
3. `save_assessment()` → INSERT `talent_assessment`，补全 `talent_code`
4. 冲突检测：新测评天赋 ≠ 已存天赋 → `talent_conflict: true`
5. 锁定检测：已确认天赋不可覆盖 → `talent_locked: true`

### 其他接口

```
POST /api/talent/assessment              # 仅落库（不返回报告）
GET  /api/talent/assessment/latest       # 最新测评
GET  /api/talent/assessment/history      # 历史列表
GET  /api/talent/assessment/{id}         # 指定测评详情
DELETE /api/talent/assessment/{id}        # 删除 → 归档到 archive 表
POST /api/user/talent/resolve-conflict   # { action: "keep_old" | "use_new" }
```

---

## 天赋报告

**前端**: `vue_fronted/src/pages/report/index.vue`
**后端**: `app/api/talent.py`

```
GET /api/talent/assessment/{assessment_id}?user_id={uid}
```

报告页支持三个特殊状态（由 assessment 落库时计算）：
- **迷者警告** (`isMizhe`): talent === "迷者" → 橙色卡片 + 重新测试按钮
- **天赋冲突** (`talentConflict`): 新测评与已存天赋不同 → 保留/使用 二选一弹窗
- **天赋锁定** (`talentLocked`): 天赋已确认 → 锁定提示

---

## 今日训练（v2.0）

**前端**: `vue_fronted/src/pages/training/index.vue`
**后端**: `app/api/training.py`
**核心引擎**: `training_formula_engine.py` + `training_mastery.py` + `child_training_state.py`

### API 列表

| 方法 | 路径 | 说明 | v2.0 |
|------|------|------|:--:|
| GET | `/api/training/entry` | 训练入口：校验天赋 + 检查方案 | 🟡 |
| POST | `/api/training/schedule` | 选时长 → 公式引擎生成方案 | 🔄 |
| GET | `/api/training/today` | 今日训练方案（含 AI 报告） | 🟡 |
| POST | `/api/training/checkin` | 提交打卡 → Tier 晋级判定 | 🔄 |
| GET | `/api/training/checkin/today` | 今日打卡记录 | 🟢 |
| GET | `/api/training/checkin/{id}` | 单条打卡详情 | 🟢 |
| PUT | `/api/training/checkin/{id}` | 更新打卡卡片 | 🟢 |
| DELETE | `/api/training/checkin/{id}` | 删除打卡（回退晋级） | 🟢 |
| GET | `/api/training/elective/list` | 🆕 可选修技能列表 | 🆕 |
| POST | `/api/training/elective` | 🆕 提交选修打卡 | 🆕 |
| GET | `/api/training/progress` | Tier 晋级进度 + OSS 状态 | 🔄 |
| GET | `/api/training/history` | 历史训练方案 | 🟢 |
| POST | `/api/training/window` | 设置训练时段 | 🟢 |
| GET | `/api/training/window` | 查询当前窗口 | 🟢 |
| DELETE | `/api/training/window` | 删除时段 | 🟢 |
| GET | `/api/training/window/status` | 窗口状态 | 🟢 |
| GET | `/api/training/video/talent` | 天赋训练视频 | 🟢 |
| POST | `/api/training/items/{id}/watch-progress` | 视频进度上报 | 🟢 |
| POST | `/api/training/plan/media-exhausted` | 时长用尽标记 | 🟢 |
| GET | `/api/training/report/today` | 今日 AI 报告 | 🟢 |
| GET | `/api/training/report/{date}` | 指定日报告 | 🟢 |

---
### POST /api/training/schedule

```json
// Request
{ "planned_minutes": 120 }

// Response (v2.0)
{
  "plan_id": 1,
  "plan_date": "2026-07-02",
  "status": "pending",
  "overall_tier": 1,
  "planned_minutes": 120,
  "items": [
    {
      "id": 1,
      "sort_order": 1,
      "title": "学者超脑速读",
      "ability_type": "audio",
      "duration_min": 5,
      "play_url": "https://oss.../xue/学者超脑速读.MP3",
      "instructions": "{\"skill\": \"超脑阅读\", \"item_type\": \"required\", \"blocks_next\": true}",
      "checkin_status": "pending"
    }
  ],
  "report_text": "今天专注阅读速度..."
}
```

---
### POST /api/training/checkin（🆕 v2.0 返回体）

```json
// Request
{
  "plan_id": 1,
  "item_id": 1,
  "cards": [
    { "name": "超脑阅读", "time": "2.5", "wordCount": "900" }
  ]
}

// Response (v2.0)
{
  "record_id": 1,
  "plan_status": "pending",
  "training_progress": {
    "overall_tier": 1,
    "skill_results": {
      "超脑阅读": {
        "tier_before": 1,
        "tier_after": 1,
        "passed": true,
        "consecutive_pass": 1,
        "tier_advanced": false,
        "oss_advanced": false,
        "threshold_detail": {
          "skill": "超脑阅读",
          "tier": 1,
          "rule_type": "wpm",
          "passed": true,
          "wpm": 360.0,
          "required_wpm": 266.7,
          "detail": "达标：2.5分钟900字（360.0字/分 ≥ 266.7字/分）"
        }
      }
    }
  }
}
```

---
### 打卡卡片字段规范

| 技能 | 必填字段 | 可选字段 | 判定方式 |
|------|---------|---------|---------|
| 超脑阅读 | `name`, `time`, `wordCount` | — | wordCount/time ≥ 阈值 |
| 影像追忆 | `name`, `wordCount`, `accuracy` | `time` | wordCount≥阈值 AND accuracy≥阈值 |
| 扫描速记 | `name`, `wordCount`, `time`, `reverseRecite` | — | wordCount/time≥阈值 AND reverseRecite=true |
| 极速运算 | `name`, `completed` | `correctCount`, `totalCount` | completed=true |
| 极速学习 | `name`, `completed` | — | completed=true |

---
### GET /api/training/elective/list

```
Query: planned_minutes=120&overall_tier=1
Response:
{
  "offers": [
    { "skill": "精力恢复", "available": false, "reason": "训练时长未达8小时", "has_checkin": false },
    { "skill": "多元感知", "available": true, "reason": "", "has_checkin": true },
    { "skill": "高效作业", "available": true, "reason": "", "has_checkin": false }
  ]
}
```

---
### GET /api/training/progress（🆕 v2.0）

```json
{
  "overall_tier": 1,
  "skills": {
    "超脑阅读": { "tier": 1, "oss_stage": 0, "oss_part": 0, "consecutive_pass": 2 },
    "影像追忆": { "tier": 1, "oss_stage": 1, "oss_part": 1, "consecutive_pass": 1 },
    "扫描速记": { "tier": 1, "oss_stage": 1, "oss_part": 1, "consecutive_pass": 0 },
    "极速运算": { "tier": 1, "oss_stage": 2, "oss_part": 1, "consecutive_pass": 0 },
    "极速学习": { "tier": 1, "oss_stage": 2, "oss_part": 1, "consecutive_pass": 0 }
  },
  "training_days": 3
}
```

---
### 排课引擎流程（v2.0）

```
POST /api/training/schedule { planned_minutes: 120 }
  1. 读取 child_training_state → 各技能 Tier + OSS stage/part
  2. overall_tier = min(所有技能 tier)
  3. 公式引擎 expand_formula(120, overall_tier, grade_band)
     → ["超脑阅读", "影像追忆", "影像追忆", "扫描速记", "高效作业"]
  4. 遍历 slots → 取各技能当前 OSS (stage,part) 音频
  5. 生成 TrainingItem（required 标记 blocks_next=true, elective 标记 false）
```

### 晋级流程（v2.0）

```
POST /api/training/checkin { cards }
  1. 解析 cards → 提取技能名 + 打卡值
  2. 查 training_tier_thresholds.yaml → 技能Tier×学段→阈值
  3. 比对判定 pass/fail
  4. pass → consecutive_pass += 1; fail → consecutive_pass = 0
  5. consecutive_pass ≥ 3 → 技能 Tier += 1, 计数重置
  6. pass → 推进 OSS stage/part (有则取、无则跳)
  7. overall_tier = min(所有技能 tier)
  8. 返回 per-skill 结果 + overall_tier
```

**核心引擎**: `training_schedule_service.py` + `training_formula_engine.py` + `training_mastery.py` + `child_training_state.py` + `training_day.py`

### 打卡校验（v2.0）

1. `plan_id` 必须属于当前用户
2. `item_id` 必须属于该 plan
3. **顺序校验**：必修技能严格按 sort_order，前一项完成→解锁下一项
4. **选修不阻塞**：item_type=elective 的项跳过不阻塞后续
5. 打卡卡片 → per-skill 判定达标/连续计数/Tier晋级/OSS推进
6. 所有必修项完成 → `training_plan.status = "completed"`

### 状态机（v2.0 重构）

```
child_training_state (profile_json.training_progress)
├── overall_tier: int                   min(所有技能 tier)
├── skills: {
│     "超脑阅读": { tier, oss_stage, oss_part, consecutive_pass },
│     "影像追忆": { tier, oss_stage, oss_part, consecutive_pass },
│     ...
│   }
├── training_days: int                 总训练天数
└── training_day_anchor: date          训练日起始锚点

训练日规则:
- 当日 04:00 ~ 次日 03:59:59 为同一训练日
- 04:00-04:05 为日切冻结窗口
- 昨日未完成 → 今日续推（按技能 carryover）
- 连续3次达标 → 技能 Tier+1
- 不达标 → consecutive_pass 重置为 0
- 整体 Tier = min(所有技能 Tier) ← 最低原则
```

---

## 学科答疑

**前端**: `vue_fronted/src/pages/qa/index.vue`
**后端**: `app/api/qa.py`

```
POST /api/qa/chat               # { message, subject?, image_id? }
GET  /api/qa/sessions           # 列出所有会话
POST /api/qa/sessions           # 新建会话
GET  /api/qa/sessions/{id}      # 会话详情 + 消息列表
DELETE /api/qa/sessions/{id}    # 删除会话（级联删除消息）
POST /api/qa/upload-image       # 拍照上传（multipart）
GET  /api/qa/images/{id}        # 获取已上传图片
POST /api/qa/clear              # 清空当前会话
```

**后端工作（POST /api/qa/chat）**:
1. `detect_subject()` → 自动识别学科（数学/语文/英语）
2. 错频道检测：数学标签问英语题 → 提醒切换学科
3. `fetch_recent_coach_context_for_prompt()` → 读取近期 `meta_json` 中的 `mistake_pattern` / `coach_hint` 注入系统提示
4. `build_qa_system_prompt()` → 天赋 + 学科 + 学段 + 教练上下文
5. RAG 可选；调用豆包 LLM
6. `build_coach_metadata()` → 本轮 `coach_hint` / `mistake_pattern` 写入 assistant 消息的 `meta_json`

`qa_message.voice_url`：预留，当前未使用。

---

## 成长里程碑

**前端**: `vue_fronted/src/pages/growth/index.vue`
**后端**: `app/api/growth.py`

```
GET /api/growth/badges       # 徽章列表（含达成状态）
GET /api/growth/timeline     # 时间线（测评+打卡+答疑事件）
GET /api/growth/milestones   # 里程碑进度（打卡7天等）
GET /api/growth/summary      # 数据总结
GET /api/growth/share        # 分享文案（标题+正文+亮点）
```

---

## 语音服务

**后端**: `app/api/voice.py`

```
POST /api/voice/tts   # { text: string } → 火山引擎 TTS（张宇老师声音）
POST /api/voice/asr   # { audio: base64 } → 火山引擎 ASR 语音识别
```

---

## 开发者工具

**后端**: `app/api/dev.py`

```
POST /api/dev/training/reset-today       # 重置今日方案
POST /api/dev/training/reset-progress    # 重置训练进度
POST /api/dev/training/reset-all         # 清空所有训练数据
POST /api/dev/training/reset-talent      # 清空天赋测评
POST /api/dev/training/next-day          # 模拟进入下一天
POST /api/dev/training/simulate-4am-cutoff  # 模拟凌晨4点截止

GET  /api/dev/training/status            # 开发者状态一览
GET  /api/dev/oss/list                   # OSS 音频列表
```

---

## 家长端

> **已实现**：家长手机号+密码注册/登录；家长中心分配孩子账号；孩子账号+密码登录。短信验证等待后续接入。

### 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                        child_user 统一用户表                  │
├──────────────┬──────────────────────────────────────────────┤
│ role=parent  │ parent_phone(唯一) + password_hash + nickname │
│              │ child_quota — 可分配孩子名额（默认 5，可运营调整）│
├──────────────┼──────────────────────────────────────────────┤
│ role=student │ login_name(唯一) + password_hash + nickname   │
│              │ parent_phone — 冗余家长手机号，便于旧逻辑兼容    │
└──────────────┴──────────────────────────────────────────────┘
                              │
                    parent_child_bind
                    (parent_id ↔ child_id)
```

**登录方式**：

| 角色 | 方式 | 请求体 |
|------|------|--------|
| 家长 | 手机号 + 密码 | `{ parent_phone, password, role: "parent" }` |
| 孩子 | 账号 + 密码 | `{ login_name, password }` |
| 孩子（旧） | 手机号 + 昵称 | `{ parent_phone, nickname }` — 兼容无密码历史用户 |

**流程**：

```
家长注册(register-parent) → POST /api/auth/register role=parent
  → 家长中心 /pages/parent/index
  → 添加孩子 POST /api/parent/children { login_name, nickname, password }
  → 孩子登录 login/index 选「学生」+ 账号密码 → 学生首页
```

### 前端页面

| 页面 | 文件 | 后端 |
|------|------|:--:|
| 登录（角色+密码/旧手机号） | `login/index.vue` | ✅ |
| 孩子账号说明 | `login/register.vue` | — |
| 家长注册 | `login/register-parent.vue` | ✅ |
| 家长中心（孩子管理） | `parent/index.vue` | ✅ |

### 数据存储

迁移脚本：`backend/migrations/009_parent_auth.sql`（`migrate.py` 幂等补丁）

```sql
-- child_user 扩展
password_hash   VARCHAR(128)   -- bcrypt
role            VARCHAR(10)    -- student | parent
login_name      VARCHAR(50)    -- 孩子登录账号，全局唯一
child_quota     INT            -- 仅家长：可分配名额，NULL=默认 5

-- 家长-孩子多对多绑定（当前业务为一对多）
parent_child_bind (parent_id, child_id, created_at)
```

### 认证 API

#### 注册 `POST /api/auth/register`

| 参数 | 类型 | 说明 |
|------|------|------|
| parent_phone | string | 家长手机号 |
| nickname | string | 昵称/姓名 |
| password | string | ≥6 位；家长必填 |
| role | string | `parent` / `student`（默认 student） |
| login_name | string | 可选，学生自助注册时 |

**家长响应**：`{ child_user_id, parent_phone, nickname, role: "parent" }`

#### 登录 `POST /api/auth/login`

见上表三种方式。响应增加 `role`、`login_name` 字段。

### 家长 API

```
GET  /api/parent/quota?user_id={parent_id}
→ { limit, used, remaining, can_add }    # 名额查询（预留运营调价入口）

GET  /api/parent/children?user_id={parent_id}
→ { children: [{ id, login_name, nickname, talent, training_days, checkins, grade }] }

POST /api/parent/children?user_id={parent_id}
← { login_name, nickname, password }
→ 新建孩子并自动绑定

PUT  /api/parent/children/{child_id}?user_id={parent_id}
← { nickname?, password? }

DELETE /api/parent/children/{child_id}?user_id={parent_id}
→ 解除绑定（不删孩子训练数据）

GET  /api/parent/children/{child_id}/summary?user_id={parent_id}   # 预留
→ { id, login_name, nickname, talent, training_days, checkins, grade, school_stage }
```

### 预留能力

| 能力 | 状态 | 说明 |
|------|------|------|
| 短信验证码注册/登录 | 待接入 | 前端可增验证码输入框，后端增 `/api/auth/sms/send` + 校验 |
| 孩子名额条件发放 | 接口已留 | `child_quota` 字段 + `GET /api/parent/quota`；运营后台可改 quota |
| 家长查看孩子详情 | 接口已留 | `GET .../summary`，可扩展最近训练、测评摘要 |
| JWT / Session | 待接入 | 当前仍 `user_id` Query 鉴权，与全站一致 |

### 前端 API（userApi.js）

| 函数 | 路径 |
|------|------|
| `registerParent` | POST `/api/auth/register` |
| `loginParent` | POST `/api/auth/login` |
| `loginStudent` | POST `/api/auth/login` |
| `fetchParentChildren` | GET `/api/parent/children` |
| `fetchParentQuota` | GET `/api/parent/quota` |
| `createParentChild` | POST `/api/parent/children` |
| `updateParentChild` | PUT `/api/parent/children/{id}` |
| `deleteParentChild` | DELETE `/api/parent/children/{id}` |
| `fetchChildSummary` | GET `/api/parent/children/{id}/summary` |

---

## 老学员注册全链路（总结）

```
Step 1  选"老学员"         → 前端本地
Step 2  开始天赋测试        → 天赋测试 → 报告 → 回到 Step 4
Step 4  全局数据+选项目     → 纯前端本地
Step 5+ 逐项填详情          → 纯前端本地
Step 100 "开始训练"         → PUT /api/user/profile  保存完整 JSON blob
                              redirect → 首页 → GET /api/training/entry
```

## 新学员全链路

```
Step 1  选"新学员"
Step 2  开始天赋测试 → 报告 → 首页（onboarding 完成）
```

### onboarding JSON schema（给后端看）

```
PUT /api/user/profile  { profile_json: { onboarding: { ... } } }

onboarding:
├── student_type:           "new" | "returning"
├── completed_at:           ISO 8601
├── self_reported_talent:   "学者"|"思者"|"行者"|"德者"|"赢者"    ← 老学员必填
├── self_reported_talent_code: 1|2|3|4|5
├── talent_unknown:         false                   ← 老学员恒 false
├── first_training_date:    "2025年3月" | null      ← Step 4 全局
├── total_training_sessions: 120 | null             ← Step 4 全局
├── prior_abilities:        ["超脑阅读", ...]        ← Step 4
└── prior_training_data: {                          ← Step 5+
      "<项目名>": {
        firstDate, totalCount, lastTime, lastResult, note
        # 全部可选，空值传空字符串
      }
    }
```

**后端只管存 JSON blob**，不解析 `prior_training_data` 内部字段。唯一提取的是 `self_reported_talent_code` 用于同步到 `child_user` 顶层。

---

## 附录：完整 API 对照表

> 2026-06-30 全量扫描：前端 45 个 API 调用 ↔ 后端 45 个端点，零缺口。

### 前端 userApi.js → 后端 对照

| 前端函数 | 方法 | 路径 | 状态 |
|----------|------|------|:--:|
| `loginUser` | POST | `/api/auth/login` | ✅ |
| `registerChild` | POST | `/api/auth/register` | ✅ |
| `fetchProfile` | GET | `/api/user/profile` | ✅ |
| `saveProfile` | PUT | `/api/user/profile` | ✅ |
| `updateLearnerProfile` | PUT | `/api/user/learner-profile` | ✅ |
| `submitTalentReport` | POST | `/api/talent/report` | ✅ |
| `fetchLatestAssessment` | GET | `/api/talent/assessment/latest` | ✅ |
| `fetchAssessmentHistory` | GET | `/api/talent/assessment/history` | ✅ |
| `fetchAssessmentReport` | GET | `/api/talent/assessment/{id}` | ✅ |
| `deleteAssessmentReport` | DELETE | `/api/talent/assessment/{id}` | ✅ |
| `resolveTalentConflict` | POST | `/api/user/talent/resolve-conflict` | ✅ |
| `fetchTrainingEntry` | GET | `/api/training/entry` | ✅ |
| `fetchTrainingToday` | GET | `/api/training/today` | ✅ |
| `scheduleTrainingPlan` | POST | `/api/training/schedule` | ✅ |
| `submitTrainingCheckin` | POST | `/api/training/checkin` | ✅ |
| `fetchTodayCheckins` | GET | `/api/training/checkin/today` | ✅ |
| `updateTrainingCheckin` | PUT | `/api/training/checkin/{id}` | ✅ |
| `deleteTrainingCheckin` | DELETE | `/api/training/checkin/{id}` | ✅ |
| `fetchTrainingHistory` | GET | `/api/training/history` | ✅ |
| `fetchTrainingProgress` | GET | `/api/training/progress` | ✅ |
| `refreshTrainingReport` | GET | `/api/training/report/today` | ✅ |
| `fetchTalentTrainingVideo` | GET | `/api/training/video/talent` | ✅ |
| `postTrainingWatchProgress` | POST | `/api/training/items/{id}/watch-progress` | ✅ |
| `sendGuideMessage` | POST | `/api/guide/chat` | ✅ |
| `fetchGuideSession` | GET | `/api/guide/session` | ✅ |
| `clearGuideSession` | POST | `/api/guide/clear` | ✅ |
| `sendQaMessage` | POST | `/api/qa/chat` | ✅ |
| `fetchQaSessions` | GET | `/api/qa/sessions` | ✅ |
| `createQaSession` | POST | `/api/qa/sessions` | ✅ |
| `deleteQaSession` | DELETE | `/api/qa/sessions/{id}` | ✅ |
| `fetchQaSession` | GET | `/api/qa/sessions/{id}` | ✅ |
| `uploadQaImage` | POST | `/api/qa/upload-image` | ✅ |
| `fetchGrowthBadges` | GET | `/api/growth/badges` | ✅ |
| `fetchGrowthTimeline` | GET | `/api/growth/timeline` | ✅ |
| `fetchGrowthSummary` | GET | `/api/growth/summary` | ✅ |
| `fetchGrowthMilestones` | GET | `/api/growth/milestones` | ✅ |
| `fetchGrowthShare` | GET | `/api/growth/share` | ✅ |
| `transcribeVoice` | POST | `/api/voice/asr` | ✅ |
| `fetchDevTrainingStatus` | GET | `/api/dev/training/status` | ✅ |
| `devResetTodayTraining` | POST | `/api/dev/training/reset-today` | ✅ |
| `devResetTrainingProgress` | POST | `/api/dev/training/reset-progress` | ✅ |
| `devResetAllTraining` | POST | `/api/dev/training/reset-all` | ✅ |
| `devSimulateNextDay` | POST | `/api/dev/training/next-day` | ✅ |
| `devSimulate4amCutoff` | POST | `/api/dev/training/simulate-4am-cutoff` | ✅ |
| `devResetTalent` | POST | `/api/dev/training/reset-talent` | ✅ |

### 后端有但前端 userApi.js 未直接调用的端点

以下端点存在但在组件中内联调用或暂未使用，**不是缺口**：

`GET /api/training/checkin/{id}` `POST /api/training/schedule/optional` `POST /api/training/window` `GET /api/training/window` `GET /api/training/window/status` `POST /api/training/plan/media-exhausted` `GET /api/training/report/{date}` `POST /api/talent/jnao/submit` `GET /api/talent/jnao/report/{id}` `POST /api/talent/assessment` `POST /api/chat` `GET /api/chat/stream` `POST /api/voice/tts` `GET /api/resources/oss/list` `GET /api/resources/list` `GET /api/resources/{id}` `GET /api/guide/debug` `GET /api/health`
