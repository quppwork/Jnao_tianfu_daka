# uni-app x 原地改造实施计划

## 目标与边界

在现有 `vue_fronted` 目录直接修改、改名和归位原文件。HBuilderX 将同一个目录识别为 uni-app x 工程，采用参考项目的 Vue 3、UTS、UVue 和 VDOM 开发方式。交付目标为微信小程序、Android 和 iOS。已终止原 H5 客户端的构建、运行以及部署。

业务以本仓库为准。保留现有 36 条路由对应的业务入口、视觉结构、交互、角色权限和 FastAPI 接口契约。保留本项目的微信 AppID `wxbca3a9ba6f39a3df` 和已部署的外部报告入口。工程组织参考 `D:/personal-item/Jnao/Jnao_UniApp`，参考目录只读。DCloud AppID、Android 包名、iOS Bundle ID 和签名使用本项目获准的配置。

每批改动落在同一个工程内。保留当前工作区已有的删除、AppID 和白屏修复。每批登记已改、可复用和待删除文件，留下能定位回归的构建结果。正式发布、外部资源上传和超出前端交付范围的调整独立确认。

## 1. 建立清单与改造基线

- [ ] 读取 `src/pages.json` 的 19 条主包路由和五个分包的 17 条路由。按路径、入口、关联页面、依赖接口和关键交互登记 36 条，记录登录回跳、家长与学生互切、报告深链、管理后台入口及新旧样式入口。
- [ ] 从 `src/App.vue`、`src/main.js`、页面和样式的导入关系核对 npm 使用点。明确 `katex`、`augmented-ui`、浏览器 API、嵌入 HTML、绝对资源路径和构建脚本各自的归属。
- [ ] 建立资产清单，查页面、CSS、动态拼接、后端配置、Nginx 和外部嵌入 URL。记录微信基线为主包约 86.57 MiB，静态资源约 85 MiB。给每项标明本地、分包、远程或可清除及依据。
- [ ] 留存当前登录页、训练、答疑、测评和家长侧的可复现路径。已有测试基线为 253 通过、2 条家长跳转断言失败。核对当前产品预期再更新这两项断言。

## 2. 改造根目录入口与配置

| 当前文件或目录 | 原地调整后的职责 |
| --- | --- |
| `src/App.vue`、`src/main.js` | 移到工程根目录并改为 `App.uvue`、`main.uts`。应用层管理启动、回前台和会话恢复。首页动画放在实际页面组件 |
| `src/manifest.json`、`src/pages.json`、`src/uni.scss` | 移到根目录。应用配置使用 `uni-app-x`、`app`、`app-android`、`app-ios`和 `mp-weixin` 对应配置。保留微信 AppID，重建应用身份、权限、图标和启动图映射 |
| `src/pages/`、`src/components/` | 归位到根目录的 `pages/` 和 `components/`。页面原文件改为 `.uvue`，组件按参考工程的 `index.uvue`、按需 `index.scss` 和精确 easycom 映射整理 |
| `src/utils/api/`、`src/utils/appSession.js`、`src/utils/mainTabs.js` | 现有职责归位到根目录 `api/`、`network/`、`state/`、`router/`。环境、静态地址和可用能力放入 `config/` |
| `src/static/`、`src/styles/`、`src/data/questions.js` | 资源和样式归位到根目录或归属分包，保留既有路由和公开路径所需的资源。题库改为 UTS 数据并与测评契约比对 |
| `.hbuilderx/launch.json` | 使用 HBuilderX 的运行配置验证 Android、iOS、微信。 |

- [ ] 首批以真实登录页和启动依赖完成工程类型切换。其余业务源码按原路径登记待改造，最终逐条注册到根目录 `pages.json`。保留体量较大的业务文件，避免把占位页当成验收通过。
- [ ] 用 HBuilderX 完成微信、Android、iOS 各自的开发编译。从 IDE 项目类型和构建产物验证实际使用的是 uni-app x 的编译链。Windows 的 iOS 模拟器资源编译单独记录。

## 3. 改造公共能力，再逐组改业务页面

- [ ] 在 `config/environment.uts` 集中现有后端的开发、测试和生产地址。真机和微信联调使用可达的测试 HTTPS 地址。Docker 保留现有 HTTPS 入口的 API、媒体和合作方报告转发。请求层保留当前约定的 URL、请求体、角色鉴权、超时和错误处理，使用实际接口测试。
- [ ] 将浏览器 `localStorage`、`sessionStorage` 和 DOM 事件依赖按职责替换为平台存储、生命周期和组件状态。使用现有角色槽位语义并核对小程序、App 冷启动和退出清理。
- [ ] 给大宇、答疑和报告聊天分别核对 SSE 事件协议。先测 Android、iOS、微信各端传输是否支持逐块到达、中文跨块解码、取消和断网恢复。传输按平台实现，事件解析和 UI 状态规则共享。只有实际验证到的方式进入实现。
- [ ] 在现有页面和组件内调整样式。服从参考工程的 VDOM 兼容规则，验证滚动容器、安全区、键盘、返回动作、富文本、公式和选择器。动态效果或富文本库退役前核对用户可见结果。

