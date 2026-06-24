# 从 0 到 1 实施手册（Cursor 协作版）

> 项目路径：`D:\daka\Jnao_tianfu_daka`  
> MVP：**儿童天赋测评 → 按天赋推「脑力奥秘」音频 → 每日打卡**  
> 给 Cursor 的指令：按本文「阶段任务」逐项实现，每完成一项打勾

---

## 0. 当前状态（2026-06-13）

| 模块 | 状态 |
|------|------|
| 天赋测评（JNAO API） | ✅ 前后端已有 |
| 今日训练 / 打卡 UI | 🔨 前端原型，无持久化 |
| MySQL / 用户体系 | ❌ 未实现 |
| 音频推送 | ❌ 未实现 |
| 音频资源清单 | ✅ `docs/data/brain_power_audio_catalog.json` |

**后端端口**：8012（以 `scripts/start_all.ps1` 为准）  
**前端端口**：5185

---

## 1. 相关文档索引

| 文档 | 用途 |
|------|------|
| [老板确认清单-可填写.md](./老板确认清单-可填写.md) | 找老板填答案 |
| [data/脑力奥秘-音频资源说明.md](./data/脑力奥秘-音频资源说明.md) | 音频 URL、天赋标签、SQL |
| [data/brain_power_audio_catalog.json](./data/brain_power_audio_catalog.json) | 41 条 MP3 机器可读清单 |
| [功能模块文档/今日训练.md](./功能模块文档/今日训练.md) | 打卡 UI 与 API 草案 |
| [功能模块文档/天赋测试.md](./功能模块文档/天赋测试.md) | 测评状态机 |
| [API接入文档.md](./API接入文档.md) | JNAO / AI 接口 |

---

## 2. MVP 闭环定义

```text
打开 App
  → 儿童天赋测评（35 题）
  → 得到主天赋（思/赢/德/行/学）
  → 写入数据库
  → 「今日训练」展示 1 条对应天赋的 MP3
  → 用户播放 + 打卡
  → 第二天推下一条（按 lesson_sort）
  → 刷新/重进 App 进度仍在
```

**刻意不做（第一期）**：视频、家长账号、微信登录、云端部署、162 条全量同步。

---

## 3. 数据库方案

### 3.1 新建库（不要写老库）

- 库名：`jnao_daka`
- 老库 `db_fz_jingnao`：**只读**，用于导入音频目录

### 3.2 MVP 表结构（Cursor 待建）

```sql
-- 用户（MVP 可简化为单表 child_user）
child_user (
  id, nickname, jnao_uid, created_at
)

talent_assessment (
  id, child_user_id,
  jnao_record_id, answer_bitstring, test_type,
  talent_primary,      -- 思者/赢者/...
  talent_tag,          -- 思/赢/德/行/学
  talent_code,         -- 1-5 对应 ys_c_course.talent
  report_json, assessed_at
)

content_item (
  id, source_id, course_id, talent_code, talent_tag,
  lesson_title, lesson_sort, play_url, content_type  -- audio
)

daily_plan (
  id, child_user_id, plan_date, content_item_id, status
)

checkin_record (
  id, child_user_id, daily_plan_id, checked_at
)
```

### 3.3 导入音频

1. 读 `docs/data/brain_power_audio_catalog.json`
2. 写入 `content_item`
3. 或运行将创建的 `scripts/import_audio_catalog.py`

---

## 4. 分阶段任务（按顺序做）

### 阶段 A：基础设施 ⬜

- [ ] **A1** 添加依赖：`sqlalchemy`, `pymysql`, `alembic`（或纯 SQL 迁移脚本）
- [ ] **A2** `backend/config/settings.yaml` 增加 `database.url`
- [ ] **A3** `backend/.env.example` 增加 `DATABASE_URL=mysql+pymysql://root:xxx@127.0.0.1:3306/jnao_daka`
- [ ] **A4** 创建 `jnao_daka` 库 + 建表 SQL：`backend/migrations/001_mvp.sql`
- [ ] **A5** `backend/app/db/` 连接与会话管理

**Cursor 提示词示例：**

> 阅读 `docs/从0到1实施手册-Cursor协作版.md` 阶段 A，为 backend 接入 MySQL jnao_daka，创建 MVP 表。

---

### 阶段 B：音频目录入库 ⬜

- [ ] **B1** `scripts/import_audio_catalog.py`：JSON → `content_item`
- [ ] **B2** 天赋映射常量：`TALENT_NAME_TO_CODE = {"思者":2, "赢者":5, ...}`
- [ ] **B3** 单元测试：导入后 41 条、五天赋条数正确

**Cursor 提示词：**

> 根据 `docs/data/brain_power_audio_catalog.json` 写 import 脚本，写入 content_item 表。

---

### 阶段 C：测评落库 ⬜

- [ ] **C1** 测评完成时 POST 保存 `talent_assessment`（不只 localStorage）
- [ ] **C2** 从 JNAO 报告 JSON 解析 `talent_primary` → `talent_code` / `talent_tag`
- [ ] **C3** `GET /api/talent/assessment/latest?user_id=` 供训练模块读取
- [ ] **C4** testresult 失败时：本地 scoring 回退（参考 `backend/app/core/scoring.py`）

