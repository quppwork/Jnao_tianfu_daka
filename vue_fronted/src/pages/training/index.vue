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
        <view class="nav-history" @click.stop="openHistory"><text>历史</text></view>
        <view v-if="devToolsAvailable" class="nav-dev" :class="{ active: devMode }" @click.stop="toggleDevMode">
          <text>{{ devMode ? 'DEV ✓' : 'DEV' }}</text>
        </view>
      </view>
    </view>

    <view class="body">
      <view v-if="guideHandoffBanner" class="guide-handoff-banner">
        <view class="guide-handoff-main">
          <text class="guide-handoff-title">张宇老师提醒</text>
          <text v-if="guideHandoffBanner.focus" class="guide-handoff-text">
            可关注：{{ guideHandoffBanner.focus }}
          </text>
          <text v-else-if="guideHandoffBanner.hint" class="guide-handoff-text">
            {{ guideHandoffBanner.hint }}
          </text>
        </view>
        <view class="guide-handoff-close" @click="guideHandoffBanner = null"><text>×</text></view>
      </view>
      <!-- 今日训练时长 -->
      <view class="card time-card" :class="{ 'time-card-alert': redAlertActive }">
        <view class="time-header">
          <text class="plan-label">{{ timeCardTitle }}</text>
          <text v-if="timerPhase === 'running'" class="time-status-tag running">进行中</text>
          <text v-else-if="timerPhase === 'expired'" class="time-status-tag expired">已结束</text>
          <text v-else-if="durationLocked && planJustGenerated" class="time-status-tag pending">待确认</text>
        </view>

        <view v-if="timerPhase === 'setup' && !durationLocked" class="time-setup">
          <view v-if="showGuideArrow" class="guide-arrow">
            <text>👇 请选择训练时长</text>
          </view>
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
          <view
            v-if="agentScheduleEnabled"
            class="time-start-btn time-start-btn-agent"
            :class="{ disabled: !canStartTimer }"
            @click="startTrainingTimerAgent"
          >
            <text>智能排课</text>
          </view>
          <text class="time-setup-hint">{{ timeSetupHint }}</text>
        </view>

        <view v-else-if="timerPhase === 'setup' && durationLocked" class="time-locked">
          <text class="time-locked-val">{{ lockedDurationLabel }}</text>
          <text class="time-setup-hint">{{ timeSetupHint }}</text>
        </view>

        <view v-else-if="timerPhase === 'running'" class="time-running">
          <view class="time-countdown">
            <text v-for="(item, ci) in countdownChars" :key="ci" class="countdown-char" :class="{ 'char-changed': item.changed }">{{ item.ch }}</text>
          </view>
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
          <view v-if="scheduleAssistDevText" class="dev-status dev-assist">
            <text class="dev-section-label" style="margin-top:0">Agent 排课理由</text>
            <text>{{ scheduleAssistDevText }}</text>
          </view>
          <text class="dev-section-label">今日操作</text>
          <view class="dev-actions">
            <view class="dev-action dev-action-primary" @click="devResetToday"><text>🔄 重置今日</text></view>
            <view class="dev-action" @click="devResetTimer"><text>⏱ 重置计时</text></view>
            <view class="dev-action" @click="devSimulateExpire"><text>⏰ 模拟结束</text></view>
          </view>
          <text class="dev-section-label">日切 / 时间</text>
          <view class="dev-actions">
            <view class="dev-action" @click="devSimulate4amCutoffAction"><text>🌙 模拟4点</text></view>
            <view class="dev-action" @click="devGoNextDay"><text>🌅 新一天</text></view>
            <view class="dev-action" @click="devResetClockAction"><text>🕐 回归实际</text></view>
          </view>
          <text class="dev-section-label">进度 / 内容</text>
          <view class="dev-actions">
            <view class="dev-action" @click="devResetMainLine"><text>↩ 回主线A</text></view>
            <view class="dev-action" @click="devRefreshAiPlan"><text>🤖 刷新 AI</text></view>
            <view class="dev-action" @click="devUnlockNextPhase"><text>🔓 解锁下阶段</text></view>
          </view>
          <text class="dev-section-label">提醒预览</text>
          <view class="dev-actions">
            <view class="dev-action" @click="devPreviewCongrats"><text>🎉 晋级成功</text></view>
            <view class="dev-action" @click="devPreviewRegret"><text>😔 遗憾失败</text></view>
          </view>
          <text class="dev-section-label">危险操作</text>
          <view class="dev-actions">
            <view class="dev-action dev-action-danger" @click="devClearAllHistory"><text>🗑 清空历史</text></view>
            <view class="dev-action dev-action-danger" @click="devResetTalentAction"><text>🧬 重置天赋</text></view>
          </view>
          <text class="dev-panel-hint">重置今日 = 仅删今日方案与计时 · 模拟4点 = 虚拟时钟快进到截止 · 新一天 = 快进到 4:05</text>
        </view>
      </view>

      <!-- Summary：今日打卡明细 + 配合度（历史记录在右上角） -->
      <view
        class="card summary-card"
        :class="{ 'summary-empty': !submittedCards.length }"
      >
        <template v-if="submittedCards.length">
          <view class="summary-header">
            <text class="summary-label">📝 今日已打卡 {{ submittedCards.length }} 项</text>
          </view>
          <view class="summary-mini-cards">
            <view v-for="(c, idx) in submittedCards" :key="idx" class="mini-card mini-card-v1" @click.stop="editCard(idx)">
              <view class="mini-card-accent"></view>
              <view class="mini-card-left">
                <text class="mini-card-name">{{ c.name }}{{ c.phaseBlock ? ` · 训练${c.phaseBlock}` : '' }}</text>
                <text class="mini-card-summary">{{ miniCardSummary(c) }}</text>
              </view>
            </view>
          </view>
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
          <text class="summary-empty-text">今日还未打卡 · 完成训练后在下方训练块打卡</text>
        </template>
      </view>

      <!-- Plan · 时间轴总览（生成方案后或计时开始后显示） -->
      <view v-if="timerPhase !== 'setup' || planJustGenerated" class="card plan-card" data-augmented-ui="tl-clip tr-clip br-clip bl-clip border">
        <view class="plan-header">
          <text class="plan-label">📋 今日方案</text>
          <text v-if="talentLabel && !entryLoading && !scheduleLoading" class="plan-header-meta">{{ planHeaderMeta }}</text>
        </view>
        <view v-if="scheduleLoading" class="plan-loading-wrap">
          <view class="plan-loading-ring">
            <view class="plr-core"></view>
            <view class="plr-arc"></view>
          </view>
          <text class="plan-loading-title">正在生成今日训练内容</text>
          <view class="plan-loading-bar">
            <view class="plan-loading-bar-fill"></view>
          </view>
          <text class="plan-loading-hint">根据天赋与昨日进度安排音频与训练项…</text>
        </view>

        <!-- Done -->
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
                    <text class="tl-phase-title">{{ phase.label }}</text>
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
                    <text class="tl-item-title">{{ item.title || '训练项' }}</text>
                    <text class="tl-item-right">
                      <text v-if="item.duration_min" class="tl-item-dur">{{ item.duration_min }}分钟</text>
                    </text>
                  </view>
                </view>
              </view>
            </view>
          </view>
          <view v-else class="plan-empty card-empty">
            <text class="plan-empty-text">{{ planEmptyHint }}</text>
          </view>

          <view v-if="planTotalCount > 0" class="plan-progress">
            <view class="plan-progress-track">
              <view class="plan-progress-fill" :style="{ width: planProgressPct + '%' }"></view>
            </view>
            <text class="plan-progress-text">{{ planCompletedCount }}/{{ planTotalCount }} 项已完成</text>
          </view>

          <text v-if="needAssessment" class="plan-warn" @click="goTalent">尚未完成天赋测评，点击前往测评 ›</text>

          <!-- 确认今日方案 -->
          <view v-if="planJustGenerated" class="btn-confirm-plan" style="margin-bottom:12px;" @click="confirmPlan">
            <text>确认今日方案并开始训练</text>
          </view>

          <!-- 🆕 编辑方案 -->
          <text class="plan-edit-guide">点击 ⓘ 查看解释说明</text>
          <view v-if="canCustomizePlan" class="plan-edit-block">
            <view class="plan-edit-bar" @click="openPlanEditor">
              <view class="plan-edit-bar-text">
                <text class="peb-title">📝 编辑方案</text>
              </view>
              <view class="et-info" @click.stop="showElectiveInfoModal('edit_plan')"><text>ⓘ</text></view>
              <text class="et-arrow">›</text>
            </view>
            <text class="plan-edit-tip">⚠️ 仅可编辑一次，开始打卡后不可再修改</text>
          </view>

          <!-- 🆕 选修环节 -->
          <view v-if="(timerPhase !== 'setup' || planJustGenerated) && todayPlan?.plan_id" class="elective-toggles">
            <text class="elective-section-label">🧩 选修环节</text>
            <view class="elective-toggle-item" v-for="es in electiveSkills" :key="es.skill">
              <text class="et-label">{{ es.label }}</text>
              <view class="et-switch" :class="{ on: es.inPlan }" @click="toggleElective(es.skill)">
                <view class="et-knob"></view>
              </view>
              <view class="et-info" @click.stop="showElectiveInfoModal(es.skill)"><text>ⓘ</text></view>
            </view>
            <text class="elective-hint">开启后将在训练计划中增加对应的训练环节，可随时开关</text>
      </view>
        </template>
      </view>

      <!-- 全部必修完成 -->
      <view v-if="allRequiredDone" class="training-done-wrap">
        <view class="btn-checkin" @click="showDoneConfirm = true">
          <text class="btn-checkin-text">🎉 点击我进行自我评分哦～</text>
        </view>
      </view>

      <!-- 训练阶段 -->
      <template v-if="showTraining && timerPhase !== 'setup' && !dayTransition && todayPlan?.status !== 'transition'" v-for="(phase, pi) in visiblePhases" :key="phase.block">
        <view v-if="pi > 0" class="divider"></view>
        <view :id="'phase-block-' + phase.block" class="phase-section">
          <text class="section-title" :class="{ dim: !phase.unlocked, elective: phase.isElective }">
            {{ phase.label }}{{ phase.unlocked ? '' : ' 🔒' }}{{ phase.isElective ? ' 🆓' : '' }}
          </text>

          <view class="media-block" :class="{ locked: isPhaseMediaLocked(phase) }">
            <view v-if="isPhaseMediaLocked(phase)" class="media-lock-overlay">
              <text class="media-lock-text">{{ phaseMediaLockText(phase) }}</text>
            </view>

            <template v-if="phase.items.length">
              <view class="step-grid">
                <template v-for="(item, idx) in phase.items" :key="item.id || idx">
                  <!-- 音频卡片（仅当有音频时） -->
                  <view
                    v-if="item.audio_url"
                    class="step"
                    :class="{
                      'step-preview-locked': !phase.unlocked,
                      'step-locked': phase.unlocked && isMediaLocked,
                      'step-watched': phase.unlocked && isItemWatched(item),
                    }"
                    @click="openPhaseMediaItem(item, phase, 'audio')"
                  >
                    <view class="step-num" :class="{ 'step-num-done': isItemWatched(item), dim: !phase.unlocked }">{{ idx + 1 }}</view>
                    <view class="step-content">
                      <text class="step-label" :class="{ 'dim-text': !phase.unlocked }">🎧 音频训练</text>
                      <view class="step-box" :class="{ 'dim-box': !phase.unlocked }">{{ item.title || '训练项' }}</view>
                      <text class="step-time" :class="{ 'dim-text': !phase.unlocked }">{{ itemStepHint(item, phase) }}</text>
                    </view>
                  </view>
                  <!-- 视频卡片（仅当有 video_url 时） -->
                  <view
                    v-if="item.video_url"
                    class="step step-video"
                    :class="{
                      'step-preview-locked': !phase.unlocked,
                      'step-locked': phase.unlocked && isMediaLocked,
                      'step-watched': phase.unlocked && isItemWatched(item),
                    }"
                    @click.stop="openPhaseMediaItem(item, phase, 'video')"
                  >
                    <view class="step-num" :class="{ 'step-num-done': isItemWatched(item), dim: !phase.unlocked }">▶</view>
                    <view class="step-content">
                      <text class="step-label" :class="{ 'dim-text': !phase.unlocked }">🎬 视频训练</text>
                      <view class="step-box" :class="{ 'dim-box': !phase.unlocked }">{{ videoTitle(item) }}</view>
                      <text class="step-time" :class="{ 'dim-text': !phase.unlocked }">点击播放</text>
                    </view>
                  </view>
                </template>
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

            <text class="lock-tip">{{ phaseTip(phase) }}</text>

            <template v-if="!isPerceptionPhase(phase) && !phase.isElective">
            <view class="checkin-block" :class="{ locked: !isPhaseListenDone(phase) }">
              <view v-if="!isPhaseListenDone(phase)" class="checkin-lock-overlay">
                <text class="checkin-lock-text">🔒 请先听完/看完音视频（{{ WATCH_DONE_PCT }}%）</text>
              </view>
              <view class="btn-checkin btn-cyber" data-augmented-ui="tl-clip br-clip border" @click="openPicker(phase.block)">
                <text class="btn-checkin-text">{{ phaseRecordIds[phase.block] ? '✏️ 修改打卡' : '✅ 点击我进行打卡哦！' }}</text>
              </view>
            </view>
            </template>
            <template v-else-if="isPerceptionPhase(phase)">
              <text v-if="phase.allDone" class="perception-done-text">✅ 多元感知训练已完成 · 点击音频可回听</text>
              <text v-else class="perception-done-text">点击音频即可完成多元感知训练</text>
            </template>
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
              <view v-for="(item, ai) in abilities" :key="item" class="picker-item" :class="{ active: hasPickerCard(item), disabled: allowedAbility && item !== allowedAbility, 'ability-spark': sparkAbi === ai }" @click="togglePickerCard(item, ai)">
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
                <text class="form-label">完成状态</text>
                <view class="form-tags">
                  <text class="ftag" :class="{ on: card.completed }" @click="card.completed = true">✓ 已完成</text>
                  <text class="ftag" :class="{ on: !card.completed }" @click="card.completed = false">✗ 未完成</text>
                </view>
              </view>
              <view class="form-row">
                <text class="form-label">时间<text class="req-star">*</text></text>
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
                <text class="form-label">结果<text class="req-star">*</text></text>
                <view style="display:flex;flex-direction:column;gap:6px;flex:1;">
                  <view style="display:flex;align-items:center;gap:6px;">
                    <input class="form-input" style="flex:1;min-width:0;" v-model="card.count" placeholder="题数" type="number" />
                    <text class="form-unit" style="width:24px;">题</text>
                  </view>
                  <view style="display:flex;align-items:center;gap:6px;">
                    <input class="form-input" :class="{ 'form-input-err': accErrorCards[idx]?.accuracy }" style="flex:1;min-width:0;" v-model="card.accuracy" placeholder="正确率" type="number" />
                    <text class="form-unit" style="width:24px;">%</text>
                  </view>
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
              <text class="form-soft-tip">填实际练习情况即可，不用刻意凑整数</text>
              <view class="form-row">
                <text class="form-label">材料类型</text>
                <view class="form-tags">
                  <text class="ftag" :class="{ on: card.materialType === '书' }" @click="card.materialType = '书'">书</text>
                  <text class="ftag" :class="{ on: card.materialType === '文章' }" @click="card.materialType = '文章'">文章</text>
                  <text class="ftag" :class="{ on: card.materialType === '自定义' }" @click="card.materialType = '自定义'">自定义</text>
                </view>
              </view>
              <view class="form-row">
                <text class="form-label">材料名称<text class="req-star">*</text></text>
                <input class="form-input" v-model="card.materialName" :placeholder="card.materialType === '书' ? '如：《西游记》' : card.materialType === '文章' ? '如：作文《我的姐姐》' : '如：圆周率前100位'" />
              </view>
              <view class="form-row">
                <text class="form-label">训练<text class="req-star">*</text></text>
                <view style="display:flex;align-items:center;gap:6px;flex:1;">
                  <input class="form-input" style="flex:1;min-width:0;" v-model.number="card.time" placeholder="实际用时约几分钟" type="number" />
                  <text class="form-unit">分钟</text>
                  <input class="form-input" style="flex:1;min-width:0;" v-model.number="card.wordCount" placeholder="大约记住多少字" type="number" />
                  <text class="form-unit">字</text>
                </view>
              </view>
              <!-- 倒背验证：先选择模式，再决定显示正背还是倒背 -->
              <view class="form-row">
                <text class="form-label">倒背验证</text>
                <view class="form-tags">
                  <text class="ftag" :class="{ on: card.reverseRecite }" @click="card.reverseRecite = true">✓ 可逐字倒背</text>
                  <text class="ftag" :class="{ on: !card.reverseRecite }" @click="card.reverseRecite = false">✗ 暂不能</text>
                </view>
              </view>
              <view class="form-row" v-if="!card.reverseRecite">
                <text class="form-label">正背</text>
                <view style="display:flex;align-items:center;gap:6px;flex:1;">
                  <input class="form-input" style="flex:1;min-width:0;" v-model="card.forwardTime" placeholder="用时" type="number" />
                  <text class="form-unit">分钟</text>
                  <input class="form-input" :class="{ 'form-input-err': accErrorCards[idx]?.forwardAcc }" style="flex:1;min-width:0;" v-model="card.forwardAcc" placeholder="正确率" type="number" />
                  <text class="form-unit">%</text>
                </view>
              </view>
              <view class="form-row" v-if="card.reverseRecite">
                <text class="form-label">倒背</text>
                <view style="display:flex;align-items:center;gap:6px;flex:1;">
                  <input class="form-input" style="flex:1;min-width:0;" v-model="card.backwardTime" placeholder="用时" type="number" />
                  <text class="form-unit">分钟</text>
                  <input class="form-input" :class="{ 'form-input-err': accErrorCards[idx]?.backwardAcc }" style="flex:1;min-width:0;" v-model="card.backwardAcc" placeholder="正确率" type="number" />
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
                <textarea class="form-textarea" v-model="card.note" placeholder="可选：卡在哪、感觉如何" style="height:50px;" />
              </view>
            </template>
            <template v-else-if="card.name === '影像追忆'">
              <text class="form-soft-tip">填实际练习情况即可，不用刻意凑整数</text>
              <view class="form-row">
                <text class="form-label">使用工具</text>
                <view class="form-tags">
                  <text class="ftag" :class="{ on: card.tool === '书本' }" @click="card.tool = '书本'">书本</text>
                  <text class="ftag" :class="{ on: card.tool === '视频' }" @click="card.tool = '视频'">视频</text>
                  <text class="ftag" :class="{ on: card.tool === '自定义' }" @click="card.tool = '自定义'">自定义</text>
                </view>
              </view>
              <view class="form-row">
                <text class="form-label">训练<text class="req-star">*</text></text>
                <view style="display:flex;flex-direction:column;gap:6px;flex:1;">
                  <view style="display:flex;align-items:center;gap:6px;">
                    <input class="form-input" style="flex:1;min-width:0;" v-model.number="card.time" placeholder="实际用时约几分钟" type="number" />
                    <text class="form-unit" style="width:32px;">分钟</text>
                  </view>
                  <view style="display:flex;align-items:center;gap:6px;">
                    <input class="form-input" style="flex:1;min-width:0;" v-model.number="card.wordCount" placeholder="大约看完多少字" type="number" />
                    <text class="form-unit" style="width:32px;">字</text>
                  </view>
                </view>
              </view>
              <view class="form-row">
                <text class="form-label">材料<text class="req-star">*</text></text>
                <textarea class="form-textarea form-textarea-sm" v-model="card.content" placeholder="如：一卜语文重要知识点" />
              </view>
              <view class="form-row">
                <text class="form-label">追忆率<text class="req-star">*</text></text>
                <view class="form-inline">
                  <input class="form-input short" :class="{ 'form-input-err': accErrorCards[idx]?.accuracy }" v-model="card.accuracy" placeholder="正确率" type="number" />
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
                <textarea class="form-textarea" v-model="card.note" placeholder="可选：卡在哪、感觉如何" style="height:50px;" />
              </view>
            </template>
            <template v-else-if="card.name === '超脑阅读'">
              <text class="form-soft-tip">填实际练习情况即可，不用刻意凑整数</text>
              <view class="form-row">
                <text class="form-label">训练<text class="req-star">*</text></text>
                <view style="display:flex;flex-direction:column;gap:6px;flex:1;">
                  <view style="display:flex;align-items:center;gap:6px;">
                    <input class="form-input" style="flex:1;min-width:0;" v-model.number="card.time" placeholder="实际阅读约几分钟" type="number" />
                    <text class="form-unit" style="width:32px;">分钟</text>
                  </view>
                  <view style="display:flex;align-items:center;gap:6px;">
                    <input class="form-input" style="flex:1;min-width:0;" v-model.number="card.wordCount" placeholder="本次大约阅读多少字" type="number" />
                    <text class="form-unit" style="width:32px;">字</text>
                  </view>
                </view>
              </view>
              <view class="form-row">
                <text class="form-label">结果</text>
                <textarea class="form-textarea form-textarea-sm" v-model="card.result" placeholder="训练效果如何？" />
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
                <textarea class="form-textarea form-textarea-sm" v-model="card.note" placeholder="可选：卡在哪、感觉如何" />
              </view>
            </template>
            <template v-else>
              <view class="form-row">
                <text class="form-label">时长<text class="req-star">*</text></text>
                <view style="display:flex;align-items:center;gap:6px;flex:1;">
                  <input class="form-input" v-model="card.time" placeholder="实际用时约几分钟" type="number" />
                  <text class="form-unit">分</text>
                </view>
              </view>
              <view class="form-row">
                <text class="form-label">字数<text class="req-star">*</text></text>
                <view style="display:flex;align-items:center;gap:6px;flex:1;">
                  <input class="form-input" v-model="card.wordCount" placeholder="本次大约多少字" type="number" />
                  <text class="form-unit">字</text>
                </view>
              </view>
              <view class="form-row">
                <text class="form-label">效果</text>
                <input class="form-input" v-model="card.result" placeholder="训练效果" />
              </view>
              <view class="form-row">
                <text class="form-label">备注</text>
                <input class="form-input" v-model="card.note" placeholder="可选补充说明" />
              </view>
            </template>
          </view>
          </TransitionGroup>

          <view class="btn-checkin" @click="submitFormWithAnim" style="margin-top:8px;">
            <text>{{ checkinSubmitting ? '提交中...' : '✅ 提交打卡 ' + (pickerCards.length ? '(' + pickerCards.length + ')' : '') }}</text>
          </view>
        </view>
      </view>

      </view>

    <!-- (选修弹窗已移除，改用开关控制) -->

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


    <!-- 🆕 方案编辑弹窗 -->
    <view v-if="showPlanEditor" class="picker-overlay" @click="closePlanEditor">
      <view class="picker-card plan-editor-modal" @click.stop>
        <view class="modal-header">
          <text class="modal-title">📝 编辑今日方案</text>
          <view class="modal-close" @click="closePlanEditor">✕</view>
        </view>
        <view class="editor-list">
          <view v-for="(item, idx) in editableItems" :key="item.id" class="editor-row">
            <text class="editor-label">项目 {{ idx + 1 }}</text>
            <picker class="editor-picker" :range="allReplacableSkills" :value="editorSkillIndex(item)" @change="(e) => onEditorSkillChange(idx, e)">
              <view class="editor-picker-display">{{ editorSkillName(item) || '选择技能' }}</view>
            </picker>
          </view>
        </view>
        <view v-if="!editableItems.length" style="padding:16px;text-align:center;color:#8b949e;">
          无可编辑的训练项目
        </view>
        <view v-if="editableItems.length" class="editor-actions">
          <view class="editor-btn secondary" @click="closePlanEditor"><text>取消</text></view>
          <view class="btn-checkin" style="flex:1;padding:12px;margin:0;box-shadow:none;border-radius:10px;" @click="confirmCustomize"><text>确认修改</text></view>
        </view>
      </view>
    </view>

    <!-- 信息说明弹窗 -->
    <view v-if="showInfoModal" class="picker-overlay" @click="showInfoModal = false">
      <view class="picker-card confirm-modal" @click.stop>
        <view class="modal-header">
          <text class="modal-title">{{ infoModalData.title }}</text>
          <view class="modal-close" @click="showInfoModal = false">✕</view>
        </view>
        <text class="confirm-modal-text">{{ infoModalData.desc }}</text>
        <text v-if="infoModalData.age" class="confirm-modal-text" style="margin-top:-8px;">{{ infoModalData.age }}</text>
        <text v-if="infoModalData.how" class="confirm-modal-text" style="margin-top:-8px;">{{ infoModalData.how }}</text>
        <view class="confirm-modal-actions">
          <view class="btn-checkin" style="flex:1;padding:12px;margin:0;box-shadow:none;border-radius:10px;" @click="showInfoModal = false"><text>知道了</text></view>
        </view>
      </view>
    </view>

    <!-- 确认修改方案弹窗 -->
    <view v-if="showCustomizeConfirm" class="picker-overlay" @click="showCustomizeConfirm = false; pendingCustomize = null">
      <view class="picker-card confirm-modal" @click.stop>
        <view class="modal-header">
          <text class="modal-title">确认修改方案</text>
          <view class="modal-close" @click="showCustomizeConfirm = false; pendingCustomize = null">✕</view>
        </view>
        <text class="confirm-modal-text">每个训练日仅可修改一次，打卡后不可再改。修改后将按所选技能重新匹配训练内容，请谨慎操作。确定继续吗？</text>
        <view class="confirm-modal-actions">
          <view class="editor-btn secondary" @click="showCustomizeConfirm = false; pendingCustomize = null"><text>取消</text></view>
          <view class="btn-checkin" style="flex:1;padding:12px;margin:0;box-shadow:none;border-radius:10px;" @click="doCustomize"><text>确认修改</text></view>
        </view>
      </view>
    </view>

    <!-- 提交确认弹窗 -->
    <view v-if="showSubmitConfirm" class="picker-overlay" @click="showSubmitConfirm = false; pendingSubmitBlock = null">
      <view class="picker-card confirm-modal" @click.stop>
        <view class="modal-header">
          <text class="modal-title">确认提交打卡</text>
          <view class="modal-close" @click="showSubmitConfirm = false; pendingSubmitBlock = null">✕</view>
        </view>
        <text class="confirm-modal-text">请确认填写内容准确无误。错误填写会影响后续课程推荐和训练效果。</text>
        <view class="confirm-modal-actions">
          <view class="editor-btn secondary" @click="showSubmitConfirm = false; pendingSubmitBlock = null"><text>再检查一下</text></view>
          <view class="btn-checkin" style="flex:1;padding:12px;margin:0;box-shadow:none;border-radius:10px;" @click="confirmSubmit"><text>确认提交</text></view>
        </view>
      </view>
    </view>

    <!-- 删除确认弹窗 -->
    <view v-if="showDeleteConfirm" class="picker-overlay" style="z-index:650;" @click="cancelDeleteConfirm">
      <view class="picker-card confirm-modal" @click.stop>
        <view class="modal-header">
          <text class="modal-title" style="color:#ef4444;">⚠️ 删除打卡记录</text>
          <view class="modal-close" @click="cancelDeleteConfirm">✕</view>
        </view>
        <text class="confirm-modal-text">确定删除「{{ deleteTargetName }}」的打卡记录吗？删除后需重新按顺序打卡，该训练项会重新出现在下方列表中。</text>
        <view class="confirm-modal-actions">
          <view class="editor-btn secondary" @click="cancelDeleteConfirm"><text>取消</text></view>
          <view class="btn-checkin" style="flex:1;padding:12px;margin:0;box-shadow:none;border-radius:10px;background:#ef4444;" @click="confirmDelete"><text>确定删除</text></view>
        </view>
      </view>
    </view>

    <!-- 完成确认弹窗 -->
    <view v-if="showDoneConfirm" class="picker-overlay" @click="showDoneConfirm = false">
      <view class="picker-card" style="max-width:360px;" @click.stop>
        <view class="modal-header">
          <text class="modal-title">今日配合度</text>
          <view class="modal-close" @click="showDoneConfirm = false">✕</view>
        </view>
        <view class="sa-grid" style="padding:16px;">
          <view v-for="s in scores" :key="s.pct" class="sa-item" :class="{ active: summaryAttitude === s.pct }" @click="summaryAttitude = s.pct">
            <text class="sa-pct">{{ s.pct }}%</text>
            <text class="sa-emoji">{{ s.emoji }}</text>
          </view>
        </view>
        <view class="btn-checkin" style="margin:0;" @click="showDoneConfirm = false">
          <text class="btn-checkin-text">确认完成</text>
        </view>
      </view>
    </view>

