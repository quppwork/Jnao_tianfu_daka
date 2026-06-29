# 前端-后端 API 文档

> 最后更新：2026-06-29
> 按前端页面编排，请求/响应格式 + 后端业务逻辑

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
新学员: Step1 选类型 → Step2 选天赋(可"不知道") → 确认 → 跳天赋测试 或 首页
老学员: Step1 选类型 → Step3 选天赋(必选五者) → 确认(立即保存)
                     → Step4 填全局数据+选项目 → Step5+ 逐项详情
                     → Step100 完成 → 保存完整数据 → 首页
```

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
| `self_reported_talent` | string | Step 3 | 五者之一；**老学员不可为 "unknown"**（前端拦截 + 后端 `talent_unknown:false`） |
| `self_reported_talent_code` | int | Step 3 | TALENT_CODE_MAP 编码（学者=1, 思者=2, 行者=3, 德者=4, 赢者=5） |
| `talent_unknown` | bool | Step 3 | 新学员可选 true（跳天赋测试）；老学员恒为 false |
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
- Step 3 老学员：`!selectedTalent \|\| selectedTalent === 'unknown'` → toast "请选择一个天赋"，阻止继续
- Step 4：至少选 1 个训练项目，否则 toast "请至少选择一项"
- Step 5+：所有字段选填，可跳过，可留空

**保存时机**:
| 时机 | 触发函数 | 保存内容 |
|------|----------|----------|
| 老学员 Step 3 确认天赋 | `confirmReturningTalent()` → `persistOnboarding()` | 天赋信息（talent + talent_code + talent_unknown） |
| Step 100 "开始训练" | `goHome()` → `persistOnboarding()` | 完整 JSON（含全局数据 + 项目列表 + 逐项详情） |

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

## 今日训练

**前端**: `vue_fronted/src/pages/training/index.vue`
**后端**: `app/api/training.py`
**核心引擎**: `training_service.py` + `training_schedule_service.py` + `training_block_builder.py` + `training_duration_pack.py` + `training_day.py` + `child_training_state.py`

### API 列表

```
# 入口 + 方案
GET  /api/training/entry                # 训练入口（校验天赋 + 检查方案）
GET  /api/training/today                # 今日训练方案（无方案时自动排课）
GET  /api/training/today?skip_ai=1      # 跳过 AI 报告，快速返回

# 打卡
POST /api/training/checkin              # { plan_id, item_id, action, cards? }
GET  /api/training/checkin/today        # 今日所有打卡记录
GET  /api/training/checkin/{id}         # 单条打卡
PUT  /api/training/checkin/{id}         # 更新打卡卡片
DELETE /api/training/checkin/{id}        # 删除打卡（回退方案状态）

# 排课
POST /api/training/schedule             # { planned_minutes: 45 }  手动排课
POST /api/training/schedule/optional    # { item_id, action }  可选训练确认

# 时段窗口
POST /api/training/window               # { start_time: "08:00", end_time: "09:00" }
GET  /api/training/window               # 查询当前窗口
GET  /api/training/window/status        # 窗口状态（是否在窗口内）

# 进度 + 历史
GET  /api/training/progress             # 主线阶段 A-E + 技能 stage/part + 训练天数
GET  /api/training/history              # 历史训练方案列表

# 报告 + 资源
GET  /api/training/report/today         # 今日 AI 训练报告
GET  /api/training/report/{date}        # 指定日期的训练报告
GET  /api/training/resources/list       # 资源库
GET  /api/training/resources/{id}       # 资源详情

# 视频 + 进度
GET  /api/training/video/talent         # 天赋相关训练视频
POST /api/training/items/{id}/watch-progress  # 视频观看进度上报
POST /api/training/plan/media-exhausted       # 标记媒体已用完

# 训练状态
GET  /api/training/status               # 全局训练状态
```

### 今日方案响应

```json
{
  "plan_id": 1,
  "plan_date": "2026-06-29",
  "status": "in_progress",
  "items": [
    {
      "id": 1,
      "item_type": "a_lesson",
      "status": "pending",
      "title": "学者影像追忆1阶段1",
      "duration_min": 15,
      "content_type": "audio",
      "play_url": "https://oss-cn-beijing.aliyuncs.com/...",
      "instructions": "专注回忆画面细节..."
    }
  ],
  "coach_text": "今天专注阅读速度，目标 800 字/分钟",
  "schedule_mode": "day_one"
}
```

### 排课引擎流程

```
GET /api/training/today
  → get_today_plan()                   已有方案 → 直接返回
  → schedule_training_by_duration()    无方案 → 启动排课:
      1. 读取 child_user.talent_code + content_index
      2. 首日固定（training_curriculum.yaml day_one）
         次日随机（after_day_one.strategy = "random"）
      3. 主线 A-E 排课（training_curriculum.py）
      4. 背包填充：按时长选训练项数量 + 轮次（training_duration_pack.py）
      5. 依赖校验：A→B 顺序，先看后练（training_block_builder.py）
      6. 从 content_item 表匹配音频/视频
      7. LLM 生成教练文案（training_child_guide.py）
      8. 训练日锁定：凌晨 4:00 截止，4:00-4:05 日切窗口（training_day.py）
```

### 打卡校验

1. `plan_id` 必须属于当前用户
2. `item_id` 必须属于该 plan
3. **顺序校验**：A 方案所有项完成 → 才能打卡 B 方案
4. 所有项完成 → `training_plan.status = "completed"` → `bump_training_completed_day()`

### 状态机

```
child_training_state (profile_json.training_progress)
├── main_line: "A"|"B"|"C"|"D"|"E"    主线阶段
├── skills: { "超脑阅读": {stage,part}, ... }  各技能进度
├── main_line_sessions: int            当前主线已训练天数
├── training_days: int                 总训练天数
└── training_day_anchor: date          训练日起始锚点

训练日规则:
- 当日 04:00 ~ 次日 03:59:59 为同一训练日
- 04:00-04:05 为日切冻结窗口
- 昨日未完成 → 今日继续同方案
- 昨日完成 → 推进到下一项/下一阶段
- **昨日打卡 `result` / `note`（及分项 cards）→ `get_yesterday_training_context()` → 次日 AI 报告与排课**（见 [数据闭环与预留说明.md](数据闭环与预留说明.md)）
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

## 老学员注册全链路（总结）

```
Step 1  选"老学员"         → 前端本地
Step 3  选天赋 → 确认      → PUT /api/user/profile  立即保存天赋
                              sync_child_user_talent() → child_user.talent_code 写入
Step 4  全局数据+选项目     → 纯前端本地
Step 5+ 逐项填详情          → 纯前端本地
Step 100 "开始训练"         → PUT /api/user/profile  保存完整 JSON blob
                              redirect → 首页 → GET /api/training/entry
                              → GET /api/training/today → 排课引擎运行
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
