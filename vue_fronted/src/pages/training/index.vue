<template>
  <view class="app">
    <!-- 扫描线 -->
    <view class="cyber-scanlines"></view>
    <view class="nav">
      <view class="nav-back" @click="goBack">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#8b949e" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      </view>
      <text class="nav-title cyber-glitch" @click="triggerGlitch">今日训练</text>
      <view class="nav-actions">
        <view class="nav-history" @click="openHistory"><text>记录</text></view>
        <view class="nav-dev" :class="{ active: devMode }" @click="toggleDevMode">
          <text>{{ devMode ? 'DEV ✓' : 'DEV' }}</text>
        </view>
      </view>
    </view>

    <view class="body">
      <!-- Plan · 时间轴总览 -->
      <view class="card plan-card" data-augmented-ui="tl-clip tr-clip br-clip bl-clip border">
        <view class="plan-header">
          <text class="plan-label">📋 今日方案</text>
          <text v-if="talentLabel && !planLoading" class="plan-header-meta">{{ talentLabel }} · 第 {{ lessonIndex }} 课</text>
        </view>
        <!-- Loading -->
        <view v-if="planLoading" class="plan-loading-wrap">
          <view class="plan-loading-ring">
            <view class="plr-core"></view>
            <view class="plr-arc"></view>
          </view>
          <text class="plan-loading-title">AI 正在生成今日方案</text>
          <view class="plan-loading-bar">
            <view class="plan-loading-bar-fill"></view>
          </view>
          <text class="plan-loading-hint">首次生成约需 3~5 秒，分析天赋与训练进度...</text>
        </view>

        <!-- Done -->
        <view v-else-if="planJustGenerated" class="plan-done-wrap">
          <text class="plan-done-icon">✅</text>
          <text class="plan-done-title">方案生成完毕</text>
          <text class="plan-done-sub">请开始今日的训练</text>
        </view>

        <!-- Plan content (loaded) -->
        <template v-else>
          <view v-if="todayPlan?.status === 'transition' || dayTransition" class="plan-transition-wrap">
            <text class="plan-transition-icon">🌙</text>
            <text class="plan-transition-title">训练日切换中</text>
            <text class="plan-transition-sub">{{ aiPlanText || '约5分钟后开始新的一天' }}</text>
          </view>
          <view v-else-if="planPhases.length" class="plan-timeline">
            <view
              v-for="(phase, pi) in planPhases"
              :key="phase.block"
              class="tl-phase"
            >
              <view class="tl-rail">
                <view class="tl-node" :class="phase.nodeClass">
                  <text class="tl-node-icon">{{ phase.nodeIcon }}</text>
                </view>
                <view v-if="pi < planPhases.length - 1" class="tl-line"></view>
              </view>
              <view class="tl-content">
                <view class="tl-node-row" @click="togglePhase(phase.block)">
                  <view class="tl-phase-head">
                    <text class="tl-phase-title">{{ phase.label }} · {{ phase.subtitle }}</text>
                    <view class="tl-phase-right">
                      <text class="tl-phase-meta">{{ phaseMetaText(phase) }}</text>
                      <text class="tl-phase-toggle">{{ planExpanded[phase.block] ? '▾' : '▸' }}</text>
                    </view>
                  </view>
                </view>
                <view v-if="planExpanded[phase.block]" class="tl-items">
                  <view
                    v-for="item in phase.items"
                    :key="item.id"
                    class="tl-item"
                    @click="scrollToPhase(phase.block)"
                  >
                    <text class="tl-item-icon">{{ itemStatusIcon(item, phase) }}</text>
                    <text class="tl-item-title">{{ itemTypeEmoji(item) }} {{ item.title || '训练项' }}</text>
                    <text class="tl-item-right">
                      <text v-if="item.duration_min" class="tl-item-dur">{{ item.duration_min }}分钟</text>
                      <text class="tl-item-status" :class="itemStatusClass(item, phase)">{{ itemStatusLabel(item, phase) }}</text>
                    </text>
                  </view>
                </view>
              </view>
            </view>
          </view>
          <view v-else class="plan-empty">
            <text class="plan-empty-text">暂无训练项，请先设置时长并开始训练</text>
          </view>

          <view v-if="planTotalCount > 0" class="plan-progress">
            <view class="plan-progress-track">
              <view class="plan-progress-fill" :style="{ width: planProgressPct + '%' }"></view>
            </view>
            <text class="plan-progress-text">{{ planCompletedCount }}/{{ planTotalCount }} 项已完成</text>
          </view>

          <view v-if="aiPlanText" class="plan-ai-box">
            <text class="plan-ai-label">💬 教练</text>
            <text class="plan-ai-text">{{ aiPlanText }}</text>
          </view>
          <text v-if="needAssessment" class="plan-warn" @click="goTalent">尚未完成天赋测评，点击前往测评 ›</text>
        </template>
      </view>

      <!-- Summary -->
      <view
        class="card summary-card"
        :class="{ 'summary-empty': !submittedCards.length }"
        @click="submittedCards.length ? showSummary = true : null"
      >
        <template v-if="submittedCards.length">
          <text class="summary-label">📝 打卡训练总结</text>
          <text class="summary-text">今日已打卡 {{ submittedCards.length }} 项 · {{ checkedPhaseCount }} 个阶段</text>
          <text class="summary-more">点击管理打卡 ›</text>
          <view class="summary-attitude">
            <text class="sa-label">配合度</text>
            <view class="sa-grid">
              <view v-for="s in scores" :key="s.pct" class="sa-item" :class="{ active: summaryAttitude === s.pct }" @click.stop="setAttitude(s.pct)">
                <text class="sa-pct">{{ s.pct }}%</text>
                <text class="sa-emoji">{{ s.emoji }}</text>
              </view>
            </view>
          </view>
        </template>
        <template v-else>
          <text class="summary-empty-text">今日还未打卡 · 完成训练后点击下方按钮记录</text>
        </template>
      </view>

      <!-- 今日训练时长 -->
      <view class="card time-card">
        <view class="time-header">
          <text class="plan-label">⏰ 今日训练时长</text>
          <text v-if="timerPhase === 'running'" class="time-status-tag running">进行中</text>
          <text v-else-if="timerPhase === 'expired'" class="time-status-tag expired">已结束</text>
        </view>

        <view v-if="timerPhase === 'setup'" class="time-setup">
          <view class="time-pickers">
            <picker mode="selector" :range="hourLabels" :value="hourIndex" @change="onHourPick">
              <view class="time-select">
                <text class="time-select-val">{{ selectedHours }}</text>
                <text class="time-select-unit">小时</text>
              </view>
            </picker>
            <picker mode="selector" :range="minuteLabels" :value="minuteIndex" @change="onMinutePick">
              <view class="time-select">
                <text class="time-select-val">{{ selectedMinutes }}</text>
                <text class="time-select-unit">分钟</text>
              </view>
            </picker>
          </view>
          <view class="time-start-btn" :class="{ disabled: !canStartTimer }" @click="startTrainingTimer">
            <text>开始训练</text>
          </view>
          <text class="time-setup-hint">选择本次训练时长，确认后开始倒计时</text>
        </view>

        <view v-else-if="timerPhase === 'running'" class="time-running">
          <text class="time-countdown">{{ countdownDisplay }}</text>
          <text class="time-running-hint">剩余时间 · 今日计划 {{ durationLabel }}</text>
        </view>

        <view v-else class="time-expired">
          <text class="time-expired-icon">🔒</text>
          <text class="time-expired-text">{{ globalLockTitle }}</text>
          <text class="time-expired-sub">{{ globalLockSub }}</text>
        </view>

        <view v-if="devMode" class="dev-panel">
          <text class="dev-panel-label">🔧 开发者测试</text>
          <view v-if="devStatusText" class="dev-status">
            <text>{{ devStatusText }}</text>
          </view>
          <view class="dev-actions">
            <view class="dev-action dev-action-primary" @click="devRefreshAll"><text>🔄 重置今日</text></view>
            <view class="dev-action" @click="devSimulate4amCutoffAction"><text>🌙 模拟4点</text></view>
            <view class="dev-action" @click="devGoNextDay"><text>🌅 新一天</text></view>
            <view class="dev-action" @click="devRefreshAiPlan"><text>🤖 刷新 AI</text></view>
          </view>
          <view class="dev-actions">
            <view class="dev-action" @click="devResetTimer"><text>⏱ 重置计时</text></view>
            <view class="dev-action" @click="devSimulateExpire"><text>⏰ 模拟结束</text></view>
            <view class="dev-action" @click="devUnlockNextPhase"><text>🔓 解锁下阶段</text></view>
          </view>
          <view class="dev-actions">
            <view class="dev-action dev-action-danger" @click="devClearAllHistory"><text>🗑 清空历史</text></view>
            <view class="dev-action dev-action-danger" @click="devResetTalentAction"><text>🧬 重置天赋</text></view>
          </view>
          <text class="dev-panel-hint">模拟4点 = 全局截止并隐藏昨日内容 · 新一天 = 4:05 后切换</text>
        </view>
      </view>

      <!-- 训练阶段（动态 A/B/C…，依据今日方案） -->
      <template v-if="!dayTransition && todayPlan?.status !== 'transition'" v-for="(phase, pi) in planPhases" :key="phase.block">
        <view v-if="pi > 0" class="divider"></view>
        <view :id="'phase-block-' + phase.block" class="phase-section">
          <text class="section-title" :class="{ dim: !phase.unlocked }">训练 {{ phase.block }}{{ phase.unlocked ? '' : ' 🔒' }}</text>

          <view class="media-block" :class="{ locked: isPhaseMediaLocked(phase) }">
            <view v-if="isPhaseMediaLocked(phase)" class="media-lock-overlay">
              <text class="media-lock-text">{{ phaseMediaLockText(phase) }}</text>
            </view>

            <template v-if="phase.items.length">
              <view
                v-for="(item, idx) in phase.items"
                :key="item.id || idx"
                class="step"
                :class="{
                  'step-preview-locked': !phase.unlocked,
                  'step-locked': phase.unlocked && isMediaLocked,
                  'step-watched': phase.unlocked && isItemWatched(item),
                }"
                @click="openPhaseMediaItem(item, phase)"
              >
                <view class="step-num" :class="{ 'step-num-done': isItemWatched(item), dim: !phase.unlocked }">{{ idx + 1 }}</view>
                <view class="step-content">
                  <text class="step-label" :class="{ 'dim-text': !phase.unlocked }">{{ itemLabel(item) }}</text>
                  <view class="step-box" :class="{ 'dim-box': !phase.unlocked }">{{ itemTypeEmoji(item) }} {{ item.title || '训练项' }}</view>
                  <text class="step-time" :class="{ 'dim-text': !phase.unlocked }">{{ itemStepHint(item, phase) }}</text>
                </view>
              </view>
            </template>
            <view v-else class="step dim-step">
              <view class="step-num dim">1</view>
              <view class="step-content">
                <text class="step-label dim-text">训练项</text>
                <view class="step-box dim-box">暂无内容</view>
                <text class="step-time dim-text">请先生成今日方案</text>
              </view>
            </view>
          </view>

          <text class="lock-tip">{{ phaseTip(phase) }}</text>

          <view class="checkin-block" :class="{ locked: !canPhaseCheckin(phase) }">
            <view v-if="!canPhaseCheckin(phase)" class="checkin-lock-overlay">
              <text class="checkin-lock-text">{{ phaseCheckinLockText(phase) }}</text>
            </view>
            <view class="btn-checkin btn-cyber" data-augmented-ui="tl-clip br-clip border" @click="openPicker(phase.block)">
              <text>{{ phase.allDone ? '✅ 训练 ' + phase.block + ' 已打卡' : '✅ 训练 ' + phase.block + ' 打卡' }}</text>
            </view>
          </view>
        </view>
      </template>

      <!-- 打卡弹窗（各阶段共用） -->
      <view v-if="showPicker && activePickerBlock" class="picker-overlay" @click="closePicker">
        <view class="picker-card checkin-modal" @click.stop>
          <view class="modal-header">
            <text class="modal-title">训练 {{ activePickerBlock }} 打卡</text>
            <view class="modal-close" @click="closePicker">✕</view>
          </view>

          <!-- 能力选择 -->
          <view class="picker-panel" data-augmented-ui="tl-clip tr-clip br-clip bl-clip border">
            <view class="picker-panel-header">
              <text class="pph-dot">◆</text>
              <text class="pph-title">选择训练能力</text>
              <text class="pph-dot">◆</text>
            </view>
            <view class="picker-grid">
              <view v-for="(item, ai) in abilities" :key="item" class="picker-item" :class="{ active: hasPickerCard(item), 'ability-spark': sparkAbi === ai }" @click="togglePickerCard(item, ai)">
                <text class="pi-text">{{ item }}</text>
              </view>
            </view>
          </view>

          <!-- 已选卡片列表 -->
          <TransitionGroup v-if="pickerCards.length" name="card">
            <view v-for="(card, idx) in pickerCards" :key="card.name + '-' + idx" class="form-card">
            <view class="scan-line"></view>
            <view class="form-header">
              <text class="form-title">{{ card.name }} — 训练记录</text>
              <view class="form-del" @click="removePickerCard(idx)">✕</view>
            </view>

            <template v-if="card.name === '极速运算'">
              <view class="form-row">
                <text class="form-label">时间</text>
                <input class="form-input" v-model="card.time" placeholder="训练时长（分钟）" type="number" />
              </view>
              <view class="form-row">
                <text class="form-label">内容</text>
                <view class="form-tags">
                  <text class="ftag" :class="{ on: card.tag === '加减法' }" @click="card.tag = '加减法'">加减法</text>
                  <text class="ftag" :class="{ on: card.tag === '乘除法' }" @click="card.tag = '乘除法'">乘除法</text>
                  <text class="ftag" :class="{ on: card.tag === '混合运算' }" @click="card.tag = '混合运算'">混合运算</text>
                  <text class="ftag" :class="{ on: card.tag === '口算' }" @click="card.tag = '口算'">口算</text>
                </view>
              </view>
              <view class="form-row">
                <text class="form-label">结果</text>
                <view class="form-inline">
                  <input class="form-input short" v-model="card.count" placeholder="题数" type="number" />
                  <text class="form-unit">题</text>
                  <input class="form-input short" v-model="card.accuracy" placeholder="正确率" type="number" />
                  <text class="form-unit">%</text>
                </view>
              </view>
              <view class="form-row">
                <text class="form-label">图片/视频</text>
                <view class="form-file-wrap">
                  <view class="file-btn" @click="pickPickerFile(idx)"><text>📷 选择文件</text></view>
                  <view v-if="card.files && card.files.length" class="file-previews">
                    <view v-for="(f,fi) in card.files" :key="fi" class="file-preview">
                      <image v-if="f.type === 'image'" :src="f.url" mode="aspectFill" class="preview-img" />
                      <video v-if="f.type === 'video'" :src="f.url" class="preview-video" />
                      <text class="file-del" @click="removePickerFile(idx, fi)">✕</text>
                    </view>
                  </view>
                </view>
              </view>
              <view class="form-row">
                <text class="form-label">备注</text>
                <textarea class="form-textarea" v-model="card.note" placeholder="补充说明..." style="height:50px;" />
              </view>
            </template>
            <template v-else-if="card.name === '扫描速记'">
              <view class="form-row">
                <text class="form-label">材料类型</text>
                <view class="form-tags">
                  <text class="ftag" :class="{ on: card.materialType === '书' }" @click="card.materialType = '书'">书</text>
                  <text class="ftag" :class="{ on: card.materialType === '文章' }" @click="card.materialType = '文章'">文章</text>
                  <text class="ftag" :class="{ on: card.materialType === '自定义' }" @click="card.materialType = '自定义'">自定义</text>
                </view>
              </view>
              <view class="form-row">
                <text class="form-label">材料名称</text>
                <input class="form-input" v-model="card.materialName" :placeholder="card.materialType === '书' ? '如：《西游记》' : card.materialType === '文章' ? '如：作文《我的姐姐》' : '如：圆周率前100位'" />
              </view>
              <view class="form-row">
                <text class="form-label">字数</text>
                <view class="form-inline">
                  <input class="form-input short" v-model="card.wordCount" placeholder="字数" type="number" />
                  <text class="form-unit">字</text>
                </view>
              </view>
              <view class="form-row">
                <text class="form-label">正背</text>
                <view class="form-inline">
                  <input class="form-input short" v-model="card.forwardTime" placeholder="用时" />
                  <text class="form-unit">·</text>
                  <input class="form-input short" v-model="card.forwardAcc" placeholder="准确度" />
                </view>
              </view>
              <view class="form-row">
                <text class="form-label">倒背</text>
                <view class="form-inline">
                  <input class="form-input short" v-model="card.backwardTime" placeholder="用时" />
                  <text class="form-unit">·</text>
                  <input class="form-input short" v-model="card.backwardAcc" placeholder="准确度" />
                </view>
              </view>
              <view class="form-row">
                <text class="form-label">图片/视频</text>
                <view class="form-file-wrap">
                  <view class="file-btn" @click="pickPickerFile(idx)"><text>📷 选择文件</text></view>
                  <view v-if="card.files && card.files.length" class="file-previews">
                    <view v-for="(f,fi) in card.files" :key="fi" class="file-preview">
                      <image v-if="f.type === 'image'" :src="f.url" mode="aspectFill" class="preview-img" />
                      <video v-if="f.type === 'video'" :src="f.url" class="preview-video" />
                      <text class="file-del" @click="removePickerFile(idx, fi)">✕</text>
                    </view>
                  </view>
                </view>
              </view>
              <view class="form-row">
                <text class="form-label">备注</text>
                <textarea class="form-textarea" v-model="card.note" placeholder="补充说明..." style="height:50px;" />
              </view>
            </template>
            <template v-else-if="card.name === '影像追忆'">
              <view class="form-row">
                <text class="form-label">使用工具</text>
                <view class="form-tags">
                  <text class="ftag" :class="{ on: card.tool === '书本' }" @click="card.tool = '书本'">书本</text>
                  <text class="ftag" :class="{ on: card.tool === '视频' }" @click="card.tool = '视频'">视频</text>
                  <text class="ftag" :class="{ on: card.tool === '自定义' }" @click="card.tool = '自定义'">自定义</text>
                </view>
              </view>
              <view class="form-row">
                <text class="form-label">时长</text>
                <input class="form-input" v-model="card.time" placeholder="训练时长（分钟）" type="number" />
              </view>
              <view class="form-row">
                <text class="form-label">材料</text>
                <textarea class="form-textarea" v-model="card.content" placeholder="如：一卜语文重要知识点" />
              </view>
              <view class="form-row">
                <text class="form-label">追忆率</text>
                <view class="form-inline">
                  <input class="form-input short" v-model="card.accuracy" placeholder="正确率" type="number" />
                  <text class="form-unit">%</text>
                </view>
              </view>
              <view class="form-row">
                <text class="form-label">图片/视频</text>
                <view class="form-file-wrap">
                  <view class="file-btn" @click="pickPickerFile(idx)"><text>📷 选择文件</text></view>
                  <view v-if="card.files && card.files.length" class="file-previews">
                    <view v-for="(f,fi) in card.files" :key="fi" class="file-preview">
                      <image v-if="f.type === 'image'" :src="f.url" mode="aspectFill" class="preview-img" />
                      <video v-if="f.type === 'video'" :src="f.url" class="preview-video" />
                      <text class="file-del" @click="removePickerFile(idx, fi)">✕</text>
                    </view>
                  </view>
                </view>
              </view>
              <view class="form-row">
                <text class="form-label">备注</text>
                <textarea class="form-textarea" v-model="card.note" placeholder="补充说明..." style="height:50px;" />
              </view>
            </template>
            <template v-else>
              <view class="form-row">
                <text class="form-label">时间</text>
                <input class="form-input" v-model="card.time" placeholder="训练时长/分钟" />
              </view>
              <view class="form-row">
                <text class="form-label">内容</text>
                <textarea class="form-textarea" v-model="card.content" placeholder="训练了什么内容？" />
              </view>
              <view class="form-row">
                <text class="form-label">结果</text>
                <textarea class="form-textarea" v-model="card.result" placeholder="训练效果如何？" />
              </view>
              <view class="form-row">
                <text class="form-label">图片/视频</text>
                <view class="form-file-wrap">
                  <view class="file-btn" @click="pickPickerFile(idx)"><text>📷 选择文件</text></view>
                  <text class="file-hint" v-if="!card.files.length">支持图片和视频</text>
                  <view v-if="card.files.length" class="file-previews">
                    <view v-for="(f,fi) in card.files" :key="fi" class="file-preview">
                      <image v-if="f.type === 'image'" :src="f.url" mode="aspectFill" class="preview-img" />
                      <video v-if="f.type === 'video'" :src="f.url" class="preview-video" />
                      <text class="file-del" @click="removePickerFile(idx, fi)">✕</text>
                    </view>
                  </view>
                </view>
              </view>
              <view class="form-row">
                <text class="form-label">备注</text>
                <textarea class="form-textarea" v-model="card.note" placeholder="补充说明..." style="height:50px;" />
              </view>
            </template>
          </view>
          </TransitionGroup>

          <view class="btn-checkin" @click="submitFormWithAnim" style="margin-top:8px;">
            <text>{{ checkinSubmitting ? '提交中...' : '✅ 提交打卡 ' + (pickerCards.length ? '(' + pickerCards.length + ')' : '') }}</text>
          </view>
        </view>
      </view>

      <view v-if="showSummary && submittedCards.length" class="picker-overlay" @click="showSummary = false">
        <view class="picker-card" @click.stop>
          <text class="picker-title">📝 已打卡项目</text>
          <view v-for="(c, idx) in submittedCards" :key="idx" class="submitted-item">
            <text class="si-text">{{ getCardSummary(c) }}</text>
            <view class="si-actions">
              <text class="si-edit" @click="editCard(idx)">✎</text>
              <text class="si-del" @click="deleteCard(idx)">✕</text>
            </view>
          </view>
          <view class="picker-close" @click="showSummary = false"><text>关闭</text></view>
        </view>
      </view>

      <view v-if="showHistory" class="picker-overlay" @click="showHistory = false">
        <view class="picker-card" @click.stop>
          <text class="picker-title">📅 打卡记录</text>
          <view v-if="checkinHistory.length" class="history-list">
            <view v-for="(r, idx) in checkinHistory" :key="r.id || idx" class="history-row">
              <text class="hr-date">{{ formatHistoryDate(r.created_at) }}</text>
              <text class="hr-meta">{{ r.ability_type || '训练' }}{{ r.attitude_pct != null ? ' · 配合度' + r.attitude_pct + '%' : '' }}</text>
              <text v-if="r.note" class="hr-note">{{ r.note }}</text>
            </view>
          </view>
          <text v-else class="history-empty">暂无打卡记录</text>
          <view class="picker-close" @click="showHistory = false"><text>关闭</text></view>
        </view>
      </view>

      <view style="height:40px;"></view>
    </view>

    <!-- 天赋测评引导 -->
    <view v-if="showAssessmentModal" class="picker-overlay" @click="dismissAssessmentModal">
      <view class="picker-card assessment-modal" @click.stop>
        <text class="assessment-modal-icon">🎯</text>
        <text class="assessment-modal-title">需要先进行天赋测试</text>
        <text class="assessment-modal-desc">完成天赋测试后，才能帮你安排今日训练方案</text>
        <view class="assessment-modal-actions">
          <view class="assessment-btn secondary" @click="dismissAssessmentModal"><text>稍后再说</text></view>
          <view class="assessment-btn primary" @click="confirmGoTalent"><text>去测试</text></view>
        </view>
      </view>
    </view>

    <!-- Media Player Overlay -->
    <view v-if="mediaPlayer.show" class="player-overlay" @click="closeMedia">
      <view class="player-card" @click.stop>
        <view class="player-header">
          <text class="player-title">{{ mediaPlayer.type === 'video' ? '🎬 视频训练' : '🎧 音频训练' }}</text>
          <view class="player-close" @click="closeMedia">✕</view>
        </view>
        <view v-if="mediaPlayer.type === 'video'" class="player-body">
          <video
            v-if="videoSrc"
            ref="trainingVideoEl"
            class="training-video"
            :src="videoSrc"
            controls
            autoplay
            @timeupdate="onVideoTimeUpdate"
            @loadedmetadata="onVideoLoadedMetadata"
            @pause="flushWatchProgress"
          />
          <text v-else>暂无视频资源</text>
        </view>
        <view v-if="mediaPlayer.type === 'audio'" class="player-body">
          <text class="pa-icon" style="font-size:48px;display:block;text-align:center;margin-bottom:8px;">🎧</text>
          <view v-html="audioHtml"></view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { ensureChildUser, fetchTrainingEntry, fetchTrainingToday, fetchTrainingProgress, submitTrainingCheckin, fetchTrainingHistory, refreshTrainingReport, fetchTodayCheckins, updateTrainingCheckin, deleteTrainingCheckin, scheduleTrainingPlan, fetchTalentTrainingVideo, fetchDevTrainingStatus, devResetTodayTraining, devResetAllTraining, devSimulateNextDay, devSimulate4amCutoff, devResetTalent, postTrainingWatchProgress, fetchLatestAssessment, fetchAssessmentHistory } from '@/utils/userApi.js'