<!-- Media Player Overlay — 方案C 封面风；v-show 保留 video 实例与浏览器缓冲，避免每次重进全量加载 -->
    <view v-show="mediaPlayer.show" class="player-overlay" @click="closeMedia">
      <view class="player-card player-card-c" @click.stop>
        <view class="player-cover">
          <view v-if="mediaPlayer.type === 'video'" class="player-cover-video">
            <video
              v-if="videoSrc"
              :key="'training-video-' + activeVideoItemId"
              ref="trainingVideoEl"
              class="training-video"
              :src="videoSrc"
              playsinline
              webkit-playsinline
              x5-playsinline
              x5-video-player-type="h5"
              preload="metadata"
              @click.stop="toggleVideoPlay"
              @timeupdate="onMediaTimeUpdate"
              @loadedmetadata="onMediaLoadedMetadata"
              @loadeddata="onVideoLoadedData"
              @durationchange="onVideoDurationChange"
              @seeking="onMediaSeeking"
              @ratechange="lockMediaPlaybackRate"
              @pause="onVideoPause"
              @playing="onVideoPlaying"
              @waiting="onVideoWaiting"
              @canplay="onVideoCanPlay"
              @ended="onMediaEnded"
              @error="onTrainingVideoError"
            />
            <view v-if="videoLoading" class="player-video-loading">
              <text class="player-video-loading-text">{{ videoLoadingHint }}</text>
            </view>
            <view v-else-if="!videoMetadataReady" class="player-cover-placeholder">
              <text class="player-cover-icon">🎬</text>
              <text class="player-cover-hint">视频加载中…</text>
            </view>
          </view>
          <view v-else class="player-cover-audio">
            <text class="player-cover-icon">{{ playerCoverEmoji }}</text>
            <text class="player-cover-label">{{ audioTitle || mediaPlayerTitle }}</text>
          </view>
          <view class="player-cover-progress">
            <view class="player-cover-progress-fill" :style="{ width: (mediaPlayer.type === 'video' ? videoProgressPct : audioProgressPct) + '%' }"></view>
          </view>
        </view>
        <view class="player-header">
          <text class="player-title">{{ mediaPlayerTitle }}</text>
          <view class="player-close" @click="closeMedia">✕</view>
        </view>
        <view v-if="mediaPlayer.type === 'audio'" class="player-controls">
          <view class="player-ctrl-left">
            <text class="player-time-label">{{ audioTimeLabel }}</text>
          </view>
          <view class="player-ctrl-center">
            <view class="player-ctrl-btn sm" @click="rewindAudioTen">
              <text>⏪</text>
            </view>
            <view class="player-ctrl-btn" @click="toggleMediaPlay">
              <text>{{ mediaPlayIcon }}</text>
            </view>
          </view>
          <view class="player-ctrl-right">
            <text class="player-time-label">{{ audioDurationLabel }}</text>
          </view>
        </view>
        <text v-if="mediaPlayer.type === 'audio'" class="media-listen-hint">{{ mediaPlayerHint }}</text>
      </view>
    </view>
<!-- 已打卡卡片详情 / 页内编辑 -->
  <view v-if="showCardDetail" class="detail-overlay" @click="closeCardDetail">
    <view class="detail-test-card" @click.stop>
      <text class="detail-slide-name">{{ activeDetailCard?.name }}</text>

      <template v-if="!detailEditing">
        <view v-for="(val, key) in cardDetailFields(activeDetailCard)" :key="key" class="detail-row">
          <text class="detail-label">{{ key }}</text>
          <text class="detail-value">{{ val || '—' }}</text>
        </view>
      </template>

      <view v-else class="detail-edit-body">
        <template v-if="detailEditCard?.name === '极速运算'">
          <view class="detail-form-row">
            <text class="detail-form-label">时间</text>
            <input class="detail-form-input" v-model="detailEditCard.time" placeholder="分钟" type="number" />
          </view>
          <view class="detail-form-row">
            <text class="detail-form-label">内容</text>
            <view class="detail-form-tags">
              <text v-for="t in ['加减法','乘除法','混合运算','口算']" :key="t" class="detail-ftag" :class="{ on: detailEditCard.tag === t }" @click="detailEditCard.tag = t">{{ t }}</text>
            </view>
          </view>
          <view class="detail-form-row">
            <text class="detail-form-label">结果</text>
            <view class="detail-form-inline">
              <input class="detail-form-input short" v-model="detailEditCard.count" placeholder="题数" type="number" />
              <text class="detail-form-unit">题</text>
              <input class="detail-form-input short" v-model="detailEditCard.accuracy" placeholder="正确率" type="number" />
              <text class="detail-form-unit">%</text>
            </view>
          </view>
          <view class="detail-form-row">
            <text class="detail-form-label">备注</text>
            <textarea class="detail-form-textarea" v-model="detailEditCard.note" placeholder="补充说明..." />
          </view>
        </template>

        <template v-else-if="detailEditCard?.name === '扫描速记'">
          <view class="detail-form-row">
            <text class="detail-form-label">材料类型</text>
            <view class="detail-form-tags">
              <text v-for="t in ['书','文章','自定义']" :key="t" class="detail-ftag" :class="{ on: detailEditCard.materialType === t }" @click="detailEditCard.materialType = t">{{ t }}</text>
            </view>
          </view>
          <view class="detail-form-row">
            <text class="detail-form-label">材料名称</text>
            <input class="detail-form-input" v-model="detailEditCard.materialName" placeholder="材料名称" />
          </view>
          <view class="detail-form-row" style="flex-wrap:nowrap;align-items:center;">
            <text class="detail-form-label">训练</text>
            <text class="detail-form-unit">用时</text>
            <input class="detail-form-input short" v-model.number="detailEditCard.time" placeholder="0" type="number" style="width:50px;flex:none;" />
            <text class="detail-form-unit">分钟</text>
            <input class="detail-form-input short" v-model.number="detailEditCard.wordCount" placeholder="0" type="number" style="width:50px;flex:none;" />
            <text class="detail-form-unit">字</text>
          </view>
          <!-- 倒背验证 -->
          <view class="detail-form-row">
            <text class="detail-form-label">倒背验证</text>
            <view class="detail-form-tags">
              <text class="detail-ftag" :class="{ on: detailEditCard.reverseRecite }" @click="detailEditCard.reverseRecite = true">✓ 可逐字倒背</text>
              <text class="detail-ftag" :class="{ on: !detailEditCard.reverseRecite }" @click="detailEditCard.reverseRecite = false">✗ 暂不能</text>
            </view>
          </view>
          <view class="detail-form-row" v-if="!detailEditCard.reverseRecite">
            <text class="detail-form-label">正背</text>
            <view class="detail-form-inline">
              <input class="detail-form-input short" v-model="detailEditCard.forwardTime" placeholder="用时" />
              <text class="detail-form-unit">/</text>
              <input class="detail-form-input short" v-model="detailEditCard.forwardAcc" placeholder="准确度" />
            </view>
          </view>
          <view class="detail-form-row" v-if="detailEditCard.reverseRecite">
            <text class="detail-form-label">倒背</text>
            <view class="detail-form-inline">
              <input class="detail-form-input short" v-model="detailEditCard.backwardTime" placeholder="用时" />
              <text class="detail-form-unit">/</text>
              <input class="detail-form-input short" v-model="detailEditCard.backwardAcc" placeholder="准确度" />
            </view>
          </view>
          <view class="detail-form-row">
            <text class="detail-form-label">备注</text>
            <textarea class="detail-form-textarea" v-model="detailEditCard.note" placeholder="补充说明..." />
          </view>
        </template>

        <template v-else-if="detailEditCard?.name === '影像追忆'">
          <view class="detail-form-row">
            <text class="detail-form-label">使用工具</text>
            <view class="detail-form-tags">
              <text v-for="t in ['书本','视频','自定义']" :key="t" class="detail-ftag" :class="{ on: detailEditCard.tool === t }" @click="detailEditCard.tool = t">{{ t }}</text>
            </view>
          </view>
          <view class="detail-form-row" style="align-items:center;">
            <text class="detail-form-label">训练</text>
            <input class="detail-form-input short" v-model.number="detailEditCard.time" placeholder="0" type="number" style="width:56px;" />
            <text class="detail-form-unit">分钟</text>
            <input class="detail-form-input short" v-model.number="detailEditCard.wordCount" placeholder="0" type="number" style="width:56px;" />
            <text class="detail-form-unit">字</text>
          </view>
          <view class="detail-form-row">
            <text class="detail-form-label">材料</text>
            <textarea class="detail-form-textarea" v-model="detailEditCard.content" placeholder="训练材料" />
          </view>
          <view class="detail-form-row">
            <text class="detail-form-label">追忆率</text>
            <view class="detail-form-inline">
              <input class="detail-form-input short" v-model="detailEditCard.accuracy" placeholder="%" type="number" />
              <text class="detail-form-unit">%</text>
            </view>
          </view>
          <view class="detail-form-row">
            <text class="detail-form-label">备注</text>
            <textarea class="detail-form-textarea" v-model="detailEditCard.note" placeholder="补充说明..." />
          </view>
        </template>

        <template v-else-if="detailEditCard?.name === '超脑阅读'">
          <view style="display:flex;align-items:center;gap:4px;margin-bottom:10px;">
            <text class="detail-form-label" style="width:auto;">训练</text>
            <view style="display:flex;align-items:center;gap:4px;margin-left:auto;">
              <text class="detail-form-unit">用时</text>
              <input class="detail-form-input short" v-model.number="detailEditCard.time" placeholder="0" type="number" />
              <text class="detail-form-unit">分钟，完成</text>
              <input class="detail-form-input short" v-model.number="detailEditCard.wordCount" placeholder="0" type="number" />
              <text class="detail-form-unit">字</text>
            </view>
          </view>
          <view class="detail-form-row">
            <text class="detail-form-label">结果</text>
            <input class="detail-form-input" v-model="detailEditCard.result" placeholder="训练效果" />
          </view>
          <view class="detail-form-row">
            <text class="detail-form-label">备注</text>
            <input class="detail-form-input" v-model="detailEditCard.note" placeholder="补充说明..." />
          </view>
        </template>

        <template v-else>
          <view class="detail-form-row">
            <text class="detail-form-label">时间</text>
            <input class="detail-form-input" v-model="detailEditCard.time" placeholder="分钟" />
          </view>
          <view class="detail-form-row">
            <text class="detail-form-label">内容</text>
            <textarea class="detail-form-textarea" v-model="detailEditCard.content" placeholder="训练内容" />
          </view>
          <view class="detail-form-row">
            <text class="detail-form-label">结果</text>
            <textarea class="detail-form-textarea" v-model="detailEditCard.result" placeholder="训练效果" />
          </view>
          <view class="detail-form-row">
            <text class="detail-form-label">备注</text>
            <textarea class="detail-form-textarea" v-model="detailEditCard.note" placeholder="补充说明..." />
          </view>
        </template>
      </view>

      <view class="detail-actions">
        <template v-if="!detailEditing">
          <view class="btn-outline-sm" @click="startDetailEdit">✎ 编辑</view>
          <view class="btn-del-sm" @click="confirmDeleteCard(detailCardIndex)">删除</view>
        </template>
        <template v-else>
          <view class="btn-outline-sm" @click="cancelDetailEdit">取消</view>
          <view class="btn-outline-sm detail-save-btn" @click="saveDetailEdit">{{ checkinSubmitting ? '保存中...' : '保存' }}</view>
        </template>
      </view>
    </view>
  </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { onLoad, onShow, onHide } from '@dcloudio/uni-app'
import { requirePageAuth, ensureChildUser, getChildUserId, resolveTrainingStreamUrl, fetchTrainingEntry, fetchTrainingToday, fetchTrainingProgress, submitTrainingCheckin, refreshTrainingReport, fetchTodayCheckins, updateTrainingCheckin, deleteTrainingCheckin, scheduleTrainingPlan, setTrainingWindow, clearTrainingWindow, markPlanMediaExhausted, fetchDevTrainingStatus, devResetTodayTraining, devResetTrainingProgress, devResetAllTraining, devSimulateNextDay, devSimulate4amCutoff, devResetTalent, devResetClock, postTrainingWatchProgress, fetchLatestAssessment, fetchAssessmentHistory, customizePlan, toggleElectiveItem } from '@/utils/userApi.js'
import { ensureTalentState, hasEffectiveTalent, clearTalentState, refreshTalentState } from '@/utils/talentState.js'
import { getDevMode, isDevToolsAvailable, setDevMode } from '@/utils/devMode.js'
import { miniCardSummary, resolvePlanItemSkill, TRAINING_ABILITIES } from '@/utils/trainingCardDisplay.js'

const TIMER_STORAGE_KEY_PREFIX = 'jnao_training_timer'
const HOUR_OPTIONS = [0, 1, 2, 3, 4, 5, 6, 7, 8]
/** 0 小时时可选分钟（最短 20）；有小时时含 0/5/10/15 以便拼整点 */
const MINUTE_OPTIONS_WITH_HOUR = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]
const MINUTE_OPTIONS_ZERO_HOUR = [20, 25, 30, 35, 40, 45, 50, 55]
const MIN_TRAINING_MINUTES = 20

/** Guide 深交接：仅展示提示，不改排课/计时逻辑 */
const guideHandoffBanner = ref(null)

onLoad((opts) => {
  const from = String(opts?.from || '').trim()
  const rawFocus = String(opts?.focus || '').trim()
  const rawHint = String(opts?.hint || '').trim()
  let focus = rawFocus
  let hint = rawHint
  try { if (rawFocus) focus = decodeURIComponent(rawFocus) } catch (_) { /* keep raw */ }
  try { if (rawHint) hint = decodeURIComponent(rawHint) } catch (_) { /* keep raw */ }
  if (from === 'guide' && (focus || hint)) {
    guideHandoffBanner.value = {
      focus: focus.slice(0, 40) || '',
      hint: hint.slice(0, 60) || '',
    }
  }
})

const devToolsAvailable = isDevToolsAvailable()
const devMode = ref(getDevMode())
const scheduleLoading = ref(false)
const agentScheduleEnabled = ref(false)
const entryLoading = ref(false)
const devStatusText = ref('')
const timerPhase = ref('setup') // setup | running | expired
const serverTimeOffsetMs = ref(0)
const unlockAtMs = ref(null)
const cutoffAtMs = ref(null)
const newDayAtMs = ref(null)
const dayTransition = ref(false)
const trainingDayKey = ref('')
let dayUnlockTickId = null
const selectedHours = ref(0)
const selectedMinutes = ref(0)
const remainingSeconds = ref(0)
const plannedDurationSec = ref(0)
let timerTickId = null

function todayAnimKey() { return 'jnao_plan_anim_' + new Date().toDateString() }
function planAnimShownToday() { try { return localStorage.getItem(todayAnimKey()) === '1' } catch (_) { return false } }
function markPlanAnimShown() { try { localStorage.setItem(todayAnimKey(), '1') } catch (_) {} }

const hourLabels = HOUR_OPTIONS.map(h => `${h} 小时`)
const minuteOptions = computed(() =>
  selectedHours.value === 0 ? MINUTE_OPTIONS_ZERO_HOUR : MINUTE_OPTIONS_WITH_HOUR
)
const minuteLabels = computed(() => minuteOptions.value.map(m => `${m} 分钟`))
const hourIndex = computed(() => Math.max(0, HOUR_OPTIONS.indexOf(selectedHours.value)))
const minuteIndex = computed(() => {
  const opts = minuteOptions.value
  const idx = opts.indexOf(selectedMinutes.value)
  return idx >= 0 ? idx : 0
})
const canStartTimer = computed(() => {
  if (durationLocked.value) return false
  if (trainingDayLocked.value || scheduleLoading.value || entryLoading.value || planJustGenerated.value) return false
  const total = selectedHours.value * 60 + selectedMinutes.value
  return total >= MIN_TRAINING_MINUTES
})
const durationLocked = computed(() => {
  if (timerPhase.value === 'running' || timerPhase.value === 'expired') return true
  if (planJustGenerated.value) return true
  const pm = Number(todayPlan.value?.planned_minutes || 0)
  return !!(todayPlan.value?.plan_id && pm >= MIN_TRAINING_MINUTES)
})
const timeCardTitle = computed(() => {
  if (timerPhase.value === 'running') return '⏰ 今日训练计时'
  if (timerPhase.value === 'expired') return '⏰ 今日训练'
  if (durationLocked.value) return '⏰ 今日训练时长'
  return '⏰ 请选择训练时长'
})
const lockedDurationLabel = computed(() => {
  const pm = Number(todayPlan.value?.planned_minutes || 0)
  if (pm >= MIN_TRAINING_MINUTES) return formatDuration(pm * 60)
  return formatDuration((selectedHours.value * 60 + selectedMinutes.value) * 60)
})
const isPageLoading = computed(() => scheduleLoading.value || entryLoading.value || planJustGenerated.value)
const hasPlanItems = computed(() => (todayPlan.value?.items?.length || 0) > 0)
const trainingHasStarted = computed(() => {
  if (timerPhase.value === 'running' || timerPhase.value === 'expired') return true
  if (Object.keys(phaseRecordIds.value).length > 0) return true
  const items = todayPlan.value?.items || []
  return items.some(i => i.checkin_status === 'done' || Number(i.watch_progress?.pct || 0) > 0)
})
const planEmptyHint = computed(() => {
  if (needAssessment.value) return '完成天赋测评后可开始训练'
  if (scheduleLoading.value) return '正在生成今日训练内容…'
  return '选择训练时长，点击「开始训练」生成今日内容'
})
const timeSetupHint = computed(() => {
  if (scheduleLoading.value) return '正在按设定时长生成训练内容…'
  if (planJustGenerated.value) return '可在下方查看、编辑训练内容，确认后开始计时'
  if (durationLocked.value) return '时长已锁定，确认方案后开始计时'
  if (agentScheduleEnabled.value) {
    return '「开始训练」走标准方案；「智能排课」先试推荐，失败自动改用标准方案'
  }
  return '选择时长后点击「开始训练」，将按孩子情况分配今日内容'
})
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
/** 音视频：计时结束、后端 media_exhausted 或全局截止 */
const isMediaExhausted = computed(() => !!todayPlan.value?.media_exhausted)
const isMediaLocked = computed(() => !devMode.value && (isPageLoading.value || timerPhase.value === 'setup' || timerPhase.value === 'expired' || isGlobalCutoff.value))
/** 打卡：仅全局4点截止前可修改，不受 day_locked / 计时状态影响 */
const isCheckinLocked = computed(() => !devMode.value && (isPageLoading.value || isGlobalCutoff.value))
const mediaLockText = computed(() => {
  if (isPageLoading.value) return '方案生成中，请稍候...'
  if (dayTransition.value || todayPlan.value?.status === 'transition') return '训练日切换中，请稍候'
  if (isGlobalCutoff.value) return '凌晨4点训练日已截止'
  if (isMediaExhausted.value || timerPhase.value === 'expired') return '训练时长已到，音视频已锁定'
  if (trainingDayLocked.value && timerPhase.value === 'setup') return dayLockText.value
  return '请先设置时长并开始训练'
})
const checkinLockText = computed(() => {
  if (isPageLoading.value) return '方案生成中，请稍候...'
  if (dayTransition.value || todayPlan.value?.status === 'transition') return '训练日切换中，请稍候'
  if (isGlobalCutoff.value) return '凌晨4点训练日已截止，无法修改打卡'
  return ''
})
const countdownDisplay = computed(() => formatDuration(remainingSeconds.value))
let _prevDisplay = ''
const countdownChars = computed(() => {
  const cur = countdownDisplay.value
  const chars = cur.split('').map((ch, i) => ({ ch, changed: _prevDisplay[i] !== ch }))
  _prevDisplay = cur
  return chars
})
const durationLabel = computed(() => formatDuration(plannedDurationSec.value))

function timerStorageKey() {
  const uid = getChildUserId()
  const day = trainingDayKey.value || 'default'
  return `${TIMER_STORAGE_KEY_PREFIX}_${uid || 0}_${day}`
}

function nowSynced() {
  return Date.now() + serverTimeOffsetMs.value
}

function formatWindowTime(ms) {
  const s = new Date(ms).toLocaleString('sv-SE', { timeZone: 'Asia/Shanghai' })
  const timePart = s.split(' ')[1] || '00:00:00'
  const [hh, mm, ss = '00'] = timePart.split(':')
  return `${hh}:${mm}:${ss}`
}

function remainingSecondsUntil(endAtMs) {
  if (!endAtMs) return 0
  return Math.max(0, Math.ceil((endAtMs - nowSynced()) / 1000))
}

