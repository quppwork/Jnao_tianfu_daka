/** 与后端 nickname_policy 一致的客户端校验 */

const FORBIDDEN_EXACT = new Set([
  'admin', 'administrator', 'root', 'system', 'test', 'null', 'undefined',
  '管理员', '系统', '官方', '客服', '运营',
])

const FORBIDDEN_SUBSTR = [
  /fuck|shit|bitch|porn|sex|nazi/i,
  /习近平|法轮功|六四|台独|藏独|疆独/,
  /admin|root|system/i,
]

const ILLEGAL_CHARS = /[<>\/\\|@#$%^&*()+=;:"'`~]/

function rejectForbidden(text, fieldLabel) {
  const lower = text.toLowerCase()
  if (FORBIDDEN_EXACT.has(lower)) {
    return `${fieldLabel}不符合规范，请更换`
  }
  for (const pat of FORBIDDEN_SUBSTR) {
    if (pat.test(text)) return `${fieldLabel}含有不允许的内容`
  }
  return null
}

/** @returns {string|null} */
export function validateRealNameClient(name, fieldLabel = '真实姓名') {
  const value = (name || '').trim()
  if (!value) return `请填写${fieldLabel}`
  if (value.length < 2 || value.length > 20) return `${fieldLabel}需为2-20个字符`
  if (!/^[\u4e00-\u9fa5·]{2,20}$/.test(value)) {
    return `${fieldLabel}请使用中文姓名（可含·）`
  }
  return rejectForbidden(value, fieldLabel)
}

/** @returns {string|null} */
export function validateNicknameClient(nickname, fieldLabel = '昵称') {
  const value = (nickname || '').trim()
  if (value.length < 2 || value.length > 20) return `${fieldLabel}需为2-20个字符`
  if (ILLEGAL_CHARS.test(value)) return `${fieldLabel}含非法字符`
  if (/^\d+$/.test(value)) return `${fieldLabel}不能为纯数字`
  if (/(.)\1{3,}/.test(value)) return `${fieldLabel}过于简单，请更换`
  return rejectForbidden(value, fieldLabel)
}