import { getDevMode, setDevMode } from '@/utils/devMode.js'

const TIMER_STORAGE_KEY_PREFIX = 'jnao_training_timer'
const HOUR_OPTIONS = [0, 1, 2, 3, 4, 5, 6, 7, 8]
const MINUTE_OPTIONS = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]

const devMode = ref(getDevMode())
const devStatusText = ref('')
const timerPhase = ref('setup') // setup | running | expired
const serverTimeOffsetMs = ref(0)
const unlockAtMs = ref(null)
const cutoffAtMs = ref(null)
const newDayAtMs = ref(null)
const dayTransition = ref(false)
const trainingDayKey = ref('')
let dayUnlockTickId = null
const selectedHours = ref(1)
const selectedMinutes = ref(30)
const remainingSeconds = ref(0)
const plannedDurationSec = ref(0)
let timerTickId = null

function todayAnimKey() { return 'jnao_plan_anim_' + new Date().toDateString() }
function planAnimShownToday() { try { return sessionStorage.getItem(todayAnimKey()) === '1' } catch (_) { return false } }
function markPlanAnimShown() { try { sessionStorage.setItem(todayAnimKey(), '1') } catch (_) {} }

const hourLabels = HOUR_OPTIONS.map(h => `${h} 小时`)
const minuteLabels = MINUTE_OPTIONS.map(m => `${m} 分钟`)
const hourIndex = computed(() => Math.max(0, HOUR_OPTIONS.indexOf(selectedHours.value)))
const minuteIndex = computed(() => Math.max(0, MINUTE_OPTIONS.indexOf(selectedMinutes.value)))
const canStartTimer = computed(() => !trainingDayLocked.value && !planLoading.value && !planJustGenerated.value && (selectedHours.value > 0 || selectedMinutes.value > 0))
const isPageLoading = computed(() => planLoading.value || planJustGenerated.value)
/** 训练日已完成（次日凌晨4点才能新开一天），仅禁止重新「开始训练」 */
const trainingDayLocked = computed(() => todayPlan.value?.day_locked === true)
const dayLockText = computed(() => {
  if (!unlockAtMs.value) return '今日训练已完成，次日凌晨4点解锁'
  const left = unlockAtMs.value - (Date.now() + serverTimeOffsetMs.value)
  if (left <= 0) return '训练日已解锁，请刷新页面'
  const h = Math.floor(left / 3600000)
  const m = Math.floor((left % 3600000) / 60000)
  return `今日训练已完成，${h}小时${m}分钟后解锁（凌晨4点）`
})
/** 全局凌晨4点截止或日切窗口 */
const isGlobalCutoff = computed(() => {
  if (dayTransition.value || todayPlan.value?.status === 'transition') return true
  if (todayPlan.value?.globally_cutoff) return true
  if (cutoffAtMs.value && nowSynced() >= cutoffAtMs.value) return true
  return false
})
const globalLockTitle = computed(() => {
  if (dayTransition.value || todayPlan.value?.status === 'transition') return '训练日切换中'
  if (isGlobalCutoff.value && timerPhase.value !== 'expired') return '凌晨4点训练日已截止'
  return '训练时长已到，音视频已锁定'
})
const globalLockSub = computed(() => {
  if (dayTransition.value || todayPlan.value?.status === 'transition') {
    const left = newDayAtMs.value ? newDayAtMs.value - nowSynced() : 0
    if (left > 0) {
      const m = Math.ceil(left / 60000)
      return `约 ${m} 分钟后开始新的一天`
    }
    return '即将加载新一天训练'
  }
  if (isGlobalCutoff.value) return '全局截止，音视频与打卡已锁定'
  return `仍可继续打卡 · 今日计划 ${durationLabel.value}`
})
/** 音视频/打卡：计时结束或全局4点截止 */
const isMediaLocked = computed(() => !devMode.value && (isPageLoading.value || timerPhase.value === 'setup' || timerPhase.value === 'expired' || isGlobalCutoff.value))
const isCheckinLocked = computed(() => !devMode.value && (isPageLoading.value || timerPhase.value === 'setup' || timerPhase.value === 'expired' || isGlobalCutoff.value))
const mediaLockText = computed(() => {
  if (isPageLoading.value) return '方案生成中，请稍候...'
  if (dayTransition.value || todayPlan.value?.status === 'transition') return '训练日切换中，请稍候'
  if (isGlobalCutoff.value) return '凌晨4点训练日已截止'
  if (timerPhase.value === 'expired') return '训练时长已到，音视频已锁定'
  if (trainingDayLocked.value && timerPhase.value === 'setup') return dayLockText.value
  return '请先设置时长并开始训练'
})
const checkinLockText = computed(() => {
  if (isPageLoading.value) return '方案生成中，请稍候...'
  if (dayTransition.value || todayPlan.value?.status === 'transition') return '训练日切换中，请稍候'
  if (isGlobalCutoff.value) return '凌晨4点训练日已截止，无法修改打卡'
  if (timerPhase.value === 'expired') return '训练时长已到，无法修改打卡'
  if (trainingDayLocked.value && timerPhase.value === 'setup') return dayLockText.value
  return '请先设置时长并开始训练'
})
const countdownDisplay = computed(() => formatDuration(remainingSeconds.value))
const durationLabel = computed(() => formatDuration(plannedDurationSec.value))

function timerStorageKey() {
  return `${TIMER_STORAGE_KEY_PREFIX}_${trainingDayKey.value || 'default'}`
}

function nowSynced() {
  return Date.now() + serverTimeOffsetMs.value
}

function applyServerTimeMeta(data) {
  if (!data) return
  if (data.server_now) {
    serverTimeOffsetMs.value = new Date(data.server_now).getTime() - Date.now()
  }
  if (data.unlock_at) unlockAtMs.value = new Date(data.unlock_at).getTime()
  if (data.cutoff_at) cutoffAtMs.value = new Date(data.cutoff_at).getTime()
  if (data.new_day_at) newDayAtMs.value = new Date(data.new_day_at).getTime()
  if (data.day_transition != null) dayTransition.value = !!data.day_transition
  if (data.training_day) trainingDayKey.value = data.training_day
}