function applyDevTimeOverride(iso) {
  if (!iso) return
  serverTimeOffsetMs.value = new Date(iso).getTime() - Date.now()
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

let _transitionReloading = false

function checkGlobalSchedule() {
  checkDayUnlock()
  if (isGlobalCutoff.value && timerPhase.value === 'running') {
    expireTrainingTimer(true)
  }
  const inTransition = dayTransition.value || todayPlan.value?.status === 'transition'
  if (inTransition && newDayAtMs.value && nowSynced() >= newDayAtMs.value) {
    if (_transitionReloading) return
    _transitionReloading = true
    resetAllLocalState()
    loadTodayPlan(true).finally(() => { _transitionReloading = false })
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

const showGuideArrow = ref(false)
const redAlertActive = ref(false)

function onHourPick(e) {
  if (durationLocked.value) return
  selectedHours.value = HOUR_OPTIONS[Number(e.detail.value)] ?? 0
  // 切回 0 小时时，分钟不得低于 20
  if (selectedHours.value === 0 && selectedMinutes.value < MIN_TRAINING_MINUTES) {
    selectedMinutes.value = MIN_TRAINING_MINUTES
  }
  showGuideArrow.value = false
  redAlertActive.value = false
}
function onMinutePick(e) {
  if (durationLocked.value) return
  const opts = minuteOptions.value
  selectedMinutes.value = opts[Number(e.detail.value)] ?? opts[0] ?? MIN_TRAINING_MINUTES
  showGuideArrow.value = false
  redAlertActive.value = false
}

function clearTimerTick() {
  if (timerTickId != null) {
    clearInterval(timerTickId)
    timerTickId = null
  }
}

function writeTimerStorage(payload) {
  try {
    const data = { ...payload, trainingDay: trainingDayKey.value || payload.trainingDay || null }
    localStorage.setItem(timerStorageKey(), JSON.stringify(data))
  } catch (_) { /* ignore */ }
}

function persistTimer(endAt, plannedSec, planId = null) {
  writeTimerStorage({
    phase: 'running',
    endAt,
    plannedSec,
    planId: planId ?? todayPlan.value?.plan_id ?? null,
  })
}

function readTimerData() {
  try {
    let raw = localStorage.getItem(timerStorageKey())
    // 仅在 trainingDay 尚未从服务端加载时，才按 userId 前缀扫缓存（进页秒开）
    if (!raw && !trainingDayKey.value) {
      const uid = getChildUserId()
      if (uid) {
        const prefix = `${TIMER_STORAGE_KEY_PREFIX}_${uid}_`
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i)
          if (key?.startsWith(prefix)) {
            raw = localStorage.getItem(key)
            break
          }
        }
      }
    }
    if (!raw) return null
    return JSON.parse(raw) || null
  } catch (_) { return null }
}

function clearAllTimerKeysForUser(uid = getChildUserId()) {
  if (!uid) return
  const prefix = `${TIMER_STORAGE_KEY_PREFIX}_${uid}_`
  try {
    const keys = []
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key?.startsWith(prefix)) keys.push(key)
    }
    keys.forEach((key) => localStorage.removeItem(key))
  } catch (_) { /* ignore */ }
}

function resetTimerToSetup() {
  clearTimerTick()
  timerPhase.value = 'setup'
  remainingSeconds.value = 0
  plannedDurationSec.value = 0
  resetDurationPickers()
  closeMedia()
}

function clearTimerSession() {
  clearAllTimerKeysForUser()
  ensureChildUser().then((uid) => clearTrainingWindow(uid)).catch(() => {})
}

function applyTimerFromServer(data) {
  if (!data) return
  const phase = data.timer_phase || 'setup'

  if (phase === 'setup') {
    clearAllTimerKeysForUser()
    resetTimerToSetup()
    const items = todayPlan.value?.items || []
    const hasProgress = items.some(
      i => i.checkin_status === 'done' || Number(i.watch_progress?.pct || 0) > 0
    )
    if (!hasProgress) {
      showTraining.value = false
    }
    return
  }

  if (phase === 'expired') {
    clearTimerTick()
    timerPhase.value = 'expired'
    remainingSeconds.value = 0
    plannedDurationSec.value = data.timer_planned_seconds || (data.planned_minutes || 0) * 60
    writeTimerStorage({
      phase: 'expired',
      plannedSec: plannedDurationSec.value,
      planId: data.plan_id || null,
    })
    return
  }

  const endAt = data.timer_end_at ? new Date(data.timer_end_at).getTime() : null
  const plannedSec = data.timer_planned_seconds || (data.planned_minutes || 0) * 60 || 0
  if (!endAt) {
    const fallback = Number(data.timer_remaining_seconds || 0)
    if (fallback <= 0) {
      applyTimerFromServer({ ...data, timer_phase: 'expired' })
      return
    }
    plannedDurationSec.value = plannedSec || fallback
    remainingSeconds.value = fallback
    timerPhase.value = 'running'
    const syntheticEnd = nowSynced() + fallback * 1000
    persistTimer(syntheticEnd, plannedDurationSec.value, data.plan_id)
    clearTimerTick()
    timerTickId = setInterval(tickTrainingTimer, 1000)
    return
  }

  const remaining = remainingSecondsUntil(endAt)
  if (remaining <= 0) {
    applyTimerFromServer({ ...data, timer_phase: 'expired' })
    return
  }

  plannedDurationSec.value = plannedSec || remaining
  remainingSeconds.value = remaining
  timerPhase.value = 'running'
  persistTimer(endAt, plannedDurationSec.value, data.plan_id)
  clearTimerTick()
  timerTickId = setInterval(tickTrainingTimer, 1000)
}

function resetDurationPickers() {
  selectedHours.value = 0
  selectedMinutes.value = 0
}

function syncPickersFromPlannedMinutes(minutes) {
  if (!minutes || minutes < MIN_TRAINING_MINUTES) return
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (HOUR_OPTIONS.includes(h)) selectedHours.value = h
  const opts = h === 0 ? MINUTE_OPTIONS_ZERO_HOUR : MINUTE_OPTIONS_WITH_HOUR
  let best = opts[0]
  for (const x of opts) {
    if (Math.abs(x - m) < Math.abs(best - m)) best = x
  }
  selectedMinutes.value = best
}

function syncPickersAfterTimerRestore(planMinutes) {
  if (timerPhase.value === 'setup') {
    resetDurationPickers()
    return
  }
  const mins = planMinutes || Math.round((plannedDurationSec.value || 0) / 60)
  syncPickersFromPlannedMinutes(mins)
}

/**
 * 训练卡显隐是前端状态（confirmPlan），离页再进会丢。
 * 已有方案且计时已开始/结束（或已有进度）时自动恢复展示，避免「方案在、卡片没了」。
 */
function restoreTrainingVisibility(data) {
  if (showTraining.value) return
  const plan = data || todayPlan.value
  if (!plan?.plan_id) return
  const items = plan.items || []
  if (!items.length) return
  const phase = plan.timer_phase || timerPhase.value
  if (phase === 'running' || phase === 'expired') {
    showTraining.value = true
    planJustGenerated.value = false
    return
  }
  if (items.some(i => i.checkin_status === 'done' || Number(i.watch_progress?.pct || 0) > 0)) {
    showTraining.value = true
    planJustGenerated.value = false
  }
}

function syncPlanMetaFromApi(data) {
  if (!data) return
  // 课序用训练天数；勿用 content_index（v3 存 overall_tier）
  lessonIndex.value = data.training_day_number ?? data.lesson_day ?? 1
  if (data.overall_tier != null) overallTier.value = data.overall_tier
}

async function applyScheduledPlan(uid, data) {
  todayPlan.value = data
  applyServerTimeMeta(data)
  syncPlanMetaFromApi(data)
  aiPlanText.value = data.report_text || ''
  applyPlanMedia(data)
  hydrateWatchProgressFromPlan(data)
  if (Number(data.planned_minutes || 0) >= MIN_TRAINING_MINUTES) {
    syncPickersFromPlannedMinutes(data.planned_minutes)
    plannedDurationSec.value = data.planned_minutes * 60
  }
  // 方案变更后清除 position-based 状态，避免 block ID 碰撞
  phaseRecordIds.value = {}
  phaseClicked.value = {}
  planExpanded.value = {}
  // 时长选择器仅在用户本次已选；不在此回填 planned_minutes
  await loadTodayCheckinRecords(uid, data.plan_id)
  nextTick(() => syncPhaseExpand())
  refreshAiPlanInBackground(uid)
}

function syncMediaExhausted() {
  if (todayPlan.value) todayPlan.value.media_exhausted = true
  ensureChildUser()
    .then((uid) => markPlanMediaExhausted(uid))
    .then((res) => {
      if (res?.data && todayPlan.value) Object.assign(todayPlan.value, res.data)
    })
    .catch(() => {})
}

function expireTrainingTimer(silent = false) {
  clearTimerTick()
  const data = readTimerData()
  const plannedSec = plannedDurationSec.value || data?.plannedSec || 0
  writeTimerStorage({
    phase: 'expired',
    plannedSec,
    planId: data?.planId ?? todayPlan.value?.plan_id ?? null,
  })
  timerPhase.value = 'expired'
  remainingSeconds.value = 0
  closeMedia()
  syncMediaExhausted()
  if (!silent) {
    const msg = isGlobalCutoff.value ? '凌晨4点训练日已截止' : '训练时长已到，仍可打卡'
    uni.showToast({ title: msg, icon: 'none', duration: 2500 })
  }
}

function syncTimerFromEndAt(endAt) {
  const left = remainingSecondsUntil(endAt)
  if (left <= 0) {
    expireTrainingTimer(true)
    return
  }
  timerPhase.value = 'running'
  remainingSeconds.value = left
}

function resumeTimerFromStorage() {
  const data = readTimerData()
  if (!data || data.phase !== 'running' || !data.endAt) return false
  if (Number(data.plannedSec) > 0) plannedDurationSec.value = Number(data.plannedSec)
  syncTimerFromEndAt(Number(data.endAt))
  if (timerPhase.value !== 'running') return true
  clearTimerTick()
  timerTickId = setInterval(tickTrainingTimer, 1000)
  return true
}

function tickTrainingTimer() {
  const data = readTimerData()
  if (!data) {
    clearTimerTick()
    return
  }
  syncTimerFromEndAt(data.endAt)
}

function maxBlocksForMinutes(minutes) {
  // 与 backend slot_table + homework 上界对齐（含非精确点 floor）
  if (minutes < 40) return 1       // 5–39 → 20min 档
  if (minutes < 60) return 2       // 40–59 → 40min 档
  if (minutes <= 120) return 3     // 60–120
  if (minutes <= 180) return 5     // 4 + homework
  if (minutes <= 240) return 6     // 4 + 最多 2 homework
  if (minutes < 480) return 8      // 5 + 最多 3 homework
  return 10                        // ≥480：6 + homework / 精力恢复
}

function isPlanStructureStale(plannedMinutes) {
  // v2.0: each item is an independent training unit; structure is stale only if
  // the item count exceeds the expected max for the planned duration
  const items = todayPlan.value?.items || []
  if (!items.length) return false
  const maxBlocks = maxBlocksForMinutes(plannedMinutes)
  return items.length > maxBlocks
}

async function startTrainingTimer() {
  return startTrainingWithPrefer('rule')
}

async function startTrainingTimerAgent() {
  return startTrainingWithPrefer('agent')
}

async function startTrainingWithPrefer(schedulePrefer = 'rule') {
  if (trainingDayLocked.value) {
    uni.showToast({ title: dayLockText.value, icon: 'none', duration: 2500 })
    return
  }
  if (!canStartTimer.value) {
    if (entryLoading.value) {
      uni.showToast({ title: '方案加载中，请稍候', icon: 'none' })
    } else if (scheduleLoading.value) {
      uni.showToast({ title: '正在生成训练内容，请稍候', icon: 'none' })
    }
    showGuideArrow.value = true
    redAlertActive.value = false
    nextTick(() => { redAlertActive.value = true })
    return
  }
  const plannedMinutes = selectedHours.value * 60 + selectedMinutes.value
  if (plannedMinutes < MIN_TRAINING_MINUTES) {
    uni.showToast({ title: `训练时长至少 ${MIN_TRAINING_MINUTES} 分钟`, icon: 'none' })
    return
  }

  scheduleLoading.value = true
  try {
    const uid = await ensureChildUser()
    // 一天一次：仅未开始时允许生成/按新时长重生；已开始绝不因 stale 再调 schedule
    const hasContent = (todayPlan.value?.items?.length || 0) > 0
    const minutesChanged = todayPlan.value?.planned_minutes !== plannedMinutes
    const needSchedule = !trainingHasStarted.value && (
      !hasContent
      || minutesChanged
      || isPlanStructureStale(plannedMinutes)
    )
    if (trainingHasStarted.value && minutesChanged) {
      uni.showToast({ title: '今日训练已开始，无法更改时长', icon: 'none' })
      scheduleLoading.value = false
      return
    }
    if (needSchedule) {
      const result = await scheduleTrainingPlan(uid, plannedMinutes, schedulePrefer)
      if (result.error) throw new Error(result.message || '生成训练内容失败')
      await applyScheduledPlan(uid, result.data)
      if (schedulePrefer === 'agent' && result.data?.schedule_mode === 'agent_fallback') {
        uni.showToast({ title: '智能排课未生效，已改用标准方案', icon: 'none', duration: 2500 })
      } else {
        uni.showToast({ title: '方案已生成，请确认后开始', icon: 'none' })
      }
    } else if (!hasContent) {
      throw new Error('暂无训练内容，请稍后重试')
    } else {
      uni.showToast({ title: '方案已生成，请确认后开始', icon: 'none' })
    }

    // 远端修复：此处只生成方案并锁定时长，计时在 confirmPlan 后启动
    planJustGenerated.value = true
    showTraining.value = false
  } catch (e) {
        uni.showToast({ title: e.message || '生成训练内容失败', icon: 'none', duration: 2500 })
  } finally {
    scheduleLoading.value = false
  }
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
    uni.showToast({ title: '请先选择时长并点击「开始训练」', icon: 'none' })
    return false
  }
  return true
}