| 现有依赖 | 替代方向和退役条件 |
| --- | --- |
| Vite 代理、`fetch` 和浏览器 Cookie | HBuilderX 编译与分环境请求。普通接口走 `uni.request`，核对现有服务端所支持的会话传递，逐端验收后移除旧入口 |
| `MediaRecorder`、`FormData`、浏览器文件选择 | 用目标平台支持的录音、选择与上传 API，保持原接口字段和媒体格式，验收权限拒绝和上传失败 |
| `katex`、`v-html` 和答疑 CSS | 先验证各端富文本与公式渲染能力。可用的 UVue 富文本能力承担普通消息，公式按真机验证结果选定渲染方案。数学公式和流式渲染通过后退役 npm 依赖 |
| `augmented-ui` | 用 UVue 兼容的组件结构和 SCSS 保留训练卡、弹层和打卡按钮的表现，验收旧版入口后删除样式依赖 |
| `vite.config.js`、`unh.config.js`、`@dcloudio/*` 与 CLI 专用依赖 | HBuilderX 内置编译链及原生运行配置。改造后由 HBuilderX 自带工具运行和编译 |

| 顺序 | 原业务文件分组 | 验收路径 |
| --- | --- | --- |
| 1 | `pages/login/`、`pages/dayu/`、`pages/index.vue` | 家长和孩子入口、注册、绑手机号、新手流程、登录回跳、账号切换、对话与退出 |
| 2 | `pages/training/`、`pages/qa/`、`pages/growth/` | 今日训练、播放、计时、打卡和历史，答疑拍照上传、语音和公式，成长进度和徽章 |
| 3 | `pages/talent/`、`pages/report/`、`pages/plan/` | 测评入口、答题、历史弹层、按测评类型打开报告、报告问答、学业规划和外部报告 URL |
| 4 | `pages/hub/`、`pages/parent/`、`pages/admin/` | 学院、课程、剧情和中央电脑，家长账号管理、数据和算力，管理员登录、列表和详情 |

- [ ] 逐项拆解 `DayuFrame` 与 `static/dayu/html/` 的入口、消息桥、登录态及外链。适合原生实现的现有页面转为 UVue。外部报告和确实需要 WebView 的功能按端验证 URL、域名、导航、消息时机及安全的会话传递，核对后端和合作方链接仍可打开。
- [ ] 每组完成后核对其路由、组件与引用，按受影响平台编译。真机使用测试账号检查对应主路径，逐端记录待验证项。对浏览器变更按项目约定使用 Chrome DevTools MCP。

## 4. 调整分包与静态资源

- [ ] 在根目录 `pages.json` 配置 `pages` 主包与 `subPackages` 分包。主包包含登录、首页、必须常驻的导航入口和共享基础代码。已有 admin、parent、report、plan、growth 继续作为分包候选。训练、答疑、测评、学院按实际启动和导航关系划分，检查跨包引用，并用生成的 `app.json` 核对最终布局。
- [ ] 微信只打包首屏和必要的本地资源。大量报告图、课程图、动画、视频用项目获准的 HTTPS 静态资源源站，或放入体积合适且引用边界明确的分包。先核对线上资源可访问、失败提示和本地布局，再清理本地重复副本。App 和微信小程序的资源策略分别验收。
- [ ] 重新测量微信主包、各分包与整包，使用实际微信开发者工具检查当前限制。启用真实 AppID 的开发者权限，生成预览二维码，再分别验证扫码与真机调试。App 的加载行为按 HBuilderX 实际产物验证。

## 5. 清理旧工具链与验证发布链路

- [ ] 实施中先更新接收前端产物的启动和部署流程。当前 `docker/Dockerfile.frontend` 依赖 `package.json`、锁文件和 `dist/build/h5`。现有 `scripts/run_frontend.ps1`、`scripts/start_frontend.*`、`scripts/start_all.sh` 也调用 npm。移除 Docker 的应用构建，验证 Nginx 仍能提供媒体、微信校验、合作方报表入口和 API 代理。跨目录更新只涉及前端构建接入，实施前核对修改范围。
- [ ] 启动、业务、构建及部署验证完成后，清理 `node_modules/`、`package.json`、`package-lock.json`、`.npmrc`、`unh.config.js`、`vite.config.js`、`vitest.config.js`、失效的 `jsconfig.json`、旧 `dist/` 和空的 `src/`。逐项确认替代和引用检查结果，包含只验证旧实现的测试及用途已结束的一次性脚本。
- [ ] 将有价值的回归保留为现有 UTS 实现的测试，参考项目的 `node --test scripts/test-*.mjs` 方式。Node.js 可用于独立测试，HBuilderX 开发和发行从无 `node_modules` 的工程验证。生成目录及本机缓存按项目约定忽略。
- [ ] 用同一个目录完成微信预览及真机调试、Android 和 iOS 真机运行。具备本项目签名后验证 Android 安装包和 iOS 安装或 TestFlight。记录每端的编译、运行与发布结果。代码变更按顺序完成 `simplify`、`code-review`，关键行为按现有规则做 OCR 原生补充审查。

