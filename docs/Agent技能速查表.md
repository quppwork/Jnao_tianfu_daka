# Agent Skills 速查表

> 基于 `.agents/skills/` 目录下 29 个 Skill 定义生成。标注 🧑 的技能只能由用户调用（Agent 无法通过 Skill 工具触发）。

---

## 写代码

| 需求 | 命令 | 说明 | 使用场景 |
|------|------|------|----------|
| 设计新模块接口 | `/design-an-interface` | 3 个子 Agent 并行产出不同约束下的接口方案，对比合并，不实现代码 | 新模块 API、重构对外接口、选型对比 |
| 重构改进架构 | `/improve-codebase-architecture` | 扫描 CONTEXT.md + ADR，找出浅层模块，生成 Mermaid 架构图 HTML 报告 | 模块太浅（一堆方法缺乏抽象）、耦合过紧 |
| 规划重构步骤 | `/request-refactor-plan` | 访谈 → 探查代码 → 检查测试覆盖 → 拆成 Martin Fowler 风格微小 commit → 生成 Issue | 有重构想法但不知道从哪下手 |
| 审查代码变更 | `/review` | 双轴审查（规范合规 + 需求一致性），并行子 Agent 报告 | PR review、合并前自查 |
| 测试驱动开发 | `/tdd` | 红-绿-重构循环，强调通过公共接口的集成测试，垂直切片 | 新功能开发、有明确行为预期 |
| 迁移类型断言 | `/migrate-to-shoehorn` | `as Type` → `fromPartial()`，批量替换测试文件中的类型断言 | TypeScript 测试代码清理 |
| 搭建一次性原型 🧑 | `/prototype` | 终端 App（逻辑/状态机验证）或 UI 多方案切换（URL param），用完即弃 | 不确定方案时快速验证 |

## 查 bug

| 需求 | 命令 | 说明 | 使用场景 |
|------|------|------|----------|
| 调试疑难 bug | `/diagnose` | 6 步闭环：建反馈回路 → 复现 → 3-5 个可证伪假设 → 插桩 → 修复+回归 → 复盘 | 难以稳定复现的 bug、性能退化 |
| 口述报 bug | `/qa` | 交互式收集 → 探查代码找领域术语 → 归档为 GitHub Issue（用户视角，无文件路径） | 口述问题、bug bash 后集中归档 |

## 管需求

| 需求 | 命令 | 说明 | 使用场景 |
|------|------|------|----------|
| Issue 分诊流转 | `/triage` | 状态机：needs-triage → needs-info → ready-for-agent → ready-for-human → wontfix，支持快捷覆盖 | 积压 Issue 清理、新 Issue 标记 |
| 计划拆工单 | `/to-issues` | 把计划/PRD 拆成独立可领取的垂直切片 Issue，按依赖顺序发布，偏好 AFK>HITL | 有 PRD/方案，准备分配实施 |
| 会话生成 PRD | `/to-prd` | 从当前对话 + 代码库直接合成 PRD，不访谈——纯提炼已知信息 | 讨论完方案后直接生成文档 |

## 写文档

| 需求 | 命令 | 说明 | 使用场景 |
|------|------|------|----------|
| 收集写作素材 🧑 | `/writing-fragments` | 访谈式挖掘散碎素材（论点、片段、半想法），追加到单个 md 文件，无结构约束 | 文章初期积累原始素材 |
| 逐拍写作 🧑 | `/writing-beats` | 选起始拍 → 写一"拍" → 给出 2-3 个候选下一拍，循环直到文章自然收尾 | 从素材推进到结构化初稿 |
| 素材塑形成文 🧑 | `/writing-shape` | 读素材文件 → 拟 2-3 个不同立意的开头 → 逐段生长，边写边争论格式 | 有素材后需要产出正式文章 |
| 编辑改进文章 🧑 | `/edit-article` | 分节 → 确认顺序（尊重依赖 DAG）→ 逐节重写，每段 ≤240 字符 | 有初稿需要打磨 |
| 建立领域术语表 🧑 | `/ubiquitous-language` | 扫描对话 → 找歧义/同义词 → 给权威术语 → 写 UBIQUITOUS_LANGUAGE.md（含关系图+示例对话） | 多人协作术语不一致、DDD 建模 |

## 讨论 & 决策

| 需求 | 命令 | 说明 | 使用场景 |
|------|------|------|----------|
| 方案压力测试 🧑 | `/grill-me` | 逐决策分支质询，每问一个，给出推荐答案 | 有方案但不确定是否周全 |
| 方案+文档对照质询 🧑 | `/grill-with-docs` | 同上，但对照 CONTEXT.md + ADR 挑战术语/假设，适时更新文档 | 方案影响到现有架构/领域模型 |
| 代码全景地图 🧑 | `/zoom-out` | Agent 不知道这片代码时，上一抽象层，给出模块+调用者的全景地图 | 接手不熟悉的代码区域 |
| 系统化教学 🧑 | `/teach` | 创建 MISSION.md + 参考文档 + 学习记录，按最近发展区上课，持久化多会话 | 学习新技术或领域知识 |

## 效率 & 交接

| 需求 | 命令 | 说明 | 使用场景 |
|------|------|------|----------|
| 节省 token 🧑 | `/caveman` | 极简模式，省 ~75% token，保持技术准确，安全警告时自动恢复完整 | 简单查代码、大量重复操作 |
| 会话交接 🧑 | `/handoff` | 压缩当前会话 → 临时目录交接文档，含"建议 Skills"段落，引用不重复已有产物 | 交给下一个 Agent 或同事继续 |

## 工具设置

| 需求 | 命令 | 说明 | 使用场景 |
|------|------|------|----------|
| 初始化工程配置 🧑 | `/setup-matt-pocock-skills` | 为仓库配置：Issue Tracker 类型 + 分诊标签词汇 + 领域文档布局，写入 CLAUDE.md/AGENTS.md + docs/agents/ | 首次使用工程类 Skills（to-issues、triage、tdd 等）前 |
| Git 安全防护 | `/git-guardrails-claude-code` | 注册 PreToolUse Hook 拦截危险 git 命令（push、reset --hard、clean、branch -D 等） | 防止误操作破坏仓库 |
| Pre-commit 钩子 | `/setup-pre-commit` | 安装 Husky + lint-staged + Prettier + 类型检查，检测包管理器，验证并提交 | 新项目初始化或补充提交规范 |
| 创建新 Skill | `/write-a-skill` | 需求收集 → 草拟 SKILL.md → 审查 → >100 行或跨领域时拆分为多文件 | 把重复工作流固化为 Skill |
| 脚手架练习目录 🧑 | `/scaffold-exercises` | 创建 `01.03-xxx/` 结构（problem/solution/explainer），支持 `git mv` 重新编号 | 教学/课程内容组织 |
| Obsidian 笔记 🧑 | `/obsidian-vault` | 在 `/mnt/d/Obsidian Vault/AI Research/` 搜索/创建/链接笔记，[[wikilinks]] + 索引笔记 | 管理 Obsidian 知识库 |

---

## 调用约定

| 标记 | 含义 |
|------|------|
| 🧑 | **仅用户可调用** — 技能设置了 `disable-model-invocation: true`，Agent 无法通过 Skill 工具触发，需用户直接输入 `/命令` |
| 无标记 | Agent 可通过 Skill 工具代表用户调用 |

> **提示**：标记为 🧑 的技能基本覆盖了需要"人在回路"的场景——写作、决策、学习等需要用户判断的工作流。