function guardCheckin(block) {
  if (devMode.value) return true
  if (isGlobalCutoff.value) {
    uni.showToast({ title: '训练日已截止，无法修改打卡', icon: 'none' })
    return false
  }
  if (block && (phaseRecordIds.value[block] || planPhases.value.find(p => p.block === block)?.allDone)) {
    return true
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

function openHistory() {
  uni.navigateTo({
    url: '/pages/training/history',
    fail: (err) => {
      console.error('openHistory failed', err)
      uni.showToast({ title: '无法打开历史页', icon: 'none' })
    },
  })
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
  clearTimerSession()
  resetTimerToSetup()
  pickerCards.value = []
  activePickerBlock.value = null
  watchedItemIds.value = new Set()
  watchProgressMap.value = {}
  showPicker.value = false
  submittedCards.value = []
  phaseRecordIds.value = {}
  primaryCheckinRecordId.value = null
  showTraining.value = false
  planJustGenerated.value = false
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
    const clock = s.dev_time_override ? ` · 虚拟 ${s.dev_time_override.slice(0, 16).replace('T', ' ')}` : ''
    devStatusText.value = `主线 ${s.main_line ?? 'A'} · 第 ${s.training_day_number ?? 1} 天 · ${tag} · 计划 ${s.plan_count} 条 · 打卡 ${s.record_count} 条${clock}`
  } catch (_) {
    devStatusText.value = ''
  }
}

async function devResetMainLine() {
  if (!devMode.value) return
  try {
    uni.showLoading({ title: '回到主线A...' })
    const uid = await ensureChildUser()
    await devResetTrainingProgress(uid)
    overallTier.value = 1
    await loadTodayPlan(true)
    await loadDevStatus()
    uni.showToast({ title: '训练进度已重置（今日方案未删）', icon: 'none' })
  } catch (e) {
        uni.showToast({ title: e.message || '重置训练进度失败', icon: 'none', duration: 2500 })
  } finally {
    uni.hideLoading()
  }
}

async function devResetToday() {
  if (!devMode.value) return
  try {
    uni.showLoading({ title: '重置今日...' })
    const uid = await ensureChildUser()
    await devResetTodayTraining(uid)
    devResetTimer(true)
    todayPlan.value = null
    aiPlanText.value = ''
    videoSrc.value = ''
    audioSrc.value = ''
    submittedCards.value = []
    showTraining.value = false
    planJustGenerated.value = false
    await loadTodayPlan(true)
    await loadDevStatus()
    uni.showToast({ title: '今日方案已清空（历史保留）', icon: 'none' })
  } catch (e) {
        uni.showToast({ title: e.message || '重置今日方案失败', icon: 'none', duration: 2500 })
  } finally {
    uni.hideLoading()
  }
}

async function devSimulate4amCutoffAction() {
  if (!devMode.value) return
  try {
    uni.showLoading({ title: '模拟4点截止...' })
    const uid = await ensureChildUser()
    const res = await devSimulate4amCutoff(uid)
    applyDevTimeOverride(res.dev_time_override)
    devResetTimer(true)
    expireTrainingTimer(true)
    if (res.today_plan?.plan_id) {
      todayPlan.value = res.today_plan
      applyPlanMedia(res.today_plan)
      aiPlanText.value = res.today_plan.report_text || ''
      syncPlanMetaFromApi(res.today_plan)
    } else {
      await loadTodayPlan(true)
    }
    await loadDevStatus()
    uni.showToast({ title: res.message || '已模拟凌晨4点全局截止', icon: 'none', duration: 2500 })
  } catch (e) {
        uni.showToast({ title: e.message || '模拟截止失败', icon: 'none', duration: 2500 })
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
    applyDevTimeOverride(res.dev_time_override)
    devResetTimer(true)
    todayPlan.value = res.today?.plan_id ? res.today : (res.today || null)
    aiPlanText.value = res.today?.report_text || ''
    if (res.today?.plan_id) {
      applyPlanMedia(res.today)
      syncPlanMetaFromApi(res.today)
    } else {
      videoSrc.value = ''
      audioSrc.value = ''
      lessonIndex.value = res.status?.training_day_number ?? res.today?.training_day_number ?? 1
      syncPlanMetaFromApi(res.today || res.status)
    }
    await loadTodayPlan(true)
    nextTick(() => syncPhaseExpand())
    await loadDevStatus()
    const idx = res.today?.training_day_number ?? res.status?.training_day_number ?? '?'
    uni.showToast({ title: res.message || `已进入下一天 · 课序 ${idx}`, icon: 'none', duration: 2500 })
  } catch (e) {
        uni.showToast({ title: e.message || '模拟下一天失败', icon: 'none', duration: 2500 })
  } finally {
    uni.hideLoading()
  }
}

async function devResetClockAction() {
  if (!devMode.value) return
  try {
    uni.showLoading({ title: '清除虚拟时钟...' })
    const uid = await ensureChildUser()
    const res = await devResetClock(uid)
    applyDevTimeOverride(null)
    devResetTimer(true)
    await loadTodayPlan(true)
    nextTick(() => syncPhaseExpand())
    await loadDevStatus()
    uni.showToast({ title: res.message || '已回归实际日期', icon: 'none', duration: 2000 })
  } catch (e) {
        uni.showToast({ title: e.message || '回归实际日期失败', icon: 'none', duration: 2500 })
  } finally {
    uni.hideLoading()
  }
}

function devPreviewCongrats() {
  uni.showToast({ title: '🎉 超脑阅读 晋级成功！', icon: 'none', duration: 3000 })
}
function devPreviewRegret() {
  uni.showToast({ title: '😔 超脑阅读 差一点就晋级了，明天继续加油！', icon: 'none', duration: 3000 })
}

async function devClearAllHistory() {
  if (!devMode.value) return
  try {
    uni.showLoading({ title: '清空中...' })
    const uid = await ensureChildUser()
    await devResetAllTraining(uid)
    resetAllLocalState()
    todayPlan.value = null
    aiPlanText.value = ''
    videoSrc.value = ''
    audioSrc.value = ''
    await loadTodayPlan(true)
    await loadDevStatus()
    uni.showToast({ title: '训练历史已清空', icon: 'none' })
  } catch (e) {
        uni.showToast({ title: e.message || '清空历史失败', icon: 'none', duration: 2500 })
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
    clearTalentState()
    const talent = await refreshTalentState(uid)
    needAssessment.value = !hasEffectiveTalent(talent)
    showAssessmentModal.value = needAssessment.value
    todayPlan.value = null
    await loadTodayPlan(true)
    await loadDevStatus()
    uni.showToast({ title: '天赋测评已重置', icon: 'none' })
  } catch (e) {
        uni.showToast({ title: e.message || '重置天赋失败', icon: 'none', duration: 2500 })
  } finally {
    uni.hideLoading()
  }
}

function clearTimerStorage() {
  clearAllTimerKeysForUser()
}

function devResetTimer(silent = false) {
  clearTimerSession()
  resetTimerToSetup()
  if (!silent) uni.showToast({ title: '计时已重置', icon: 'none' })
}

function devSimulateExpire() {
  clearTimerTick()
  clearTimerStorage()
  resetDurationPickers()
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
  scheduleLoading.value = true
  planJustGenerated.value = false
  try {
    const uid = await ensureChildUser()
    const result = await refreshTrainingReport(uid, true)
    if (result.error) throw new Error(result.message)
    todayPlan.value = result.data
    applyPlanMedia(result.data)
    aiPlanText.value = result.data.report_text || ''
    syncPlanMetaFromApi(result.data)
    nextTick(() => syncPhaseExpand())
  } catch (e) {
    scheduleLoading.value = false
        uni.showToast({ title: e.message || '刷新AI方案失败', icon: 'none', duration: 2500 })
    return
  }
  scheduleLoading.value = false
  planJustGenerated.value = true
  setTimeout(() => { planJustGenerated.value = false }, 1500)
  uni.showToast({ title: 'AI 方案已刷新', icon: 'none' })
}

const showPicker = ref(false)
const activePickerBlock = ref(null)
const submittedCards = ref([])
const summaryAttitude = ref(60)

// ── 选修开关（替代弹窗）──
const electiveSkills = computed(() => {
  const items = todayPlan.value?.items || []
  const list = []

  function skillInPlan(skill) {
    return items.some(item => {
      const inst = parseItemInstructions(item.instructions)
      return inst.skill === skill
    })
  }

  // 多元感知（OSS 内部名：感知力）
  list.push({ skill: '感知力', label: '多元感知', inPlan: skillInPlan('感知力') })
  // 开口窍：视频选修，独立开关
  list.push({ skill: '开口窍', label: '开口窍 🎬', inPlan: skillInPlan('开口窍') })

  return list
})

const electiveToggling = ref(false)

async function toggleElective(skill) {
  if (electiveToggling.value) return
  const uid = await ensureChildUser()
  const planId = todayPlan.value?.plan_id
  if (!planId) { uni.showToast({ title: '方案不存在', icon: 'none' }); return }
  const pendingConfirm = planJustGenerated.value && timerPhase.value === 'setup'
  const inPlan = electiveSkills.value.find(e => e.skill === skill)?.inPlan
  const action = inPlan ? 'remove' : 'add'
  electiveToggling.value = true
  try {
    const data = await toggleElectiveItem(uid, planId, skill, action)
    await applyScheduledPlan(uid, data)
    if (pendingConfirm) planJustGenerated.value = true
    uni.showToast({ title: inPlan ? `已移除 ${skill}` : `已添加 ${skill}`, icon: 'none' })
  } catch (e) {
    const msg = e.data?.detail || e.message || '操作失败'
    uni.showToast({ title: Array.isArray(msg) ? msg.map(d => d.msg || JSON.stringify(d)).join('; ') : msg, icon: 'none', duration: 3000 })
  } finally {
    electiveToggling.value = false
  }
}

// ── 选修说明 ──
const ELECTIVE_INFO = {
  '感知力': {
    title: '🧩 多元感知是什么？',
    desc: '多元感知是双人互动训练，需要家长或同学配合完成。通过听觉、视觉等多感官刺激，提升专注力和感知能力。',
    age: '适合各年龄段孩子训练，低龄儿童可在家长陪伴下进行。',
    how: '开启后，训练计划中将出现「多元感知」环节，按提示播放音频并完成互动即可。',
  },
  '开口窍': {
    title: '🗣️ 开口窍是什么？',
    desc: '开口窍通过朗读口腔操训练唇舌灵活度，激活语言中枢，促进左右脑协同工作，有效提升阅读速度与理解能力。',
    age: '适合各年龄段，低龄孩子可每天跟练5分钟，发音更清晰流畅。',
    how: '开启后，训练计划中将出现「开口窍」视频环节，跟随老师朗读练习即可。',
  },
  'edit_plan': {
    title: '📝 编辑方案说明',
    desc: '如果您觉得推荐内容可以，就点击音频｜视频开始训练吧，不认可可以自行编辑方案哦。',
    age: '',
    how: '⚠️ 仅可编辑一次，开始打卡后不可再修改。',
  },
}
const showInfoModal = ref(false)
const infoModalData = ref({ title: '', desc: '', age: '', how: '' })

function showElectiveInfoModal(skill) {
  const info = ELECTIVE_INFO[skill]
  if (!info) return
  infoModalData.value = { ...info }
  showInfoModal.value = true
}

function isPerceptionPhase(phase) {
  if (!phase?.items?.length) return false
  const item = phase.items[0]
  return item.item_type === 'perception' || (item.title || '').includes('多元感知')
}

async function autoCompletePerception(phase) {
  if (phase.allDone || phaseRecordIds.value[phase.block]) return
  if (perceptionSubmitting.value) return
  const item = phase.items[0]
  if (!item?.id) return
  perceptionSubmitting.value = true
  try {
    const uid = await ensureChildUser()
    const cardsList = [{ name: '多元感知', time: item.duration_min || '', content: '已听音频', phaseBlock: phase.block }]
    await persistPhaseCheckin(phase.block, cardsList)
    await loadTodayCheckinRecords(uid, todayPlan.value.plan_id)
    await loadTodayPlan(true)
    uni.showToast({ title: '✅ 多元感知训练完成！', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '提交失败', icon: 'none', duration: 2500 })
  } finally {
    perceptionSubmitting.value = false
  }
}

// ── 方案编辑 ──
const showCustomizeConfirm = ref(false)
const pendingCustomize = ref(null)
const showSubmitConfirm = ref(false)
const pendingSubmitBlock = ref(null)
const showDeleteConfirm = ref(false)
const deleteTargetIdx = ref(-1)
const deleteTargetName = ref('')
const showPlanEditor = ref(false)
const editorSkills = ref([])

const allReplacableSkills = ['超脑阅读', '影像追忆', '扫描速记', '极速运算', '极速学习']

const editableItems = computed(() => {
  const items = todayPlan.value?.items || []
  return items.filter(i => i.checkin_status !== 'done').filter(i => {
    const inst = parseItemInstructions(i.instructions)
    return inst.item_type !== 'elective' && inst.blocks_next !== false
  })
})

const canCustomizePlan = computed(() => !!todayPlan.value?.can_customize_plan)

function editorSkillName(item) {
  const idx = editorSkills.value.findIndex(s => s.startsWith(item.id + ':'))
  if (idx >= 0) return editorSkills.value[idx].split(':')[1]
  const inst = parseItemInstructions(item.instructions)
  return inst.skill || resolvePlanItemSkill(item) || '训练'
}

function editorSkillIndex(item) {
  const name = editorSkillName(item)
  const idx = allReplacableSkills.indexOf(name)
  return idx >= 0 ? idx : 0
}

function onEditorSkillChange(itemIdx, e) {
  const val = e.detail.value
  const skill = allReplacableSkills[val]
  const item = editableItems.value[itemIdx]
  if (item && skill) {
    editorSkills.value[itemIdx] = item.id + ':' + skill
  }
}

function openPlanEditor() {
  if (!canCustomizePlan.value) {
    const reason = todayPlan.value?.plan_customized
      ? '今日方案已编辑过，不可再次修改'
      : todayPlan.value?.has_checkin
        ? '已有打卡记录，无法编辑方案'
        : '当前不可编辑方案'
    uni.showToast({ title: reason, icon: 'none' })
    return
  }
  editorSkills.value = editableItems.value.map(item => {
    const inst = parseItemInstructions(item.instructions)
    const sk = inst.skill || resolvePlanItemSkill(item) || '训练'
    return item.id + ':' + sk
  })
  showPlanEditor.value = true
}

function closePlanEditor() { showPlanEditor.value = false }

function confirmCustomize() {
  const uid = ensureChildUser()
  const planId = todayPlan.value?.plan_id
  if (!planId) { uni.showToast({ title: '方案不存在', icon: 'none' }); return }
  const skills = editorSkills.value.map(s => s.split(':')[1])
  pendingCustomize.value = { uid, planId, skills }
  showCustomizeConfirm.value = true
}

async function doCustomize() {
  const c = pendingCustomize.value
  if (!c) return
  showCustomizeConfirm.value = false
  try {
    const uid = await c.uid
    await customizePlan(uid, c.planId, c.skills)
    uni.showToast({ title: '方案已更新', icon: 'none' })
    closePlanEditor()
    await loadTodayPlan(true)
  } catch (e) {
    const detail = e.data?.detail || e.message || '修改失败'
    const msg = Array.isArray(detail) ? detail.map(d => d.msg || JSON.stringify(d)).join('; ') : detail
    uni.showToast({ title: msg, icon: 'none', duration: 3000 })
  } finally {
    pendingCustomize.value = null
  }
}

const attitudeTouched = ref(false)
const scores = [
  { pct:100, emoji:'🔴', desc:'身体已透支，精神还要求进步' },
  { pct:80,  emoji:'🟡', desc:'能完成任务，但还有余力学习' },
  { pct:60,  emoji:'🔵', desc:'做基本任务，被动的低效训练' },
  { pct:40,  emoji:'🟤', desc:'不完成任务，不认真逃避训练' },
  { pct:20,  emoji:'⚫️', desc:'不完成任务，基本不配合训练' },
  { pct:0,   emoji:'☠️', desc:'不完成任务，严重不配合训练' },
]
const mediaPlayer = ref({ show: false, type: 'video', title: '' })
const watchedItemIds = ref(new Set())
const watchProgressMap = ref({})
const trainingVideoEl = ref(null)
let trainingAudio = null
let watchProgressSaveTimer = null
const lastOpenedItem = ref(null)
const mediaMaxHeardSec = ref(0)
const audioPlaying = ref(false)
const videoPlaying = ref(false)
const videoLoading = ref(false)
const videoMetadataReady = ref(false)
const videoLoadAttempt = ref(0)
const VIDEO_LOAD_MAX_RETRIES = 3
let videoRetryTimer = null
const planMediaPreloaded = ref(false)
const audioUiSec = ref(0)
const audioUiDuration = ref(0)
const WATCH_DONE_PCT = 90
const MEDIA_SEEK_EPS = 1.2
const phaseClicked = ref({})
const primaryCheckinRecordId = ref(null)
const planJustGenerated = ref(false)
const showTraining = ref(false)
const showDoneConfirm = ref(false)
const videoSrc = ref('')
const activeVideoItemId = ref(0)
const audioSrc = ref('')
const audioTitle = ref('🎧 训练用音频')
const talentLabel = ref('')
const aiPlanText = ref('')

const coachCollapsed = ref(false)
const coachGuideText = computed(() => {
  const t = (aiPlanText.value || todayPlan.value?.report_text || '').trim()
  if (!t) return ''
  if (/训练块|primary|optional|块\s*1|分钟\s*→/i.test(t)) return ''
  return t
})
const lessonIndex = ref(1)
const curMainLine = ref('A')
const curMainLineName = ref('')
// 🆕 v2.0
const overallTier = ref(1)
const skillTierProgress = ref({})

const planHeaderMeta = computed(() => {
  const parts = [talentLabel.value]
  const tier = overallTier.value || todayPlan.value?.overall_tier || 1
  if (tier > 1) parts.push(`Lv.${tier}`)
  const day = todayPlan.value?.training_day_number ?? todayPlan.value?.lesson_day ?? lessonIndex.value
  if (day) parts.push(`第 ${day} 天`)
  return parts.filter(Boolean).join(' · ')
})
const needAssessment = ref(false)
const showAssessmentModal = ref(false)
const todayPlan = ref(null)
const phaseRecordIds = ref({})

/** DEV only：Agent 排课理由（正式 UI 不展示） */
const scheduleAssistDevText = computed(() => {
  const a = todayPlan.value?.schedule_assist
  if (!a || typeof a !== 'object') return ''
  const lines = []
  if (a.mode) lines.push(`模式：${a.mode}`)
  if (a.reason) lines.push(String(a.reason))
  else if (a.mode === 'agent') lines.push('（模型未返回 reason）')
  if (Array.isArray(a.draft) && a.draft.length) {
    lines.push(`草案：${a.draft.join(' → ')}`)
  }
  if (Array.isArray(a.rule_slots) && a.rule_slots.length) {
    lines.push(`规则对照：${a.rule_slots.join(' → ')}`)
  }
  if (Array.isArray(a.projected) && a.projected.length) {
    lines.push(`落库：${a.projected.join(' → ')}`)
  }
  if (Array.isArray(a.padded_from_intent) && a.padded_from_intent.length) {
    lines.push(`画像补齐：${a.padded_from_intent.join('、')}`)
  }
  if (Array.isArray(a.padded_from_rule) && a.padded_from_rule.length) {
    lines.push(`规则垫底：${a.padded_from_rule.join('、')}`)
  }
  if (Array.isArray(a.dropped_for_slot_cap) && a.dropped_for_slot_cap.length) {
    lines.push(`槽位截断：${a.dropped_for_slot_cap.join('、')}`)
  }
  return lines.join('\n')
})

async function confirmPlan() {
  // 确认方案后才开始计时；训练块在此之后解锁。
  if (scheduleLoading.value || !planJustGenerated.value) {
    showTraining.value = true
    planJustGenerated.value = false
    return
  }
  const plannedMinutes = todayPlan.value?.planned_minutes
    ?? (selectedHours.value * 60 + selectedMinutes.value)
  if (plannedMinutes < MIN_TRAINING_MINUTES) {
    uni.showToast({ title: `训练时长至少 ${MIN_TRAINING_MINUTES} 分钟`, icon: 'none' })
    return
  }

  scheduleLoading.value = true
  try {
    const uid = await ensureChildUser()
    const totalSec = plannedMinutes * 60
    plannedDurationSec.value = totalSec
    const nowMs = nowSynced()
    const endAt = nowMs + totalSec * 1000
    const runningTimerPayload = {
      timer_phase: 'running',
      timer_end_at: new Date(endAt).toISOString(),
      timer_planned_seconds: totalSec,
      timer_remaining_seconds: Math.ceil((endAt - nowSynced()) / 1000),
      plan_id: todayPlan.value?.plan_id,
    }

    await setTrainingWindow(uid, formatWindowTime(nowMs), formatWindowTime(endAt))
    const synced = await fetchTrainingToday(uid, { skipAi: true })
    if (!synced.error && synced.data?.timer_phase === 'running') {
      applyServerTimeMeta(synced.data)
      applyTimerFromServer(synced.data)
      syncPickersAfterTimerRestore(synced.data.planned_minutes)
    } else {
      applyTimerFromServer(runningTimerPayload)
      syncPickersAfterTimerRestore(plannedMinutes)
    }

    showTraining.value = true
    planJustGenerated.value = false
    preloadTodayPlanMedia(uid)
    uni.showToast({ title: '训练已开始', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '开始训练失败', icon: 'none', duration: 2500 })
  } finally {
    scheduleLoading.value = false
  }
}

const checkinSubmitting = ref(false)
const perceptionSubmitting = ref(false)
const accErrorCards = ref({})

const todayCompleted = computed(() => todayPlan.value?.status === 'completed')
const checkedPhaseCount = computed(() => new Set(submittedCards.value.map(c => c.phaseBlock).filter(Boolean)).size)

function getPhaseItems(block) {
  // v2.0: planPhases uses index-based block ("1","2","3"), each phase has exactly one item
  const phase = planPhases.value.find(p => p.block === block)
  if (!phase || phase.itemId == null) return []
  return (todayPlan.value?.items || []).filter(i => i.id === phase.itemId)
}

function blockForItemId(itemId) {
  // v2.0: find which phase contains this item by matching phase.itemId
  const phase = planPhases.value.find(p => p.itemId === itemId)
  return phase ? phase.block : '1'
}

function buildPhaseSubtitle(items) {
  const names = []
  for (const item of items) {
    const t = (item.title || '').trim()
    if (t) names.push(t)
  }
  if (names.length) return names.join('、')
  const tags = new Set()
  for (const item of items) {
    if (item.item_type === 'video' || item.video_url) tags.add('视频')
    if (item.item_type === 'audio' || (item.audio_url && !item.video_url)) tags.add('音频')
  }
  if (!tags.size) return '综合训练'
  return `${[...tags].join('+')}训练`
}

const mediaPlayerTitle = computed(() => {
  const mp = mediaPlayer.value
  const raw = (mp.title || audioTitle.value || '').replace(/^🎧\s*/, '').replace(/^🎬\s*/, '').trim()
  if (raw) {
    return mp.type === 'video' ? `🎬 ${raw}` : `🎧 ${raw}`
  }
  return mp.type === 'video' ? '🎬 视频训练' : '🎧 音频训练'
})

function isPhaseUnlocked(block) {
  // v2.0: use planPhases which pre-calculates unlocked status
  const phase = planPhases.value.find(p => p.block === block)
  return phase ? phase.unlocked : true
}

const planExpanded = ref({})
const visiblePhases = computed(() => {
  return planPhases.value.filter(p => {
    // 有打卡记录且不是多元感知 → 隐藏
    if (phaseRecordIds.value[p.block] && !isPerceptionPhase(p)) return false
    return true
  })
})

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
      next[p.block] = false
    }
  }
  planExpanded.value = next
}

const planPhases = computed(() => {
  const items = todayPlan.value?.items || []
  if (!items.length) return []

  // v2.0: 每个 item 独立为一个 phase，按 sort_order 顺序
  const sorted = [...items].sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
  let prevDone = true  // first item always unlocked

  return sorted.map((item, idx) => {
    const inst = parseItemInstructions(item.instructions)
    const isRequired = inst.item_type !== 'elective' && inst.blocks_next !== false
    const isDone = item.checkin_status === 'done'
    const unlocked = isRequired ? (prevDone || isDone) : true  // elective always unlocked

    // Update prevDone for next iteration — completed items keep the chain alive
    if (isRequired && !isDone) prevDone = false
    if (isDone) prevDone = true

    const skillName = inst.skill || resolvePlanItemSkill(item) || ''
    const isElective = !isRequired
    const label = isElective ? `${skillName || '选修'}（选修）` : `${idx + 1}. ${skillName || '训练'}`

    let nodeIcon = '○'
    let nodeClass = 'tl-node-locked'
    if (unlocked) {
      nodeIcon = isDone ? '✓' : '●'
      nodeClass = isDone ? 'tl-node-done' : 'tl-node-active'
    }

    return {
      block: String(idx + 1),
      itemId: item.id,
      firstItemId: item.id,
      label,
      subtitle: item.title || '',
      items: [item],
      unlocked,
      allDone: isDone,
      doneCount: isDone ? 1 : 0,
      totalCount: 1,
      nodeIcon,
      nodeClass,
      isElective,
      skillName,
    }
  })
})

function parseItemInstructions(instructions) {
  if (typeof instructions === 'string' && instructions.trim().startsWith('{')) {
    try { return JSON.parse(instructions) } catch (_) { /* */ }
  }
  return {}
}

/** 排除选修/多元感知等不需要打卡的项，避免进度卡住 */
function itemNeedsCheckin(item) {
  if (!item) return false
  const inst = parseItemInstructions(item.instructions)
  // 选修 / 多元感知 / blocks_next=false 的项不参与完成计数
  if (inst.item_type === 'elective' || inst.item_type === 'perception') return false
  if (inst.blocks_next === false) return false
  if (item.ability_type === 'elective') return false
  if (item.item_type === 'elective' || item.item_type === 'perception') return false
  return true
}

const planTotalCount = computed(() => (todayPlan.value?.items || []).filter(itemNeedsCheckin).length)
const planCompletedCount = computed(() => (todayPlan.value?.items || []).filter(i => itemNeedsCheckin(i) && i.checkin_status === 'done').length)
const planProgressPct = computed(() => {
  if (!planTotalCount.value) return 0
  return Math.round((planCompletedCount.value / planTotalCount.value) * 100)
})
const allRequiredDone = computed(() => {
  return planTotalCount.value > 0 && planCompletedCount.value === planTotalCount.value
})

function itemTypeEmoji(item) {
  if (item.item_type === 'perception' || (item.title || '').includes('多元感知')) return '🧠'
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
  if (item.item_type === 'perception' || (item.title || '').includes('多元感知')) return '多元感知'
  if (item.item_type === 'video' || item.video_url) return '视频训练'
  if (item.item_type === 'audio' || item.audio_url) return '音频训练'
  return '训练项'
}

function isVideoItem(item) {
  return item?.item_type === 'video' || !!item?.video_url
}

function videoTitle(item) {
  if (item?.title) return item.title
  if (!item?.video_url) return '训练视频'
  const url = item.video_url
  // 后端代理流地址不含文件名，勿从 /stream 解析
  if (url.includes('/stream')) return '训练视频'
  try {
    const name = decodeURIComponent(url.split('/').pop().split('?')[0])
    const base = name.replace(/\.[^.]*$/, '')
    return base.replace(/^shipin[\/_]/, '').replace(/^[_0-9.]+/, '') || '训练视频'
  } catch {
    return '训练视频'
  }
}

function itemNeedsListen(item) {
  if (!item) return false
  if (item.item_type === 'perception' || item.item_type === 'placeholder') return false
  return !!(item.audio_url || item.video_url)
}

function getItemWatchPct(item) {
  if (!item?.id) return 0
  const wp = watchProgressMap.value[item.id] || item.watch_progress || {}
  return Number(wp.pct || 0)
}

function isItemListenDone(item) {
  if (!itemNeedsListen(item)) return true
  if (item.checkin_status === 'done') return true
  if (item.video_complete) return true
  return getItemWatchPct(item) >= WATCH_DONE_PCT
}

function isPhaseListenDone(phase) {
  if (devMode.value) return true
  if (isPerceptionPhase(phase)) return true
  const items = phase?.items || []
  if (!items.length) return true
  return items.every(isItemListenDone)
}

function isItemWatched(item) {
  if (!item?.id) return false
  return isItemListenDone(item) || watchedItemIds.value.has(item.id)
}

const audioProgressPct = computed(() => {
  const d = audioUiDuration.value
  if (!d || d <= 0) return 0
  return Math.min(100, Math.round((audioUiSec.value / d) * 1000) / 10)
})

const audioTimeLabel = computed(() => {
  const fmt = (s) => {
    const n = Math.max(0, Math.floor(s || 0))
    const m = Math.floor(n / 60)
    const r = n % 60
    return `${m}:${String(r).padStart(2, '0')}`
  }
  return `${fmt(audioUiSec.value)} / ${fmt(audioUiDuration.value)} · 已听 ${Math.round(audioProgressPct.value)}%`
})

const audioDurationLabel = computed(() => {
  const d = audioUiDuration.value
  return d ? `${Math.floor(d / 60)}:${String(Math.floor(d % 60)).padStart(2, '0')}` : '--:--'
})

const videoProgressPct = ref(0)
const videoTimeLabel = ref('0:00')
const videoDurationLabel = ref('--:--')
const videoLoadingHint = computed(() => {
  if (videoLoadAttempt.value > 0) {
    return `正在重试加载 (${videoLoadAttempt.value}/${VIDEO_LOAD_MAX_RETRIES})…`
  }
  return '视频缓冲中…'
})

const mediaPlayIcon = computed(() => {
  if (mediaPlayer.value.type === 'video') return videoPlaying.value ? '⏸' : '▶'
  return audioPlaying.value ? '⏸' : '▶'
})

const mediaPlayerHint = computed(() => {
  if (mediaPlayer.value.type === 'video' && videoLoading.value) {
    return '视频缓冲中，请稍候…'
  }
  if (mediaPlayer.value.type === 'video' && !videoPlaying.value && videoMetadataReady.value) {
    return '点击下方 ▶ 开始播放'
  }
  return `听满约 ${WATCH_DONE_PCT}% 后可解锁打卡`
})

const playerCoverEmoji = computed(() => {
  const t = (audioTitle.value || mediaPlayerTitle.value || '').toLowerCase()
  if (t.includes('超脑') || t.includes('阅读')) return '🧠'
  if (t.includes('影像') || t.includes('追忆')) return '🎬'
  if (t.includes('扫描') || t.includes('速记')) return '📝'
  if (t.includes('运算')) return '⚡'
  if (t.includes('学习')) return '🚀'
  if (t.includes('作业')) return '✅'
  if (t.includes('绘画')) return '🎨'
  if (t.includes('音乐')) return '🎵'
  if (t.includes('棋')) return '♟️'
  if (t.includes('感知')) return '🔮'
  if (t.includes('精力') || t.includes('恢复')) return '💆'
  if (t.includes('开口')) return '🗣️'
  return '🎧'
})

function formatMediaTime(sec) {
  const n = Math.max(0, Math.floor(sec || 0))
  return `${Math.floor(n / 60)}:${String(n % 60).padStart(2, '0')}`
}

/** uni-app H5 下 ref 可能不是原生 HTMLVideoElement，需兼容解析 */
function getTrainingVideoDom() {
  if (pinnedTrainingVideo) {
    try {
      if (typeof document !== 'undefined' && document.body.contains(pinnedTrainingVideo)) {
        return pinnedTrainingVideo
      }
    } catch (_) { /* ignore */ }
    pinnedTrainingVideo = null
  }
  const refVal = trainingVideoEl.value
  if (refVal) {
    if (typeof HTMLVideoElement !== 'undefined' && refVal instanceof HTMLVideoElement) return refVal
    const el = refVal.$el || refVal
    if (typeof HTMLVideoElement !== 'undefined' && el instanceof HTMLVideoElement) return el
    if (el?.querySelector) {
      const nested = el.querySelector('video')
      if (nested) return nested
    }
  }
  if (typeof document !== 'undefined') {
    return document.querySelector('.training-video')
  }
  return null
}

const videoPreloadPool = new Map()
let cachedVideoItemId = null
let cachedVideoUserId = null
let sessionChildUserId = null
let sessionPlanId = null
/** 当前播放器内唯一 video 元素 */
let pinnedTrainingVideo = null
/** 本次打开是否已执行续播 seek */
let videoResumeApplied = false
/** 打开播放器后待 seek 的续播秒数 */
let videoResumePendingSec = 0
/** 程序内 seek（续播）期间不弹「不可快进」 */
let programmaticSeekUntil = 0

function markProgrammaticSeek(ms = 1200) {
  programmaticSeekUntil = Date.now() + ms
}

function isProgrammaticSeek() {
  return Date.now() < programmaticSeekUntil
}

function resetVideoUiClock(initialSec = 0) {
  /* 保留兼容调用，UI 已直接读 currentTime */
}

function getItemWatchProgress(item) {
  if (!item?.id) return {}
  const remote = watchProgressMap.value[item.id] || item.watch_progress || {}
  const watched_sec = Math.max(0, Number(remote.watched_sec) || 0)
  const duration_sec = Math.max(0, Number(remote.duration_sec) || 0)
  const pct = duration_sec > 0
    ? Math.min(100, Math.round(watched_sec / duration_sec * 1000) / 10)
    : Math.max(0, Number(remote.pct) || 0)
  return { ...remote, watched_sec, duration_sec, pct }
}

function getItemResumeSec(item) {
  return Math.max(0, Number(getItemWatchProgress(item).watched_sec) || 0)
}

function clearVideoResumePending() {
  videoResumePendingSec = 0
  videoResumeApplied = false
}

function syncItemWatchProgress(item, wp) {
  if (!item?.id || !wp) return
  watchProgressMap.value = { ...watchProgressMap.value, [item.id]: { ...wp } }
  item.watch_progress = { ...wp }
  const planItem = (todayPlan.value?.items || []).find(i => i.id === item.id)
  if (planItem) planItem.watch_progress = { ...wp }
}

function resetMediaSessionForAccountSwitch() {
  clearVideoRetryTimer()
  watchProgressMap.value = {}
  mediaMaxHeardSec.value = 0
  watchedItemIds.value = new Set()
  videoSrc.value = ''
  activeVideoItemId.value = 0
  cachedVideoItemId = null
  cachedVideoUserId = null
  pinnedTrainingVideo = null
  clearVideoResumePending()
  videoProgressPct.value = 0
  videoTimeLabel.value = '0:00'
  videoDurationLabel.value = '--:--'
  destroyPreloadVideos()
  planMediaPreloaded.value = false
  if (mediaPlayer.value.show) {
    mediaPlayer.value.show = false
    videoPlaying.value = false
    videoLoading.value = false
    videoMetadataReady.value = false
  }
}

function ensureSessionChildUser(uid) {
  if (!uid) return
  if (sessionChildUserId != null && sessionChildUserId !== uid) {
    resetMediaSessionForAccountSwitch()
  }
  sessionChildUserId = uid
}

