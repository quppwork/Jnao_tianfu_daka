/**
 * 后端 API 统一入口（兼容旧 import）
 *
 * 实现拆分:
 *   userApiCore.js  — session / HTTP / 认证 / 家长 / 管理员
 *   api/profile.js | talent.js | training.js | guide.js | qa.js | growth.js | dev.js | account.js
 *
 * 新代码可按域引入，例如: import { sendGuideMessage } from '@/utils/api/guide.js'
 */
export * from './userApiCore.js'
export * from './api/profile.js'
export * from './api/talent.js'
export * from './api/training.js'
export * from './api/guide.js'
export * from './api/qa.js'
export * from './api/growth.js'
export * from './api/dev.js'
export * from './api/account.js'
