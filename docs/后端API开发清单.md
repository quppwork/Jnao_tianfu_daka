# 后端 API 待开发清单

> 最后更新：2026-06-24  
> 只列待开发内容，已实现的见 `git log`

---

## 一、今日训练

### 1.1 训练方案

| 方法 | 路径 | 说明 | 优先级 |
|------|------|------|--------|
| GET | `/api/training/report/today` | AI 生成今日训练报告（基于历史+模板） | P0 |
| GET | `/api/training/report/{date}` | 获取指定日期训练报告 | P1 |

**AI 职责：**
- 根据学员历史数据 + 等级 + 12 能力类型，自动编排今日训练项
- 每项从资源库拉取对应音频/视频链接
- 今日方案基于昨日内容承接推演
- 报告模板：极简文字，越少越好

### 1.2 打卡记录

| 方法 | 路径 | 说明 | 优先级 |
|------|------|------|--------|
| POST | `/api/training/checkin` | 提交打卡（能力类型+时间+内容+结果+态度分） | P0 |
| GET | `/api/training/history` | 打卡历史列表 | P1 |
| PUT | `/api/training/checkin/{id}` | 修改打卡记录 | P2 |
| DELETE | `/api/training/checkin/{id}` | 删除打卡记录 | P2 |

### 1.3 训练时段

| 方法 | 路径 | 说明 | 优先级 |
|------|------|------|--------|
| POST | `/api/training/window` | 设置今日训练时段 | P0 |
| GET | `/api/training/window` | 获取今日训练时段 | P0 |
| GET | `/api/training/window/status` | 检查当前是否在时段内 | P1 |

### 1.4 资源库

| 方法 | 路径 | 说明 | 优先级 |
|------|------|------|--------|
| GET | `/api/resources/list` | 资源列表（按类型/等级/能力筛选） | P1 |
| GET | `/api/resources/{id}` | 获取资源详情（含播放 URL） | P1 |
| POST | `/api/resources/upload` | 上传训练资源（视频/音频） | P2 |

### 1.5 数据库表

```sql
CREATE TABLE training_plan (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    plan_date DATE NOT NULL,
    level VARCHAR(20),
    report_text TEXT,           -- AI 生成的每日报告
    generated_at DATETIME,
    created_at DATETIME DEFAULT NOW()
);

CREATE TABLE training_item (
    id INT PRIMARY KEY AUTO_INCREMENT,
    plan_id INT NOT NULL,
    sort_order INT NOT NULL,    -- 顺序号
    ability_type VARCHAR(20),   -- 12 能力类型之一
    duration INT,               -- 建议时长（分钟）
    video_url VARCHAR(500),
    audio_url VARCHAR(500),
    instructions TEXT,          -- 指导建议
    created_at DATETIME DEFAULT NOW(),
    FOREIGN KEY (plan_id) REFERENCES training_plan(id)
);

CREATE TABLE training_record (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    plan_id INT,
    ability_type VARCHAR(20),
    time_spent VARCHAR(50),
    content TEXT,
    result TEXT,
    note TEXT,
    attitude_pct INT,           -- 配合度 0/20/40/60/80/100
    files JSON,                 -- 上传的文件列表
    created_at DATETIME DEFAULT NOW()
);

CREATE TABLE training_window (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    train_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    created_at DATETIME DEFAULT NOW()
);

CREATE TABLE training_resources (
    id INT PRIMARY KEY AUTO_INCREMENT,
    type VARCHAR(10) NOT NULL,  -- video/audio/doc
    title VARCHAR(200),
    url VARCHAR(500),
    level VARCHAR(20),
    ability_type VARCHAR(20),
    duration INT,
    created_at DATETIME DEFAULT NOW()
);
```

---

## 二、知识答题

| 方法 | 路径 | 说明 | 优先级 |
|------|------|------|--------|
| POST | `/api/qa/chat` | 文字对话（豆包 + 天赋类型提示词注入） | P1 |
| POST | `/api/qa/chat/stream` | SSE 流式对话 | P1 |
| GET | `/api/qa/sessions` | 对话历史列表 | P2 |
| POST | `/api/qa/sessions` | 新建对话 | P2 |
| GET | `/api/qa/sessions/{id}` | 对话消息列表 | P2 |
| DELETE | `/api/qa/sessions/{id}` | 删除对话 | P2 |

```sql
CREATE TABLE qa_session (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    title VARCHAR(200),
    subject VARCHAR(20),
    created_at DATETIME DEFAULT NOW()
);

CREATE TABLE qa_message (
    id INT PRIMARY KEY AUTO_INCREMENT,
    session_id INT NOT NULL,
    role VARCHAR(10) NOT NULL,
    content TEXT NOT NULL,
    voice_url VARCHAR(500),
    created_at DATETIME DEFAULT NOW()
);
```

---

## 三、成长里程碑

| 方法 | 路径 | 说明 | 优先级 |
|------|------|------|--------|
| GET | `/api/growth/milestones` | 荣誉级别列表+达成条件 | P2 |
| GET | `/api/growth/timeline` | 用户成长时间线（打卡+测评+答疑） | P2 |
| GET | `/api/growth/badges` | 用户已获徽章 | P2 |

---

## 四、用户系统

| 方法 | 路径 | 说明 | 优先级 |
|------|------|------|--------|
| POST | `/api/auth/register` | 注册（年级/成绩/等级） | P1 |
| POST | `/api/auth/login` | 登录 | P1 |
| GET | `/api/user/profile` | 个人信息 | P1 |
| PUT | `/api/user/profile` | 修改个人信息 | P1 |
| GET | `/api/user/students` | 家长→绑定的学生列表 | P2 |
| POST | `/api/user/bind-student` | 绑定新学生 | P2 |

```sql
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    phone VARCHAR(20) UNIQUE,
    role VARCHAR(10),
    grade VARCHAR(10),
    score_level VARCHAR(20),
    talent_type VARCHAR(20),
    training_level VARCHAR(20),
    created_at DATETIME DEFAULT NOW()
);
```

---

## 五、清北班导师审核（后续）

| 方法 | 路径 | 说明 | 优先级 |
|------|------|------|--------|
| POST | `/api/training/review/{id}` | 导师审核打卡 | P3 |
| GET | `/api/training/review/pending` | 待审核列表 | P3 |

---

## 六、语音服务

| 任务 | 说明 | 优先级 |
|------|------|--------|
| 火山引擎 TTS 开通 | 文字转语音（张宇老师声音） | P2 |
| 火山引擎 ASR 开通 | 语音转文字 | P2 |
| 语音凭证获取 | SPEECH_APP_ID + SPEECH_ACCESS_TOKEN | P2 |

---

## 七、依赖服务

| 服务 | 用途 | 状态 |
|------|------|------|
| 豆包 API (Ark) | LLM 对话 + 训练报告生成 | ✅ 已接入 |
| JNAO API | 天赋测试提交+报告 | ✅ 已接入 |
| 火山引擎 TTS | 文字转语音 | ⚠️ 需开通 |
| 火山引擎 ASR | 语音转文字 | ⚠️ 需开通 |
| MySQL | 持久化存储 | ⚠️ 待建表 |
| 云存储 (OSS/COS) | 训练资源存储 | 🔒 待定 |

---

## 八、开发优先级

```
P0（当前）: 训练打卡 API + 时段管理 API + 数据库建表
P1（随后）: AI 训练报告 + 资源库 + 知识答题 API + 用户注册
P2（后续）: 成长里程碑 + 语音服务 + 文件上传
P3（远期）: 清北班导师审核 + 家长端
```