function ensureSessionPlan(planId) {
  const pid = Number(planId) || 0
  if (!pid) return
  if (sessionPlanId != null && sessionPlanId !== pid) {
    resetMediaSessionForAccountSwitch()
  }
  sessionPlanId = pid
}

function applyVideoResume(el, force = false) {
  if (!el || mediaPlayer.value.type !== 'video') return false
  if (videoResumeApplied && !force) return true
  const resume = videoResumePendingSec > 0
    ? videoResumePendingSec
    : getItemResumeSec(lastOpenedItem.value)
  if (resume <= 0.5) {
    clearVideoResumePending()
    videoResumeApplied = true
    return false
  }
  const dur = Number(el.duration) || 0
  if (dur > 0 && resume >= dur - 1) {
    clearVideoResumePending()
    videoResumeApplied = true
    return false
  }
  const cur = Number(el.currentTime) || 0
  if (!force && cur >= resume - 0.75) {
    clearVideoResumePending()
    videoResumeApplied = true
    return true
  }
  try {
    mediaMaxHeardSec.value = Math.max(mediaMaxHeardSec.value, resume)
    markProgrammaticSeek()
    el.currentTime = resume
    videoResumeApplied = true
    clearVideoResumePending()
    return true
  } catch (_) {
    return false
  }
}

function pinTrainingVideoEl(el) {
  if (!el) return
  const node = el instanceof HTMLVideoElement ? el : (el.querySelector?.('video') || null)
  if (node instanceof HTMLVideoElement) pinnedTrainingVideo = node
}

function clearPinnedTrainingVideo() {
  pinnedTrainingVideo = null
  clearVideoResumePending()
}

function syncVideoUiFromElement(el) {
  if (!el || mediaPlayer.value.type !== 'video') return
  const durationSec = Number(el.duration) || Number(watchProgressMap.value[lastOpenedItem.value?.id]?.duration_sec) || 0
  const cur = Math.max(0, Number(el.currentTime) || 0)
  if (durationSec > 0) {
    videoMetadataReady.value = true
    videoLoading.value = false
    videoDurationLabel.value = formatMediaTime(durationSec)
    videoProgressPct.value = Math.min(100, Math.round(cur / durationSec * 1000) / 10)
  }
  videoTimeLabel.value = formatMediaTime(cur)
  videoPlaying.value = !el.paused && !el.ended
}

function destroyPreloadVideos() {
  for (const el of videoPreloadPool.values()) {
    try {
      el.pause()
      el.removeAttribute('src')
      el.load()
      el.remove()
    } catch (_) { /* ignore */ }
  }
  videoPreloadPool.clear()
  planMediaPreloaded.value = false
}

function preloadTodayPlanMedia(_uid) {
  /* 禁用后台预加载，避免与主播放器争抢带宽导致卡顿 */
  planMediaPreloaded.value = false
}

function applyPreloadedVideoMeta(item) {
  const warmed = item?.id ? videoPreloadPool.get(item.id) : null
  const d = warmed?.duration || Number(watchProgressMap.value[item.id]?.duration_sec || 0)
  if (d > 0) {
    videoDurationLabel.value = formatMediaTime(d)
    videoMetadataReady.value = true
    videoLoading.value = false
  }
}

function activeMediaEl() {
  if (mediaPlayer.value.type === 'audio') return trainingAudio
  return getTrainingVideoDom()
}

function destroyTrainingAudio() {
  if (!trainingAudio) return
  try {
    trainingAudio.pause()
    trainingAudio.removeAttribute('src')
    trainingAudio.load()
  } catch (_) { /* ignore */ }
  trainingAudio = null
}

function ensureTrainingAudio(src) {
  destroyTrainingAudio()
  if (typeof Audio === 'undefined' || !src) return null
  const el = new Audio(src)
  el.preload = 'auto'
  el.playbackRate = 1
  const onTime = () => onMediaTimeUpdate({ target: el })
  const onMeta = () => onMediaLoadedMetadata({ target: el })
  const onSeek = () => onMediaSeeking({ target: el })
  const onRate = () => lockMediaPlaybackRate({ target: el })
  const onPause = () => flushWatchProgress()
  const onEnd = () => onMediaEnded({ target: el })
  el.addEventListener('timeupdate', onTime)
  el.addEventListener('loadedmetadata', onMeta)
  el.addEventListener('seeking', onSeek)
  el.addEventListener('ratechange', onRate)
  el.addEventListener('pause', onPause)
  el.addEventListener('ended', onEnd)
  trainingAudio = el
  return el
}

function hydrateWatchProgressFromPlan(plan) {
  const map = {}
  for (const item of plan?.items || []) {
    if (!item?.id) continue
    if (item.watch_progress && typeof item.watch_progress === 'object') {
      map[item.id] = { ...item.watch_progress }
    }
  }
  watchProgressMap.value = map
}

function lockMediaPlaybackRate(e) {
  const el = e?.target || activeMediaEl()
  if (el && el.playbackRate !== 1) el.playbackRate = 1
}

function clampMediaForward(el, { silent = false } = {}) {
  if (!el) return false
  const t = Number(el.currentTime) || 0
  const max = mediaMaxHeardSec.value
  if (isProgrammaticSeek()) {
    if (t > max) mediaMaxHeardSec.value = t
    return false
  }
  if (t > max + MEDIA_SEEK_EPS) {
    el.currentTime = max
    if (!silent) {
      uni.showToast({ title: '训练音视频不可快进', icon: 'none' })
    }
    return true
  }
  if (t > max) mediaMaxHeardSec.value = t
  return false
}

function onMediaSeeking(e) {
  clampMediaForward(e?.target || activeMediaEl(), { silent: isProgrammaticSeek() })
}

async function flushWatchProgress() {
  const item = lastOpenedItem.value
  if (!item?.id || !itemNeedsListen(item)) return
  const el = activeMediaEl() || pinnedTrainingVideo
  const cached = getItemWatchProgress(item)
  const cachedDur = Number(cached.duration_sec || 0)
  const durationSec = (el && el.duration) ? el.duration : (audioUiDuration.value || cachedDur || 0)
  const finalDur = durationSec > 0 ? durationSec : cachedDur
  if (finalDur <= 0 && mediaMaxHeardSec.value <= 0) return
  const fromEl = el ? (Number(el.currentTime) || 0) : 0
  const watchedSec = finalDur > 0
    ? Math.min(Math.max(mediaMaxHeardSec.value, fromEl), finalDur)
    : Math.max(mediaMaxHeardSec.value, fromEl)
  const pct = finalDur > 0
    ? Math.min(100, Math.round(watchedSec / finalDur * 1000) / 10)
    : Number(cached.pct || 0)
  const wp = { watched_sec: watchedSec, duration_sec: finalDur || cachedDur, pct }
  syncItemWatchProgress(item, wp)
  if (item.video_complete !== undefined) {
    item.video_complete = pct >= WATCH_DONE_PCT
  }
  try {
    const uid = await ensureChildUser()
    const res = await postTrainingWatchProgress(uid, item.id, {
      watched_sec: watchedSec,
      duration_sec: finalDur > 0 ? finalDur : undefined,
    })
    if (res?.watch_progress) {
      syncItemWatchProgress(item, res.watch_progress)
    }
    if (res?.video_complete != null && lastOpenedItem.value?.id === item.id) {
      lastOpenedItem.value = { ...lastOpenedItem.value, video_complete: res.video_complete }
      const planItem = (todayPlan.value?.items || []).find(i => i.id === item.id)
      if (planItem) planItem.video_complete = res.video_complete
    }
  } catch (_) { /* ignore */ }
}

function onMediaLoadedMetadata(e) {
  const el = e?.target || activeMediaEl()
  if (!el || !lastOpenedItem.value?.id) return
  lockMediaPlaybackRate({ target: el })
  if (el instanceof HTMLVideoElement) pinTrainingVideoEl(el)
  const resume = getItemResumeSec(lastOpenedItem.value)
  mediaMaxHeardSec.value = Math.max(mediaMaxHeardSec.value, resume)
  if (mediaPlayer.value.type === 'video') {
    applyVideoResume(el)
  } else if (resume > 0 && resume < (el.duration || Infinity) && (el.currentTime || 0) < resume) {
    try {
      mediaMaxHeardSec.value = Math.max(mediaMaxHeardSec.value, resume)
      markProgrammaticSeek()
      el.currentTime = resume
    } catch (_) { /* ignore */ }
  }
  if (mediaPlayer.value.type === 'audio') {
    audioUiDuration.value = el.duration || 0
    audioUiSec.value = el.currentTime || resume || 0
  }
  if (mediaPlayer.value.type === 'video') {
    syncMediaUiFromElement(el)
  }
  flushWatchProgress()
}

