/** 与后端 password_policy 一致的客户端校验 */

const WEAK_PASSWORDS = new Set([
  '123456', '12345678', '123456789', '111111', '000000', '654321',
  'password', 'qwerty', 'abc123', 'abc12345', '123123', '888888',
  '666666', 'password1', 'qwerty123',
])

export const PASSWORD_HINT = '密码需8-32位，且同时包含大写字母、小写字母和数字'

export function passwordMeetsPolicy(password) {
  const pwd = String(password || '').trim()
  if (pwd.length < 8 || pwd.length > 32) return false
  if (!/[a-z]/.test(pwd)) return false
  if (!/[A-Z]/.test(pwd)) return false
  if (!/\d/.test(pwd)) return false
  if (WEAK_PASSWORDS.has(pwd.toLowerCase())) return false
  return true
}

/** @returns {string|null} 错误文案，通过则 null */
export function validatePasswordClient(password, fieldLabel = '密码') {
  if (!passwordMeetsPolicy(password)) {
    return `${fieldLabel}${PASSWORD_HINT}`
  }
  return null
}
