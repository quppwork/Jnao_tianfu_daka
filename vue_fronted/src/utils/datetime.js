/**
 * 格式化为北京时间 YYYY-MM-DD HH:mm
 * 约定：后端 naive 时间已是北京时间；带 Z/偏移的按 UTC 转上海时区
 */
export function formatDateTimeShanghai(value) {
  if (!value) return '—'
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(value)) return value

  const s = String(value)
  // 无时区 ISO：已是北京时间，直接展示
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(s) && !/[Z+-]\d{2}/.test(s.slice(10))) {
    return s.replace('T', ' ').slice(0, 16)
  }

  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('sv-SE', { timeZone: 'Asia/Shanghai' }).slice(0, 16)
}

/** 短格式 M/D HH:mm，用于列表 */
export function formatDateTimeShortShanghai(value) {
  const full = formatDateTimeShanghai(value)
  if (!full || full === '—') return ''
  const m = full.match(/^(\d{4})-(\d{2})-(\d{2}) (\d{2}:\d{2})$/)
  if (!m) return full
  return `${parseInt(m[2], 10)}/${parseInt(m[3], 10)} ${m[4]}`
}
