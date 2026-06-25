/** H5 浏览器原生录音（比 uni.getRecorderManager 在手机浏览器更可靠） */

export function isWebH5() {
  try {
    return uni.getSystemInfoSync().uniPlatform === 'web'
  } catch (_) {
    return typeof window !== 'undefined'
  }
}

export function browserCanUseMic() {
  return typeof window !== 'undefined' && Boolean(window.isSecureContext)
}

export function buildMicAccessHint() {
  if (typeof window === 'undefined' || window.isSecureContext) return ''
  const host = location.host
  if (location.protocol === 'http:') {
    return `语音需 HTTPS。请用 https://${host} 打开；若仍有证书提示，在电脑上运行 scripts/setup_dev_https.ps1`
  }
  return '当前连接不安全，语音不可用。请改用 HTTPS 并安装受信任开发证书（见 scripts/setup_dev_https.ps1）'
}

function pickMimeType() {
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4',
    'audio/aac',
    'audio/ogg;codecs=opus',
  ]
  if (typeof MediaRecorder === 'undefined') return ''
  for (const t of candidates) {
    if (MediaRecorder.isTypeSupported(t)) return t
  }
  return ''
}

export class BrowserVoiceRecorder {
  constructor() {
    this.stream = null
    this.mediaRecorder = null
    this.chunks = []
    this.mimeType = ''
  }

  async start() {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('当前浏览器不支持录音')
    }
    this.chunks = []
    this.mimeType = pickMimeType()
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        channelCount: 1,
      },
      video: false,
    })
    const options = this.mimeType ? { mimeType: this.mimeType } : undefined
    this.mediaRecorder = new MediaRecorder(this.stream, options)
    this.mediaRecorder.ondataavailable = (e) => {
      if (e.data?.size) this.chunks.push(e.data)
    }
    this.mediaRecorder.start(200)
  }

  stop() {
    return new Promise((resolve, reject) => {
      if (!this.mediaRecorder || this.mediaRecorder.state === 'inactive') {
        this._cleanup()
        reject(new Error('未录到音频'))
        return
      }
      this.mediaRecorder.onstop = () => {
        const type = this.mimeType || this.chunks[0]?.type || 'audio/webm'
        const blob = new Blob(this.chunks, { type })
        this._cleanup()
        if (!blob.size) {
          reject(new Error('未录到音频'))
          return
        }
        resolve({ blob, filename: mimeToFilename(type) })
      }
      this.mediaRecorder.onerror = () => {
        this._cleanup()
        reject(new Error('录音失败'))
      }
      try {
        this.mediaRecorder.stop()
      } catch (e) {
        this._cleanup()
        reject(e)
      }
    })
  }

  cancel() {
    try {
      if (this.mediaRecorder?.state === 'recording') this.mediaRecorder.stop()
    } catch (_) { /* ignore */ }
    this._cleanup()
    this.chunks = []
  }

  _cleanup() {
    this.stream?.getTracks().forEach((t) => t.stop())
    this.stream = null
    this.mediaRecorder = null
  }
}

function mimeToFilename(type) {
  if (type.includes('mp4') || type.includes('aac')) return 'recording.m4a'
  if (type.includes('ogg')) return 'recording.ogg'
  return 'recording.webm'
}

/** 启动时探测麦克风，返回提示文案（空=可用） */
export async function probeMicrophoneAccess() {
  if (!browserCanUseMic()) return buildMicAccessHint()
  if (!navigator.mediaDevices?.getUserMedia) return '当前浏览器不支持麦克风'
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
    stream.getTracks().forEach((t) => t.stop())
    return ''
  } catch (e) {
    if (e.name === 'NotAllowedError') {
      return '麦克风权限被拒：请在浏览器地址栏或系统设置中允许麦克风'
    }
    if (e.name === 'NotFoundError') return '未检测到麦克风设备'
    if (e.name === 'NotSupportedError') {
      return '证书未受信任，iPhone 可能无法录音。请运行 scripts/setup_dev_https.ps1 安装开发证书'
    }
    return `麦克风不可用（${e.message || e.name}）。开发环境请运行 scripts/setup_dev_https.ps1`
  }
}