## 参考

- 本项目的 [HBuilderX 编译基线](2026-11-21-hbuilderx-multiplatform.md)
- [uni-app x 页面与 VDOM](https://uniapp.dcloud.net.cn/uni-app-x/page.html)
- [uni-app x 应用配置](https://uniapp.dcloud.net.cn/uni-app-x/collocation/manifest.html)
- [微信独立分包](https://uniapp.dcloud.net.cn/tutorial/independent-subpackage.html)

## 第一批实施记录

- 根目录已加入 `App.uvue`、`main.uts`、应用配置、路由和登录页。学生账号密码和家长手机号密码表单连接现有 `/api/auth/login` 契约。当前阶段验证表单和响应，短信、会话保存及登录后导航随首组业务继续接入。
- HBuilderX 5.34 的内置 uni-app x VDOM 编译器已针对根目录生成微信、Android、iOS 和 Web 产物。构建输出放在 `unpackage/codex/`。微信首批产物约 107 KiB，只覆盖登录路由，完整业务包体仍按第 4 节验收。
- 旧 CLI 仍服务于其余业务、现有 H5 和 Docker。IDE 的项目列表对两类工程均显示 `UniApp_VUE`，应以编译日志确认实际走的编译器。过渡期旧 CLI 和根目录使用同一个 `index.html`，Vite 配置按各自编译链解析入口和依赖。
- Web 登录页已通过 Chrome DevTools 验证角色切换、输入校验，以及孩子和家长用隔离的内存数据库账号提交密码。请求实际进入 FastAPI，当前后端的学生与家长认证响应含 JWT，同时设置 HttpOnly Cookie。客户端按平台使用 JWT。错误密码会显示服务端返回的提示。后端认证相关 20 项测试通过。旧前端单测仍为 253 项通过及 2 项已有跳转断言失败。
- 真机联调需配置设备可达的测试服务地址并确认各端会话策略。Web 当前走同源代理，代理保留 `/api/` 下 UTS 模块的本地读取。IDE App 运行菜单切换、移动端运行、完整业务包和安装包尚待验收。
- OCR 原生使用 `deepseek-flash`，完成 6 个可审文件，0 个失败，`.uvue` 和 `.uts` 因扩展名被排除。已增加编译上下文提示并实测 Web 入口。视觉一致性与真机安全区建议留在对应页面的验收清单。

## 第二批实施记录

- 已移除 H5 应用入口、Vite、npm 清单与依赖目录、旧构建产物及 H5 启动脚本。Docker 最终镜像采用 Nginx，提供 API 和媒体转发、外部报告嵌入和域名校验。现有 FastAPI 代码未修改。
- 已接入根目录的登录与账号首页，家长密码和短信登录、资料补全、孩子账号管理，学生的训练记录和成长里程碑。训练、成长、家长分别作为微信分包。会话使用现有认证接口返回的 JWT，访问接口统一附带身份和令牌。
- 旧 `src` 中的业务实现、静态资源与行为测试继续作为逐页转换依据。现有训练打卡、答疑、测评和报告等剩余能力需要逐项完成原生实现和验收。
- HBuilderX 重启后清除了沿用旧 npm 链的运行会话。重新打开同一个工程即可使用内置 uni-app x 编译器。正式打包仍需配置产品自身的 DCloud AppID 和应用签名。

## 今日修炼实施

- [x] 以 `src/pages/training/dayu.vue` 的选时长、确认方案和能量塔布局为准，在原工程训练分包注册原生页面。保留选修置顶开关和方案单次修改。
- [x] 接入训练短期签名媒体、服务端计时、播放进度及新增与编辑打卡。等待完成实际设备播放验证。
- [x] 隔离后端验证测评拦截、排课、确认、恢复、90% 音频门槛、进度、选修开关和打卡。HBuilderX 5.34 完成微信小程序、Android、iOS 模拟器资源编译。
- [x] OCR 原生使用 `deepseek-flash` 审查 8 个可识别文件，0 个失败。已处理训练渐变、控件对齐、配合度高亮和历史详情的移动端边距。
- [ ] 微信开发者工具获取 AppID 项目信息时出现 `Failed to fetch`，需复测训练页模拟器和真机。评测、报告、答疑及未接入的训练交互继续使用旧源码作为转换依据。

## 儿童测评及报告入口

- [ ] 将儿童题库及作答逻辑接入测评分包。随机展示原题，按题号提交 35 位答案，保留家长代测确认、答题计时和撤回。
- [ ] 在训练闸门串接测评、历史及结果入口。通过原接口读取测评结果和处理天赋冲突，核对回到训练后重新读取状态。
- [ ] 核对整个旧路由与原生路由，分别标明已接入、部分接入和待改。尚有行为差异的旧实现保留作比对。
