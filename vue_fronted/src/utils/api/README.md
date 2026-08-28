# API 层（无循环依赖）

```
api/client.js          ← session + HTTP 底座（唯一底层）
      ↑
api/{profile,talent,training,guide,qa,growth,dev,account}.js
userApiCore.js         ← 认证 / 家长 / 管理员
      ↑
userApi.js             ← 兼容聚合 export（页面可继续从这里 import）
```

## 规则

1. **禁止** `api/*` 域模块互相 import，也禁止依赖 `userApi.js` / `userApiCore.js`
2. 域模块只允许：`import { apiJson, withUser, ... } from './client.js'`
3. 新代码优先按域引入，例如：`import { sendGuideMessage } from '@/utils/api/guide.js'`

## 循环依赖

当前 utils 内 import 图为 **DAG（无环）**。`useLoginFlow` 已改为只依赖 `api/client.js`，避免为两个函数加载全部域模块。
