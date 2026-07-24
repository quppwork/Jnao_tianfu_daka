/**
 * 开发态：后端进程重启后强制清本地登录（生产 force_relogin_on_boot=false 不生效）。
 * boot_id 存 localStorage，以便关标签后再开仍能发现后端已换进程。
 */

import { clearAllAuthSessions } from './appSession.js'

const BOOT_ID_KEY = 'jnao_server_boot_id'

/**
 * @returns {{ cleared: boolean, boot_id?: string, skipped?: boolean, maintenance?: boolean }}
 */
export async function applyDevBootReloginIfNeeded() {
  let data
  try {
    const res = await fetch('/api/ping', { cache: 'no-store' })
    if (!res.ok) return { cleared: false, skipped: true }
    data = await res.json()
  } catch (_) {
    return { cleared: false, skipped: true }
  }

  if (data?.maintenance) {
    return {
      cleared: false,
      skipped: true,
      maintenance: true,
      boot_id: data.boot_id,
    }
  }

  if (!data?.force_relogin_on_boot || !data.boot_id) {
    return { cleared: false, skipped: true, boot_id: data?.boot_id }
  }

  let prev = ''
  try {
    prev = localStorage.getItem(BOOT_ID_KEY) || ''
  } catch (_) { /* ignore */ }

  try {
    localStorage.setItem(BOOT_ID_KEY, data.boot_id)
  } catch (_) { /* ignore */ }

  if (prev && prev !== data.boot_id) {
    clearAllAuthSessions()
    try {
      // 保留新 boot_id（clearAllAuth 不碰此键）
      localStorage.setItem(BOOT_ID_KEY, data.boot_id)
    } catch (_) { /* ignore */ }
    console.info(
      '[auth] 开发模式：检测到后端进程重启，已清除本地登录态，请重新登录',
    )
    return { cleared: true, boot_id: data.boot_id }
  }

  return { cleared: false, boot_id: data.boot_id }
}
