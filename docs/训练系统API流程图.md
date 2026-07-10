# 今日训练系统 — 一图流

## 1. 总览

```
用户选时长 → 排课 → 听音频/看视频 → 逐项打卡 → 完成
                ↓                            ↓
           公式引擎                     晋级判断
         (YAML规则)                  (连续3次升Tier)
```

---

## 2. 每日生命周期

```
 昨日完成           今日训练                        明日
──┼──────────────────┼──────┼──────┼─────────────────
  03:59              04:00  04:05  04:06

  正常训练 ──→ 🔒 冻结5分钟 ──→ ✅ 新一天
              方案锁定        自动刷新方案
              打卡仍可提交     训练天数+1
```

---

## 3. 排课：`POST /schedule`

```
 时长(min)       公式引擎(YAML)         方案
──────────     ────────────────     ──────────
   20     →    [A]                 超脑阅读 ×1
   40     →    [A, B]              超脑阅读 + 影像追忆
 60-120   →    [A, B, C]           + 扫描速记
121-180   →    [A,B,B,C,高效]      + 高效作业
181-240   →    [A,B,B,C,高效]      同上(更多B)
241-300   →    [A,B,B,B,C,高效]    更多B
  ≥480    →    [...+ 精力恢复]     + 精力恢复

A=超脑阅读 B=影像追忆 C=扫描速记 D=极速运算 E=极速学习
Tier≥3 时: 高效作业 → 极速学习 (替换规则)
```

---

## 4. 打卡：`POST /checkin` (核心)

```
┌─────────────────────────────────────────────────────┐
│  ① 校验 cutoff?  ──YES──→ 403 "已截止"              │
│  ② 按顺序?  第一个未完成项 ≠ 指定项 → "请按顺序"     │
│  ③ 创建 TrainingRecord (打卡记录)                    │
│  ④ 原子更新 TrainingItem → done (防并发重复)         │
│  ⑤ 自动完成 选修/感知力 项 (不计入进度)               │
│  ⑥ 更新 Plan 状态 (pending / completed)              │
│  ⑦ 晋级判断 (见下方)                                │
│  ⑧ 清除缓存                                         │
└─────────────────────────────────────────────────────┘
```

---

## 5. 晋级判断：`process_checkin_progress`

```
每项技能独立追踪 ──┬── Tier (当前等级 1-5+)
                  ├── 连续合格次数 (consecutive_pass)
                  └── OSS位置 (stage + part)

  本次合格? ──YES──→ 连续次数+1
   │                 ├── bump_oss → 推进下一课
   │                 └── ≥3次? → Tier+1 🎉 (重置counter)
   │
   └─NO──→ 连续次数归零 (严格连续)

判定规则 (YAML阈值, 按技能/等级/年级分档):
  超脑阅读: 字数÷时间 ≥ 阈值 (wpm)
  影像追忆: 字数≥阈值 & 正确率≥阈值 (recall)
  扫描速记: 字数÷时间≥阈值 & 需倒背 (memory)
  极速运算: completed标记 (speed_calc)
  极速学习: completed标记 (program)
```

---

## 6. 删除打卡：`DELETE /checkin/{id}`

```
 删除TrainingRecord → 回退Item→pending → 重算Plan状态 → 重跑晋级(降级)
```

---

## 7. 选修系统

```
 感知力: 开关 → 加到方案末尾 → 点击音频即自动完成 → 不计入进度
 高效作业: 开关 → 加到方案 → 必修打卡时自动标完成
 精力恢复: ≥480min自动追加

 特点: blocks_next=false (不阻塞) | 不计入计数 | 不参与晋级
```

---

## 8. 全局规则速查

| 规则 | 值 |
|------|-----|
| 训练日分界线 | 凌晨 4:00 CST |
| 冻结窗口 | 4:00 - 4:05 |
| 最低训练时长 | 5 分钟 |
| Tier 晋级 | 连续 3 次合格 |
| Tier 降级 | 1 次不合格→归零 |
| Part 轮换(新) | 每 5 次打卡 |
| Part 轮换(老≤7天) | 每 20 次 |
| Part 轮换(老>7天) | 每 14 次 |
| 转老学员 | ≥30 次总打卡 |
| 天赋测试 | 默认 2 次(管理员可调) |
| 迷者 | 不计入次数 |

---

## 9. 数据库核心表

```
TrainingPlan    方案 (status, level, planned_minutes, media_exhausted)
  └─ TrainingItem   方案项 (sort_order, checkin_status, watch_progress)
       └─ TrainingRecord  打卡记录 (cards, attitude_pct)

TrainingWindow  时间窗口 (start_time, end_time)
ContentItem     音频内容 (OSS URL, duration, skill)
ChildUser       用户 (profile_json.training_progress 存晋级状态)
```

---

## 10. API 速查

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/entry` | 训练入口(天赋+进度) |
| GET | `/today` | 今日方案 |
| POST | `/schedule` | 排课 |
| POST | `/checkin` | 打卡 |
| PUT | `/checkin/{id}` | 修改打卡 |
| DELETE | `/checkin/{id}` | 删除打卡 |
| GET | `/checkin/today` | 今日打卡列表 |
| GET | `/history` | 打卡历史 |
| GET | `/progress` | 训练进度 |
| POST | `/window` | 设时间窗口 |
| GET | `/window/status` | 窗口状态 |
| POST | `/plan/elective-toggle` | 开关选修 |
| POST | `/plan/customize` | 自定义方案 |
| POST | `/plan/media-exhausted` | 标记媒体耗尽 |
| POST | `/items/{id}/watch-progress` | 观看进度 |
| POST | `/elective` | 选修打卡 |
| GET | `/elective/list` | 选修列表 |
| GET | `/video/talent` | 天赋视频 |
| GET | `/report/today` | 今日报告+AI |
| GET | `/report/{date}` | 历史报告 |
