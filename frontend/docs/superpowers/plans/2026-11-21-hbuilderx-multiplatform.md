# HBuilderX 三端实施计划

本文件保留现有 Vue 3 CLI 工程的验证记录。原地改造以 [uni-app x 实施计划](2026-11-21-uni-app-x-in-place.md) 为准。

目标是在 HBuilderX 中打开并运行现有工程，逐步让微信小程序、Android 和 iOS 跑通首发功能。H5 继续作为回归目标。

保留 uni-app Vue 3 CLI 工程和现有 FastAPI 接口。参考 `Jnao_UniApp` 的三端验证流程与网络分层，在本工程的 `src/manifest.json` 中配置应用身份。生产签名和证书通过 HBuilderX 管理，凭据留在版本库外。

## 1. 建立 HBuilderX 运行基线

- [x] 导入 `vue_fronted`，确认 HBuilderX 将其识别为 `UniApp_VUE`。
- [x] 使用锁文件安装依赖。实测 Node.js 24.9.0、npm 12.0.2、HBuilderX 5.34、uni-app 编译器 5.07。npm 给出了 Node.js 版本兼容提示，依赖安装和以下编译已完成。
- [x] HBuilderX 启动 Web 于 `http://localhost:5185/`。在干净的 Chrome 会话中验证入口 → 孩子登录表单 → 返回选择 → 家长登录表单，无未捕获的页面异常。本机后端 `127.0.0.1:8012` 未监听，`/api/ping` 和 `/api/meta/version` 返回 500，实际登录未验。
- [x] HBuilderX 的 `launch mp-weixin --compile true`、`launch app-android --compile true`、`launch app-ios --iosTarget simulator --compile true` 均报告编译成功。命令都通过 `--project` 指定 `vue_fronted`，产物位于 `dist/dev` 的 `mp-weixin` 和 `app-plus`。App 端产物是开发资源。
- [ ] 有设备时从 HBuilderX 运行到 Android 和 iOS 基座。微信用开发者工具预览，分别记录模拟与真机结果。

HBuilderX 运行后生成了 `.hbuilderx/launch.json`，配置 Android 与 iOS 模拟器目标的标准基座。本机 ADB 未发现设备。Chrome DevTools MCP 的浏览器配置目录被占用，Web 验收改用独立 Chrome 会话。

## 2. 适配网络、会话和 AI 对话

主要入口为 `src/utils/api/client.js`、`src/utils/api/auth.js`、`src/utils/appSession.js` 和 `src/App.vue`。

- [ ] 保留 H5 的同源代理。为 App 和微信配置可达的测试 HTTPS API 地址，在请求底座集中处理普通 JSON 请求、超时、取消和鉴权头。
- [ ] 将登录会话读写移到现有会话层，使用目标平台的存储能力，保留学生、家长、管理员槽位。验收登录、杀进程后恢复、切换账号及过期退出。
- [ ] 在 Android、iOS、微信各验证一次现有 SSE 协议的逐块消费、取消、中文分片和断网行为。根据这些结果选定各端传输方式，复用事件解析及页面回调。
- [ ] 按登录 → 大宇首页 → 发消息 → 逐字回复 → 退出的顺序完成真机验收，使用测试账户和测试后端。

## 3. 适配测评、训练和媒体

入口为 `src/components/dayu-frame/dayu-frame.vue`、`src/pages/talent/`、`src/pages/report/`、`src/pages/training/` 和 `src/pages/qa/`。

- [ ] 优先适配测评中心与报告。对 App 或微信继续用 WebView 的页面，验证域名或本地资源可达、宿主导航、数据传递和返回。需要重新实现的核心交互使用 uni-app 页面，并验证外部报告入口。
- [ ] 按现有后端接口适配相机、相册、录音和文件上传，覆盖拒绝授权及再次开启权限。验证训练音频、计时、打卡及切后台后恢复。
- [ ] 每次改动按受影响平台验证安全区、键盘和系统返回。测试用例覆盖真实实现，保留原有 H5 行为的回归检查。

## 4. 准备签名包和微信预览

- [ ] 核对并使用获准的 DCloud AppID、微信小程序 AppID、Android 包名和 iOS Bundle ID。校验微信请求域名和业务域名。
- [ ] 在 `src/manifest.json` 的 `app-plus.distribute` 配置首发所需权限、图标和系统版本，按已选发行渠道准备签名。
- [ ] 用 HBuilderX 生成签名安装包并在对应真机安装。微信走体验版或开发者预览。逐端记录编译产物、安装结果、核心流程和未验证项。

本轮重跑 Vitest，253 项通过、2 项家长跳转断言失败，和清理前基线一致。触及会话和导航时按当前产品路由核对这两项预期。
