/**
 * 后端 API 统一入口（兼容旧 import，无循环依赖）
 *
 * 依赖方向:
 *   api/client.js  ←  session + HTTP 底座
 *        ↑
 *   api/{profile,talent,training,guide,qa,growth,dev,account}.js
 *   userApiCore.js（认证/家长/管理员）
 *        ↑
 *   userApi.js（本文件，仅 re-export）
 */
export * from './api/client.js'
export * from './userApiCore.js'
export * from './api/profile.js'
export * from './api/talent.js'
export * from './api/training.js'
export * from './api/guide.js'
export * from './api/qa.js'
export * from './api/growth.js'
export * from './api/dev.js'
export * from './api/account.js'
