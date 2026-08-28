# API 域模块

按业务拆分的前端 API 封装。页面可继续 `import { … } from '@/utils/userApi.js'`。

| 文件 | 职责 |
|------|------|
| `../userApiCore.js` | session / HTTP / 认证 / 家长 / 管理员 |
| `profile.js` | 用户资料 |
| `talent.js` | 天赋测评 |
| `training.js` | 今日训练 + 选修 |
| `guide.js` | 首页引导对话 |
| `qa.js` | 学科答疑 + 语音 |
| `growth.js` | 成长里程碑 |
| `dev.js` | 开发者工具 |
| `account.js` | 切换孩子账号 |

新代码建议按域引入，例如：

```js
import { sendGuideMessage } from '@/utils/api/guide.js'
```
