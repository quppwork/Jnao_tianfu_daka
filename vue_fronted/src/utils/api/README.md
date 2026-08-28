# API 层（无循环依赖）

```
api/client.js          ← session + HTTP 底座（唯一底层）
      ↑
api/{auth,parent,admin,profile,talent,training,guide,qa,growth,dev,account}.js
      ↑
userApi.js / userApiCore.js  ← 兼容聚合 export
```

## 规则

1. **禁止** `api/*` 域模块互相 import（`parent → auth` 仅允许读 `_readStoredRole`），也禁止依赖 `userApi.js`
2. 域模块只允许：`import { … } from './client.js'`（session/HTTP）
3. 管理员/孩子 session 读写在 `client.js`；`auth.js` / `admin.js` 只做登录与业务 API
4. 新代码优先按域引入，例如：`import { sendGuideMessage } from '@/utils/api/guide.js'`