function checkGlobalSchedule() {
  checkDayUnlock()
  if (isGlobalCutoff.value && timerPhase.value === 'running') {
    expireTrainingTimer(true)
  }
  const inTransition = dayTransition.value || todayPlan.value?.status === 'transition'
  if (inTransition && newDayAtMs.value && nowSynced() >= newDayAtMs.value) {
    resetAllLocalState()
    loadTodayPlan(true)
  }
}

function checkDayUnlock() {
  if (!unlockAtMs.value || !trainingDayLocked.value) return
  if (nowSynced() >= unlockAtMs.value) {
    timerPhase.value = 'setup'
    loadTodayPlan(true)
  }
}

function startDayUnlockWatch() {
  if (dayUnlockTickId != null) return
  dayUnlockTickId = setInterval(checkGlobalSchedule, 15000)
}

function clearDayUnlockWatch() {
  if (dayUnlockTickId != null) {
    clearInterval(dayUnlockTickId)
    dayUnlockTickId = null
  }
}

function formatDuration(totalSec) {
  const sec = Math.max(0, totalSec)
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  if (h > 0) return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function onHourPick(e) {
  selectedHours.value = HOUR_OPTIONS[Number(e.detail.value)] ?? 0
}
function onMinutePick(e) {
  selectedMinutes.value = MINUTE_OPTIONS[Number(e.detail.value)] ?? 0
}

function clearTimerTick() {
  if (timerTickId != null) {
    clearInterval(timerTickId)
    timerTickId = null
  }
}

function writeTimerStorage(payload) {
  try {
    sessionStorage.setItem(timerStorageKey(), JSON.stringify(payload))
  } catch (_) { /* ignore */ }
}

function persistTimer(endAt, plannedSec) {
  writeTimerStorage({ phase: 'running', endAt, plannedSec })
}

function readTimerData() {
  try {
    const raw = sessionStorage.getItem(timerStorageKey())
    if (!raw) return null
    const data = JSON.parse(raw)
    if (!data) return null
    return data
  } catch (_) {
    return null
  }
}

function expireTrainingTimer(silent = false) {
  clearTimerTick()
  const data = readTimerData()
  const plannedSec = plannedDurationSec.value || data?.plannedSec || 0
  writeTimerStorage({ phase: 'expired', plannedSec })
  timerPhase.value = 'expired'
  remainingSeconds.value = 0
  closeMedia()
  if (!silent) {
    const msg = isGlobalCutoff.value ? '凌晨4点训练日已截止' : '训练时长已到，音视频已锁定'
    uni.showToast({ title: msg, icon: 'none', duration: 2500 })
  }
}

function syncTimerFromEndAt(endAt) {
  const left = Math.ceil((endAt - nowSynced()) / 1000)
  if (left <= 0) {
    expireTrainingTimer(true)
    return
  }
  timerPhase.value = 'running'
  remainingSeconds.value = left
}

function tickTrainingTimer() {
  const data = readTimerData()
  if (!data) {
    clearTimerTick()
    return
  }
  syncTimerFromEndAt(data.endAt)
}

function startTrainingTimer() {
  if (trainingDayLocked.value) {
    uni.showToast({ title: dayLockText.value, icon: 'none', duration: 2500 })
    return
  }
  if (!canStartTimer.value) {
    uni.showToast({ title: '请至少选择 1 分钟', icon: 'none' })
    return
  }
  const totalSec = selectedHours.value * 3600 + selectedMinutes.value * 60
  const plannedMin = Math.max(5, Math.ceil(totalSec / 60))
  plannedDurationSec.value = totalSec

  ;(async () => {
    try {
      uni.showLoading({ title: '正在排课...' })
      const uid = await ensureChildUser()
      const alreadyScheduled = todayPlan.value?.planned_minutes && (todayPlan.value?.items?.length || 0) > 1
      if (!alreadyScheduled) {
        const result = await scheduleTrainingPlan(uid, plannedMin)
        if (result.error === 'assessment') {
          needAssessment.value = true
          showAssessmentModal.value = true
          return
        }
        if (result.error) throw new Error(result.message)
        todayPlan.value = result.data
        applyServerTimeMeta(result.data)
        applyPlanMedia(result.data)
        aiPlanText.value = result.data.report_text || ''
        nextTick(() => syncPhaseExpand())
      }
    } catch (e) {
      uni.showToast({ title: e.message || '排课失败', icon: 'none' })
      return
    } finally {
      uni.hideLoading()
    }

    const endAt = nowSynced() + totalSec * 1000
    persistTimer(endAt, totalSec)
    syncTimerFromEndAt(endAt)
    clearTimerTick()
    timerTickId = setInterval(tickTrainingTimer, 1000)
    uni.showToast({ title: '训练计时已开始', icon: 'none' })
  })()
}

function restoreTrainingTimer() {
  const data = readTimerData()
  if (!data) return
  plannedDurationSec.value = data.plannedSec || 0
  if (data.phase === 'expired') {
    timerPhase.value = 'expired'
    remainingSeconds.value = 0
    clearTimerTick()
    return
  }
  if (!data.endAt) return
  const left = Math.ceil((data.endAt - nowSynced()) / 1000)
  if (left <= 0) {
    writeTimerStorage({ phase: 'expired', plannedSec: data.plannedSec || 0 })
    timerPhase.value = 'expired'
    remainingSeconds.value = 0
    clearTimerTick()
    return
  }
  syncTimerFromEndAt(data.endAt)
  clearTimerTick()
  timerTickId = setInterval(tickTrainingTimer, 1000)
}

function guardMedia() {
  if (devMode.value) return true
  if (isGlobalCutoff.value) {
    uni.showToast({ title: '训练日已截止，无法播放', icon: 'none' })
    return false
  }
  if (timerPhase.value === 'expired') {
    uni.showToast({ title: '训练时长已到，无法播放', icon: 'none' })
    return false
  }
  if (timerPhase.value === 'setup') {
    uni.showToast({ title: '请先设置时长并开始训练', icon: 'none' })
    return false
  }
  return true
}

function guardCheckin() {
  if (devMode.value) return true
  if (isGlobalCutoff.value) {
    uni.showToast({ title: '训练日已截止，无法修改打卡', icon: 'none' })
    return false
  }
  if (timerPhase.value === 'expired') {
    uni.showToast({ title: '训练时长已到，无法修改打卡', icon: 'none' })
    return false
  }
  if (timerPhase.value === 'setup') {
    uni.showToast({ title: '请先设置时长并开始训练', icon: 'none' })
    return false
  }
  return true
}

function toggleDevMode() {
  devMode.value = !devMode.value
  setDevMode(devMode.value)
  uni.showToast({
    title: devMode.value ? '开发者模式已开启' : '开发者模式已关闭',
    icon: 'none',
  })
  if (devMode.value) loadDevStatus()
}

async function openHistory() {
  try {
    const uid = await ensureChildUser()
    checkinHistory.value = await fetchTrainingHistory(uid, 30)
    showHistory.value = true
  } catch (_) {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

function formatHistoryDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return String(iso).slice(0, 16).replace('T', ' ')
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function setAttitude(pct) {
  summaryAttitude.value = pct
  attitudeTouched.value = true
  if (!primaryCheckinRecordId.value) return
  try {
    const uid = await ensureChildUser()
    await updateTrainingCheckin(uid, primaryCheckinRecordId.value, { attitude_pct: pct })
  } catch (_) { /* ignore */ }
}

function resetAllLocalState() {
  devResetTimer(true)
  pickerCards.value = []
  activePickerBlock.value = null
  watchedItemIds.value = new Set()
  watchProgressMap.value = {}
  showPicker.value = false
  showSummary.value = false
  submittedCards.value = []
  phaseRecordIds.value = {}
  primaryCheckinRecordId.value = null
  summaryAttitude.value = 60
  attitudeTouched.value = false
  closeMedia()
}

async function loadDevStatus() {
  if (!devMode.value) return
  try {
    const uid = await ensureChildUser()
    const s = await fetchDevTrainingStatus(uid)
    const tag = s.talent_tag || '?'
    devStatusText.value = `课序 ${s.content_index ?? 0} · ${tag} · 计划 ${s.plan_count} 天 · 打卡 ${s.record_count} 条`
  } catch (_) {
    devStatusText.value = ''
  }
}

async function devRefreshAll() {
  if (!devMode.value) return
  try {
    uni.showLoading({ title: '刷新全部...' })
    const uid = await ensureChildUser()
    await devResetTodayTraining(uid)
    resetAllLocalState()
    await loadTodayPlan()
    await loadDevStatus()
    uni.showToast({ title: '今日已重置并刷新', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '刷新失败', icon: 'none' })
  } finally {
    uni.hideLoading()
  }
}

async function devSimulate4amCutoffAction() {
  if (!devMode.value) return
  try {
    uni.showLoading({ title: '模拟4点截止...' })
    const uid = await ensureChildUser()
    await devSimulate4amCutoff(uid)
    resetAllLocalState()
    expireTrainingTimer(true)
    await loadTodayPlan(true)
    await loadDevStatus()
    uni.showToast({ title: '已模拟凌晨4点全局截止', icon: 'none', duration: 2500 })
  } catch (e) {
    uni.showToast({ title: e.message || '模拟失败', icon: 'none' })
  } finally {
    uni.hideLoading()
  }
}

async function devGoNextDay() {
  if (!devMode.value) return
  try {
    uni.showLoading({ title: '模拟下一天...' })
    const uid = await ensureChildUser()
    const res = await devSimulateNextDay(uid)
    resetAllLocalState()
    if (res.today) {
      todayPlan.value = res.today
      applyPlanMedia(res.today)
      aiPlanText.value = res.today.report_text || ''
      lessonIndex.value = (res.today.content_index ?? 0) + 1
    } else {
      await loadTodayPlan()
    }
    nextTick(() => syncPhaseExpand())
    await loadDevStatus()
    const idx = res.today?.content_index ?? res.status?.content_index ?? '?'
    uni.showToast({ title: `已进入下一天 · 课序 ${idx}`, icon: 'none', duration: 2500 })
  } catch (e) {
    uni.showToast({ title: e.message || '模拟失败', icon: 'none' })
  } finally {
    uni.hideLoading()
  }
}

async function devClearAllHistory() {
  if (!devMode.value) return
  try {
    uni.showLoading({ title: '清空中...' })
    const uid = await ensureChildUser()
    await devResetAllTraining(uid)
    resetAllLocalState()
    await loadTodayPlan()
    await loadDevStatus()
    uni.showToast({ title: '训练历史已清空', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '清空失败', icon: 'none' })
  } finally {
    uni.hideLoading()
  }
}

async function devResetTalentAction() {
  if (!devMode.value) return
  try {
    uni.showLoading({ title: '重置天赋...' })
    const uid = await ensureChildUser()
    await devResetTalent(uid)
    resetAllLocalState()
    needAssessment.value = true
    showAssessmentModal.value = true
    await loadDevStatus()
    uni.showToast({ title: '天赋已重置', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '重置失败', icon: 'none' })
  } finally {
    uni.hideLoading()
  }
}

function clearTimerStorage() {
  try {
    sessionStorage.removeItem(timerStorageKey())
  } catch (_) { /* ignore */ }
}

function devResetTimer(silent = false) {
  clearTimerTick()
  clearTimerStorage()
  timerPhase.value = 'setup'
  remainingSeconds.value = 0
  plannedDurationSec.value = 0
  closeMedia()
  if (!silent) uni.showToast({ title: '计时已重置', icon: 'none' })
}

function devSimulateExpire() {
  clearTimerTick()
  clearTimerStorage()
  expireTrainingTimer()
}

function devUnlockNextPhase() {
  if (!devMode.value) return
  const locked = planPhases.value.find(p => !p.unlocked)
  if (!locked) {
    uni.showToast({ title: '所有阶段已解锁', icon: 'none' })
    return
  }
  const idx = planPhases.value.indexOf(locked)
  if (idx > 0) markPhaseDoneLocally(planPhases.value[idx - 1].block)
  nextTick(() => syncPhaseExpand())
  uni.showToast({ title: `已解锁训练 ${locked.block}`, icon: 'none' })
}

async function devRefreshAiPlan() {
  if (!devMode.value) return
  planLoading.value = true
  planJustGenerated.value = false
  try {
    const uid = await ensureChildUser()
    const result = await refreshTrainingReport(uid, true)
    if (result.error) throw new Error(result.message)
    todayPlan.value = result.data
    applyPlanMedia(result.data)
    aiPlanText.value = result.data.report_text || ''
    lessonIndex.value = (result.data.content_index ?? 0) + 1
    nextTick(() => syncPhaseExpand())
  } catch (e) {
    planLoading.value = false
    uni.showToast({ title: e.message || '刷新失败', icon: 'none' })
    return
  }
  planLoading.value = false
  planJustGenerated.value = true
  setTimeout(() => { planJustGenerated.value = false }, 1500)
  uni.showToast({ title: 'AI 方案已刷新', icon: 'none' })
}

const showPicker = ref(false)
const activePickerBlock = ref(null)
const showSummary = ref(false)
const showHistory = ref(false)
const checkinHistory = ref([])
const submittedCards = ref([])
const summaryAttitude = ref(60)
const attitudeTouched = ref(false)
const scores = [
  { pct:100, emoji:'🔴', desc:'身体已透支，精神还要求进步' },
  { pct:80,  emoji:'🟡', desc:'能完成任务，但还有余力学习' },
  { pct:60,  emoji:'🔵', desc:'做基本任务，被动的低效训练' },
  { pct:40,  emoji:'🟤', desc:'不完成任务，不认真逃避训练' },
  { pct:20,  emoji:'⚫️', desc:'不完成任务，基本不配合训练' },
  { pct:0,   emoji:'☠️', desc:'不完成任务，严重不配合训练' },
]
const mediaPlayer = ref({ show: false, type: 'video' })
const watchedItemIds = ref(new Set())
const watchProgressMap = ref({})
const trainingVideoEl = ref(null)
let watchProgressSaveTimer = null
const lastOpenedItem = ref(null)
const videoSrc = ref('/static/training_video.mp4')
const audioSrc = ref('')
const audioTitle = ref('🎧 训练用音频')
const talentLabel = ref('')
const aiPlanText = ref('')
const lessonIndex = ref(1)
const needAssessment = ref(false)
const showAssessmentModal = ref(false)
const todayPlan = ref(null)
const phaseRecordIds = ref({})
const primaryCheckinRecordId = ref(null)
const planLoading = ref(false)
const planJustGenerated = ref(false)
const checkinSubmitting = ref(false)

const todayCompleted = computed(() => todayPlan.value?.status === 'completed')
const checkedPhaseCount = computed(() => new Set(submittedCards.value.map(c => c.phaseBlock).filter(Boolean)).size)

function getPhaseItems(block) {
  return (todayPlan.value?.items || []).filter(i => (i.block || 'A') === block)
}

function blockForItemId(itemId) {
  const item = todayPlan.value?.items?.find(i => i.id === itemId)
  return item?.block || 'A'
}

function buildPhaseSubtitle(items) {
  const tags = new Set()
  for (const item of items) {
    if (item.item_type === 'video' || item.video_url) tags.add('视频')
    if (item.item_type === 'audio' || (item.audio_url && !item.video_url)) tags.add('音频')
  }
  if (!tags.size) return '综合训练'
  return `${[...tags].join('+')}训练`
}

function isPhaseUnlocked(block, blockOrder, items) {
  const idx = blockOrder.indexOf(block)
  if (idx <= 0) return true
  const prevBlock = blockOrder[idx - 1]
  const prevItems = items.filter(i => (i.block || 'A') === prevBlock)
  return prevItems.length > 0 && prevItems.every(i => i.checkin_status === 'done')
}

const planExpanded = ref({})

function togglePhase(block) {
  planExpanded.value = { ...planExpanded.value, [block]: !planExpanded.value[block] }
}

function syncPhaseExpand() {
  const phases = planPhases.value
  if (!phases.length) return
  const next = {}
  for (const p of phases) {
    // 默认：进行中的阶段展开，其他折叠
    if (planExpanded.value[p.block] !== undefined) {
      next[p.block] = planExpanded.value[p.block]
    } else {
      next[p.block] = p.unlocked && !p.allDone
    }
  }
  planExpanded.value = next
}

const planPhases = computed(() => {
  const items = todayPlan.value?.items || []
  if (!items.length) return []

  const blockOrder = []
  const seen = new Set()
  for (const item of items) {
    const b = item.block || 'A'
    if (!seen.has(b)) {
      seen.add(b)
      blockOrder.push(b)
    }
  }

  return blockOrder.map(block => {
    const phaseItems = items.filter(i => (i.block || 'A') === block)
    const unlocked = isPhaseUnlocked(block, blockOrder, items)
    const doneCount = phaseItems.filter(i => i.checkin_status === 'done').length
    const allDone = phaseItems.length > 0 && doneCount === phaseItems.length
    let nodeIcon = '○'
    let nodeClass = 'tl-node-locked'
    if (unlocked) {
      nodeIcon = '●'
      nodeClass = allDone ? 'tl-node-done' : 'tl-node-active'
    }
    return {
      block,
      label: `阶段 ${block}`,
      subtitle: buildPhaseSubtitle(phaseItems),
      items: phaseItems,
      unlocked,
      allDone,
      doneCount,
      totalCount: phaseItems.length,
      nodeIcon,
      nodeClass,
    }
  })
})

const planTotalCount = computed(() => (todayPlan.value?.items || []).length)
const planCompletedCount = computed(() => (todayPlan.value?.items || []).filter(i => i.checkin_status === 'done').length)
const planProgressPct = computed(() => {
  if (!planTotalCount.value) return 0
  return Math.round((planCompletedCount.value / planTotalCount.value) * 100)
})

function itemTypeEmoji(item) {
  if (item.item_type === 'video' || item.video_url) return '🎬'
  if (item.item_type === 'audio' || item.audio_url) return '🎧'
  return '▸'
}

function itemStatusIcon(item, phase) {
  if (!phase.unlocked) return '🔒'
  if (item.checkin_status === 'done') return '☑'
  return '○'
}

function itemStatusLabel(item, phase) {
  if (!phase.unlocked) return '待解锁'
  if (item.checkin_status === 'done') return '已完成'
  return '进行中'
}

function itemStatusClass(item, phase) {
  if (!phase.unlocked) return 'tl-st-locked'
  if (item.checkin_status === 'done') return 'tl-st-done'
  return 'tl-st-active'
}

function phaseMetaText(phase) {
  if (!phase.unlocked) return '待解锁'
  if (phase.allDone) return `${phase.doneCount}/${phase.totalCount} 已完成`
  return `${phase.doneCount}/${phase.totalCount} · 进行中`
}

function itemLabel(item) {
  if (item.item_type === 'video' || item.video_url) return '视频训练'
  if (item.item_type === 'audio' || item.audio_url) return '音频训练'
  return '训练项'
}

function isVideoItem(item) {
  return item?.item_type === 'video' || !!item?.video_url
}

function isItemWatched(item) {
  if (!item?.id) return false
  if (isVideoItem(item)) return false
  return watchedItemIds.value.has(item.id)
}

function hydrateWatchProgressFromPlan(plan) {
  const map = { ...watchProgressMap.value }
  for (const item of plan?.items || []) {
    if (!item?.id) continue
    if (item.watch_progress) map[item.id] = { ...item.watch_progress }
  }
  watchProgressMap.value = map
}

async function flushWatchProgress() {
  const item = lastOpenedItem.value
  const el = trainingVideoEl.value
  if (!item?.id || !isVideoItem(item) || !el) return
  const watchedSec = el.currentTime || 0
  const durationSec = el.duration || 0
  if (durationSec <= 0) return
  const pct = Math.min(100, Math.round(watchedSec / durationSec * 1000) / 10)
  watchProgressMap.value = {
    ...watchProgressMap.value,
    [item.id]: { watched_sec: watchedSec, duration_sec: durationSec, pct },
  }
  try {
    const uid = await ensureChildUser()
    const res = await postTrainingWatchProgress(uid, item.id, {
      watched_sec: watchedSec,
      duration_sec: durationSec,
    })
    if (res?.watch_progress) {
      watchProgressMap.value = { ...watchProgressMap.value, [item.id]: res.watch_progress }
    }
  } catch (_) { /* ignore */ }
}

function onVideoLoadedMetadata(e) {
  const el = e?.target || trainingVideoEl.value
  if (!el || !lastOpenedItem.value?.id) return
  flushWatchProgress()
}

function onVideoTimeUpdate(e) {
  const el = e?.target || trainingVideoEl.value
  const item = lastOpenedItem.value
  if (!el || !item?.id) return
  const durationSec = el.duration || 0
  if (durationSec <= 0) return
  const watchedSec = el.currentTime || 0
  const pct = Math.min(100, Math.round(watchedSec / durationSec * 1000) / 10)
  watchProgressMap.value = {
    ...watchProgressMap.value,
    [item.id]: { watched_sec: watchedSec, duration_sec: durationSec, pct },
  }
  if (watchProgressSaveTimer) return
  watchProgressSaveTimer = setTimeout(() => {
    watchProgressSaveTimer = null
    flushWatchProgress()
  }, 4000)
}

function canPhaseCheckin(phase) {
  if (!phase.unlocked) return false
  if (devMode.value) return true
  if (planLoading.value || planJustGenerated.value) return false
  if (timerPhase.value === 'setup' || timerPhase.value === 'expired') return false
  if (isGlobalCutoff.value) return false
  return true
}

function phaseCheckinLockText(phase) {
  if (!phase.unlocked) {
    const idx = planPhases.value.findIndex(p => p.block === phase.block)
    const prev = idx > 0 ? planPhases.value[idx - 1]?.block : ''
    return prev ? `请先完成训练 ${prev} 打卡` : '待解锁'
  }
  return checkinLockText.value
}

function itemStepHint(item, phase) {
  if (!phase.unlocked) {
    const idx = planPhases.value.findIndex(p => p.block === phase.block)
    const prev = idx > 0 ? planPhases.value[idx - 1]?.block : ''
    return prev ? `🔒 完成训练 ${prev} 打卡后解锁` : '🔒 待解锁'
  }
  if (isMediaLocked.value && timerPhase.value === 'expired') return '🔒 时长已到'
  if (isGlobalCutoff.value) return '🔒 训练日已截止'
  if (isItemWatched(item)) return '✅ 已观看'
  if (item.video_url) return '▶ 点击播放'
  if (item.audio_url) return `▶ 约 ${item.duration_min || '?'} 分钟`
  return '暂无资源'
}

function isPhaseMediaLocked(phase) {
  if (devMode.value) return false
  if (!phase.unlocked) return true
  return isMediaLocked.value
}

function phaseMediaLockText(phase) {
  if (!phase.unlocked) {
    const idx = planPhases.value.findIndex(p => p.block === phase.block)
    const prev = idx > 0 ? planPhases.value[idx - 1]?.block : ''
    return prev ? `完成训练 ${prev} 打卡后解锁` : '待解锁'
  }
  return mediaLockText.value
}

function phaseTip(phase) {
  if (!phase.unlocked) {
    const idx = planPhases.value.findIndex(p => p.block === phase.block)
    const prev = idx > 0 ? planPhases.value[idx - 1]?.block : ''
    return prev ? `完成训练 ${prev} 打卡后解锁本阶段` : '待解锁'
  }
  if (phase.allDone) return `✅ 训练 ${phase.block} 已完成`
  return `训练 ${phase.block} 共 ${phase.totalCount} 项`
}

function scrollToPhase(block) {
  const body = document.querySelector('.body')
  const target = document.getElementById(`phase-block-${block}`)
  if (!body || !target) return
  const bodyTop = body.getBoundingClientRect().top
  const targetTop = target.getBoundingClientRect().top
  body.scrollTo({ top: body.scrollTop + targetTop - bodyTop - 12, behavior: 'smooth' })
}

function openPhaseMediaItem(item, phase) {
  if (!item) return
  if (!phase.unlocked && !devMode.value) {
    const idx = planPhases.value.findIndex(p => p.block === phase.block)
    const prev = idx > 0 ? planPhases.value[idx - 1]?.block : ''
    uni.showToast({ title: prev ? `请先完成训练 ${prev} 打卡` : '本阶段尚未解锁', icon: 'none' })
    return
  }
  openMediaItem(item)
}

const audioHtml = computed(() => audioSrc.value ? `<audio src="${audioSrc.value}" controls autoplay style="width:100%;"></audio>` : '<text>暂无音频资源</text>')
const pickerCards = ref([])
const sparkAbi = ref(-1)
const abilities = ['超脑阅读','影像追忆','扫描速记','极速运算','极速学习','难题专练','文科扫书','理科扫书','高效作业','天赋绘画','音乐灵感','棋类专注']

function hasPickerCard(name) { return pickerCards.value.some(c => c.name === name) }

function newCard(name) {
  const base = { name, time: '', content: '', result: '', tag: '', count: '', accuracy: '', note: '', files: [] }
  if (name === '扫描速记') {
    return { ...base, materialType: '书', materialName: '', wordCount: '', forwardTime: '', forwardAcc: '', backwardTime: '', backwardAcc: '' }
  }
  if (name === '影像追忆') {
    return { ...base, tool: '书本' }
  }
  return base
}

function togglePickerCard(name, abi) {
  const idx = pickerCards.value.findIndex(c => c.name === name)
  if (idx >= 0) {
    pickerCards.value.splice(idx, 1)
  } else {
    pickerCards.value.push(newCard(name))
  }
  sparkAbi.value = abi
  setTimeout(() => sparkAbi.value = -1, 1500)
}

function removePickerCard(idx) { pickerCards.value.splice(idx, 1) }
function pickPickerFile(idx) {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*,video/*'
  input.multiple = true
  input.onchange = (e) => {
    const files = e.target.files
    for (let i = 0; i < files.length; i++) {
      const f = files[i]
      const url = URL.createObjectURL(f)
      pickerCards.value[idx].files.push({ name: f.name, url, type: f.type.startsWith('video') ? 'video' : 'image' })
    }
  }
  input.click()
}
function removePickerFile(cardIdx, fileIdx) {
  const card = pickerCards.value[cardIdx]
  URL.revokeObjectURL(card.files[fileIdx].url)
  card.files.splice(fileIdx, 1)
}

function serializeCards(list) {
  return list.map(c => ({
    name: c.name,
    time: c.time,
    content: c.content,
    result: c.result,
    tag: c.tag,
    count: c.count,
    accuracy: c.accuracy,
    note: c.note,
    wordCount: c.wordCount,
    materialType: c.materialType,
    materialName: c.materialName,
    forwardTime: c.forwardTime,
    forwardAcc: c.forwardAcc,
    backwardTime: c.backwardTime,
    backwardAcc: c.backwardAcc,
    tool: c.tool,
    phaseBlock: c.phaseBlock,
    fileNames: (c.files || []).map(f => f.name),
  }))
}

function markPhaseDoneLocally(block) {
  for (const item of getPhaseItems(block)) {
    item.checkin_status = 'done'
  }
}

function cardsForBlock(block) {
  return submittedCards.value.filter(c => c.phaseBlock === block)
}

async function loadTodayCheckinRecords(uid, planId) {
  try {
    const records = await fetchTodayCheckins(uid)
    const sorted = [...records].sort((a, b) => (a.id || 0) - (b.id || 0))
    phaseRecordIds.value = {}
    primaryCheckinRecordId.value = null
    submittedCards.value = []

    if (!sorted.length) return

    for (const record of sorted) {
      const block = blockForItemId(record.item_id)
      phaseRecordIds.value[block] = record.id
      if (!primaryCheckinRecordId.value) primaryCheckinRecordId.value = record.id

      const cards = Array.isArray(record.cards) && record.cards.length
        ? record.cards
        : (record.ability_type || record.content)
          ? [{ name: record.ability_type || '训练记录', content: record.content || '', result: record.result || '', time: '', files: [] }]
          : []

      for (const c of cards) {
        submittedCards.value.push({
          ...c,
          phaseBlock: c.phaseBlock || block,
          recordId: record.id,
          files: [],
        })
      }
    }

    const primary = sorted.find(r => r.id === primaryCheckinRecordId.value)
    if (primary?.attitude_pct != null) {
      summaryAttitude.value = primary.attitude_pct
      attitudeTouched.value = true
    }
  } catch (_) { /* ignore */ }
}

async function persistPhaseCheckin(block, cardsList) {
  const uid = await ensureChildUser()
  const payload = {
    cards: serializeCards(cardsList),
    ability_type: cardsList.map(c => c.name).join('、'),
    content: cardsList.map(c => getCardSummary(c)).join('；'),
  }
  payload.attitude_pct = summaryAttitude.value

  const recordId = phaseRecordIds.value[block]
  if (!recordId) {
    const firstItem = getPhaseItems(block)[0]
    if (!todayPlan.value?.plan_id || !firstItem) throw new Error('训练方案未就绪')
    const res = await submitTrainingCheckin(uid, {
      plan_id: todayPlan.value.plan_id,
      item_id: firstItem.id,
      ...payload,
    })
    phaseRecordIds.value[block] = res.record_id
    if (!primaryCheckinRecordId.value) primaryCheckinRecordId.value = res.record_id
    if (todayPlan.value) todayPlan.value.status = res.plan_status
    markPhaseDoneLocally(block)
    return res
  }

  const res = await updateTrainingCheckin(uid, recordId, payload)
  if (todayPlan.value && res.plan_status) todayPlan.value.status = res.plan_status
  markPhaseDoneLocally(block)
  return res
}

async function deletePhaseCheckin(block) {
  const recordId = phaseRecordIds.value[block]
  if (!recordId) return null
  const uid = await ensureChildUser()
  const res = await deleteTrainingCheckin(uid, recordId)
  delete phaseRecordIds.value[block]
  submittedCards.value = submittedCards.value.filter(c => c.phaseBlock !== block)
  for (const item of getPhaseItems(block)) item.checkin_status = 'pending'
  if (primaryCheckinRecordId.value === recordId) {
    const remaining = Object.values(phaseRecordIds.value)
    primaryCheckinRecordId.value = remaining.length ? Math.min(...remaining) : null
  }
  if (todayPlan.value) todayPlan.value.status = res.plan_status || 'pending'
  return res
}

function autoDetectAbilities(block) {
  const items = getPhaseItems(block)
  if (!items.length) return
  for (const item of items) {
    const title = (item.title || item.lesson_title || '').replace(/\s+/g, '')
    if (!title) continue
    for (const ability of abilities) {
      if (title.includes(ability) && !hasPickerCard(ability)) {
        pickerCards.value.push(newCard(ability))
      }
    }
  }
}

function openPicker(block) {
  if (!guardCheckin()) return
  const phase = planPhases.value.find(p => p.block === block)
  if (!phase) return
  if (!phase.unlocked) {
    const idx = planPhases.value.indexOf(phase)
    const prev = idx > 0 ? planPhases.value[idx - 1]?.block : ''
    uni.showToast({ title: prev ? `请先完成训练 ${prev} 打卡` : '本阶段尚未解锁', icon: 'none' })
    return
  }
  if (todayCompleted.value && phase.allDone && timerPhase.value !== 'running') {
    if (submittedCards.value.length) showSummary.value = true
    else uni.showToast({ title: '今日训练已全部完成', icon: 'none' })
    return
  }
  activePickerBlock.value = block
  const existing = cardsForBlock(block)
  pickerCards.value = existing.length
    ? existing.map(c => ({ ...c, files: c.files ? [...c.files] : [] }))
    : []
  if (!pickerCards.value.length) autoDetectAbilities(block)
  showPicker.value = true
}

function closePicker() {
  showPicker.value = false
  activePickerBlock.value = null
  pickerCards.value = []
}

function submitFormWithAnim() {
  if (checkinSubmitting.value) return
  // 脉冲扩散动画
  const btn = document.querySelector('.btn-checkin')
  if (btn) {
    btn.classList.add('pulse-out')
    setTimeout(() => btn.classList.remove('pulse-out'), 500)
  }
  submitForm()
}

async function submitForm() {
  if (!guardCheckin()) return
  const block = activePickerBlock.value
  if (!block || !todayPlan.value?.plan_id) {
    uni.showToast({ title: '训练方案未加载，请稍后重试', icon: 'none' })
    return
  }
  const hasContent = pickerCards.value.some(c => c.time || c.content || c.result || c.count || c.tag || c.wordCount || c.materialName)
  if (!hasContent) {
    uni.showToast({ title: '请先填写训练记录再提交', icon: 'none', duration: 2000 })
    return
  }
  checkinSubmitting.value = true
  try {
    const cardsList = pickerCards.value.map(c => ({ ...c, phaseBlock: block }))
    await persistPhaseCheckin(block, cardsList)
    submittedCards.value = [
      ...submittedCards.value.filter(c => c.phaseBlock !== block),
      ...cardsList.map(c => ({ ...c, files: c.files || [] })),
    ]
    closePicker()
    nextTick(() => syncPhaseExpand())
    loadTodayPlan(true)
    uni.showToast({ title: `✅ 训练 ${block} 打卡成功！`, icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '打卡提交失败', icon: 'none', duration: 2500 })
  } finally {
    checkinSubmitting.value = false
  }
}

function getCardSummary(c) {
  const prefix = c.phaseBlock ? `[${c.phaseBlock}] ` : ''
  if (c.name === '极速运算') return prefix + c.name + '(' + (c.tag || '运算') + ',' + c.time + '分钟,' + c.count + '题,' + c.accuracy + '%)'
  if (c.name === '影像追忆') {
    const parts = ['工具' + (c.tool || '豆包')]
    if (c.time) parts.push(c.time + '分钟')
    if (c.content) parts.push('材料《' + c.content + '》')
    if (c.accuracy) parts.push('追忆率' + c.accuracy + '%')
    return prefix + '影像追忆：' + parts.join('，')
  }
  if (c.name === '扫描速记') {
    const parts = [(c.materialType||'书') + '《' + (c.materialName||'?') + '》', (c.wordCount||'?') + '字']
    if (c.forwardTime || c.forwardAcc) parts.push('正背' + (c.forwardTime||'?') + '/' + (c.forwardAcc||'?'))
    if (c.backwardTime || c.backwardAcc) parts.push('倒背' + (c.backwardTime||'?') + '/' + (c.backwardAcc||'?'))
    return prefix + '扫描速记：' + parts.join('，')
  }
  return prefix + c.name + '(' + c.time + '分钟)'
}

function editCard(idx) {
  if (!guardCheckin()) return
  const c = submittedCards.value[idx]
  activePickerBlock.value = c.phaseBlock || 'A'
  pickerCards.value = [{ ...c, files: c.files ? [...c.files] : [] }]
  submittedCards.value.splice(idx, 1)
  showPicker.value = true
  showSummary.value = false
}

async function deleteCard(idx) {
  const c = submittedCards.value[idx]
  const block = c.phaseBlock || 'A'
  submittedCards.value.splice(idx, 1)
  const remaining = cardsForBlock(block)
  checkinSubmitting.value = true
  try {
    if (!remaining.length) {
      await deletePhaseCheckin(block)
    } else {
      await persistPhaseCheckin(block, remaining)
    }
    if (!submittedCards.value.length) showSummary.value = false
    nextTick(() => syncPhaseExpand())
    uni.showToast({ title: '已删除', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '删除失败', icon: 'none' })
  } finally {
    checkinSubmitting.value = false
  }
}

function applyPlanMedia(plan) {
  const items = plan?.items || []
  const videoItem = items.find(i => i.item_type === 'video' || i.video_url)
  if (videoItem?.video_url) {
    videoSrc.value = videoItem.video_url
  }
  const firstBlock = items[0]?.block || 'A'
  const firstAudio = items.find(i => (i.block || 'A') === firstBlock && i.audio_url)
    || items.find(i => i.audio_url && !i.video_url)
  if (firstAudio) {
    audioSrc.value = firstAudio.audio_url
    audioTitle.value = `🎧 ${firstAudio.title || '今日训练音频'}`
  }
}

function openMediaItem(item) {
  if (!item) return
  if (!guardMedia()) return
  lastOpenedItem.value = item
  if (item.video_url) {
    videoSrc.value = item.video_url
    mediaPlayer.value = { show: true, type: 'video' }
    return
  }
  if (item.audio_url) {
    audioSrc.value = item.audio_url
    audioTitle.value = item.title || '训练音频'
    mediaPlayer.value = { show: true, type: 'audio' }
    return
  }
  if (needAssessment.value) {
    showAssessmentModal.value = true
    return
  }
  uni.showToast({ title: '暂无推荐音频', icon: 'none', duration: 2000 })
}

function openMedia(type) {
  if (!guardMedia()) return
  const firstPhase = planPhases.value[0]
  if (type === 'video') {
    const video = firstPhase?.items?.find(i => i.video_url || i.item_type === 'video')
    openMediaItem(video || { video_url: videoSrc.value })
    return
  }
  if (type === 'audio') {
    const audio = firstPhase?.items?.find(i => i.audio_url)
    openMediaItem(audio || { audio_url: audioSrc.value, title: audioTitle.value })
  }
}
function closeMedia() {
  if (watchProgressSaveTimer) {
    clearTimeout(watchProgressSaveTimer)
    watchProgressSaveTimer = null
  }
  if (lastOpenedItem.value?.id && isVideoItem(lastOpenedItem.value)) {
    flushWatchProgress()
  } else if (lastOpenedItem.value?.id) {
    watchedItemIds.value.add(lastOpenedItem.value.id)
    watchedItemIds.value = new Set(watchedItemIds.value)
  }
  mediaPlayer.value.show = false
}

function applyTalentLabelFromTag(talentTag) {
  if (!talentTag) return
  const tagMap = { 学: '学者', 思: '思者', 行: '行者', 德: '德者', 赢: '赢者' }
  talentLabel.value = tagMap[talentTag] || `${talentTag}者`
}

async function resolveAssessmentFromHistory(uid) {
  try {
    const latest = await fetchLatestAssessment(uid)
    if (latest?.talent_code || latest?.talent_primary) {
      applyTalentLabelFromTag(latest.talent_tag)
      return true
    }
  } catch (_) { /* try history list */ }
  try {
    const history = await fetchAssessmentHistory(uid)
    const h = history?.[0]
    if (h && (h.talent_primary || h.talent)) {
      applyTalentLabelFromTag(h.talent_tag)
      return true
    }
  } catch (_) { /* ignore */ }
  return false
}

async function checkTrainingEntry(uid) {
  try {
    const entry = await fetchTrainingEntry(uid)
    applyServerTimeMeta(entry)
    if (!entry.needs_assessment && entry.has_assessment) {
      needAssessment.value = false
      showAssessmentModal.value = false
      applyTalentLabelFromTag(entry.talent_tag)
      return true
    }
    if (await resolveAssessmentFromHistory(uid)) {
      needAssessment.value = false
      showAssessmentModal.value = false
      return true
    }
    needAssessment.value = true
    showAssessmentModal.value = true
    return false
  } catch (e) {
    if (await resolveAssessmentFromHistory(uid)) {
      needAssessment.value = false
      showAssessmentModal.value = false
      return true
    }
    needAssessment.value = true
    showAssessmentModal.value = true
    return false
  }
}

async function refreshAiPlanInBackground(uid) {
  if (aiPlanText.value?.trim()) return
  try {
    const result = await refreshTrainingReport(uid, false)
    if (result.data?.report_text) {
      aiPlanText.value = result.data.report_text
      if (todayPlan.value) todayPlan.value.report_text = result.data.report_text
    }
  } catch (_) { /* AI 可后台重试 */ }
}

function confirmGoTalent() {
  showAssessmentModal.value = false
  goTalent()
}

function dismissAssessmentModal() {
  showAssessmentModal.value = false
}

async function loadTodayPlan(silent = false) {
  if (planLoading.value && !silent) return

  const isFirstLoad = !silent && !planAnimShownToday()
  if (isFirstLoad) {
    planLoading.value = true
    planJustGenerated.value = false
  }
  needAssessment.value = false
  try {
    const uid = await ensureChildUser()
    const entryOk = await checkTrainingEntry(uid)
    if (!entryOk) {
      aiPlanText.value = ''
      audioSrc.value = ''
      audioTitle.value = '🎧 训练用音频'
      todayPlan.value = null
      if (isFirstLoad) planLoading.value = false
      return
    }

    const result = await fetchTrainingToday(uid, { skipAi: silent || !isFirstLoad })
    if (result.error === 'assessment') {
      needAssessment.value = true
      showAssessmentModal.value = true
      aiPlanText.value = ''
      audioSrc.value = ''
      audioTitle.value = '🎧 训练用音频'
      if (isFirstLoad) planLoading.value = false
      return
    }
    if (result.error) throw new Error(result.message)

    todayPlan.value = result.data
    applyServerTimeMeta(result.data)

    if (result.data.status === 'transition' || !result.data.plan_id) {
      resetAllLocalState()
      aiPlanText.value = result.data.report_text || '训练日切换中'
      if (isFirstLoad) planLoading.value = false
      return
    }

    if (!silent) {
      submittedCards.value = []
      phaseRecordIds.value = {}
      primaryCheckinRecordId.value = null
      summaryAttitude.value = 60
      attitudeTouched.value = false
    }
    lessonIndex.value = (result.data.content_index ?? 0) + 1
    aiPlanText.value = result.data.report_text || ''
    applyPlanMedia(result.data)
    hydrateWatchProgressFromPlan(result.data)

    await loadTodayCheckinRecords(uid, result.data.plan_id)
    nextTick(() => syncPhaseExpand())

    if (!talentLabel.value) {
      const progress = await fetchTrainingProgress(uid)
      applyTalentLabelFromTag(progress?.talent_tag)
    }

    if (!videoSrc.value || videoSrc.value === '/static/training_video.mp4') {
      try {
        const video = await fetchTalentTrainingVideo(uid)
        if (video?.url && !todayPlan.value?.items?.some(i => i.video_url)) {
          videoSrc.value = video.url
        }
      } catch (_) { /* ignore */ }
    }

    if (devMode.value) await loadDevStatus()

    if (isFirstLoad) {
      markPlanAnimShown()
      planLoading.value = false
      planJustGenerated.value = true
      setTimeout(() => { planJustGenerated.value = false }, 2000)
    }

    refreshAiPlanInBackground(uid)
  } catch (e) {
    uni.showToast({ title: e.message || '加载训练方案失败', icon: 'none' })
    if (isFirstLoad) planLoading.value = false
  }
}

function goTalent() {
  uni.navigateTo({ url: '/pages/talent/index' })
}

onMounted(async () => {
  await loadTodayPlan()
  restoreTrainingTimer()
  startDayUnlockWatch()
  if (devMode.value) loadDevStatus()
})
onShow(async () => {
  await loadTodayPlan(true)
  restoreTrainingTimer()
})
onUnmounted(() => {
  clearTimerTick()
  clearDayUnlockWatch()
})
function goBack() {
  uni.navigateBack({ delta: 1 })
}

function triggerGlitch() {
  const el = document.querySelector('.cyber-glitch')
  if (!el) return
  el.classList.add('glitching')
  setTimeout(() => el.classList.remove('glitching'), 500)
}
</script>

<style scoped>
@import 'augmented-ui/augmented-ui.min.css';
[data-augmented-ui].card, [data-augmented-ui].plan-card { --aug-border-bg:rgba(0,210,255,0.35); --aug-border-all:2px; }
.app { height:100vh; max-width:480px; margin:0 auto; background:#0b111e; font-family:PingFang SC,Roboto,sans-serif; display:flex; flex-direction:column; position:relative; overflow:hidden; }
.nav { display:flex; align-items:center; padding:14px 14px 0; }
.nav-back { width:36px; height:36px; border-radius:50%; background:rgba(0,210,255,0.08); border:1px solid rgba(0,210,255,0.2); display:flex; align-items:center; justify-content:center; cursor:pointer; }
.nav-title { flex:1; text-align:center; color:#fff; font-size:16px; font-weight:600; }
.nav-dev { min-width:36px; height:28px; padding:0 8px; border-radius:999px; background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.12); display:flex; align-items:center; justify-content:center; cursor:pointer; }
.nav-actions { display:flex; align-items:center; gap:6px; }
.nav-history { min-width:36px; height:28px; padding:0 8px; border-radius:999px; background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.12); display:flex; align-items:center; justify-content:center; cursor:pointer; }
.nav-history text { color:rgba(255,255,255,0.55); font-size:10px; font-weight:700; letter-spacing:0.04em; }
.history-list { max-height:50vh; overflow-y:auto; margin-bottom:8px; }
.history-row { padding:8px 0; border-bottom:1px solid var(--border); }
.hr-date { color:var(--text); font-size:12px; font-weight:600; display:block; }
.hr-meta { color:var(--text-dim); font-size:11px; display:block; margin-top:2px; }
.hr-note { color:var(--text-dim); font-size:10px; display:block; margin-top:2px; }
.history-empty { color:var(--text-dim); font-size:12px; text-align:center; padding:12px 0; }
.nav-dev text { color:rgba(255,255,255,0.55); font-size:10px; font-weight:700; letter-spacing:0.04em; }
.nav-dev.active { background:rgba(251,191,36,0.15); border-color:rgba(251,191,36,0.45); }
.nav-dev.active text { color:#fbbf24; }
.body { flex:1; overflow-y:auto; padding:12px 14px 0; scrollbar-width:none; -ms-overflow-style:none; }
.body::-webkit-scrollbar { display:none; }

.card { background:#243046; border-radius:10px; padding:14px 16px; margin-bottom:12px; position:relative; border:2px solid rgba(0,210,255,0.2); clip-path:polygon(8px 0,100% 0,100% calc(100% - 8px),calc(100% - 8px) 100%,0 100%,0 8px); }
.plan-label { color:#00d2ff; font-size:13px; font-weight:700; display:block; }
.plan-header { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:10px; flex-wrap:wrap; }
.plan-header-meta { color:rgba(255,255,255,0.55); font-size:11px; font-weight:600; white-space:nowrap; }
.plan-loading { color:rgba(255,255,255,0.45); font-size:12px; display:block; padding:8px 0; }

/* ---- AI 方案加载动画 ---- */
.plan-loading-wrap { text-align:center; padding:24px 8px 12px; }
.plan-loading-ring { position:relative; width:48px; height:48px; margin:0 auto 14px; }
.plr-core { position:absolute; inset:8px; border-radius:50%; background:rgba(0,210,255,0.08); border:1.5px solid rgba(0,210,255,0.25); animation:plrPulse 1.8s ease-in-out infinite; }
.plr-arc { position:absolute; inset:0; border-radius:50%; border:2px solid transparent; border-top-color:#00d2ff; animation:plrSpin 1.2s linear infinite; box-shadow:0 0 12px rgba(0,210,255,0.25); }
@keyframes plrSpin { to { transform:rotate(360deg); } }
@keyframes plrPulse { 0%,100% { transform:scale(0.85); opacity:0.5; } 50% { transform:scale(1.1); opacity:1; } }
.plan-loading-title { display:block; color:#fff; font-size:13px; font-weight:600; margin-bottom:10px; }
.plan-loading-bar { height:3px; width:70%; max-width:200px; margin:0 auto 8px; background:rgba(255,255,255,0.06); border-radius:999px; overflow:hidden; }
.plan-loading-bar-fill { height:100%; width:30%; background:linear-gradient(90deg,transparent,#00d2ff); border-radius:999px; animation:plrBar 1.6s ease-in-out infinite; }
@keyframes plrBar { 0% { margin-left:0; width:30%; } 50% { margin-left:50%; width:40%; } 100% { margin-left:70%; width:30%; } }
.plan-loading-hint { display:block; color:rgba(255,255,255,0.3); font-size:10px; }

/* ---- 方案生成完毕 ---- */
.plan-done-wrap { text-align:center; padding:28px 8px 16px; animation:doneFadeIn 0.4s ease-out; }
@keyframes doneFadeIn { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
.plan-done-icon { display:block; font-size:32px; margin-bottom:8px; animation:doneBounce 0.5s cubic-bezier(0.34,1.56,0.64,1); }
@keyframes doneBounce { from { transform:scale(0); } to { transform:scale(1); } }
.plan-done-title { display:block; color:#22c55e; font-size:15px; font-weight:700; margin-bottom:4px; }
.plan-done-sub { display:block; color:rgba(255,255,255,0.45); font-size:12px; }
.plan-empty { padding:10px 0 4px; }
.plan-empty-text { color:rgba(255,255,255,0.4); font-size:12px; line-height:1.5; }
.plan-transition-wrap { padding:16px 8px; text-align:center; }
.plan-transition-icon { font-size:28px; display:block; margin-bottom:8px; }
.plan-transition-title { color:#e6edf3; font-size:15px; font-weight:600; display:block; }
.plan-transition-sub { color:rgba(255,255,255,0.5); font-size:12px; margin-top:6px; display:block; }
.training-video { width:100%; border-radius:10px; background:#000; }
.video-progress-hint { display:block; margin-top:8px; font-size:12px; color:rgba(255,255,255,0.65); text-align:center; }
.plan-timeline { margin-top:2px; }
.tl-phase { display:flex; gap:10px; align-items:stretch; }
.tl-rail { display:flex; flex-direction:column; align-items:center; width:18px; flex-shrink:0; }
.tl-node { width:14px; height:14px; display:flex; align-items:center; justify-content:center; flex-shrink:0; margin-top:1px; }
.tl-node-icon { font-size:12px; line-height:1; color:rgba(255,255,255,0.35); }
.tl-node-active .tl-node-icon { color:#00d2ff; text-shadow:0 0 8px rgba(0,210,255,0.6); }
.tl-node-done .tl-node-icon { color:#22c55e; text-shadow:0 0 8px rgba(34,197,94,0.5); }
.tl-node-locked .tl-node-icon { color:rgba(255,255,255,0.25); }
.tl-line { width:1px; flex:1; min-height:16px; margin:3px 0; background:linear-gradient(180deg,rgba(0,210,255,0.35),rgba(0,210,255,0.08)); }
.tl-content { flex:1; min-width:0; padding-bottom:8px; }
.tl-node-row { cursor:pointer; }
.tl-phase-head { padding-top:0; min-width:0; display:flex; align-items:center; justify-content:space-between; }
.tl-phase-title { color:#fff; font-size:12px; font-weight:700; display:block; line-height:1.4; }
.tl-phase-right { display:flex; align-items:center; gap:6px; flex-shrink:0; }
.tl-phase-meta { color:rgba(255,255,255,0.38); font-size:10px; display:block; margin-top:0; }
.tl-phase-toggle { color:rgba(255,255,255,0.3); font-size:10px; cursor:pointer; }
.tl-items { margin:6px 0 2px; padding-left:2px; }
.tl-item { display:flex; align-items:center; gap:6px; padding:5px 0; cursor:pointer; }
.tl-item-icon { font-size:11px; width:14px; text-align:center; flex-shrink:0; }
.tl-item-title { flex:1; color:rgba(255,255,255,0.82); font-size:11px; line-height:1.35; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.tl-item-right { display:flex; align-items:center; gap:6px; flex-shrink:0; }
.tl-item-dur { color:rgba(255,255,255,0.35); font-size:10px; }
.tl-item-status { font-size:10px; }
.tl-st-locked { color:rgba(255,255,255,0.3); }
.tl-st-done { color:#22c55e; }
.tl-st-active { color:#00d2ff; }
.tl-st-pending { color:rgba(255,255,255,0.35); }
.plan-progress { margin-top:12px; padding-top:12px; border-top:1px solid rgba(0,210,255,0.12); }
.plan-progress-track { height:4px; background:rgba(255,255,255,0.08); border-radius:999px; overflow:hidden; }
.plan-progress-fill { height:100%; background:linear-gradient(90deg,#00d2ff,#22c55e); border-radius:999px; transition:width 0.35s ease; box-shadow:0 0 10px rgba(0,210,255,0.35); }
.plan-progress-text { display:block; margin-top:6px; color:rgba(255,255,255,0.45); font-size:10px; text-align:center; letter-spacing:0.04em; }
.plan-ai-box { background:rgba(0,210,255,0.06); border:1px solid rgba(0,210,255,0.18); border-radius:10px; padding:12px; margin-top:12px; }
.plan-ai-label { color:#00d2ff; font-size:11px; font-weight:700; display:block; margin-bottom:6px; }
.plan-ai-text { color:#fff; font-size:13px; line-height:1.65; display:block; white-space:pre-wrap; }
.plan-warn { color:#fbbf24; font-size:12px; display:block; margin-top:8px; cursor:pointer; }
.phase-section { scroll-margin-top:12px; }

.section-title { color:#fff; font-size:14px; font-weight:700; margin-bottom:8px; display:block; }
.section-title.dim { color:rgba(255,255,255,0.35); }

.step { background:#243046; border-radius:6px; padding:14px; display:flex; gap:10px; align-items:flex-start; border-left:4px solid #00d2ff; margin-bottom:8px; cursor:pointer; transition:all 0.15s; position:relative; clip-path:polygon(0 0,100% 0,100% calc(100% - 8px),calc(100% - 8px) 100%,0 100%); }
.step:active { background:#1a3040; }
.step.dim-step { border-left-color:rgba(255,255,255,0.1); }
.step.dim-step::after { border-color:rgba(255,255,255,0.1); }
.step-num { width:22px; height:22px; border-radius:50%; background:#00d2ff; color:#0b111e; display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:700; flex-shrink:0; }
.step-num.dim { background:rgba(255,255,255,0.1); }
.step-ready { border-left-color:#22c55e; }
.step-ready::after { border-color:#22c55e; }
.step-num-ready { background:#22c55e; }
.step-box-ready { background:rgba(34,197,94,0.08); border:1px solid rgba(34,197,94,0.15); }
.ready-text { color:#22c55e; }
.step-content { flex:1; }
.step-label { color:#fff; font-size:13px; font-weight:500; display:block; margin-bottom:6px; }
.step-label.dim-text { color:rgba(255,255,255,0.35); }
.step-box { background:#fff; border:2px solid rgba(0,210,255,0.2); border-radius:10px; padding:20px 14px; text-align:center; font-size:24px; color:#0b111e; }
.step-box.dim-box { opacity:0.3; }
.step-time { color:rgba(255,255,255,0.4); font-size:10px; text-align:center; display:block; margin-top:4px; }
.step-time.dim-text { color:rgba(255,255,255,0.35); }

.btn-checkin { background:linear-gradient(135deg,rgba(0,210,255,0.25),rgba(0,136,204,0.25)); border-radius:10px; padding:14px; text-align:center; margin-bottom:12px; cursor:pointer; box-shadow:0 0 20px rgba(0,210,255,0.15); }
.btn-checkin text { color:#00d2ff; font-size:15px; font-weight:600; }
.btn-checkin:active { opacity:0.85; }

.summary-card { border:2px dashed rgba(0,210,255,0.25); cursor:pointer; clip-path:polygon(8px 0,100% 0,100% calc(100% - 8px),calc(100% - 8px) 100%,0 100%,0 8px); }
.summary-card:active { background:#1a3040; }
.summary-label { color:rgba(255,255,255,0.5); font-size:12px; font-weight:500; display:block; margin-bottom:4px; }
.summary-text { color:rgba(255,255,255,0.4); font-size:12px; line-height:1.6; }
.summary-more { color:#00d2ff; font-size:11px; display:block; margin-top:4px; }
.summary-attitude { margin-top:10px; padding-top:10px; border-top:1px solid rgba(0,210,255,0.1); }
.sa-label { color:rgba(255,255,255,0.4); font-size:10px; font-weight:500; display:block; margin-bottom:6px; }
.sa-grid { display:flex; gap:4px; }
.sa-item { flex:1; text-align:center; padding:6px 2px; border-radius:6px; cursor:pointer; border:1px solid transparent; transition:all 0.15s; }
.sa-item:active { transform:scale(0.95); }
.sa-item.active { border-color:#00d2ff; background:rgba(0,136,204,0.2); }
.sa-pct { display:block; color:rgba(255,255,255,0.55); font-size:9px; font-weight:700; }
.sa-item.active .sa-pct { color:#00d2ff; }
.sa-emoji { display:block; font-size:12px; margin-top:1px; }

/* 未打卡 — 简约提示 */
.summary-empty { border:1px solid rgba(255,255,255,0.08); text-align:center; cursor:default; opacity:0.7; }
.summary-empty:active { background:var(--bg-card, #243046); }
.summary-empty-text { display:block; color:rgba(255,255,255,0.35); font-size:12px; line-height:1.5; }

.picker-overlay { position:fixed; inset:0; z-index:500; background:rgba(0,0,0,0.75); display:flex; align-items:center; justify-content:center; padding:20px; }
.picker-card { background:#1a2840; border:1px solid #00d2ff; border-radius:14px; padding:24px 20px; width:100%; max-width:360px; box-shadow:0 0 30px rgba(0,210,255,0.1); position:relative; }
.picker-card::before, .picker-card::after { content:''; position:absolute; width:10px; height:10px; border-color:#00d2ff; border-style:solid; }
.picker-card::before { top:0; left:0; border-width:1px 0 0 1px; }
.picker-card::after { bottom:0; right:0; border-width:0 1px 1px 0; }
.picker-title { color:#fff; font-size:16px; font-weight:700; text-align:center; display:block; margin-bottom:16px; }

/* 打卡弹窗 */
.checkin-modal { max-height:85vh; overflow-y:auto; padding:20px 16px; max-width:400px; }
.assessment-modal { max-width:320px; padding:28px 22px 22px; text-align:center; }
.assessment-modal-icon { font-size:40px; display:block; margin-bottom:12px; }
.assessment-modal-title { display:block; color:#fff; font-size:17px; font-weight:700; margin-bottom:10px; }
.assessment-modal-desc { display:block; color:rgba(255,255,255,0.65); font-size:13px; line-height:1.55; margin-bottom:22px; }
.assessment-modal-actions { display:flex; gap:10px; }
.assessment-btn { flex:1; padding:12px 10px; border-radius:10px; cursor:pointer; }
.assessment-btn text { font-size:14px; font-weight:600; }
.assessment-btn.secondary { background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.15); }
.assessment-btn.secondary text { color:rgba(255,255,255,0.7); }
.assessment-btn.primary { background:linear-gradient(135deg,#00d2ff,#3b8bff); }
.assessment-btn.primary text { color:#fff; }
.checkin-modal .picker-panel { margin-bottom:10px; }
.checkin-modal .form-card { margin-bottom:8px; }
.modal-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:14px; }
.modal-title { color:#fff; font-size:16px; font-weight:700; }
.modal-close { color:rgba(255,255,255,0.5); font-size:20px; cursor:pointer; padding:4px 8px; }
.picker-close { text-align:center; margin-top:16px; cursor:pointer; }
.picker-close text { color:rgba(255,255,255,0.5); font-size:14px; }
.submitted-item { display:flex; align-items:center; gap:8px; padding:10px 0; border-bottom:1px solid rgba(0,210,255,0.1); }
.submitted-item:last-child { border-bottom:none; }
.si-text { flex:1; color:#fff; font-size:13px; }
.si-actions { display:flex; gap:10px; flex-shrink:0; }
.si-edit { color:#00d2ff; font-size:16px; cursor:pointer; }
.si-del { color:rgba(255,255,255,0.4); font-size:16px; cursor:pointer; }
.si-del:active { color:#ff6b6b; }

.time-card { }
.time-header { display:flex; align-items:center; gap:8px; margin-bottom:10px; }
.time-status-tag { font-size:10px; padding:2px 8px; border-radius:999px; }
.time-status-tag.running { background:rgba(34,197,94,0.15); color:#22c55e; }
.time-status-tag.expired { background:rgba(239,68,68,0.15); color:#ef4444; }
.time-setup { display:flex; flex-direction:column; gap:10px; }
.time-pickers { display:flex; gap:10px; justify-content:center; max-width:280px; margin:0 auto; }
.time-select { flex:1; background:rgba(0,210,255,0.05); border:1px solid rgba(0,210,255,0.2); border-radius:10px; padding:12px 10px; display:flex; align-items:baseline; justify-content:center; gap:4px; cursor:pointer; }
.time-select-val { color:#fff; font-size:22px; font-weight:700; }
.time-select-unit { color:rgba(255,255,255,0.5); font-size:12px; }
.time-start-btn { background:linear-gradient(135deg,rgba(0,210,255,0.35),rgba(0,136,204,0.35)); border-radius:10px; padding:12px; text-align:center; cursor:pointer; }
.time-start-btn text { color:#00d2ff; font-size:15px; font-weight:600; }
.time-start-btn.disabled { opacity:0.4; pointer-events:none; }
.time-setup-hint { color:rgba(255,255,255,0.35); font-size:11px; text-align:center; }
.time-running { text-align:center; padding:4px 0; }
.time-countdown { display:block; color:#22c55e; font-size:36px; font-weight:800; letter-spacing:0.06em; font-variant-numeric:tabular-nums; }
.time-running-hint { display:block; margin-top:6px; color:rgba(255,255,255,0.45); font-size:11px; }
.time-expired { text-align:center; padding:6px 0; }
.time-expired-icon { display:block; font-size:28px; margin-bottom:6px; }
.time-expired-text { display:block; color:#ef4444; font-size:14px; font-weight:600; }
.time-expired-sub { display:block; margin-top:4px; color:rgba(255,255,255,0.4); font-size:11px; }
.dev-panel { margin-top:12px; padding-top:12px; border-top:1px dashed rgba(251,191,36,0.25); }
.dev-panel-label { display:block; color:#fbbf24; font-size:11px; font-weight:700; margin-bottom:8px; }
.dev-status { margin-bottom:8px; padding:6px 10px; background:rgba(251,191,36,0.06); border:1px solid rgba(251,191,36,0.2); border-radius:8px; }
.dev-status text { color:rgba(251,191,36,0.9); font-size:10px; line-height:1.4; }
.dev-actions { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:8px; }
.dev-action { flex:1; min-width:88px; background:rgba(251,191,36,0.08); border:1px solid rgba(251,191,36,0.25); border-radius:8px; padding:8px 6px; text-align:center; cursor:pointer; }
.dev-action-primary { background:rgba(34,197,94,0.12); border-color:rgba(34,197,94,0.35); }
.dev-action-primary text { color:#4ade80; }
.dev-action-danger { background:rgba(239,68,68,0.08); border-color:rgba(239,68,68,0.2); }
.dev-action-danger text { color:rgba(239,68,68,0.7); }
.dev-action text { color:#fbbf24; font-size:11px; font-weight:600; }
.dev-panel-hint { display:block; margin-top:8px; color:rgba(255,255,255,0.3); font-size:10px; text-align:center; }
.media-block, .checkin-block { position:relative; }
.media-block { display:flex; gap:8px; margin-bottom:18px; }
.media-block .step { flex:1; min-width:0; margin-bottom:0; padding:10px 8px; }
.media-block .step-box { font-size:14px; padding:12px 6px; }
.media-block .step-label { font-size:11px; margin-bottom:4px; }
.media-block .step-num { width:18px; height:18px; font-size:10px; }
.media-block.locked, .checkin-block.locked { pointer-events:none; }
.media-block.locked .step { opacity:0.4; }
.checkin-block.locked { opacity:0.35; }
.media-lock-overlay, .checkin-lock-overlay { position:absolute; inset:0; z-index:10; display:flex; align-items:center; justify-content:center; pointer-events:none; }
.media-lock-text, .checkin-lock-text { background:rgba(11,17,30,0.92); border:1px solid rgba(0,210,255,0.25); color:#00d2ff; font-size:12px; padding:8px 14px; border-radius:999px; }
.step-locked { cursor:not-allowed; }
[data-theme="white"] .nav-dev { background:#f3f4f6; border-color:#e5e7eb; }
[data-theme="white"] .nav-dev text { color:#9ca3af; }
[data-theme="white"] .nav-dev.active { background:rgba(251,191,36,0.12); border-color:rgba(251,191,36,0.45); }
[data-theme="white"] .nav-dev.active text { color:#d97706; }
[data-theme="white"] .dev-action { background:#fffbeb; border-color:#fde68a; }
[data-theme="white"] .dev-action text { color:#d97706; }
[data-theme="white"] .dev-panel-label { color:#d97706; }
[data-theme="white"] .dev-panel-hint { color:#9ca3af; }
[data-theme="white"] .time-select { background:#f9fafb; border-color:#e5e7eb; }
[data-theme="white"] .time-select-val { color:#1a1a2e; }
[data-theme="white"] .time-select-unit { color:#9ca3af; }
[data-theme="white"] .time-start-btn { background:linear-gradient(135deg,#2563eb,#1d4ed8); }
[data-theme="white"] .time-start-btn text { color:#fff; }
[data-theme="white"] .time-setup-hint { color:#9ca3af; }
[data-theme="white"] .time-running-hint { color:#9ca3af; }
[data-theme="white"] .time-expired-sub { color:#9ca3af; }
[data-theme="white"] .media-lock-text, [data-theme="white"] .checkin-lock-text { background:#fff; border-color:#e5e7eb; color:#2563eb; }

.divider { height:1px; background:linear-gradient(90deg,transparent,rgba(0,210,255,0.3),transparent); margin:12px 0; }
.b-section { }
.step-preview-locked { cursor:not-allowed; }
.step-preview-locked .step-box { border-style:dashed; opacity:0.85; }
.lock-tip { text-align:center; color:rgba(255,255,255,0.4); font-size:12px; display:block; margin-top:6px; }

.picker-panel { padding:16px 14px; margin-bottom:12px; background:rgba(13,23,40,0.6); box-shadow:0 0 24px rgba(0,210,255,0.08),inset 0 0 40px rgba(0,210,255,0.02); }
[data-augmented-ui].picker-panel { --aug-border-bg:rgba(0,210,255,0.35); --aug-border-all:2px; --aug-clip-tl:12px; --aug-clip-tr:12px; --aug-clip-br:12px; --aug-clip-bl:12px; }
[data-augmented-ui].btn-checkin { --aug-border-bg:rgba(0,210,255,0.3); --aug-border-all:1px; --aug-clip-tl:10px; --aug-clip-br:10px; }
.picker-panel-header { display:flex; align-items:center; justify-content:center; gap:8px; margin-bottom:12px; }
.pph-dot { color:#00d2ff; font-size:8px; }
.pph-title { color:rgba(255,255,255,0.5); font-size:11px; letter-spacing:0.1em; text-transform:uppercase; }

.picker-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:6px; }
.picker-item { background:rgba(200,210,230,0.25); border-radius:8px; padding:12px 4px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.1); transition:all 0.2s; opacity:0; animation:matrixReveal 0.5s ease-out forwards; position:relative; overflow:hidden; }
.picker-item:nth-child(1),.picker-item:nth-child(2),.picker-item:nth-child(3),.picker-item:nth-child(4) { animation-delay:0.05s; }
.picker-item:nth-child(5),.picker-item:nth-child(6),.picker-item:nth-child(7),.picker-item:nth-child(8) { animation-delay:0.15s; }
.picker-item:nth-child(9),.picker-item:nth-child(10),.picker-item:nth-child(11),.picker-item:nth-child(12) { animation-delay:0.25s; }
.picker-item:nth-child(13) { animation-delay:0.35s; }
@keyframes matrixReveal {
  0% { opacity:0; transform:translateY(-8px) scale(0.95); }
  60% { opacity:0.6; }
  100% { opacity:1; transform:translateY(0) scale(1); }
}
.picker-item:active { border-color:#00d2ff; transform:scale(0.96); }
.pi-text { color:#fff; font-size:11px; font-weight:600; letter-spacing:0.02em; }
.picker-item.active { border-color:#00d2ff; background:#0088cc; box-shadow:0 0 20px rgba(0,210,255,0.35),inset 0 0 10px rgba(0,0,0,0.15); }
.picker-item.active .pi-text { color:#fff; text-shadow:0 0 6px rgba(0,210,255,0.5); }
.picker-item.ability-spark::before {
  content:''; position:absolute;
  width:30px; height:2px;
  background:#00d2ff;
  box-shadow:0 0 6px #00d2ff, 0 0 14px #00d2ff;
  animation:borderSweep 1.4s ease-in-out forwards;
  pointer-events:none; z-index:3;
  border-radius:1px;
}
@keyframes borderSweep {
  0%   { top:0; left:-10px; width:30px; height:2px; }
  18%  { top:0; left:calc(100% - 20px); width:30px; height:2px; }
  22%  { top:0; left:calc(100% - 2px); width:2px; height:25px; }
  40%  { top:calc(100% - 25px); left:calc(100% - 2px); width:2px; height:25px; }
  44%  { top:calc(100% - 2px); left:calc(100% - 20px); width:30px; height:2px; }
  62%  { top:calc(100% - 2px); left:-10px; width:30px; height:2px; }
  66%  { top:calc(100% - 25px); left:0; width:2px; height:25px; }
  84%  { top:0; left:0; width:2px; height:25px; }
  100% { top:0; left:-10px; width:30px; height:2px; opacity:0; }
}

.form-card { background:#1a2840; border:2px solid rgba(0,210,255,0.5); border-radius:12px; padding:18px; margin-bottom:10px; position:relative; box-shadow:0 0 20px rgba(0,210,255,0.12), inset 0 0 30px rgba(0,210,255,0.02); clip-path:polygon(10px 0,100% 0,100% calc(100% - 10px),calc(100% - 10px) 100%,0 100%,0 10px); animation:scanDown 0.4s cubic-bezier(0.25,0.8,0.25,1) both; }
@keyframes scanDown {
  0% { clip-path:polygon(10px 0,100% 0,100% 4px,calc(100% - 10px) 4px,0 4px,0 4px); opacity:0.3; box-shadow:0 0 60px rgba(0,210,255,0.4); }
  50% { box-shadow:0 0 40px rgba(0,210,255,0.3); }
  100% { clip-path:polygon(10px 0,100% 0,100% calc(100% - 10px),calc(100% - 10px) 100%,0 100%,0 10px); opacity:1; box-shadow:0 0 20px rgba(0,210,255,0.12); }
}
.scan-line { position:absolute; top:0; left:8%; width:84%; height:1px; background:linear-gradient(90deg,transparent,#00d2ff,transparent); animation:scanLine 0.4s cubic-bezier(0.25,0.8,0.25,1) forwards; pointer-events:none; z-index:1; }
@keyframes scanLine {
  0% { top:0; opacity:1; }
  100% { top:100%; opacity:0; }
}
.form-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:14px; }
.form-title { color:#fff; font-size:14px; font-weight:700; }
.form-del { color:rgba(255,255,255,0.4); font-size:18px; cursor:pointer; padding:2px 6px; }
.form-del:active { color:#ff6b6b; }
.form-row { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
.form-label { color:rgba(255,255,255,0.5); font-size:13px; width:110px; flex-shrink:0; }
.form-input { flex:1; background:#fff; border:2px solid rgba(0,210,255,0.2); border-radius:10px; padding:10px 12px; font-size:13px; color:#0b111e; }
.form-textarea { flex:1; background:#fff; border:2px solid rgba(0,210,255,0.2); border-radius:10px; padding:10px 12px; font-size:13px; color:#0b111e; height:60px; }
.form-tags { display:flex; flex-wrap:wrap; gap:6px; flex:1; }
.ftag { padding:6px 14px; border-radius:8px; background:rgba(255,255,255,0.08); color:rgba(255,255,255,0.6); font-size:12px; border:1px solid rgba(0,210,255,0.2); cursor:pointer; transition:all 0.15s; }
.ftag.on { background:#0088cc; border-color:#00d2ff; color:#fff; box-shadow:0 0 10px rgba(0,210,255,0.2); }
.form-inline { display:flex; align-items:center; gap:6px; flex:1; }
.form-file-wrap { flex:1; }
.file-btn { background:rgba(0,210,255,0.1); border:1px dashed rgba(0,210,255,0.25); border-radius:10px; padding:10px; text-align:center; cursor:pointer; }
.file-btn text { color:#00d2ff; font-size:12px; }
.file-hint { color:rgba(255,255,255,0.3); font-size:10px; display:block; margin-top:4px; text-align:center; }
.file-previews { display:flex; flex-wrap:wrap; gap:6px; margin-top:6px; }
.file-preview { position:relative; width:60px; height:60px; border-radius:8px; overflow:hidden; }
.preview-img, .preview-video { width:100%; height:100%; object-fit:cover; }
.file-del { position:absolute; top:2px; right:2px; background:rgba(0,0,0,0.6); color:#fff; font-size:10px; width:16px; height:16px; border-radius:50%; display:flex; align-items:center; justify-content:center; cursor:pointer; }
[data-theme="white"] .file-btn { background:#f3f4f6; border-color:#e5e7eb; }
[data-theme="white"] .file-btn text { color:#2563eb; }
[data-theme="white"] .file-hint { color:#9ca3af; }

.form-input.short { width:80px; flex:none; background:#fff; color:#0b111e; }
.form-inline .form-unit { color:rgba(255,255,255,0.7); }
.form-unit { color:rgba(255,255,255,0.5); font-size:12px; }

.score-panel { border:2px solid rgba(0,210,255,0.2); border-radius:10px; padding:14px; margin-bottom:12px; background:rgba(13,23,40,0.5); }
.score-header { display:flex; align-items:center; justify-content:center; gap:8px; margin-bottom:10px; }
.score-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:6px; }
.score-item { background:rgba(200,210,230,0.1); border-radius:8px; padding:10px 6px; text-align:center; cursor:pointer; border:1px solid rgba(255,255,255,0.06); transition:all 0.2s; opacity:0; animation:popIn 0.4s cubic-bezier(0.34,1.56,0.64,1) forwards; }
.score-item:nth-child(1) { animation-delay:0.05s; }
.score-item:nth-child(2) { animation-delay:0.12s; }
.score-item:nth-child(3) { animation-delay:0.19s; }
.score-item:nth-child(4) { animation-delay:0.26s; }
.score-item:nth-child(5) { animation-delay:0.33s; }
.score-item:nth-child(6) { animation-delay:0.40s; }
.score-item:active { transform:scale(0.96); }
.score-item.active { border-color:#00d2ff; background:rgba(0,136,204,0.3); box-shadow:0 0 12px rgba(0,210,255,0.15); }
/* White theme */
[data-theme="white"] .app { background:#f0f2f5; }
[data-theme="white"] .nav-title { color:#1a1a2e; }
[data-theme="white"] .nav-back { background:#fff; border-color:#e5e7eb; }
[data-theme="white"] .card { background:#fff; border:2px solid #e5e7eb; box-shadow:0 2px 12px rgba(0,0,0,0.04); }
[data-theme="white"] .card::before, [data-theme="white"] .card::after { border-color:#2563eb; }
[data-theme="white"] [data-augmented-ui].card, [data-theme="white"] [data-augmented-ui].plan-card { --aug-border-bg:#e5e7eb; }
[data-theme="white"] .plan-label { color:#2563eb; }
[data-theme="white"] .plan-loading { color:#9ca3af; }
[data-theme="white"] .plan-loading-title { color:#1a1a2e; }
[data-theme="white"] .plan-loading-hint { color:#9ca3af; }
[data-theme="white"] .plr-core { background:rgba(37,99,235,0.05); border-color:rgba(37,99,235,0.15); }
[data-theme="white"] .plr-arc { border-top-color:#2563eb; box-shadow:0 0 12px rgba(37,99,235,0.15); }
[data-theme="white"] .plan-loading-bar { background:#e5e7eb; }
[data-theme="white"] .plan-loading-bar-fill { background:linear-gradient(90deg,transparent,#2563eb); }
[data-theme="white"] .plan-done-title { color:#16a34a; }
[data-theme="white"] .plan-done-sub { color:#6b7280; }
[data-theme="white"] .plan-ai-box { background:#eff6ff; border-color:#bfdbfe; }
[data-theme="white"] .plan-ai-label { color:#2563eb; }
[data-theme="white"] .plan-ai-text { color:#1a1a2e; }
[data-theme="white"] .section-title { color:#1a1a2e; }
[data-theme="white"] .step { background:#fff; border-left-color:#2563eb; box-shadow:0 2px 8px rgba(0,0,0,0.03); }
[data-theme="white"] .step-num { background:#2563eb; }
[data-theme="white"] .step-label { color:#1a1a2e; }
[data-theme="white"] .step-box { background:#f9fafb; border-color:#e5e7eb; color:#1a1a2e; }
[data-theme="white"] .step-time { color:#9ca3af; }
[data-theme="white"] .btn-checkin { background:linear-gradient(135deg,#2563eb,#1d4ed8); }
[data-theme="white"] .btn-checkin text { color:#fff; }
[data-theme="white"] .summary-card { border-color:#e5e7eb; }
[data-theme="white"] .summary-label { color:#6b7280; }
[data-theme="white"] .summary-text { color:#9ca3af; }
[data-theme="white"] .summary-more { color:#2563eb; }
[data-theme="white"] .summary-attitude { border-top-color:#e5e7eb; }
[data-theme="white"] .sa-label { color:#9ca3af; }
[data-theme="white"] .sa-pct { color:#6b7280; }
[data-theme="white"] .sa-item.active { border-color:#2563eb; background:rgba(37,99,235,0.06); }
[data-theme="white"] .sa-item.active .sa-pct { color:#2563eb; }
[data-theme="white"] .summary-empty { border-color:#e5e7eb; opacity:0.6; }
[data-theme="white"] .summary-empty-text { color:#9ca3af; }
[data-theme="white"] .step-watched { border-left-color:#16a34a !important; }
[data-theme="white"] .step-num-done { background:#16a34a !important; }
[data-theme="white"] .picker-panel { background:#fff; border-color:#e5e7eb; box-shadow:0 4px 24px rgba(0,0,0,0.06); }
[data-theme="white"] .pph-dot { color:#2563eb; }
[data-theme="white"] .pph-title { color:#6b7280; }
[data-theme="white"] .picker-item { background:#f3f4f6; border-color:#e5e7eb; }
[data-theme="white"] .pi-text { color:#374151; }
[data-theme="white"] .picker-item.active { background:#2563eb; border-color:#2563eb; }
[data-theme="white"] .picker-item.active .pi-text { color:#fff; text-shadow:none; }
[data-theme="white"] .form-card { background:#fff; border-color:#2563eb; box-shadow:0 4px 20px rgba(0,0,0,0.06); }
[data-theme="white"] .form-title { color:#1a1a2e; }
[data-theme="white"] .form-label { color:#6b7280; }
[data-theme="white"] .form-input { background:#f9fafb; border-color:#e5e7eb; color:#1a1a2e; }
[data-theme="white"] .form-textarea { background:#f9fafb; border-color:#e5e7eb; color:#1a1a2e; }
[data-theme="white"] .form-input.short { background:#fff; }
[data-theme="white"] .ftag { background:#f3f4f6; color:#6b7280; border-color:#e5e7eb; }
[data-theme="white"] .ftag.on { background:#2563eb; border-color:#2563eb; color:#fff; }
[data-theme="white"] .score-panel { background:#fff; border-color:#e5e7eb; box-shadow:0 4px 20px rgba(0,0,0,0.04); }
[data-theme="white"] .score-item { background:#f3f4f6; border-color:#e5e7eb; }
[data-theme="white"] .score-item.active { background:rgba(37,99,235,0.08); border-color:#2563eb; }
[data-theme="white"] .si-pct { color:#2563eb; }
[data-theme="white"] .si-desc { color:#6b7280; }
[data-theme="white"] .score-item.active .si-desc { color:#1a1a2e; }
[data-theme="white"] .divider { background:#e5e7eb; }
[data-theme="white"] .picker-overlay { background:rgba(0,0,0,0.4); }
[data-theme="white"] .picker-card { background:#fff; border-color:#e5e7eb; }
[data-theme="white"] .picker-card::before, [data-theme="white"] .picker-card::after { border-color:#2563eb; }
[data-theme="white"] .assessment-modal-title { color:#1a1a2e; }
[data-theme="white"] .assessment-modal-desc { color:#6b7280; }
[data-theme="white"] .assessment-btn.secondary { background:#f3f4f6; border-color:#e5e7eb; }
[data-theme="white"] .assessment-btn.secondary text { color:#6b7280; }
[data-theme="white"] .picker-title { color:#1a1a2e; }
[data-theme="white"] .modal-title { color:#1a1a2e; }
[data-theme="white"] .modal-close { color:#9ca3af; }
[data-theme="white"] .si-text { color:#1a1a2e; }
[data-theme="white"] .lock-tip { color:#9ca3af; }
[data-theme="white"] .step-label.dim-text { color:#d1d5db; }
[data-theme="white"] .step-time.dim-text { color:#9ca3af; }
[data-theme="white"] .step.dim-step { border-left-color:rgba(0,0,0,0.06); }
[data-theme="white"] .step.dim-step::after { border-color:rgba(0,0,0,0.06); }
[data-theme="white"] .step-num.dim { background:#d1d5db; }
[data-theme="white"] .b-section.locked .section-title { color:#d1d5db; }
[data-theme="white"] .section-title.dim { color:#d1d5db; }
[data-theme="white"] .step-num { color:#fff; }
[data-theme="white"] .si-edit { color:#2563eb; }
[data-theme="white"] .si-del { color:#9ca3af; }
[data-theme="white"] .si-del:active { color:#ef4444; }
[data-theme="white"] .form-del { color:#9ca3af; }
[data-theme="white"] .form-del:active { color:#ef4444; }
[data-theme="white"] .submitted-item { border-bottom-color:#e5e7eb; }
[data-theme="white"] .step-content .step-time { color:#9ca3af; }
[data-theme="white"] .step-box.dim-box { opacity:0.6; }

/* ---- 时间轴总览 — 白色主题 ---- */
[data-theme="white"] .plan-header-meta { color:#6b7280; }
[data-theme="white"] .plan-empty-text { color:#9ca3af; }
[data-theme="white"] .tl-phase-title { color:#1a1a2e; }
[data-theme="white"] .tl-phase-meta { color:#9ca3af; }
[data-theme="white"] .tl-phase-toggle { color:#d1d5db; }
[data-theme="white"] .tl-item-title { color:#374151; }
[data-theme="white"] .tl-item-dur { color:#9ca3af; }
[data-theme="white"] .tl-item-status.tl-st-locked { color:#d1d5db; }
[data-theme="white"] .tl-item-status.tl-st-done { color:#16a34a; }
[data-theme="white"] .tl-item-status.tl-st-active { color:#2563eb; }
[data-theme="white"] .tl-item-status.tl-st-pending { color:#9ca3af; }
[data-theme="white"] .tl-node-locked .tl-node-icon { color:#d1d5db; text-shadow:none; }
[data-theme="white"] .tl-node-active .tl-node-icon { color:#2563eb; text-shadow:0 0 8px rgba(37,99,235,0.3); }
[data-theme="white"] .tl-node-done .tl-node-icon { color:#16a34a; text-shadow:0 0 8px rgba(22,163,74,0.3); }
[data-theme="white"] .tl-line { background:linear-gradient(180deg,#2563eb,#93c5fd); }
[data-theme="white"] .plan-progress { border-top-color:#e5e7eb; }
[data-theme="white"] .plan-progress-track { background:#e5e7eb; }
[data-theme="white"] .plan-progress-fill { background:linear-gradient(90deg,#2563eb,#16a34a); box-shadow:0 0 10px rgba(37,99,235,0.2); }
[data-theme="white"] .plan-progress-text { color:#6b7280; }

@keyframes popIn {
  0% { opacity:0; transform:scale(0.5) translateY(10px); }
  100% { opacity:1; transform:scale(1) translateY(0); }
}
.si-pct { color:#00d2ff; font-size:18px; font-weight:800; display:block; }
.si-emoji { font-size:16px; display:block; margin:2px 0; }
.si-desc { color:rgba(255,255,255,0.5); font-size:9px; line-height:1.3; display:block; }
.score-item.active .si-desc { color:#fff; }

.card-enter-active { animation:scanDown 0.4s cubic-bezier(0.25,0.8,0.25,1); }
.card-leave-active { animation:cardOut 0.25s ease-in forwards; max-height:200px; overflow:hidden; }
.card-leave-to { max-height:0; padding-top:0; padding-bottom:0; margin-bottom:0; opacity:0; }
@keyframes cardOut {
  0% { clip-path:polygon(10px 0,100% 0,100% calc(100% - 10px),calc(100% - 10px) 100%,0 100%,0 10px); opacity:1; }
  100% { clip-path:polygon(10px 0,100% 0,100% 4px,calc(100% - 10px) 4px,0 4px,0 4px); opacity:0; }
}
.player-overlay { position:fixed; inset:0; z-index:600; background:rgba(0,0,0,0.85); display:flex; align-items:center; justify-content:center; padding:16px; }
.player-card { background:var(--bg-card,#1a2840); border:1px solid rgba(0,210,255,0.2); border-radius:16px; padding:16px; width:100%; max-width:420px; }
.player-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
.player-title { color:#fff; font-size:15px; font-weight:600; }
.player-close { color:rgba(255,255,255,0.5); font-size:20px; cursor:pointer; padding:4px 8px; }
.player-body { }
[data-theme="white"] .player-overlay { background:rgba(0,0,0,0.6); }
[data-theme="white"] .player-card { background:#fff; border-color:#e5e7eb; }
[data-theme="white"] .player-title { color:#1a1a2e; }
[data-theme="white"] .player-close { color:#9ca3af; }

.pulse-out { animation:pulseRing 0.5s ease-out; }
@keyframes pulseRing {
  0% { box-shadow:0 0 0 0 rgba(0,210,255,0.5); }
  100% { box-shadow:0 0 0 50px rgba(0,210,255,0); }
}
.spark { animation:btnSpark 0.4s ease-out; }
.warn-flash { animation:warnFlash 0.6s ease-out; }
@keyframes warnFlash {
  0%,100% { box-shadow:0 0 0 0 rgba(255,68,68,0); background:linear-gradient(135deg,rgba(0,210,255,0.25),rgba(0,136,204,0.25)); }
  20% { box-shadow:0 0 30px rgba(255,68,68,0.6),0 0 0 8px rgba(255,68,68,0.2); background:linear-gradient(135deg,rgba(255,68,68,0.3),rgba(255,68,68,0.2)); }
  40% { box-shadow:0 0 0 0 rgba(255,68,68,0); }
  60% { box-shadow:0 0 25px rgba(255,68,68,0.4),0 0 0 6px rgba(255,68,68,0.15); background:linear-gradient(135deg,rgba(255,68,68,0.25),rgba(255,68,68,0.15)); }
}
@keyframes btnSpark {
  0% { box-shadow:0 0 0 0 rgba(0,210,255,0.6), inset 0 0 30px rgba(0,210,255,0.3); transform:scale(1.02); }
  40% { box-shadow:0 0 20px rgba(0,210,255,0.3), 0 0 0 8px rgba(0,210,255,0.15); }
  100% { box-shadow:0 0 10px rgba(0,210,255,0.15); transform:scale(1); }
}

/* ═══════════════════════════════════════════
   赛博朋克特效层
   ═══════════════════════════════════════════ */

/* ── CRT 扫描线 ── */
.cyber-scanlines {
  position:fixed; inset:0; z-index:999; pointer-events:none;
  background:repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px);
  opacity:0.6;
}
[data-theme="white"] .cyber-scanlines {
  background:repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.015) 2px, rgba(0,0,0,0.015) 4px);
  opacity:0.4;
}

/* ── 标题故障效果 ── */
.cyber-glitch {
  position:relative; cursor:pointer; user-select:none;
}
.cyber-glitch::before,
.cyber-glitch::after {
  content:'今日训练';
  position:absolute; top:0; left:0; width:100%; height:100%;
  opacity:0; pointer-events:none;
}
.cyber-glitch::before { color:#ff6ec7; z-index:-1; }
.cyber-glitch::after  { color:#00d2ff; z-index:-2; }
.cyber-glitch.glitching { animation:glitchShake 0.3s ease-in-out; }
.cyber-glitch.glitching::before {
  animation:glitchOffset1 0.3s steps(2) forwards;
  opacity:1; clip-path:inset(20% 0 60% 0);
}
.cyber-glitch.glitching::after {
  animation:glitchOffset2 0.3s steps(2) forwards;
  opacity:1; clip-path:inset(60% 0 20% 0);
}
@keyframes glitchShake {
  0%,100% { transform:translate(0); }
  20% { transform:translate(-3px,2px); }
  40% { transform:translate(3px,-1px); }
  60% { transform:translate(-1px,-2px); }
  80% { transform:translate(2px,1px); }
}
@keyframes glitchOffset1 {
  0% { transform:translate(0); }
  100% { transform:translate(-4px,1px); }
}
@keyframes glitchOffset2 {
  0% { transform:translate(0); }
  100% { transform:translate(4px,-1px); }
}

/* ── 全息光泽（卡片） ── */
.card {
  position:relative; overflow:hidden;
}
.card::before {
  content:''; position:absolute; inset:0; z-index:0; pointer-events:none;
  background:linear-gradient(125deg, transparent 30%, rgba(0,210,255,0.04) 45%, rgba(255,110,199,0.04) 55%, transparent 70%);
  background-size:200% 200%;
  animation:holoSheen 6s ease-in-out infinite;
  border-radius:inherit;
}
@keyframes holoSheen {
  0%,100% { background-position:0% 50%; }
  50% { background-position:100% 50%; }
}

/* ── 霓虹呼吸 ── */
.card { animation:neonBreathe 4s ease-in-out infinite; }
@keyframes neonBreathe {
  0%,100% { box-shadow:0 0 8px rgba(0,210,255,0.08), inset 0 0 20px rgba(0,210,255,0.01); }
  50% { box-shadow:0 0 18px rgba(0,210,255,0.18), 0 0 40px rgba(255,110,199,0.06), inset 0 0 30px rgba(0,210,255,0.03); }
}

/* ── 悬浮微倾斜 ── */
.card:active {
  transform:perspective(600px) rotateX(1deg) rotateY(-1deg) scale(0.985);
  transition:transform 0.1s ease-out;
}

/* ── 按钮霓虹爆发 ── */
.btn-checkin {
  position:relative; overflow:hidden;
}
.btn-checkin::after {
  content:''; position:absolute; top:50%; left:50%; width:0; height:0;
  border-radius:50%; background:rgba(0,210,255,0.3);
  transform:translate(-50%,-50%);
  transition:width 0.6s ease-out, height 0.6s ease-out, opacity 0.6s;
  pointer-events:none;
}
.btn-checkin:active::after {
  width:600px; height:600px; opacity:0;
}

/* ── 进度条数据流 ── */
.plan-progress-track {
  position:relative; overflow:hidden;
}
.plan-progress-track::after {
  content:''; position:absolute; top:0; left:-60px; width:60px; height:100%;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,0.3),transparent);
  animation:dataStream 2s linear infinite;
  pointer-events:none; z-index:2;
}
@keyframes dataStream {
  0% { left:-60px; }
  100% { left:100%; }
}

/* ── 步骤卡片光晕增强 ── */
.step {
  transition:all 0.2s ease, box-shadow 0.3s ease;
}
.step:active {
  box-shadow:0 0 20px rgba(0,210,255,0.25), inset 0 0 30px rgba(0,210,255,0.04) !important;
  border-left-width:6px;
}

/* ── 计时器数字终端风格 ── */
.time-countdown {
  font-family:'SF Mono','Cascadia Code','Fira Code','Courier New',monospace !important;
  text-shadow:0 0 20px rgba(34,197,94,0.5), 0 0 40px rgba(34,197,94,0.2);
}
[data-theme="white"] .time-countdown {
  text-shadow:none;
}

/* ── 分割线动态 ── */
.divider {
  background:linear-gradient(90deg,transparent,rgba(0,210,255,0.4),rgba(255,110,199,0.2),rgba(0,210,255,0.4),transparent) !important;
  animation:dividerFlow 3s ease-in-out infinite;
  background-size:200% 100% !important;
}
@keyframes dividerFlow {
  0%,100% { background-position:0% 50%; }
  50% { background-position:100% 50%; }
}

/* ── 能力网格悬浮全息 ── */
.picker-item {
  position:relative; overflow:hidden;
}
.picker-item::after {
  content:''; position:absolute; inset:0; pointer-events:none;
  background:radial-gradient(circle at var(--mx,50%) var(--my,50%), rgba(0,210,255,0.15) 0%, transparent 60%);
  opacity:0; transition:opacity 0.2s;
}
.picker-item:active::after { opacity:1; }

/* ── 解锁B段动画 ── */
.b-section.locked { transition:all 0.3s; }
.lock-tip {
  animation:lockPulse 2.5s ease-in-out infinite;
}
@keyframes lockPulse {
  0%,100% { opacity:0.4; }
  50% { opacity:0.8; text-shadow:0 0 8px rgba(0,210,255,0.3); }
}

/* ── 训练项已完成标记 ── */
.step-watched { border-left-color:#22c55e !important; opacity:0.7; }
.step-num-done { background:#22c55e !important; }
</style>