**Cursor 提示词：**

> 测评完成后持久化到 talent_assessment，并解析天赋标签映射到 talent_code 1-5。

---

### 阶段 D：今日训练 API ⬜

- [ ] **D1** `GET /api/training/today?user_id=`  
  - 无测评 → 403 + 提示先测评  
  - 有测评 → 查今日是否已有 plan，无则按进度取下一条 `content_item`
- [ ] **D2** `POST /api/training/checkin`  body: `{ user_id, plan_id }`
- [ ] **D3** `GET /api/training/progress?user_id=` 返回已打卡天数、当前序号
- [ ] **D4** 推送逻辑：同一 `talent_code` 下按 `lesson_sort` 递增；跳过 `lesson_sort=0` 的「我是冠军」可选（见老板确认 #7）

**Cursor 提示词：**

> 实现今日训练 API：根据 talent_assessment 的 talent_code 从 content_item 按序推送 MP3，支持打卡持久化。

---

### 阶段 E：前端对接 ⬜

- [ ] **E1** `vue_fronted/src/pages/training/index.vue` 接 `GET /api/training/today`
- [ ] **E2** 用 `<audio>` 或 uni 音频组件播放 `play_url`
- [ ] **E3** 打卡按钮调 `POST /api/training/checkin`
- [ ] **E4** 无测评时引导到 `/pages/talent/index`
- [ ] **E5** 测评页完成后刷新训练入口状态

**Cursor 提示词：**

> 对接 training 页面与 /api/training/*，实现音频播放和打卡。

---

### 阶段 F：联调验收 ⬜

- [ ] **F1** 本地跑通：`scripts/start_all.ps1`
- [ ] **F2** 走通：测评 → 今日音频 → 打卡 → 改系统日期/第二天 → 下一条
- [ ] **F3** pytest：`backend/tests/test_training_api.py`
- [ ] **F4** 更新 `docs/功能模块文档/今日训练.md` 状态为「已开发」

**验收清单：**

| 步骤 | 预期 |
|------|------|
| 新用户测评 | DB 有 talent_assessment |
| 打开今日训练 | 显示对应天赋第一条 MP3 |
| 播放 URL | 浏览器/真机能出声 |
| 打卡 | DB 有 checkin_record |
| 刷新 | 仍显示已打卡 |
| 次日 | 自动第二条 |

---

### 阶段 G：云端部署（MVP 后） ⬜

- [ ] **G1** 阿里云 RDS 建 `jnao_daka`
- [ ] **G2** ECS + Nginx 反代 8012
- [ ] **G3** 构建 uni-app H5 / 小程序
- [ ] **G4** HTTPS 域名
- [ ] **G5** 环境变量与密钥上云

详见老板确认清单第七节。

---

## 5. 天赋映射代码（直接复用）

```python
TALENT_NAME_TO_CODE = {
    "学者": 1, "思者": 2, "行者": 3, "德者": 4, "赢者": 5,
    "迷者": 2,  # 儿童卷备用，按老板确认调整
}
TALENT_CODE_TO_TAG = {1: "学", 2: "思", 3: "行", 4: "德", 5: "赢"}
TALENT_CODE_TO_COURSE = {1: 28, 2: 25, 3: 24, 4: 27, 5: 26}
```

---

## 6. 给 Cursor 的全局协作约定

1. **每次开新任务**：先读本文当前阶段 + `老板确认清单` 已填项。
2. **不要**把新用户写入 `db_fz_jingnao`。
3. **音频 URL** 优先读 `content_item`，不要每次查老库。
4. **最小 diff**：MVP 不做家长端、视频、推送通知。
5. **端口**：后端 8012，前端 proxy 指向 8012。
6. **测试**：改 backend 必跑 `pytest backend/tests/`。

### 一键启动

```powershell
cd D:\daka\Jnao_tianfu_daka
.\scripts\start_all.ps1
```

### 重新导出音频清单

```powershell
python scripts/export_brain_power_audio.py
```

---

## 7. 阻塞项（需老板确认后再改逻辑）

见 [老板确认清单-可填写.md](./老板确认清单-可填写.md) 中带 🔴 的条目：

- 162 vs 41 条以哪个为准
- 每日几条、听完标准、未测评能否训练
- 162 条若为准：需提供线上表名或导出文件

---

## 8. 进度追踪（手动打勾）

| 阶段 | 状态 | 完成日期 |
|------|------|----------|
| A 基础设施 | ⬜ | |
| B 音频入库 | ⬜ | |
| C 测评落库 | ⬜ | |
| D 训练 API | ⬜ | |
| E 前端对接 | ⬜ | |
| F 联调验收 | ⬜ | |
| G 云端部署 | ⬜ | |

---

## 9. 下一步（你现在就可以做）

1. 打开 [老板确认清单-可填写.md](./老板确认清单-可填写.md)，至少填完 **第一节 + 第二节 + 第三节**。
2. 在 Cursor 中说：

> 按 `docs/从0到1实施手册-Cursor协作版.md` 阶段 A 和 B 开始实现。

3. 确认本机 MySQL 有 `db_fz_jingnao`，并已生成 `brain_power_audio_catalog.json`。
