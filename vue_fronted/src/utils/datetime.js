/** 将 ISO / 时间戳格式化为北京时间 YYYY-MM-DD HH:mm */
export function formatDateTimeShanghai(value) {
  if (!value) return '—'
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(value)) return value

  let s = String(value)
  // 无时区的 ISO 字符串按 UTC 解析（兼容历史会话数据）
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(s) && !/[Z+-]\d{2}/.test(s.slice(10))) {
    s = `${s}Z`
  }

  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('sv-SE', { timeZone: 'Asia/Shanghai' }).slice(0, 16)
}