function syncMediaUiFromElement(el, opts = {}) {
  const item = lastOpenedItem.value
  if (!el || !item?.id) return
  if (!opts.skipClamp && clampMediaForward(el)) return
  lockMediaPlaybackRate({ target: el })
  const durationSec = el.duration || Number(watchProgressMap.value[item.id]?.duration_sec || 0) || 0
  if (durationSec > 0) {
    videoMetadataReady.value = true
    videoLoading.value = false
  }
  const rawCur = Number(el.currentTime) || 0
  if (rawCur > mediaMaxHeardSec.value) mediaMaxHeardSec.value = rawCur
  const watchedSec = mediaMaxHeardSec.value

  if (mediaPlayer.value.type === 'audio') {
    audioUiDuration.value = durationSec
    audioUiSec.value = rawCur
    audioPlaying.value = !el.paused && !el.ended
  }
  if (mediaPlayer.value.type === 'video') {
    syncVideoUiFromElement(el)
  }

  if (durationSec <= 0) return
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

function onMediaTimeUpdate(e) {
  const el = e?.target
  if (el instanceof HTMLVideoElement) pinTrainingVideoEl(el)
  syncMediaUiFromElement(el || activeMediaEl())
}

function onVideoLoadedData(e) {
  const el = e?.target
  if (!el || mediaPlayer.value.type !== 'video') return
  pinTrainingVideoEl(el)
  applyVideoResume(el)
  syncMediaUiFromElement(el)
}

function onVideoDurationChange(e) {
  const el = e?.target
  if (!el || mediaPlayer.value.type !== 'video') return
  if (el instanceof HTMLVideoElement) pinTrainingVideoEl(el)
  const d = el.duration || 0
  if (d > 0) {
    videoDurationLabel.value = formatMediaTime(d)
    videoMetadataReady.value = true
    videoLoading.value = false
  }
}

function onMediaEnded(e) {
  const el = e?.target || activeMediaEl()
  if (el?.duration) mediaMaxHeardSec.value = Math.max(mediaMaxHeardSec.value, el.duration)
  audioPlaying.value = false
  videoPlaying.value = false
  videoLoading.value = false
  flushWatchProgress()
}

function onVideoWaiting() {
  videoLoading.value = true
}

function onVideoCanPlay() {
  videoLoading.value = false
  videoMetadataReady.value = true
  videoLoadAttempt.value = 0
  clearVideoRetryTimer()
  const el = getTrainingVideoDom()
  if (el) syncMediaUiFromElement(el)
}

function onVideoPlaying() {
  videoPlaying.value = true
  videoLoading.value = false
  videoMetadataReady.value = true
  const el = getTrainingVideoDom()
  if (el) syncMediaUiFromElement(el)
}

function onVideoPause() {
  videoPlaying.value = false
  flushWatchProgress()
}

async function toggleMediaPlay() {
  if (mediaPlayer.value.type === 'audio') return toggleAudioPlay()
  return toggleVideoPlay()
}

async function toggleVideoPlay() {
  const el = getTrainingVideoDom()
  if (!el) {
    uni.showToast({ title: '视频仍在加载，请稍候', icon: 'none' })
    return
  }
  lockMediaPlaybackRate({ target: el })
  try {
    if (el.paused) {
      videoLoading.value = true
      await el.play()
      videoPlaying.value = true
      videoMetadataReady.value = true
      syncMediaUiFromElement(el)
    } else {
      el.pause()
      videoPlaying.value = false
      syncMediaUiFromElement(el)
      flushWatchProgress()
    }
  } catch (_) {
    videoPlaying.value = false
    uni.showToast({ title: '播放失败，请稍候再试', icon: 'none', duration: 2500 })
  } finally {
    videoLoading.value = false
  }
}

function prepareVideoAfterOpen(el) {
  if (!el) return
  pinTrainingVideoEl(el)
  applyVideoResume(el)
  syncMediaUiFromElement(el)
}

async function toggleAudioPlay() {
  const el = trainingAudio
  if (!el) return
  lockMediaPlaybackRate({ target: el })
  try {
    if (el.paused) {
      await el.play()
      audioPlaying.value = true
    } else {
      el.pause()
      audioPlaying.value = false
      flushWatchProgress()
    }
  } catch (_) {
    uni.showToast({ title: '音频播放失败', icon: 'none' })
  }
}

function rewindAudioTen() {
  const el = trainingAudio
  if (!el) return
  const next = Math.max(0, (el.currentTime || 0) - 10)
  el.currentTime = next
  audioUiSec.value = next
  // 不降低 mediaMaxHeardSec，避免用回退刷进度
}

function canPhaseCheckin(phase) {
  if (!phase.unlocked) return false
  if (devMode.value) return true
  if (scheduleLoading.value || entryLoading.value || planJustGenerated.value) return false
  if (isGlobalCutoff.value) return false
  if (phase.allDone || phaseRecordIds.value[phase.block]) return true
  if (timerPhase.value === 'setup') return false
  if (!isPhaseListenDone(phase)) return false
  return true
}

function phaseHasCheckin(phase) {
  return !!(phase.allDone || phaseRecordIds.value[phase.block])
}

function phaseCheckinLockText(phase) {
  if (!phase.unlocked) {
    const idx = planPhases.value.findIndex(p => p.block === phase.block)
    const prev = idx > 0 ? planPhases.value[idx - 1]?.block : ''
    return prev ? `请先完成训练 ${prev} 打卡` : '待解锁'
  }
  if (phaseHasCheckin(phase)) return checkinLockText.value
  if (timerPhase.value === 'setup') return '请先选择时长并开始训练'
  if (timerPhase.value === 'expired') return '时长已到，仍可填写打卡'
  return checkinLockText.value
}

function itemStepHint(item, phase) {
  if (!phase.unlocked) {
    const idx = planPhases.value.findIndex(p => p.block === phase.block)
    const prev = idx > 0 ? planPhases.value[idx - 1]?.block : ''
    return prev ? `🔒 完成训练 ${prev} 打卡后解锁` : '🔒 待解锁'
  }
  if (isMediaLocked.value && (timerPhase.value === 'expired' || isMediaExhausted.value)) return '🔒 时长已到'
  if (item.media_hidden) return '🔒 时长已到'
  if (item.item_type === 'placeholder') return '📝 实操打卡'
  if (item.item_type === 'perception' || (item.title || '').includes('多元感知')) {
    if (item.audio_url) return `▶ 点击听多元感知 · 约 ${item.duration_min || '?'} 分钟`
    return '📝 多元感知待同步，可先打卡'
  }
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
  if (phase.allDone) return ''
  return `训练 ${phase.block}`
}

function scrollToPhase(block) {
  const body = document.querySelector('.body')
  const target = document.getElementById(`phase-block-${block}`)
  if (!body || !target) return
  const bodyTop = body.getBoundingClientRect().top
  const targetTop = target.getBoundingClientRect().top
  body.scrollTo({ top: body.scrollTop + targetTop - bodyTop - 12, behavior: 'smooth' })
}

async function openPhaseMediaItem(item, phase, forceType) {
  if (!item) return
  if (!phase.unlocked && !devMode.value) {
    const idx = planPhases.value.findIndex(p => p.block === phase.block)
    const prev = idx > 0 ? planPhases.value[idx - 1]?.block : ''
    uni.showToast({ title: prev ? `请先完成训练 ${prev} 打卡` : '本阶段尚未解锁', icon: 'none' })
    return
  }

  // 多元感知：首次点击自动完成，完成后可回听不重复提交
  if (isPerceptionPhase(phase)) {
    phaseClicked.value = { ...phaseClicked.value, [phase.block]: true }
    if (!phase.allDone) {
      await autoCompletePerception(phase)
    }
    openMediaItem(item, forceType)
    return
  }

  openMediaItem(item, forceType)
}
const pickerCards = ref([])
const allowedAbility = ref('')
const sparkAbi = ref(-1)
const abilities = TRAINING_ABILITIES

function hasPickerCard(name) { return pickerCards.value.some(c => c.name === name) }

function newCard(name) {
  const base = { name, time: '', content: '', result: '', tag: '', count: '', accuracy: '', note: '', files: [] }
  if (name === '超脑阅读') {
    return { ...base, time: '', wordCount: '' }
  }
  if (name === '扫描速记') {
    return { ...base, materialType: '书', materialName: '', wordCount: '', forwardTime: '', forwardAcc: '', backwardTime: '', backwardAcc: '' }
  }
  if (name === '影像追忆') {
    return { ...base, time: '', wordCount: '', tool: '书本' }
  }
  return base
}

// ── 必填字段定义 ──
const CARD_REQUIRED = {
  '超脑阅读': { time: '训练时长', wordCount: '完成字数' },
  '影像追忆': { time: '训练时长', wordCount: '完成字数', content: '训练材料', accuracy: '追忆率' },
  '扫描速记': { time: '训练用时', wordCount: '记住字数', materialName: '材料名称' },
  '极速运算': { time: '训练时长', count: '完成题数', accuracy: '正确率' },
}
/** 字/分钟软上限：仅提醒，不改达标算法 */
const WORD_SPEED_SOFT_LIMIT = 800
const WORD_SPEED_SKILLS = new Set(['超脑阅读', '影像追忆', '扫描速记'])

function findAbnormalWordSpeedCards(cards) {
  const names = []
  for (const c of cards || []) {
    if (!WORD_SPEED_SKILLS.has(c.name)) continue
    const t = Number(c.time)
    const w = Number(c.wordCount)
    if (!(t > 0) || !(w > 0)) continue
    if (w / t > WORD_SPEED_SOFT_LIMIT) names.push(c.name)
  }
  return names
}

function getRequired(cardName) { return CARD_REQUIRED[cardName] || { time: '训练时长', wordCount: '完成字数' } }
function isRequired(cardName, field) { return field in (CARD_REQUIRED[cardName] || { time: 1, wordCount: 1 }) }
function missingFields(card) {
  const required = getRequired(card.name)
  const missing = []
  for (const [field, label] of Object.entries(required)) {
    const val = card[field]
    if (val === undefined || val === null || val === '' || (typeof val === 'number' && isNaN(val))) {
      missing.push(label)
    }
  }
  return missing
}

function togglePickerCard(name, abi) {
  if (allowedAbility.value && name !== allowedAbility.value) return
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
  const wordCountSkills = new Set(['超脑阅读', '影像追忆', '扫描速记'])
  return list.map(c => {
    const wordCount = c.wordCount
    const content = c.content || (wordCountSkills.has(c.name) && wordCount != null && wordCount !== ''
      ? String(wordCount)
      : c.content)
    return {
      name: c.name,
      time: c.time,
      content,
      result: c.result,
      tag: c.tag,
      count: c.count,
      accuracy: c.accuracy,
      note: c.note,
      wordCount,
      materialType: c.materialType,
      materialName: c.materialName,
      forwardTime: c.forwardTime,
      forwardAcc: c.forwardAcc,
      backwardTime: c.backwardTime,
      backwardAcc: c.backwardAcc,
      tool: c.tool,
      phaseBlock: c.phaseBlock,
      reverseRecite: c.reverseRecite || false,     // 🆕 v2.0
      completed: c.completed || false,              // 🆕 v2.0
      fileNames: (c.files || []).map(f => f.name),
    }
  })
}

function markPhaseDoneLocally(block) {
  for (const item of getPhaseItems(block)) {
    item.checkin_status = 'done'
  }
}

function cardsForBlock(block) {
  return submittedCards.value.filter(c => c.phaseBlock === block)
}

async function loadTodayCheckinRecords(uid, _planId) {
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

function applyCheckinProgress(res) {
  const tp = res?.training_progress
  if (!tp) return
  // 🆕 v2.0: per-skill tier results
  if (tp.overall_tier != null) overallTier.value = tp.overall_tier
  const sr = tp.skill_results
  if (sr) {
    skillTierProgress.value = sr
    for (const [skill, result] of Object.entries(sr)) {
      // 仅在第 3 次尝试（小晋级考核）时触发通知
      if (!result.was_deciding) continue
      if (result.tier_advanced) {
        uni.showToast({
          title: `🎉 ${skill} 晋级成功！`,
          icon: 'none',
          duration: 3000,
        })
      } else if (!result.passed) {
        uni.showToast({
          title: `😔 ${skill} 差一点就晋级了，明天继续加油！`,
          icon: 'none',
          duration: 3000,
        })
      }
    }
  }
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
    applyCheckinProgress(res)
    return res
  }

  const res = await updateTrainingCheckin(uid, recordId, payload)
  if (todayPlan.value && res.plan_status) todayPlan.value.status = res.plan_status
  markPhaseDoneLocally(block)
  applyCheckinProgress(res)
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

function detectAbilitiesForBlock(block) {
  const found = []
  const seen = new Set()
  for (const item of getPhaseItems(block)) {
    const skill = resolvePlanItemSkill(item, abilities)
    if (skill && !seen.has(skill)) {
      seen.add(skill)
      found.push(skill)
    }
  }
  return found
}

function autoDetectAbilities(block) {
  const detected = detectAbilitiesForBlock(block)
  if (!detected.length) return
  let sparkIdx = -1
  for (const ability of detected) {
    if (hasPickerCard(ability)) continue
    const card = newCard(ability)
    pickerCards.value.push(card)
    if (sparkIdx < 0) sparkIdx = abilities.indexOf(ability)
  }
  if (sparkIdx >= 0) {
    sparkAbi.value = sparkIdx
    setTimeout(() => { sparkAbi.value = -1 }, 1500)
  }
}

function openPicker(block) {
  if (!guardCheckin(block)) return
  const phase = planPhases.value.find(p => p.block === block)
  if (!phase) return
  if (!phase.unlocked) {
    const idx = planPhases.value.indexOf(phase)
    const prev = idx > 0 ? planPhases.value[idx - 1]?.block : ''
    uni.showToast({ title: prev ? `请先完成训练 ${prev} 打卡` : '本阶段尚未解锁', icon: 'none' })
    return
  }
  if (!isPhaseListenDone(phase)) {
    uni.showToast({ title: `请先听完/看完音视频（约 ${WATCH_DONE_PCT}%）`, icon: 'none' })
    return
  }
  allowedAbility.value = phase.skillName || ''
  activePickerBlock.value = block
  const isEdit = phase.allDone && phaseRecordIds.value[block]
  if (isEdit) {
    const existing = cardsForBlock(block)
    pickerCards.value = existing.length
      ? existing.map(c => ({ ...c, files: c.files ? [...c.files] : [] }))
      : []
  } else {
    pickerCards.value = []
    autoDetectAbilities(block)
  }
  showPicker.value = true
}

function closePicker() {
  showPicker.value = false
  activePickerBlock.value = null
  pickerCards.value = []
  pendingSubmitBlock.value = null
  allowedAbility.value = ''
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
  if (!guardCheckin(activePickerBlock.value)) return
  const block = activePickerBlock.value
  if (!block || !todayPlan.value?.plan_id) {
    uni.showToast({ title: '训练方案未加载，请稍后重试', icon: 'none' })
    return
  }

  // 校验必填字段
  for (const card of pickerCards.value) {
    const missing = missingFields(card)
    if (missing.length) {
      uni.showToast({ title: card.name + '的「' + missing.join('、') + '」为必填', icon: 'none', duration: 2500 })
      return
    }
  }

  // 校验正确率不超过 100
  for (let ci = 0; ci < pickerCards.value.length; ci++) {
    const card = pickerCards.value[ci]
    const accFields = [
      { key: 'accuracy', val: card.accuracy },
      { key: 'forwardAcc', val: card.forwardAcc },
      { key: 'backwardAcc', val: card.backwardAcc },
    ]
    for (const f of accFields) {
      const v = parseFloat(f.val)
      if (!isNaN(v) && v > 100) {
        accErrorCards.value[ci] = (accErrorCards.value[ci] || {})
        accErrorCards.value[ci][f.key] = true
        uni.showToast({ title: '数据填写有误，请重新填写', icon: 'none', duration: 2500 })
        setTimeout(() => { accErrorCards.value = {} }, 3000)
        return
      }
    }
  }

  const hasContent = pickerCards.value.some(c => c.time || c.content || c.result || c.count || c.tag || c.wordCount || c.materialName)
  if (!hasContent) {
    uni.showToast({ title: '请先填写训练记录再提交', icon: 'none', duration: 2000 })
    return
  }

  const speedNames = findAbnormalWordSpeedCards(pickerCards.value)
  if (speedNames.length) {
    uni.showModal({
      title: '确认训练数据',
      content: speedNames.join('、') + ' 填写的字数相对用时偏高，确认是本次真实练习量吗？',
      confirmText: '确认提交',
      cancelText: '再改改',
      success: (res) => {
        if (res.confirm) {
          pendingSubmitBlock.value = block
          showSubmitConfirm.value = true
        }
      },
    })
    return
  }

  // 提交前确认
  pendingSubmitBlock.value = block
  showSubmitConfirm.value = true
}

async function confirmSubmit() {
  if (checkinSubmitting.value) return
  const block = pendingSubmitBlock.value
  if (!block) return
  if (!guardCheckin(block)) return
  showSubmitConfirm.value = false
  checkinSubmitting.value = true
  try {
    const cardsList = pickerCards.value.map(function(c) {
      const data = { ...c, phaseBlock: block }
      delete data._editIndex
      return data
    })
    await persistPhaseCheckin(block, cardsList)
    const uid = await ensureChildUser()
    await loadTodayCheckinRecords(uid, todayPlan.value.plan_id)
    closePicker()
    await nextTick(function() { syncPhaseExpand() })
    loadTodayPlan(true)
    uni.showToast({ title: '训练 ' + block + ' 打卡成功！', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '打卡提交失败', icon: 'none', duration: 2500 })
  } finally {
    checkinSubmitting.value = false
    pendingSubmitBlock.value = null
  }
}

function getCardSummary(c) {
  const prefix = c.phaseBlock ? `[${c.phaseBlock}] ` : ''
  if (c.name === '极速运算') return prefix + c.name + '(' + (c.tag || '运算') + ',' + c.time + '分钟,' + c.count + '题,' + c.accuracy + '%)'
  if (c.name === '影像追忆') {
    const parts = ['工具' + (c.tool || '豆包')]
    if (c.time) parts.push(c.time + '分钟')
    if (c.wordCount) parts.push('看完' + c.wordCount + '字')
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

const showCardDetail = ref(false)
const detailCardIndex = ref(-1)
const detailEditing = ref(false)
const detailEditCard = ref(null)

const activeDetailCard = computed(() => {
  if (detailEditing.value && detailEditCard.value) return detailEditCard.value
  if (detailCardIndex.value < 0) return null
  return submittedCards.value[detailCardIndex.value] || null
})

const easingSmooth = 'cubic-bezier(0.23,1,0.32,1)'

function editCard(idx) {
  detailCardIndex.value = idx
  detailEditing.value = false
  detailEditCard.value = null
  showCardDetail.value = true
}

function closeCardDetail() {
  showCardDetail.value = false
  detailEditing.value = false
  detailEditCard.value = null
}

function startDetailEdit() {
  const c = submittedCards.value[detailCardIndex.value]
  if (!c || !guardCheckin(c.phaseBlock || 'A')) return
  detailEditCard.value = { ...c, files: c.files ? [...c.files] : [] }
  detailEditing.value = true
}

function cancelDetailEdit() {
  detailEditing.value = false
  detailEditCard.value = null
}

async function saveDetailEdit() {
  const idx = detailCardIndex.value
  const card = detailEditCard.value
  if (!card || idx < 0) return
  const block = card.phaseBlock || 'A'
  if (!guardCheckin(block)) return
  const hasContent = card.time || card.content || card.result || card.count || card.tag || card.wordCount || card.materialName
  if (!hasContent) {
    uni.showToast({ title: '请填写训练记录', icon: 'none' })
    return
  }
  checkinSubmitting.value = true
  try {
    submittedCards.value[idx] = { ...card, files: card.files || [] }
    await persistPhaseCheckin(block, cardsForBlock(block))
    const uid = await ensureChildUser()
    await loadTodayCheckinRecords(uid, todayPlan.value?.plan_id)
    detailEditing.value = false
    detailEditCard.value = null
    uni.showToast({ title: '已保存', icon: 'none' })
  } catch (e) {
        uni.showToast({ title: e.message || '保存失败', icon: 'none', duration: 2500 })
  } finally {
        checkinSubmitting.value = false
  }
}

function cardDetailFields(c) {
  const map = {}
  if (!c) return map
  if (c.time) map['训练时长'] = c.time + ' 分钟'
  if (c.content) map['内容'] = c.content
  if (c.result) map['结果'] = c.result
  if (c.tag) map['类型'] = c.tag
  if (c.count) map['题数'] = c.count + ' 题'
  if (c.accuracy) map[c.name === '影像追忆' ? '追忆率' : '正确率'] = c.accuracy + '%'
  if (c.tool) map['工具'] = c.tool
  if (c.materialType) map['材料类型'] = c.materialType
  if (c.materialName) map['材料名称'] = c.materialName
  if (c.wordCount) {
    const wcLabel = c.name === '扫描速记' ? '记住字数' : '完成字数'
    map[wcLabel] = c.wordCount + ' 字'
  }
  if (c.forwardTime || c.forwardAcc) map['正背'] = (c.forwardTime || '?') + '/' + (c.forwardAcc || '?')
  if (c.backwardTime || c.backwardAcc) map['倒背'] = (c.backwardTime || '?') + '/' + (c.backwardAcc || '?')
  if (c.note) map['备注'] = c.note
  return map
}

function confirmDeleteCard(idx) {
  const c = submittedCards.value[idx]
  if (!c) return
  if (!guardCheckin(c.phaseBlock || 'A')) return
  deleteTargetIdx.value = idx
  deleteTargetName.value = c.name || ('训练' + (c.phaseBlock || 'A'))
  showDeleteConfirm.value = true
}

function cancelDeleteConfirm() {
  showDeleteConfirm.value = false
  deleteTargetIdx.value = -1
  deleteTargetName.value = ''
}

async function confirmDelete() {
  showDeleteConfirm.value = false
  closeCardDetail()
  const idx = deleteTargetIdx.value
  deleteTargetIdx.value = -1
  deleteTargetName.value = ''
  if (idx < 0) return
  await deleteCard(idx)
}

async function deleteCard(idx) {
  const c = submittedCards.value[idx]
  const block = c.phaseBlock || 'A'
  const remaining = submittedCards.value.filter((_, i) => i !== idx && (_.phaseBlock || 'A') === block)
  checkinSubmitting.value = true
  try {
    if (!remaining.length) {
      await deletePhaseCheckin(block)
    } else {
      await persistPhaseCheckin(block, remaining)
    }
    const uid = await ensureChildUser()
    await loadTodayCheckinRecords(uid, todayPlan.value?.plan_id)
    // 删除后重新加载方案，确保 item 状态与后端对齐
    await loadTodayPlan(true)
    if (!submittedCards.value.length) closeCardDetail()
    nextTick(() => syncPhaseExpand())
    uni.showToast({ title: '已删除', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '删除失败', icon: 'none', duration: 2500 })
  } finally {
    checkinSubmitting.value = false
  }
}

function clearVideoRetryTimer() {
  if (videoRetryTimer) {
    clearTimeout(videoRetryTimer)
    videoRetryTimer = null
  }
}

function buildVideoStreamSrc(rawUrl, uid, attempt = 0) {
  let url = resolveTrainingStreamUrl(rawUrl, uid)
  if (!url) return url
  if (attempt > 0) {
    const sep = url.includes('?') ? '&' : '?'
    url = `${url}${sep}_retry=${attempt}&_t=${Date.now()}`
  }
  return url
}

function reloadTrainingVideo(item, uid) {
  videoLoading.value = true
  videoMetadataReady.value = false
  videoResumeApplied = false
  videoSrc.value = buildVideoStreamSrc(item.video_url, uid, videoLoadAttempt.value)
  nextTick(() => {
    const el = getTrainingVideoDom()
    if (el) {
      pinTrainingVideoEl(el)
      try { el.load() } catch (_) { /* ignore */ }
    }
    prepareVideoAfterOpen(getTrainingVideoDom())
  })
}

function onTrainingVideoError() {
  const item = lastOpenedItem.value
  const uid = getChildUserId()
  if (item?.video_url && uid && videoLoadAttempt.value < VIDEO_LOAD_MAX_RETRIES) {
    videoLoadAttempt.value += 1
    videoLoading.value = true
    videoMetadataReady.value = false
    clearVideoRetryTimer()
    videoRetryTimer = setTimeout(() => reloadTrainingVideo(item, uid), 700 * videoLoadAttempt.value)
    return
  }
  clearVideoRetryTimer()
  videoLoading.value = false
  videoPlaying.value = false
  videoMetadataReady.value = false
  console.error('[training] video load failed:', videoSrc.value)
  uni.showToast({ title: '视频加载失败，请关闭后重试或刷新页面', icon: 'none', duration: 3000 })
}

function applyPlanMedia(plan) {
  const uid = getChildUserId()
  const items = plan?.items || []
  const sorted = [...items].sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
  const firstAudio = sorted.find(i => i.audio_url)
  if (firstAudio) {
    audioSrc.value = resolveTrainingStreamUrl(firstAudio.audio_url, uid)
    audioTitle.value = `🎧 ${firstAudio.title || '今日训练音频'}`
  }
}

async function openMediaItem(item, forceType) {
  if (!item) return
  if (item.media_hidden || item.item_type === 'placeholder') {
    if (item.item_type === 'perception' && item.audio_url) {
      // 多元感知有音频时允许播放
    } else {
      uni.showToast({ title: '该项请直接打卡，无音视频', icon: 'none' })
      return
    }
  }
  if (!item.video_url && !item.audio_url) {
    uni.showToast({ title: '暂无音视频，请直接打卡', icon: 'none' })
    return
  }
  if (!guardMedia()) return
  lastOpenedItem.value = item
  let uid = getChildUserId()
  if (!uid) {
    try {
      uid = await ensureChildUser()
    } catch (_) {
      return
    }
  }
  const wp = getItemWatchProgress(item)
  mediaMaxHeardSec.value = Number(wp.watched_sec || 0)
  audioPlaying.value = false
  videoPlaying.value = false
  audioUiSec.value = mediaMaxHeardSec.value
  audioUiDuration.value = Number(wp.duration_sec || 0)

  const openVideo = () => {
    const resumeSec = Number(wp.watched_sec || 0)
    const durSec = Number(wp.duration_sec || 0)
    videoResumePendingSec = resumeSec
    videoResumeApplied = false
    videoLoading.value = true
    videoMetadataReady.value = false
    videoLoadAttempt.value = 0
    clearVideoRetryTimer()
    applyPreloadedVideoMeta(item)
    mediaPlayer.value = { show: true, type: 'video', title: item.title || '训练视频' }

    cachedVideoItemId = item.id
    cachedVideoUserId = uid
    activeVideoItemId.value = item.id
    videoProgressPct.value = 0
    videoTimeLabel.value = '0:00'
    videoDurationLabel.value = durSec > 0 ? formatMediaTime(durSec) : '--:--'
    videoSrc.value = buildVideoStreamSrc(item.video_url, uid, 0)
    nextTick(() => prepareVideoAfterOpen(getTrainingVideoDom()))
  }
  const openAudio = () => {
    const streamUrl = resolveTrainingStreamUrl(item.audio_url, uid)
    audioSrc.value = streamUrl
    audioTitle.value = item.title || '训练音频'
    mediaPlayer.value = { show: true, type: 'audio', title: audioTitle.value }
    const el = ensureTrainingAudio(streamUrl)
    if (!el) {
      uni.showToast({ title: '当前环境无法播放音频', icon: 'none' })
      return
    }
    try {
      if (mediaMaxHeardSec.value > 0) el.currentTime = mediaMaxHeardSec.value
      el.playbackRate = 1
      el.play().then(() => { audioPlaying.value = true }).catch(() => {})
    } catch (_) { /* ignore */ }
  }

  if (forceType === 'video' && item.video_url) return openVideo()
  if (forceType === 'audio' && item.audio_url) return openAudio()
  if (item.video_url) return openVideo()
  if (item.audio_url) return openAudio()
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
async function closeMedia() {
  if (watchProgressSaveTimer) {
    clearTimeout(watchProgressSaveTimer)
    watchProgressSaveTimer = null
  }
  clearVideoRetryTimer()
  const item = lastOpenedItem.value
  if (item?.id && itemNeedsListen(item)) {
    const el = pinnedTrainingVideo || activeMediaEl()
    if (el) {
      const t = Number(el.currentTime) || 0
      if (t > mediaMaxHeardSec.value) mediaMaxHeardSec.value = t
      syncMediaUiFromElement(el, { skipClamp: true })
    }
    await flushWatchProgress()
    if (isItemListenDone(item)) {
      watchedItemIds.value.add(item.id)
      watchedItemIds.value = new Set(watchedItemIds.value)
    }
  }
  try { trainingAudio?.pause() } catch (_) { /* ignore */ }
  try {
    const el = pinnedTrainingVideo || getTrainingVideoDom()
    el?.pause()
  } catch (_) { /* ignore */ }
  destroyTrainingAudio()
  pinnedTrainingVideo = null
  videoResumeApplied = false
  clearVideoResumePending()
  videoLoadAttempt.value = 0
  audioPlaying.value = false
  videoPlaying.value = false
  videoLoading.value = false
  videoMetadataReady.value = false
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
    const talent = await ensureTalentState(uid)
    if (hasEffectiveTalent(talent) && !talent.needs_assessment) {
      needAssessment.value = false
      showAssessmentModal.value = false
      applyTalentLabelFromTag(talent.talent_tag)
      try {
        const entry = await fetchTrainingEntry(uid)
        applyServerTimeMeta(entry)
        agentScheduleEnabled.value = !!entry.agent_schedule_enabled
      } catch (_) { /* 开关失败不影响进页 */ }
      return true
    }
    const entry = await fetchTrainingEntry(uid)
    applyServerTimeMeta(entry)
    agentScheduleEnabled.value = !!entry.agent_schedule_enabled
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
    try {
      const talent = await ensureTalentState(uid)
      if (hasEffectiveTalent(talent) && !talent.needs_assessment) {
        needAssessment.value = false
        showAssessmentModal.value = false
        applyTalentLabelFromTag(talent.talent_tag)
        return true
      }
    } catch (_) { /* ignore */ }
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

const todayPlanLoading = ref(false)

async function loadTodayPlan(silent = true) {
  if (todayPlanLoading.value) return
  todayPlanLoading.value = true
  entryLoading.value = !silent
  needAssessment.value = false
  try {
    const uid = await ensureChildUser()
    ensureSessionChildUser(uid)

    // 提前启动 progress 请求，与主流程并行
    const progressPromise = !talentLabel.value
      ? fetchTrainingProgress(uid).catch(() => null)
      : Promise.resolve(null)

    const entryOk = await checkTrainingEntry(uid)
    if (!entryOk) {
      aiPlanText.value = ''
      audioSrc.value = ''
      audioTitle.value = '🎧 训练用音频'
      todayPlan.value = null
      entryLoading.value = false
      return
    }

    const result = await fetchTrainingToday(uid, { skipAi: true })
    if (result.error === 'assessment') {
      // entry 已确认有天赋，today 403 可能是并发/缓存问题，不弹窗
      uni.showToast({ title: result.message || '方案加载中，请稍后', icon: 'none' })
      entryLoading.value = false
      return
    }
    if (result.error) throw new Error(result.message)

    todayPlan.value = result.data
    applyServerTimeMeta(result.data)
    ensureSessionPlan(result.data.plan_id)
    applyTimerFromServer(result.data)
    restoreTrainingVisibility(result.data)

    if (result.data.status === 'transition' || !result.data.plan_id) {
      resetAllLocalState()
      todayPlan.value = result.data.plan_id ? result.data : { ...result.data, items: [] }
      aiPlanText.value = result.data.report_text || (result.data.status === 'transition' ? '训练日切换中' : '')
      audioSrc.value = ''
      audioTitle.value = '🎧 训练用音频'
      videoSrc.value = ''
      entryLoading.value = false
      return
    }

    if (!silent) {
      submittedCards.value = []
      phaseRecordIds.value = {}
      primaryCheckinRecordId.value = null
      summaryAttitude.value = 60
      attitudeTouched.value = false
    }
    syncPlanMetaFromApi(result.data)
    aiPlanText.value = result.data.report_text || ''
    applyPlanMedia(result.data)
    hydrateWatchProgressFromPlan(result.data)

    syncPickersAfterTimerRestore(result.data.planned_minutes)

    if (
      result.data.timer_phase === 'setup'
      && result.data.items?.length
      && !result.data.items.some(
        i => i.checkin_status === 'done' || Number(i.watch_progress?.pct || 0) > 0
      )
    ) {
      planJustGenerated.value = true
    }

    // checkin records + progress 并行等待
    const [progress] = await Promise.all([
      progressPromise,
      loadTodayCheckinRecords(uid, result.data.plan_id),
    ])
    nextTick(() => syncPhaseExpand())

    if (progress && !talentLabel.value) {
      applyTalentLabelFromTag(progress?.talent_tag)
    }

    if (devMode.value) await loadDevStatus()

    if (result.data.plan_id && result.data.items?.length) {
      refreshAiPlanInBackground(uid)
    }

    if (result.data.timer_phase === 'running' && result.data.items?.length) {
      preloadTodayPlanMedia(uid)
    }
  } catch (e) {
    uni.showToast({ title: e.message || '加载今日方案失败', icon: 'none', duration: 2500 })
  } finally {
    entryLoading.value = false
    todayPlanLoading.value = false
  }
}

function goTalent() {
  uni.navigateTo({ url: '/pages/talent/index' })
}

let idleGuideTimer = null

onMounted(async () => {
  const auth = await requirePageAuth('student')
  if (!auth) return
  // App.vue 已做系统偏好+硬件检测；此处补 FPS 实测捕获弱 GPU 边缘机型
  if (!document.documentElement.hasAttribute('data-reduced-motion')) {
    try {
      const fps = await new Promise<number>(resolve => {
        let frames = 0
        const start = performance.now()
        function tick() {
          frames++
          if (performance.now() - start < 500) {
            requestAnimationFrame(tick)
          } else {
            resolve(Math.round(frames / ((performance.now() - start) / 1000)))
          }
        }
        requestAnimationFrame(tick)
      })
      if (fps < 30) document.documentElement.setAttribute('data-reduced-motion', '')
    } catch (_) {}
  }
  await loadTodayPlan()
  startDayUnlockWatch()
  if (devMode.value) loadDevStatus()
  idleGuideTimer = setTimeout(() => {
    if (timerPhase.value === 'setup' && selectedHours.value === 0 && selectedMinutes.value === 0) {
      showGuideArrow.value = true
      redAlertActive.value = false
      nextTick(() => { redAlertActive.value = true })
    }
  }, 5000)
})
onShow(async () => {
  const uid = getChildUserId()
  if (uid) ensureSessionChildUser(uid)
  resumeTimerFromStorage()
  await loadTodayPlan(true)
})
onHide(() => {
  clearTimerTick()
})
onUnmounted(() => {
  clearTimerTick()
  clearDayUnlockWatch()
  clearVideoRetryTimer()
  destroyPreloadVideos()
  cachedVideoItemId = null
  cachedVideoUserId = null
  sessionChildUserId = null
  sessionPlanId = null
  if (idleGuideTimer) clearTimeout(idleGuideTimer)
  destroyTrainingAudio()
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
.app { height:100vh;height:100dvh; max-width:var(--app-max-width, 480px); margin:0 auto; background:#0b111e; font-family:PingFang SC,Roboto,sans-serif; display:flex; flex-direction:column; position:relative; overflow:hidden; }
.nav { display:flex; align-items:center; padding:28rpx 28rpx 0; position:relative; z-index:1001; }
.nav-actions { display:flex; align-items:center; gap:6px; margin-left:auto; }
.nav-back { width:36px; height:36px; border-radius:50%; background:rgba(0,210,255,0.08); border:1px solid rgba(0,210,255,0.2); display:flex; align-items:center; justify-content:center; cursor:pointer; }
.nav-title { flex:1; text-align:center; color:#fff; font-size:16px; font-weight:600; }
.nav-dev { min-width:36px; height:28px; padding:0 8px; border-radius:999px; background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.12); display:flex; align-items:center; justify-content:center; cursor:pointer; }
.nav-history { min-width:36px; height:28px; padding:0 8px; border-radius:999px; background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.12); display:flex; align-items:center; justify-content:center; cursor:pointer; position:relative; z-index:1002; }
.nav-history text { color:rgba(255,255,255,0.55); font-size:10px; font-weight:700; letter-spacing:0.04em; }
[data-theme="white"] .nav-history { background:#f3f4f6; border-color:#e5e7eb; }
[data-theme="white"] .nav-history text { color:#374151; }
.history-list { max-height:50vh; max-height:50dvh; overflow-y:auto; margin-bottom:8px; }
.history-overlay { position:fixed; inset:0; z-index:600; background:rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; padding:40px; }
.history-panel { width:100%; max-width:340px; background:#1a2030; border-radius:32rpx; padding:40rpx 32rpx; max-height:60vh; max-height:60dvh; overflow-y:auto; }
.history-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.history-title { font-size:17px; font-weight:700; color:#e5e7eb; }
.history-header-close { width:28px; height:28px; border-radius:50%; background:rgba(255,255,255,0.08); display:flex; align-items:center; justify-content:center; cursor:pointer; }
.history-header-close text { font-size:14px; color:#9ca3af; }
.history-grid { display:flex; flex-direction:column; gap:8px; }
.history-day-label { display:block; font-size:12px; font-weight:600; color:#9ca3af; margin:10px 0 6px; padding-left:2px; }
.history-card-meta text { font-size:12px; color:#9ca3af; margin-bottom:4px; display:block; }
.history-card { background:rgba(255,255,255,0.05); border-radius:12px; padding:12px 14px; }
.history-card-top { display:flex; align-items:center; justify-content:space-between; margin-bottom:6px; }
.history-card-name { font-size:14px; font-weight:600; color:#00d2ff; }
.history-card-date { font-size:11px; color:#6b7280; }
.history-card-content { margin-bottom:4px; }
.history-card-content text { font-size:13px; color:#d1d5db; }
.history-card-result text { font-size:12px; color:#9ca3af; }

[data-theme="white"] .history-panel { background:#fff; }
[data-theme="white"] .history-title { color:#1a1a2e; }
[data-theme="white"] .history-header-close { background:#f3f4f6; }
[data-theme="white"] .history-card { background:#f9fafb; }
[data-theme="white"] .history-card-name { color:#2563eb; }
[data-theme="white"] .history-card-content text { color:#374151; }
[data-theme="white"] .history-card-result text { color:#9ca3af; }
.history-row { padding:8px 0; border-bottom:1px solid var(--border); }
.hr-date { color:var(--text); font-size:12px; font-weight:600; display:block; }
.hr-meta { color:var(--text-dim); font-size:11px; display:block; margin-top:2px; }
.hr-note { color:var(--text-dim); font-size:10px; display:block; margin-top:2px; }
.history-empty { color:var(--text-dim); font-size:13px; text-align:center; padding:16px 0; }
.nav-dev text { color:rgba(255,255,255,0.55); font-size:10px; font-weight:700; letter-spacing:0.04em; }
.nav-dev.active { background:rgba(251,191,36,0.15); border-color:rgba(251,191,36,0.45); }
.nav-dev.active text { color:#fbbf24; }
.body { flex:1; overflow-y:auto; padding:24rpx 28rpx 0; scrollbar-width:none; -ms-overflow-style:none; }
.guide-handoff-banner {
  display:flex; align-items:flex-start; gap:12rpx;
  margin-bottom:24rpx; padding:20rpx 24rpx;
  background:rgba(0,210,255,0.08); border:1px solid rgba(0,210,255,0.35);
  border-radius:16rpx;
}
.guide-handoff-main { flex:1; min-width:0; }
.guide-handoff-title {
  display:block; color:#7dd3fc; font-size:22rpx; font-weight:700; margin-bottom:6rpx;
}
.guide-handoff-text {
  display:block; color:#c9d1d9; font-size:24rpx; line-height:1.45; word-break:break-word;
}
.guide-handoff-close {
  flex-shrink:0; width:44rpx; height:44rpx;
  display:flex; align-items:center; justify-content:center;
  color:#8b949e; font-size:32rpx;
}
.body::-webkit-scrollbar { display:none; }

.card { background:#243046; border-radius:20rpx; padding:28rpx 32rpx; margin-bottom:24rpx; position:relative; border:2px solid rgba(0,210,255,0.2); clip-path:polygon(8px 0,100% 0,100% calc(100% - 8px),calc(100% - 8px) 100%,0 100%,0 8px); }
.plan-label { color:#00d2ff; font-size:13px; font-weight:700; display:block; }
.plan-header { display:flex; align-items:center; justify-content:space-between; gap:16rpx; margin-bottom:20rpx; flex-wrap:wrap; }
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
.card-empty { background:rgba(10,18,30,0.6); border:1px solid rgba(0,210,255,0.12); border-radius:14px; padding:20px 16px; text-align:center; }
.plan-empty-text { color:rgba(255,255,255,0.4); font-size:12px; line-height:1.5; }
.plan-transition-wrap { padding:16px 8px; text-align:center; }
.plan-transition-icon { font-size:28px; display:block; margin-bottom:8px; }
.plan-transition-title { color:#e6edf3; font-size:15px; font-weight:600; display:block; }
.plan-transition-sub { color:rgba(255,255,255,0.5); font-size:12px; margin-top:6px; display:block; }
.training-video { width:100%; border-radius:10px; background:#000; }
.audio-controls { display:flex; flex-direction:column; gap:10px; margin-top:4px; }
.audio-btn-row { display:flex; gap:10px; justify-content:center; flex-wrap:wrap; }
.audio-play-btn {
  min-width:112px; text-align:center; padding:10px 18px; border-radius:999px;
  background:rgba(0,210,255,0.15); border:1px solid rgba(0,210,255,0.45); color:#00d2ff; font-weight:700; cursor:pointer;
}
.audio-play-btn.secondary {
  background:rgba(255,255,255,0.06); border-color:rgba(255,255,255,0.18); color:rgba(255,255,255,0.85); font-weight:600;
}
.audio-progress-wrap { display:flex; flex-direction:column; gap:6px; }
.audio-progress-track { height:8px; border-radius:999px; background:rgba(255,255,255,0.12); overflow:hidden; }
.audio-progress-fill { height:100%; border-radius:999px; background:linear-gradient(90deg,#22d3ee,#2563eb); }
.audio-progress-text { color:rgba(255,255,255,0.7); font-size:12px; text-align:center; }
.media-listen-hint { display:block; margin-top:10px; text-align:center; color:rgba(255,255,255,0.55); font-size:11px; line-height:1.4; }
[data-theme="white"] .audio-play-btn { background:#eff6ff; border-color:#93c5fd; color:#2563eb; }
[data-theme="white"] .audio-progress-track { background:#e5e7eb; }
[data-theme="white"] .audio-progress-text,
[data-theme="white"] .media-listen-hint { color:#6b7280; }
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
.plan-ai-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:6px; }
.plan-ai-label { color:#00d2ff; font-size:11px; font-weight:700; }
.plan-ai-text { color:#fff; font-size:13px; line-height:1.65; display:block; white-space:pre-wrap; }
.plan-ai-header { cursor:pointer; }
.plan-ai-hint { color:rgba(255,255,255,0.35); font-size:10px; }
.plan-warn { color:#fbbf24; font-size:12px; display:block; margin-top:8px; cursor:pointer; }
.phase-shine {
  position:absolute; top:0; left:-100%; width:100%; height:100%;
  background:linear-gradient(90deg, transparent 0%, rgba(0,210,255,0.06) 30%, rgba(0,210,255,0.15) 50%, rgba(0,210,255,0.06) 70%, transparent 100%);
  animation:phaseShine 6s ease-in-out infinite;
  pointer-events:none; z-index:0;
}
@keyframes phaseShine {
  0% { transform:translateX(0); }
  60% { transform:translateX(200%); }
  100% { transform:translateX(200%); }
}
.phase-section {
  scroll-margin-top:12px;
  background:rgba(0,210,255,0.04);
  border:1.5px solid rgba(0,210,255,0.2);
  border-radius:14px;
  padding:16px;
  margin-bottom:14px;
  position:relative;
}


.section-title { color:#fff; font-size:14px; font-weight:700; margin-bottom:8px; display:block; }
.section-title.dim { color:rgba(255,255,255,0.35); }

.step { background:rgba(15,28,48,0.85); border-radius:10px; padding:14px; display:flex; gap:10px; align-items:flex-start; border:1px solid rgba(0,210,255,0.15); border-left:4px solid #00d2ff; margin-bottom:10px; cursor:pointer; transition:all 0.15s; position:relative; box-shadow:0 0 0 1px rgba(0,210,255,0.08), 0 4px 20px rgba(0,0,0,0.5), 0 8px 32px rgba(0,0,0,0.35), 0 1px 4px rgba(0,0,0,0.3); }
.step-grid { display:flex; flex-direction:column; gap:8px; width:100%; box-sizing:border-box; }
.step-grid .step { width:100%; box-sizing:border-box; max-width:100%; }
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
.step-video { border-left-color:#f59e0b; }
.step-time { color:rgba(255,255,255,0.4); font-size:10px; text-align:center; display:block; margin-top:4px; }
.step-time.dim-text { color:rgba(255,255,255,0.35); }

.btn-checkin { background:linear-gradient(135deg,rgba(0,210,255,0.3),rgba(0,136,204,0.3)); border-radius:12px; padding:10px 8px; text-align:center; cursor:pointer; box-shadow:0 0 20px rgba(0,210,255,0.15); display:flex; align-items:center; justify-content:center; width:100%; box-sizing:border-box; }
.btn-checkin text, .btn-checkin-text { color:#fff !important; font-size:14px; font-weight:700; }
.btn-checkin:active { opacity:0.85; }

.summary-card { border:2px solid rgba(0,210,255,0.15); cursor:pointer; clip-path:polygon(8px 0,100% 0,100% calc(100% - 8px),calc(100% - 8px) 100%,0 100%,0 8px); }
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
.sa-pct { display:block; color:rgba(255,255,255,0.55); font-size:10px; font-weight:700; }
.sa-item.active .sa-pct { color:#00d2ff; }
.sa-emoji { display:block; font-size:12px; margin-top:1px; }

/* 未打卡 — 简约提示 */
.summary-empty { border:1px solid rgba(255,255,255,0.08); text-align:center; cursor:default; opacity:0.7; }
.summary-empty:active { background:var(--bg-card, #243046); }
.summary-empty-text { display:block; color:rgba(255,255,255,0.35); font-size:12px; line-height:1.5; }

.picker-overlay { position:fixed; inset:0; z-index:500; background:rgba(0,0,0,0.75); display:flex; align-items:center; justify-content:center; padding:40rpx; }
.picker-card { background:#1a2840; border:1px solid #00d2ff; border-radius:28rpx; padding:48rpx 40rpx; width:100%; max-width:360px; box-shadow:0 0 30px rgba(0,210,255,0.1); position:relative; }
.picker-card::before, .picker-card::after { content:''; position:absolute; width:10px; height:10px; border-color:#00d2ff; border-style:solid; }
.picker-card::before { top:0; left:0; border-width:1px 0 0 1px; }
.picker-card::after { bottom:0; right:0; border-width:0 1px 1px 0; }
.picker-title { color:#fff; font-size:16px; font-weight:700; text-align:center; display:block; margin-bottom:16px; }

/* 打卡弹窗 */
.checkin-modal { max-height:85vh; max-height:85dvh; overflow-y:auto; padding:40rpx 32rpx; max-width:400px; }
.assessment-modal { max-width:320px; padding:28px 22px 22px; text-align:center; }
.assessment-modal-icon { font-size:40px; display:block; margin-bottom:12px; }
.assessment-modal-title { display:block; color:#fff; font-size:17px; font-weight:700; margin-bottom:10px; }
.assessment-modal-desc { display:block; color:rgba(255,255,255,0.65); font-size:13px; line-height:1.55; margin-bottom:22px; }
.assessment-modal-actions { display:flex; gap:10px; }
.assessment-btn { flex:1; padding:12px 10px; border-radius:10px; cursor:pointer; }
.assessment-btn text { font-size:14px; font-weight:600; }
.assessment-btn.secondary { background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.15); }
.assessment-btn.secondary text { color:rgba(255,255,255,0.7); }

/* 🆕 v2.0 选修弹窗 */
.elective-entry {
  margin-top: 10px; padding: 8px 12px; border-radius: 8px;
  background: rgba(0, 210, 255, 0.06); border: 1px solid rgba(0, 210, 255, 0.18);
  cursor: pointer; text-align: center;
}
.elective-entry text { color: #00d2ff; font-size: 13px; }
.elective-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; border-bottom: 1px solid rgba(255,255,255,0.05);
}
.elective-info { display: flex; flex-direction: column; gap: 2px; }
.elective-name { color: #e6edf3; font-size: 15px; font-weight: 600; }
.elective-btn {
  padding: 6px 14px; border-radius: 6px; background: rgba(139, 92, 246, 0.2);
  border: 1px solid rgba(139, 92, 246, 0.4); cursor: pointer;
}
.elective-btn.disabled { opacity: 0.4; cursor: not-allowed; }
.elective-btn text { color: #a78bfa; font-size: 13px; font-weight: 600; }
.section-title.elective { color: #a78bfa; }
.assessment-btn.primary { background:linear-gradient(135deg,#00d2ff,#3b8bff); }
.assessment-btn.primary text { color:#fff; }
.checkin-modal .picker-panel { margin-bottom:10px; }
.checkin-modal .form-card { margin-bottom:8px; }
.modal-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:14px; }
.modal-title { color:#fff; font-size:16px; font-weight:700; }
.modal-close { color:rgba(255,255,255,0.5); font-size:20px; cursor:pointer; padding:4px 8px; }

.plan-editor-modal { max-width:340px; position:relative; overflow:hidden; }
.plan-editor-modal::before {
  content:''; position:absolute; top:0; left:0; right:0; height:1px;
  background:linear-gradient(90deg,transparent,#00d2ff,transparent);
  opacity:0.6;
}
.plan-editor-modal::after {
  content:''; position:absolute; bottom:0; left:0; right:0; height:1px;
  background:linear-gradient(90deg,transparent,#00d2ff,transparent);
  opacity:0.4;
}
.confirm-modal { max-width:320px; padding:32px 28px; }
.confirm-modal-text { display:block; color:rgba(255,255,255,0.7); font-size:13px; line-height:1.5; text-align:left; margin:12px 0 20px; }
.confirm-modal-actions { display:flex; gap:10px; }
[data-theme="white"] .confirm-modal-text { color:rgba(0,0,0,0.6); }
.editor-hint { color:var(--text-dim); font-size:12px; text-align:center; margin-bottom:16px; display:block; }
.editor-list { max-height:300px; overflow-y:auto; scrollbar-width:none; -ms-overflow-style:none; }
.editor-row {
  display:flex; align-items:center; gap:10px; padding:10px 0;
  border-bottom:1px solid rgba(0,210,255,0.12);
  position:relative;
}
.editor-row:last-child { border-bottom:none; }
.editor-row::after {
  content:''; position:absolute; bottom:-1px; left:50%; width:0;
  height:1px; background:#00d2ff; transition:width 0.3s,left 0.3s;
}
.editor-row:focus-within::after { width:100%; left:0; }
.editor-label {
  color:#00d2ff; font-size:12px; font-weight:700; white-space:nowrap; min-width:56px;
  text-shadow:0 0 8px rgba(0,210,255,0.3);
  letter-spacing:0.5px;
}
.editor-picker { flex:1; }
.editor-picker-display {
  background:rgba(0,210,255,0.06); border:1px solid rgba(0,210,255,0.25);
  border-radius:8px; padding:10px 12px; font-size:13px; color:#fff;
  position:relative; overflow:hidden;
  transition:border-color 0.2s, box-shadow 0.2s;
}
.editor-picker-display:active {
  border-color:#00d2ff; box-shadow:0 0 12px rgba(0,210,255,0.2);
}
[data-theme="white"] .editor-label { color:#2563eb; text-shadow:none; }
[data-theme="white"] .editor-picker-display { background:rgba(37,99,235,0.04); border-color:rgba(37,99,235,0.2); color:#1a1a2e; }
[data-theme="white"] .editor-picker-display:active { border-color:#2563eb; box-shadow:0 0 12px rgba(37,99,235,0.15); }
.editor-actions { display:flex; gap:10px; margin-top:18px; }
.editor-btn { flex:1; padding:12px; border-radius:10px; text-align:center; cursor:pointer; }
.editor-btn text { font-size:14px; font-weight:600; }
.editor-btn.primary { background:linear-gradient(135deg,rgba(0,210,255,0.3),rgba(0,136,204,0.3)); box-shadow:0 0 20px rgba(0,210,255,0.15); }
.editor-btn.primary text { color:#fff; }
.editor-btn.secondary { background:var(--bg-card); border:1px solid var(--border); }
.editor-btn.secondary text { color:var(--text-dim); }
.plan-edit-block { margin-top:8px; }
.training-done-wrap { margin-top:12px; margin-bottom:20px; }
.training-done-card { text-align:center; padding:16px; background:rgba(34,197,94,0.08); border:1px solid rgba(34,197,94,0.2); border-radius:12px; }
.training-done-icon { font-size:28px; display:block; margin-bottom:4px; }
.training-done-title { font-size:15px; font-weight:600; color:#22c55e; }
.btn-confirm-plan { display:block; margin:16px auto 0; padding:12px 28px; background:linear-gradient(135deg,#00d2ff,#0088cc); color:#fff; font-size:14px; font-weight:600; border-radius:24px; text-align:center; cursor:pointer; box-shadow:0 4px 16px rgba(0,210,255,0.3); }
.btn-confirm-plan text { color:#fff; }
.plan-edit-guide { display:block; color:rgba(255,255,255,0.5); font-size:13px; margin-bottom:4px; }
.plan-edit-bar { display:flex; align-items:center; gap:8px; background:var(--bg-card); border:1px solid var(--border); border-radius:10px; padding:10px 12px; cursor:pointer; }
.plan-edit-bar-text { display:flex; flex-direction:column; gap:3px; flex:1; min-width:0; }
.peb-title { color:var(--text); font-size:13px; font-weight:600; }
.peb-desc { color:rgba(255,255,255,0.55); font-size:11px; line-height:1.4; }
.plan-edit-tip { display:block; color:rgba(255,255,255,0.4); font-size:11px; margin-top:4px; }
.elective-toggles { display:flex; flex-wrap:wrap; gap:8px; margin-top:8px; }
.elective-toggle-item { display:flex; align-items:center; gap:8px; background:var(--bg-card); border:1px solid var(--border); border-radius:10px; padding:6px 12px; cursor:pointer; }
.et-label { color:var(--text); font-size:12px; font-weight:500; }
.et-switch { width:36px; height:20px; border-radius:10px; background:var(--border); cursor:pointer; position:relative; transition:background 0.2s; }
.et-switch.on { background:#00d2ff; }
.et-knob { width:16px; height:16px; border-radius:50%; background:var(--text); position:absolute; top:2px; left:2px; transition:left 0.2s; }
.et-switch.on .et-knob { background:#fff; left:18px; }
.et-info { display:flex; align-items:center; justify-content:center; width:20px; height:20px; cursor:pointer; margin-left:2px; padding:0; transition:all 0.2s; border-radius:50%; background:rgba(0,210,255,0.12); }
.et-info text { color:#00d2ff; font-size:13px; font-weight:700; line-height:1; }
.et-info:active { background:rgba(0,210,255,0.2); }
.et-info:active text { color:#5ce0ff; }
.et-arrow { color:rgba(255,255,255,0.3); font-size:16px; font-weight:300; margin-left:auto; flex-shrink:0; }
.elective-section-label { width:100%; color:rgba(255,255,255,0.5); font-size:12px; font-weight:500; margin-bottom:2px; }
.elective-hint { width:100%; color:rgba(255,255,255,0.3); font-size:12px; line-height:1.4; margin-top:2px; }
ker-close { text-align:center; margin-top:16px; cursor:pointer; }
.picker-close text { color:rgba(255,255,255,0.5); font-size:14px; }
.submitted-item { display:flex; align-items:center; gap:8px; padding:10px 0; border-bottom:1px solid rgba(0,210,255,0.1); }
.submitted-item:last-child { border-bottom:none; }
.si-text { flex:1; color:#fff; font-size:13px; }
.si-actions { display:flex; gap:10px; flex-shrink:0; }
.si-edit { color:#00d2ff; font-size:16px; cursor:pointer; }
.si-del { color:rgba(255,255,255,0.4); font-size:16px; cursor:pointer; }
.si-del:active { color:#ff6b6b; }

.time-card-alert {
  border-color:rgba(255,77,79,0.9) !important;
  box-shadow:0 0 24px rgba(255,77,79,0.6), 0 0 48px rgba(255,77,79,0.3) !important;
  clip-path:none !important;
  animation:redFlash 0.6s ease-in-out 3;
}
@keyframes redFlash {
  0%,100% { border-color:rgba(255,77,79,0.9); box-shadow:0 0 24px rgba(255,77,79,0.6), 0 0 48px rgba(255,77,79,0.3); }
  50% { border-color:rgba(255,77,79,0.2); box-shadow:0 0 4px rgba(255,77,79,0.1); }
}
.time-header { display:flex; align-items:center; gap:8px; margin-bottom:10px; }
.time-status-tag { font-size:10px; padding:2px 8px; border-radius:999px; }
.time-status-tag.running { background:rgba(34,197,94,0.15); color:#22c55e; }
.time-status-tag.expired { background:rgba(239,68,68,0.15); color:#ef4444; }
.time-status-tag.pending { background:rgba(59,130,246,0.15); color:#3b82f6; }
.time-locked { text-align:center; padding:8px 0 4px; }
.time-locked-val { display:block; color:var(--accent); font-size:32px; font-weight:800; letter-spacing:0.06em; font-variant-numeric:tabular-nums; }
.time-setup { display:flex; flex-direction:column; gap:10px; }
.guide-arrow { text-align:center; animation: guideBounce 0.8s ease-in-out infinite; }
.guide-arrow text { font-size:16px; color:#f5a623; font-weight:600; }
@keyframes guideBounce { 0%,100% { transform:translateY(0); } 50% { transform:translateY(-8px); } }
.time-pickers { display:flex; gap:10px; justify-content:center; max-width:280px; margin:0 auto; }
.time-select { flex:1; background:rgba(0,210,255,0.05); border:1px solid rgba(0,210,255,0.2); border-radius:10px; padding:12px 10px; display:flex; align-items:baseline; justify-content:center; gap:4px; cursor:pointer; }
.time-select-val { color:#e5e7eb; font-size:22px; font-weight:700; }
.time-select-unit { color:#6b7280; font-size:12px; }
.time-start-btn { background:linear-gradient(135deg,rgba(0,210,255,0.35),rgba(0,136,204,0.35)); border-radius:10px; padding:12px; text-align:center; cursor:pointer; }
.time-start-btn text { color:#00d2ff; font-size:15px; font-weight:600; }
.time-start-btn.disabled { opacity:0.4; }
.time-start-btn-agent { margin-top:10px; background:linear-gradient(135deg,rgba(120,90,255,0.28),rgba(0,180,200,0.28)); }
.time-start-btn-agent text { color:#c4b5fd; }
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
.dev-section-label { display:block; color:rgba(251,191,36,0.55); font-size:10px; font-weight:600; margin:8px 0 4px; }
.dev-status { margin-bottom:8px; padding:6px 10px; background:rgba(251,191,36,0.06); border:1px solid rgba(251,191,36,0.2); border-radius:8px; }
.dev-status text { color:rgba(251,191,36,0.9); font-size:10px; line-height:1.4; }
.dev-assist text { white-space: pre-wrap; word-break: break-word; }
.dev-actions { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:8px; }
.dev-action { flex:1; min-width:88px; background:rgba(251,191,36,0.08); border:1px solid rgba(251,191,36,0.25); border-radius:8px; padding:8px 6px; text-align:center; cursor:pointer; }
.dev-action-primary { background:rgba(34,197,94,0.12); border-color:rgba(34,197,94,0.35); }
.dev-action-primary text { color:#4ade80; }
.dev-action-danger { background:rgba(239,68,68,0.08); border-color:rgba(239,68,68,0.2); }
.dev-action-danger text { color:rgba(239,68,68,0.7); }
.dev-action text { color:#fbbf24; font-size:11px; font-weight:600; }
.dev-panel-hint { display:block; margin-top:8px; color:rgba(255,255,255,0.3); font-size:10px; text-align:center; }
.media-block, .checkin-block { position:relative; }
.media-block { margin-bottom:18px; }
.media-block .step { margin-bottom:0; padding:10px 8px; }
.media-block .step-box { font-size:14px; padding:12px 6px; }
.media-block .step-label { font-size:11px; margin-bottom:4px; }
.media-block .step-num { width:18px; height:18px; font-size:10px; }
.media-block.locked, .checkin-block.locked { pointer-events:none; }
.media-block.locked .step { opacity:0.4; }
.checkin-block.locked { opacity:0.6; }
.media-lock-overlay, .checkin-lock-overlay { position:absolute; inset:0; z-index:10; display:flex; align-items:center; justify-content:center; pointer-events:none; }
.media-lock-text, .checkin-lock-text { background:rgba(11,17,30,0.92); border:1px solid rgba(0,210,255,0.25); color:#00d2ff; font-size:12px; padding:8px 14px; border-radius:999px; }
.perception-done-text { display:block; text-align:center; color:rgba(0,210,255,0.5); font-size:12px; padding:8px 4px; }
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
[data-theme="white"] .time-start-btn-agent { background:linear-gradient(135deg,#7c3aed,#4f46e5); }
[data-theme="white"] .time-start-btn-agent text { color:#fff; }
[data-theme="white"] .time-setup-hint { color:#9ca3af; }
[data-theme="white"] .time-running-hint { color:#9ca3af; }
[data-theme="white"] .time-expired-sub { color:#9ca3af; }
[data-theme="white"] .media-lock-text, [data-theme="white"] .checkin-lock-text { background:#fff; border-color:#e5e7eb; color:#2563eb; }
[data-theme="white"] .form-input { background:#f9fafb; border-color:#d1d5db; color:#1f2937; }
[data-theme="white"] .form-input.short { background:#f9fafb; color:#1f2937; }
[data-theme="white"] .form-input.mini { background:#f9fafb; color:#1f2937; }
[data-theme="white"] .form-textarea { background:#f9fafb; border-color:#d1d5db; color:#1f2937; }
[data-theme="white"] .ftag { background:#f3f4f6; color:#374151; border-color:#d1d5db; }

.divider { height:1px; background:linear-gradient(90deg,transparent,rgba(0,210,255,0.3),transparent); margin:12px 0; }
.b-section { }
.step-preview-locked { cursor:not-allowed; }
.step-preview-locked .step-box { border-style:dashed; opacity:0.85; }
.lock-tip { text-align:center; color:rgba(255,255,255,0.4); font-size:12px; display:block; margin-top:6px; }

.picker-panel { padding:16px 14px; margin-bottom:12px; background:rgba(13,23,40,0.6); box-shadow:0 0 24px rgba(0,210,255,0.08),inset 0 0 40px rgba(0,210,255,0.02); }
[data-augmented-ui].picker-panel { --aug-border-bg:rgba(0,210,255,0.35); --aug-border-all:2px; --aug-clip-tl:12px; --aug-clip-tr:12px; --aug-clip-br:12px; --aug-clip-bl:12px; }
[data-augmented-ui].btn-checkin { --aug-border-bg:rgba(0,210,255,0.3); --aug-border-all:1px; --aug-clip-tl:10px; --aug-clip-br:10px; }
.picker-panel-header { display:flex; align-items:center; justify-content:center; gap:8px; margin-bottom:12px; }
.pph-dot { color:#00d2ff; font-size:10px; }
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
.picker-item.disabled { opacity:0.25; pointer-events:none; }
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

.form-card { background:#1a2840; border:2px solid rgba(0,210,255,0.5); border-radius:24rpx; padding:36rpx; margin-bottom:20rpx; position:relative; box-shadow:0 0 20px rgba(0,210,255,0.12), inset 0 0 30px rgba(0,210,255,0.02); clip-path:polygon(10px 0,100% 0,100% calc(100% - 10px),calc(100% - 10px) 100%,0 100%,0 10px); animation:scanDown 0.4s cubic-bezier(0.25,0.8,0.25,1) both; }
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
.form-label { color:rgba(255,255,255,0.5); font-size:13px; width:auto; min-width:56px; flex-shrink:0; }
.form-soft-tip {
  display: block;
  margin: 0 0 10px;
  padding: 0 2px;
  color: rgba(255, 255, 255, 0.45);
  font-size: 12px;
  line-height: 1.4;
}
[data-theme="white"] .form-soft-tip { color: #6b7280; }
.form-input { flex:1; background:#fff; border:2px solid rgba(0,210,255,0.2); border-radius:10px; padding:10px 12px; font-size:13px; color:#0b111e; }
.form-input-err { border-color:#ef4444 !important; animation: flash-red 0.5s ease-in-out 3; }
@keyframes flash-red { 0%,100% { background:#fff; } 50% { background:rgba(239,68,68,0.2); } }
.form-textarea { flex:1; background:#fff; border:2px solid rgba(0,210,255,0.2); border-radius:10px; padding:10px 12px; font-size:13px; color:#0b111e; height:60px; }
.form-textarea-sm { height:36px; padding:6px 10px; }
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
.form-input.mini { width:40px; flex:none; background:#fff; color:#0b111e; padding:6px 0; text-align:center; appearance:textfield; -moz-appearance:textfield; -webkit-appearance:none; }
.form-inline .form-unit { color:rgba(255,255,255,0.7); }
.form-unit { color:rgba(255,255,255,0.7); font-size:12px; background:rgba(255,255,255,0.06); border:1px solid rgba(0,210,255,0.2); border-radius:6px; padding:4px 8px; }

.req-star { color:#ff4757; font-size:14px; font-weight:700; margin-left:2px; line-height:1; }
[data-theme="white"] .req-star { color:#ef4444; }
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
[data-theme="white"] .plan-edit-guide { color:rgba(0,0,0,0.5); }
[data-theme="white"] .peb-desc { color:rgba(0,0,0,0.55); }
[data-theme="white"] .plan-edit-tip { color:rgba(0,0,0,0.45); }
[data-theme="white"] .btn-confirm-plan { background:linear-gradient(135deg,#2563eb,#1d4ed8); }
[data-theme="white"] .btn-confirm-plan text { color:#fff; }
[data-theme="white"] .et-info { background:rgba(0,210,255,0.1); }
[data-theme="white"] .et-info text { color:#00d2ff; }
[data-theme="white"] .et-info:active { background:rgba(0,210,255,0.18); }
[data-theme="white"] .et-info:active text { color:#5ce0ff; }
[data-theme="white"] .elective-section-label { color:rgba(0,0,0,0.5); }
[data-theme="white"] .elective-entry { background:#f3f4f6; border-color:#e5e7eb; }
[data-theme="white"] .elective-entry text { color:#2563eb; }
[data-theme="white"] .elective-item { border-bottom-color:#e5e7eb; }
[data-theme="white"] .elective-name { color:#1a1a2e; }
[data-theme="white"] .elective-btn { background:rgba(139,92,246,0.08); border-color:rgba(139,92,246,0.2); }
[data-theme="white"] .elective-btn text { color:#7c3aed; }
[data-theme="white"] .elective-btn.disabled { opacity:0.3; }
[data-theme="white"] .et-arrow { color:rgba(0,0,0,0.3); }
[data-theme="white"] .et-desc { color:rgba(0,0,0,0.35); }
[data-theme="white"] .elective-hint { color:rgba(0,0,0,0.35); }
[data-theme="white"] .plan-ai-label { color:#2563eb; }
[data-theme="white"] .plan-ai-text { color:#1a1a2e; }
[data-theme="white"] .plan-ai-hint { color:#9ca3af; }
[data-theme="white"] .section-title { color:#1a1a2e; }
[data-theme="white"] .step { background:#fff; border-color:#e5e7eb; border-left-color:#2563eb; box-shadow:0 1px 3px rgba(0,0,0,0.08), 0 4px 16px rgba(0,0,0,0.06); }
[data-theme="white"] .step-num { background:#2563eb; }
[data-theme="white"] .step-label { color:#1a1a2e; }
[data-theme="white"] .step-box { background:#f9fafb; border-color:#e5e7eb; color:#1a1a2e; }
[data-theme="white"] .step-time { color:#9ca3af; }
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
[data-theme="white"] .picker-item.disabled { opacity:0.2; }
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
[data-theme="white"] .submitted-item { border-bottom-color:#e5e7eb; }
[data-theme="white"] .step-content .step-time { color:#9ca3af; }
[data-theme="white"] .step-box.dim-box { opacity:0.6; }

/* ---- 时间轴总览 — 白色主题 ---- */
[data-theme="white"] .plan-header-meta { color:#6b7280; }
[data-theme="white"] .card-empty { background:#fff; border-color:#e5e7eb; }
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
[data-theme="white"] .phase-section { background:#fff; border-color:#e5e7eb; }
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
.si-desc { color:rgba(255,255,255,0.5); font-size:10px; line-height:1.3; display:block; }
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
/* 方案C：封面风 */
.player-card-c { background:var(--bg-card,#1a2840); border:1px solid rgba(0,210,255,0.2); border-radius:16px; width:100%; max-width:380px; overflow:hidden; padding:0; }
.player-cover { position:relative; height:180px; background:linear-gradient(135deg,rgba(0,210,255,0.08),rgba(139,92,246,0.08)); display:flex; align-items:center; justify-content:center; overflow:hidden; }
.player-cover::before { content:''; position:absolute; inset:0; background:repeating-linear-gradient(0deg,transparent,transparent 30px,rgba(255,255,255,0.015) 30px,rgba(255,255,255,0.015) 31px); pointer-events:none; }
.player-cover-video { width:100%; height:100%; position:relative; }
.player-cover-video .training-video { width:100%; height:100%; object-fit:cover; }
.player-video-loading {
  position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
  background:rgba(0,0,0,0.45); pointer-events:none;
}
.player-video-loading-text { color:#fff; font-size:14px; }
.player-cover-placeholder { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:8px; pointer-events:none; background:rgba(0,0,0,0.35); }
.player-cover-icon { font-size:48px; }
.player-cover-hint { color:rgba(255,255,255,0.4); font-size:12px; }
.player-cover-audio { display:flex; flex-direction:column; align-items:center; gap:8px; }
.player-cover-label { color:rgba(255,255,255,0.7); font-size:13px; font-weight:500; text-align:center; padding:0 16px; }
.player-cover-progress { position:absolute; bottom:0; left:0; right:0; height:3px; background:rgba(255,255,255,0.1); }
.player-cover-progress-fill { height:100%; background:linear-gradient(90deg,#22d3ee,#34d399); }
.player-header { display:flex; align-items:center; justify-content:space-between; padding:12px 14px 4px; margin-bottom:0; }
.player-title { color:#fff; font-size:14px; font-weight:600; }
.player-audio-name { display:block; text-align:center; color:rgba(255,255,255,0.85); font-size:13px; margin-bottom:12px; line-height:1.4; }
.player-close { color:rgba(255,255,255,0.4); font-size:18px; cursor:pointer; padding:4px 6px; }
.player-body { }
.player-controls { display:flex; align-items:center; justify-content:space-between; padding:8px 14px 14px; }
.player-ctrl-center { display:flex; align-items:center; gap:12px; }
.player-ctrl-btn { width:44px; height:44px; border-radius:50%; background:rgba(0,210,255,0.12); display:flex; align-items:center; justify-content:center; cursor:pointer; transition:all 0.15s; }
.player-ctrl-btn text { font-size:18px; }
.player-ctrl-btn:active { background:rgba(0,210,255,0.25); transform:scale(0.95); }
.player-ctrl-btn.sm { width:32px; height:32px; }
.player-ctrl-btn.sm text { font-size:14px; }
.player-time-label { color:rgba(255,255,255,0.5); font-size:12px; font-variant-numeric:tabular-nums; }
.player-ctrl-left .player-time-label { text-align:left; }
.player-ctrl-right .player-time-label { text-align:right; }
.media-listen-hint { display:block; padding:0 14px 10px; text-align:center; color:rgba(255,255,255,0.4); font-size:10px; }
[data-theme="white"] .player-overlay { background:rgba(0,0,0,0.6); }
[data-theme="white"] .player-card { background:#fff; border-color:#e5e7eb; }
[data-theme="white"] .player-card-c { background:#fff; border-color:#e5e7eb; }
[data-theme="white"] .player-cover { background:linear-gradient(135deg,rgba(37,99,235,0.03),rgba(139,92,246,0.03)); }
[data-theme="white"] .player-title { color:#1a1a2e; }
[data-theme="white"] .player-audio-name { color:#374151; }
[data-theme="white"] .player-cover-label { color:rgba(0,0,0,0.6); }
[data-theme="white"] .player-time-label { color:rgba(0,0,0,0.4); }
[data-theme="white"] .player-ctrl-btn { background:rgba(37,99,235,0.08); }
[data-theme="white"] .media-listen-hint { color:#9ca3af; }
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

/* ── 已打卡迷你卡片 ── */
.summary-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; }
.summary-mini-cards { display:flex; flex-direction:column; gap:8px; margin-bottom:10px; }
.mini-card {
  display:flex; align-items:center; gap:8px;
  background:rgba(0,210,255,0.04); border:1px solid rgba(0,210,255,0.1);
  border-radius:8px; padding:10px 10px 10px 0;
  cursor:pointer; transition:all 0.15s; position:relative; overflow:hidden;
}
.mini-card:active { background:rgba(0,210,255,0.1); border-color:rgba(0,210,255,0.3); }

/* V1 — 左侧蓝色竖条 */
.mini-card-v1 .mini-card-accent {
  width:3px; height:60%; border-radius:0 2px 2px 0;
  background:linear-gradient(180deg,#00d2ff,#0088cc);
  box-shadow:0 0 8px rgba(0,210,255,0.4);
  flex-shrink:0; align-self:center;
}
.mini-card-v1 { padding-left:8px; }

/* V2 — 书签折角 */
.mini-card-v2 {
  padding-left:14px;
  clip-path:polygon(0 0,100% 0,100% 100%,14px 100%,0 calc(100% - 12px),0 0);
}
.mini-card-v2 .mini-card-accent {
  position:absolute; top:0; left:0; width:20px; height:20px;
  background:linear-gradient(135deg,transparent 50%,rgba(0,210,255,0.3) 50%);
  border-radius:0 0 4px 0;
}
.mini-card-v2 .mini-card-accent::after {
  content:''; position:absolute; top:2px; left:2px; width:4px; height:4px;
  border-radius:50%; background:#00d2ff; box-shadow:0 0 6px #00d2ff;
}

.mini-card-left { flex:1; min-width:0; }
.mini-card-name { color:#fff; font-size:12px; font-weight:600; display:block; }
.mini-card-summary { color:rgba(255,255,255,0.45); font-size:10px; display:block; margin-top:2px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }

.summary-add-btn {
  text-align:center; padding:10px; border-radius:10px;
  background:linear-gradient(135deg,rgba(0,210,255,0.25),rgba(0,136,204,0.25));
  box-shadow:0 0 20px rgba(0,210,255,0.15); cursor:pointer;
  transition:all 0.15s; margin-bottom:10px;
}
.summary-add-btn text { color:#00d2ff; font-size:13px; font-weight:600; }
.summary-add-btn:active { opacity:0.85; transform:scale(0.97); }
[data-theme="white"] .summary-add-btn { background:linear-gradient(135deg,#2563eb,#1d4ed8); }
[data-theme="white"] .summary-add-btn text { color:#fff; }

/* ── 已打卡滑动详情弹窗 ── */
.detail-overlay {
  position:fixed; inset:0; z-index:500;
  background:rgba(0,0,0,0.75);
  overflow-y:auto; -webkit-overflow-scrolling:touch;
  display:flex; justify-content:center; padding:24px 0 40px;
}
.detail-test-card {
  width:90%; max-width:340px; margin:auto;
  background:#1a2840; border-radius:12px;
  border:1.5px solid rgba(0,210,255,0.35);
  box-shadow:0 0 24px rgba(0,210,255,0.12);
  padding:16px;
}
.detail-swiper-wrap { width:90%; max-width:360px; }
.detail-swiper { height:420px; }
.detail-card-slide {
  background:#1a2840; height:100%; border-radius:12px;
  border:1.5px solid rgba(0,210,255,0.35);
  box-shadow:0 0 24px rgba(0,210,255,0.12), 0 0 60px rgba(0,210,255,0.04), inset 0 0 40px rgba(0,210,255,0.02);
  padding:10px 12px; margin:0 3px; display:flex; flex-direction:column;
}
.detail-slide-name { color:#fff; font-size:13px; font-weight:700; display:block; margin-bottom:4px; flex-shrink:0; }
.detail-slide-body { flex:1; overflow-y:auto; min-height:0; padding-right:2px; }
.detail-row { display:flex; align-items:flex-start; gap:6px; padding:6px 0; border-bottom:1px solid rgba(0,210,255,0.06); position:relative; }
.detail-row::before { content:'›'; position:absolute; left:-6px; top:6px; color:rgba(0,210,255,0.25); font-size:9px; font-family:monospace; }
.detail-label { color:#fff; font-size:12px; width:56px; flex-shrink:0; font-weight:500; }
.detail-value { color:rgba(0,210,255,0.55); font-size:11px; flex:1; line-height:1.4; word-break:break-all; }

[data-theme="white"] .detail-label { color:#1a1a2e; }
[data-theme="white"] .detail-value { color:#6b7280; }
.detail-actions { display:flex; gap:6px; padding-top:8px; flex-shrink:0; border-top:1px solid rgba(0,210,255,0.08); }
.detail-edit-body { max-height:52vh; max-height:52dvh; overflow-y:auto; margin-bottom:4px; }
.detail-form-row { display:flex; align-items:flex-start; gap:8px; margin-bottom:10px; }
.detail-form-label { color:rgba(0,210,255,0.55); font-size:10px; width:52px; flex-shrink:0; padding-top:8px; }
.detail-form-unit { color:rgba(0,210,255,0.45); font-size:11px; }
.detail-form-input {
  flex:1; background:rgba(255,255,255,0.06); border:1px solid rgba(0,210,255,0.25);
  border-radius:8px; padding:8px 10px; font-size:12px; color:#fff;
}
.detail-form-input.short { width:72px; flex:none; }
.detail-form-textarea {
  flex:1; min-height:36px; height:36px; background:rgba(255,255,255,0.06); border:1px solid rgba(0,210,255,0.25);
  border-radius:8px; padding:6px 10px; font-size:12px; color:#fff;
}
.detail-form-inline { display:flex; align-items:center; gap:6px; flex:1; flex-wrap:wrap; }
.detail-form-tags { display:flex; flex-wrap:wrap; gap:6px; flex:1; }
.detail-ftag {
  padding:4px 8px; border-radius:6px; font-size:11px;
  border:1px solid rgba(0,210,255,0.2); color:rgba(255,255,255,0.65);
}
.detail-ftag.on { border-color:rgba(0,210,255,0.55); color:#00d2ff; background:rgba(0,210,255,0.1); }
.detail-save-btn { border-color:rgba(34,197,94,0.45); color:#4ade80; background:rgba(34,197,94,0.08); }
[data-theme="white"] .detail-test-card { background:#fff; border-color:rgba(37,99,235,0.25); }
[data-theme="white"] .detail-slide-name { color:#1a1a2e; }
[data-theme="white"] .detail-form-input,
[data-theme="white"] .detail-form-textarea { background:#f9fafb; border-color:#e5e7eb; color:#1a1a2e; }
[data-theme="white"] .detail-form-label { color:#6b7280; }
[data-theme="white"] .detail-form-unit { color:#9ca3af; }
[data-theme="white"] .detail-ftag { border-color:#e5e7eb; color:#6b7280; }
[data-theme="white"] .detail-ftag.on { border-color:#bfdbfe; color:#2563eb; background:#eff6ff; }
.detail-card-slide::before {
  content:''; position:absolute; top:0; left:10%; width:80%; height:1px;
  background:linear-gradient(90deg,transparent,rgba(0,210,255,0.4),transparent);
}
.detail-card-slide::after {
  content:''; position:absolute; bottom:0; left:10%; width:80%; height:1px;
  background:linear-gradient(90deg,transparent,rgba(0,210,255,0.15),transparent);
}
.btn-outline-sm {
  flex:1; padding:10px; text-align:center;
  border:1px solid rgba(0,210,255,0.4); border-radius:8px;
  color:#00d2ff; font-size:12px; font-weight:600; cursor:pointer;
  background:rgba(0,210,255,0.05);
  transition:all 0.15s;
}
.btn-outline-sm:active { background:rgba(0,210,255,0.15); box-shadow:0 0 16px rgba(0,210,255,0.2); }
.btn-del-sm {
  flex:1; padding:10px; text-align:center;
  border:1px solid rgba(239,68,68,0.2); border-radius:8px;
  color:rgba(239,68,68,0.5); font-size:12px; font-weight:600; cursor:pointer;
  background:rgba(239,68,68,0.03);
  transition:all 0.15s;
}
.btn-del-sm:active { background:rgba(239,68,68,0.1); box-shadow:0 0 16px rgba(239,68,68,0.15); }
[data-theme="white"] .detail-card-slide {
  background:#fff; border-color:rgba(37,99,235,0.25);
  box-shadow:0 0 24px rgba(37,99,235,0.06), 0 4px 20px rgba(0,0,0,0.04);
}
[data-theme="white"] .detail-slide-name { color:#1a1a2e; }
[data-theme="white"] .detail-dot.active { background:#2563eb; box-shadow:0 0 6px rgba(37,99,235,0.3); }
[data-theme="white"] .btn-outline-sm { border-color:#bfdbfe; color:#2563eb; background:#eff6ff; }
[data-theme="white"] .btn-del-sm { border-color:rgba(239,68,68,0.2); }
[data-theme="white"] .mini-card { background:#f9fafb; border-color:#e5e7eb; }
[data-theme="white"] .mini-card:active { background:#eff6ff; border-color:#bfdbfe; }
[data-theme="white"] .mini-card-v1 .mini-card-accent { background:linear-gradient(180deg,#2563eb,#1d4ed8); box-shadow:0 0 6px rgba(37,99,235,0.3); }
[data-theme="white"] .mini-card-v2 .mini-card-accent { background:linear-gradient(135deg,transparent 50%,rgba(37,99,235,0.2) 50%); }
[data-theme="white"] .mini-card-v2 .mini-card-accent::after { background:#2563eb; box-shadow:0 0 6px #2563eb; }
[data-theme="white"] .mini-card-name { color:#1a1a2e; }
[data-theme="white"] .mini-card-summary { color:#9ca3af; }


/* ═══════════════════════════════════════════
   交互感增强
   ═══════════════════════════════════════════ */

/* 1. 全局按钮按压下沉 */
.btn-checkin, .btn-cyber, .picker-item, .time-start-btn, .btn-outline, .btn-solid,
.nav-back, .nav-dev, .btn-send, .btn-speaker {
  transition:transform 0.12s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.12s ease, opacity 0.12s ease !important;
}
.btn-checkin:active, .picker-item:active, .time-start-btn:active {
  transform:scale(0.94) !important;
}
.time-select:active, .nav-back:active, .nav-dev:active, .sa-item:active {
  transform:scale(0.92);
}
.btn-checkin:active { box-shadow:0 0 4px rgba(0,210,255,0.1) !important; }

/* 2. 卡片悬浮抬起 */
.card {
  transition:transform 0.25s cubic-bezier(0.25,0.8,0.25,1), box-shadow 0.25s ease !important;
}
@media (hover:hover) {
  .card:hover { transform:translateY(-2px); box-shadow:0 8px 24px rgba(0,210,255,0.1), 0 0 40px rgba(0,210,255,0.04) !important; }
}
.card:active { transform:translateY(0) scale(0.985); }

/* 3. 列表项依次入场 */
.tl-phase {
  animation:phaseSlideIn 0.4s cubic-bezier(0.25,0.8,0.25,1) both;
}
.tl-phase:nth-child(1) { animation-delay:0s; }
.tl-phase:nth-child(2) { animation-delay:0.08s; }
.tl-phase:nth-child(3) { animation-delay:0.16s; }
.tl-phase:nth-child(4) { animation-delay:0.24s; }
@keyframes phaseSlideIn {
  from { opacity:0; transform:translateX(-12px); }
  to   { opacity:1; transform:translateX(0); }
}
/* 训练步骤依次滑入 */
.step {
  animation:stepSlideUp 0.35s cubic-bezier(0.25,0.8,0.25,1) both;
}
.step:nth-child(1) { animation-delay:0.05s; }
.step:nth-child(2) { animation-delay:0.12s; }
.step:nth-child(3) { animation-delay:0.19s; }
@keyframes stepSlideUp {
  from { opacity:0; transform:translateY(10px); }
  to   { opacity:1; transform:translateY(0); }
}

/* 4. 状态切换平滑过渡 */
.tl-items {
  transition:max-height 0.3s cubic-bezier(0.25,0.8,0.25,1), opacity 0.25s ease;
  overflow:hidden;
}
.form-card {
  transition:max-height 0.35s cubic-bezier(0.25,0.8,0.25,1), opacity 0.3s ease, padding 0.3s ease;
}
.time-setup, .time-running, .time-expired {
  transition:opacity 0.3s ease, transform 0.3s cubic-bezier(0.25,0.8,0.25,1);
}
.plan-progress-fill {
  transition:width 0.5s cubic-bezier(0.25,0.8,0.25,1) !important;
}

/* 5. 倒计时 — 仅变动数字跳动 */
.countdown-char {
  display:inline-block; transition:transform 0.15s ease;
}
.char-changed {
  animation:charBounce 0.35s cubic-bezier(0.34,1.56,0.64,1);
}
@keyframes charBounce {
  0% { transform:translateY(-3px) scale(1.15); color:#fff; }
  100% { transform:translateY(0) scale(1); }
}
/* 训练步骤悬浮 */
.step {
  transition:transform 0.2s cubic-bezier(0.25,0.8,0.25,1), box-shadow 0.2s ease !important;
}
.step:hover {
  transform:translateY(-3px) !important;
  box-shadow:0 8px 24px rgba(0,210,255,0.2), 0 0 36px rgba(0,210,255,0.06) !important;
}

/* 6. 弹窗入场 */
.picker-overlay {
  animation:overlayFadeIn 0.25s ease-out;
}
@keyframes overlayFadeIn {
  from { background:rgba(0,0,0,0); }
  to   { background:rgba(0,0,0,0.75); }
}
.picker-card {
  animation:modalSlideUp 0.35s cubic-bezier(0.34,1.56,0.64,1);
}
@keyframes modalSlideUp {
  from { opacity:0; transform:translateY(40px) scale(0.95); }
  to   { opacity:1; transform:translateY(0) scale(1); }
}
.player-overlay {
  animation:overlayFadeIn 0.2s ease-out;
}
.player-card {
  animation:modalSlideUp 0.3s cubic-bezier(0.34,1.56,0.64,1);
}

/* ── 动画降级：系统偏好 或 低端设备 ── */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
[data-reduced-motion] *,
[data-reduced-motion] *::before,
[data-reduced-motion] *::after {
  animation-duration: 0.01ms !important;
  animation-iteration-count: 1 !important;
  transition-duration: 0.01ms !important;
}
/* 保留必要交互反馈 */
[data-reduced-motion] .btn-checkin:active,
[data-reduced-motion] .ftag:active,
[data-reduced-motion] .step:active {
  opacity: 0.85;
}
/* 低端机关闭昂贵光效 */
[data-reduced-motion] .cyber-scanlines,
[data-reduced-motion] .cyber-scanlines::before,
[data-reduced-motion] .cyber-scanlines::after {
  display: none;
}
[data-reduced-motion] .card,
[data-reduced-motion] .form-card,
[data-reduced-motion] .picker-card,
[data-reduced-motion] .picker-item,
[data-reduced-motion] .step,
[data-reduced-motion] .score-item {
  box-shadow: none !important;
}
[data-reduced-motion] .plr-arc,
[data-reduced-motion] .plr-core {
  display: none;
}
</style>

<style>
[data-theme="white"] .form-card { background:#fff; border-color:#2563eb; box-shadow:0 4px 20px rgba(0,0,0,0.06); }
[data-theme="white"] .form-title { color:#1a1a2e; }
[data-theme="white"] .form-label { color:#1f2937; font-size:13px; }
[data-theme="white"] .form-input { background:#f9fafb; border-color:#e5e7eb; color:#1a1a2e; }
[data-theme="white"] .form-textarea { background:#f9fafb; border-color:#e5e7eb; color:#1a1a2e; }
[data-theme="white"] .form-input.short { background:#fff; }
[data-theme="white"] .ftag { background:#f3f4f6; color:#374151; border-color:#e5e7eb; }
[data-theme="white"] .ftag.on { background:#2563eb; border-color:#2563eb; color:#fff; }
[data-theme="white"] .form-unit { color:#1f2937; background:#f3f4f6; border-color:#d1d5db; }
[data-theme="white"] .form-inline .form-unit { color:#1f2937; }
[data-theme="white"] .form-del { color:#9ca3af; }
[data-theme="white"] .form-del:active { color:#ef4444; }
[data-theme="white"] .btn-checkin { background:linear-gradient(135deg,#2563eb,#1d4ed8); }
.editor-list::-webkit-scrollbar { display:none; width:0; height:0; }
</style>
