/**
 * 后端 API 统一入口（兼容旧 import，无循环依赖）
 *
 *   api/client.js
 *        ↑
 *   api/{auth,parent,admin,profile,talent,training,guide,qa,growth,dev,account}.js
 *        ↑
 *   userApi.js
 */
export * from './api/client.js'
export * from './api/auth.js'
export * from './api/parent.js'
export * from './api/admin.js'
export * from './api/profile.js'
export * from './api/talent.js'
export * from './api/training.js'
export * from './api/guide.js'
export * from './api/qa.js'
export * from './api/growth.js'
export * from './api/dev.js'
export * from './api/account.js'
