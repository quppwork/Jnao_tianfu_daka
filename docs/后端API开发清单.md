# 后端 API 开发清单

> 最后更新：2026-06-23

---

## 一、已实现

| 方法 | 路径 | 说明 | 依赖 |
|------|------|------|------|
| GET | `/api/health` | 健康检查 + 集成状态 | — |
| POST | `/api/talent/report` | 天赋测试：提交35位答案 → 获取报告 | JNAO 外部 API (m.jnao.com) |
| POST | `/api/talent/jnao/submit` | 代理提交答案到 JNAO | JNAO 外部 API |
| GET | `/api/talent/jnao/report/{id}` | 代理获取 JNAO 报告 | JNAO 外部 API |
| POST | `/api/chat` | 同步 AI 对话（代理 tianfu_rag） | tianfu_rag |
| GET | `/api/chat/stream` | SSE 流式 AI 对话 | tianfu_rag |
| POST | `/api/guide/chat` | 首页引导对话（豆包 AI） | 豆包 API |
| POST | `/api/voice/tts` | 文字 → 语音 mp3 | 火山引擎语音（待开通）|
| POST | `/api/voice/asr` | 语音 → 文字（本地 Whisper） | faster-whisper |
| — | 日志系统 | 控制台 + 文件轮转 (5MB×3) | — |

---

## 二、待开发：今日训练

| 方法 | 路径 | 说明 | 优先级 |
|------|------|------|--------|
| GET | `/api/training/today` | 获取今日训练方案（等级+内容+状态） | P0 |
| POST | `/api/training/checkin` | 提交打卡记录（能力类型+时间+内容+结果） | P0 |
| GET | `/api/training/history` | 打卡历史列表 | P1 |
| DELETE | `/api/training/checkin/{id}` | 删除打卡记录 | P2 |
| PUT | `/api/training/checkin/{id}` | 修改打卡记录 | P2 |

### 数据库表（需新建）

```sql
CREATE TABLE training_plan (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    train_date DATE NOT NULL,
    level VARCHAR(20),         -- 训练等级
    created_at DATETIME DEFAULT NOW()
);

CREATE TABLE training_record (
    id INT PRIMARY KEY AUTO_INCREMENT,
    plan_id INT,
    user_id INT NOT NULL,
    ability_type VARCHAR(20),  -- 能力类型（极速运算/扫描速记/...）
    time_spent VARCHAR(50),    -- 用时
    content TEXT,              -- 训练内容
    result TEXT,               -- 训练结果
    created_at DATETIME DEFAULT NOW()
);
```

---

## 三、待开发：知识答题

| 方法 | 路径 | 说明 | 优先级 |
|------|------|------|--------|
| POST | `/api/qa/chat` | 文字对话（豆包 + 天赋类型提示词注入） | P1 |
| POST | `/api/qa/chat/stream` | SSE 流式对话 | P1 |
| POST | `/api/qa/voice` | 语音输入：上传音频 → 返回文字+TTS音频 | P2 |
| GET | `/api/qa/history` | 对话历史列表 | P2 |
| POST | `/api/qa/session` | 新建对话 | P2 |
| GET | `/api/qa/session/{id}` | 获取对话详情 | P2 |
| DELETE | `/api/qa/session/{id}` | 删除对话 | P2 |

### 数据库表

```sql
CREATE TABLE qa_session (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    title VARCHAR(200),        -- AI 自动生成标题
    subject VARCHAR(20),       -- math/chinese/english/science/other
    created_at DATETIME DEFAULT NOW()
);

CREATE TABLE qa_message (
    id INT PRIMARY KEY AUTO_INCREMENT,
    session_id INT NOT NULL,
    role VARCHAR(10) NOT NULL,  -- user/assistant
    content TEXT NOT NULL,
    voice_url VARCHAR(500),
    created_at DATETIME DEFAULT NOW()
);
```

### 豆包提示词注入方案

- 方案 A：开局设 system prompt（天赋类型+特点）
- 方案 B：每条消息前追加简短上下文
- 推荐 A+B 混合使用

---

## 四、待开发：成长里程碑

| 方法 | 路径 | 说明 | 优先级 |
|------|------|------|--------|
| GET | `/api/growth/milestones` | 荣誉级别列表+达成条件 | P2 |
| GET | `/api/growth/timeline` | 用户成长时间线 | P2 |
| GET | `/api/growth/badges` | 用户已获徽章 | P2 |

---

## 五、待开发：用户系统

| 方法 | 路径 | 说明 | 优先级 |
|------|------|------|--------|
| POST | `/api/auth/register` | 用户注册（年级/成绩等个人信息） | P1 |
| POST | `/api/auth/login` | 登录 | P1 |
| GET | `/api/user/profile` | 获取个人信息 | P1 |
| PUT | `/api/user/profile` | 修改个人信息 | P1 |
| GET | `/api/user/students` | 家长查看绑定的学生列表 | P2 |
| POST | `/api/user/bind-student` | 绑定新学生 | P2 |

### 数据库表

```sql
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    phone VARCHAR(20) UNIQUE,
    role VARCHAR(10),          -- student/parent/teacher
    grade VARCHAR(10),
    score_level VARCHAR(20),
    talent_type VARCHAR(20),
    training_level VARCHAR(20),
    created_at DATETIME DEFAULT NOW()
);

CREATE TABLE parent_student (
    id INT PRIMARY KEY AUTO_INCREMENT,
    parent_id INT NOT NULL,
    student_id INT NOT NULL,
    FOREIGN KEY (parent_id) REFERENCES users(id),
    FOREIGN KEY (student_id) REFERENCES users(id)
);
```

---

## 六、依赖服务清单

| 服务 | 用途 | 状态 | 凭证 |
|------|------|------|------|
| JNAO API (m.jnao.com) | 天赋测试提交+报告 | ✅ 已接入 | — |
| 豆包 API (Ark) | LLM 对话 | ✅ 已接入 | `DOUBAO_API_KEY` |
| 火山引擎 TTS | 文字转语音 | ⚠️ 需开通 | `SPEECH_APP_ID` + `SPEECH_ACCESS_TOKEN` |
| 火山引擎 ASR | 语音转文字 | ⚠️ 需开通 | 同上 |
| 本地 Whisper | 语音转文字（备选） | ✅ 已部署 | — |
| tianfu_rag | RAG 知识库 | ✅ 已接入 | 端口 8010 |
| MySQL | 持久化存储 | ⚠️ 待建表 | 端口 3306 |

---

## 七、开发优先级

```
P0（本周）: 今日训练 API + 数据库建表
P1（下周）: 知识答题 API + 用户注册登录
P2（后续）: 成长里程碑 + 家长端 + 语音服务开通
```
