/** 学科答疑 — 拍照/相册权限与选图（手机端优先） */

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
  return source === 'camera' && systemPlatform() === 'web' && !isMobileH5()
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
