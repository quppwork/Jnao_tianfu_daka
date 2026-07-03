/** 学科答疑 — 拍照/相册权限与选图 + 图片压缩（手机端优先） */

/**
 * H5 端压缩图片：限制最大宽度，超出则等比缩放
 * Android/iOS 原生端 uni.chooseImage 已传 sizeType:['compressed']，无需重复压缩
 * @param {File|Blob} file
 * @param {number} maxWidth
 * @returns {Promise<File>}
 */
export async function compressImage(file, maxWidth = 1200) {
  // 非 H5 环境不压缩（原生 chooseImage 已压缩）
  if (!file || typeof Image === 'undefined') return file
  try {
    const bmp = await createImageBitmap(file)
    if (bmp.width <= maxWidth) { bmp.close(); return file }
    const ratio = maxWidth / bmp.width
    const canvas = document.createElement('canvas')
    canvas.width = maxWidth
    canvas.height = Math.round(bmp.height * ratio)
    const ctx = canvas.getContext('2d')
    ctx.drawImage(bmp, 0, 0, canvas.width, canvas.height)
    bmp.close()
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.85))
    return new File([blob], file.name || 'photo.jpg', { type: 'image/jpeg' })
  } catch (_) {
    return file  // 压缩失败不影响发送
  }
}

function systemPlatform() {
  try {
    const info = uni.getSystemInfoSync()
    return info.uniPlatform || info.platform || 'web'
  } catch (_) {
    return 'web'
  }
}

/** 手机浏览器 / 小程序 / App */
export function isMobileH5() {
  try {
    const info = uni.getSystemInfoSync()
    if (info.platform === 'ios' || info.platform === 'android') return true
  } catch (_) { /* ignore */ }
  if (typeof navigator !== 'undefined') {
    return /Android|iPhone|iPad|iPod|Mobile|Harmony/i.test(navigator.userAgent)
  }
  return false
}

/** 电脑浏览器 H5：uni.chooseImage(camera) 只会弹出「选文件」，需改用摄像头预览 */
export function needsWebcamCapture(source) {
  return source === 'camera' && systemPlatform() === 'web'
}

/** H5 是否可用 getUserMedia 拍照（需 HTTPS） */
export function browserCanUseCamera() {
  return (
    typeof window !== 'undefined'
    && Boolean(window.isSecureContext)
    && typeof navigator !== 'undefined'
    && Boolean(navigator.mediaDevices?.getUserMedia)
  )
}

/**
 * 将 uni.chooseImage 临时路径转为可预览的 blob（H5 <image> 无法直接显示部分 temp 路径）
 * @returns {{ file: File, preview: string, path: string }}
 */
export async function buildPendingImageFromPath(path) {
  const resp = await fetch(path)
  if (!resp.ok) throw new Error('读取图片失败，请重新选择')
  const blob = await resp.blob()
  if (!blob.size) throw new Error('图片为空，请重新拍摄')
  const preview = URL.createObjectURL(blob)
  const ext = blob.type.includes('png') ? 'png' : 'jpg'
  const file = new File([blob], `photo.${ext}`, { type: blob.type || 'image/jpeg' })
  return { file, preview, path: preview }
}

/**
 * 原生 file input 拍照/选图（DeepSeek 式 fallback，强制后置摄像头）
 * @param {'environment'|'user'|''} captureMode
 */
export function pickImageViaNativeInput(captureMode = 'environment') {
  return new Promise((resolve, reject) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'image/*'
    if (captureMode) input.setAttribute('capture', captureMode)
    input.style.cssText = 'position:fixed;left:-9999px;opacity:0'
    document.body.appendChild(input)
    const cleanup = () => {
      try { document.body.removeChild(input) } catch (_) { /* ignore */ }
    }
    input.addEventListener('change', () => {
      const file = input.files?.[0]
      cleanup()
      if (!file || !file.size) {
        reject(new Error('cancel'))
        return
      }
      const preview = URL.createObjectURL(file)
      resolve({ file, preview, path: preview })
    })
    input.addEventListener('cancel', () => {
      cleanup()
      reject(new Error('cancel'))
    })
    input.click()
  })
}

function openSettingModal(permissionName) {
  return new Promise((resolve, reject) => {
    uni.showModal({
      title: '需要授权',
      content: `请允许访问${permissionName}，以便上传题目图片`,
      confirmText: '去设置',
      cancelText: '取消',
      success(res) {
        if (res.confirm && uni.openSetting) {
          uni.openSetting({
            success(setting) {
              if (setting.authSetting) resolve(setting.authSetting)
              else reject(new Error('denied'))
            },
            fail: () => reject(new Error('denied')),
          })
        } else {
          reject(new Error('denied'))
        }
      },
      fail: () => reject(new Error('denied')),
    })
  })
}

/** 微信小程序 scope 授权 */
function ensureMpScope(scope, label) {
  return new Promise((resolve, reject) => {
    uni.getSetting({
      success(res) {
        const auth = res.authSetting || {}
        if (auth[scope]) {
          resolve()
          return
        }
        uni.authorize({
          scope,
          success: () => resolve(),
          fail: () => {
            openSettingModal(label).then(() => resolve()).catch(reject)
          },
        })
      },
      fail: () => resolve(),
    })
  })
}

/** App Android 运行时权限 */
function ensureAppAndroidPermissions(permissions, label) {
  return new Promise((resolve, reject) => {
    if (typeof plus === 'undefined' || !plus.android?.requestPermissions) {
      resolve()
      return
    }
    plus.android.requestPermissions(
      permissions,
      (result) => {
        const denied = [
          ...(result.deniedAlways || []),
          ...(result.deniedPresent || []),
        ]
        if (denied.length) {
          openSettingModal(label).then(resolve).catch(reject)
        } else {
          resolve()
        }
      },
      () => reject(new Error('denied')),
    )
  })
}

/** 打开相机前申请权限 */
export async function ensureCameraPermission() {
  const platform = systemPlatform()
  if (platform === 'mp-weixin') {
    await ensureMpScope('scope.camera', '相机')
    return
  }
  if (platform === 'app') {
    await ensureAppAndroidPermissions(['android.permission.CAMERA'], '相机')
    return
  }
  // H5：由浏览器在调起相机时弹窗授权
}

/** 打开相册前申请权限 */
export async function ensureAlbumPermission() {
  const platform = systemPlatform()
  if (platform === 'mp-weixin') {
    // 部分基础库支持 scope.album；不支持时 chooseImage 会自行申请
    try {
      await ensureMpScope('scope.album', '相册')
    } catch (_) {
      /* chooseImage 相册路径仍可尝试 */
    }
    return
  }
  if (platform === 'app') {
    const perms = [
      'android.permission.READ_EXTERNAL_STORAGE',
      'android.permission.READ_MEDIA_IMAGES',
    ]
    await ensureAppAndroidPermissions(perms, '相册')
    return
  }
}

/**
 * @param {'camera'|'album'} source
 * @returns {Promise<string>} tempFilePath
 */
export async function chooseQuestionImage(source) {
  if (needsWebcamCapture(source)) {
    const err = new Error('webcam')
    err.code = 'WEBCAM'
    throw err
  }

  if (source === 'camera') {
    await ensureCameraPermission()
  } else {
    await ensureAlbumPermission()
  }

  const sourceType = source === 'camera' ? ['camera'] : ['album']
  return new Promise((resolve, reject) => {
    uni.chooseImage({
      count: 1,
      sizeType: ['compressed'],
      sourceType,
      success(res) {
        const path = res.tempFilePaths?.[0]
        if (path) resolve(path)
        else reject(new Error('未选择图片'))
      },
      fail(err) {
        const msg = err?.errMsg || ''
        if (msg.includes('cancel')) reject(new Error('cancel'))
        else if (msg.includes('auth') || msg.includes('deny')) {
          reject(new Error('权限被拒绝，请在系统设置中允许相机/相册访问'))
        } else {
          reject(new Error('选择图片失败'))
        }
      },
    })
  })
}
