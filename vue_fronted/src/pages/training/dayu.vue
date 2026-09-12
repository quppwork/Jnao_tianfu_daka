<template>
  <view class="phone">
    <!-- 顶栏 -->
    <view class="topbar">
      <view class="brand">
        <view class="logo" />
        <view>
          <text class="t1">大宇智能体</text>
          <text class="t2">DAYU · 今日通关挑战</text>
        </view>
      </view>
      <view class="top-right">
        <view
          v-if="devToolsAvailable"
          class="nav-dev"
          :class="{ active: devMode }"
          @click.stop="toggleDevMode"
        >{{ devMode ? 'DEV ✓' : 'DEV' }}</view>
        <view class="chip-g">{{ chipText }}</view>
      </view>
    </view>

    <!-- 开发者面板（对齐旧版 training/index） -->
    <view v-if="devMode" class="dev-panel">
      <text class="dev-panel-label">🔧 开发者测试</text>
      <view v-if="devStatusText" class="dev-status"><text>{{ devStatusText }}</text></view>
      <view v-if="usageLine" class="dev-status"><text>{{ usageLine }}</text></view>
      <text class="dev-section-label">今日操作</text>
      <view class="dev-actions">
        <view class="dev-action primary" @click="devResetToday"><text>🔄 重置今日</text></view>
        <view class="dev-action" @click="devResetTimer()"><text>⏱ 重置计时</text></view>
        <view class="dev-action" @click="devSimulateExpire"><text>⏰ 模拟结束</text></view>
      </view>
      <text class="dev-section-label">日切 / 时间</text>
      <view class="dev-actions">
        <view class="dev-action" @click="devSimulate4am"><text>🌙 模拟4点</text></view>
        <view class="dev-action" @click="devGoNextDay"><text>🌅 新一天</text></view>
        <view class="dev-action" @click="devResetClockAction"><text>🕐 回归实际</text></view>
      </view>
      <text class="dev-section-label">进度 / 内容</text>
      <view class="dev-actions">
        <view class="dev-action" @click="devResetMainLine"><text>↩ 回主线A</text></view>
        <view class="dev-action" @click="devRefreshAi"><text>🤖 刷新 AI</text></view>
      </view>
      <text class="dev-section-label">危险操作</text>
      <view class="dev-actions">
        <view class="dev-action danger" @click="devClearAll"><text>🗑 清空历史</text></view>
        <view class="dev-action danger" @click="devResetTalentAction"><text>🧬 重置天赋</text></view>
      </view>
      <text class="dev-panel-hint">重置今日 = 删今日方案与计时 · 需后端 JNAO_DEV_MODE=1</text>
    </view>

    <!-- 需测评 -->
    <view v-if="phase === 'need_assessment'" class="block">
      <view class="dayu">
        <view class="bear" />
        <view class="bubble"><text class="b">需要先完成天赋测评</text>，再回来生成今日方案。</view>
      </view>
      <view class="goPlan" @click="goTalent">去测评</view>
    </view>

    <!-- Step1：选时长 -->
    <view v-else-if="phase === 'setup'" class="block">
      <view class="tpick">
        <view class="tt">
          <text>⏰ 今天练多久？</text>
          <text class="st8">第 1 步 · 选时长</text>
        </view>
        <text class="big">{{ fmtClock(mins) }}</text>
        <text class="cap">选多久，就排多少</text>
        <view class="quick">
          <view
            v-for="p in presets"
            :key="p.m"
            class="q"
            :class="{ on: mins === p.m }"
            @click="mins = p.m"
          >{{ p.label }}</view>
        </view>
        <view class="step">
          <view class="col">
            <view class="round" @click="adj(-60)">−</view>
            <text class="lab">减1小时</text>
          </view>
          <view class="col">
            <text class="val">{{ Math.floor(mins / 60) }}小时 {{ mins % 60 }}分</text>
          </view>
          <view class="col">
            <view class="round" @click="adj(60)">＋</view>
            <text class="lab">加1小时</text>
          </view>
        </view>
        <view class="step" style="margin-top:4px">
          <view class="col">
            <view class="round" @click="adj(-10)">−</view>
            <text class="lab">减10分钟</text>
          </view>
          <view class="col" />
          <view class="col">
            <view class="round" @click="adj(10)">＋</view>
            <text class="lab">加10分钟</text>
          </view>
        </view>
      </view>
      <view class="goPlan" :class="{ dim: scheduleBusy }" @click="genPlan">
        {{ scheduleBusy ? '排课中…' : '生成今日挑战' }}
        <text class="sub">按 {{ Math.floor(mins / 60) }} 小时 {{ mins % 60 }} 分排课</text>
      </view>
      <view class="dayu">
        <view class="bear" />
        <view class="bubble"><text class="b">练多久，排多少关。</text>按所选时长由后端真实排课。</view>
      </view>
    </view>

    <!-- Step2：确认方案 -->
    <view v-else-if="phase === 'confirm'" class="block">
      <view class="gate">
        <view class="gt">
          <text>🏮 今日通关挑战</text>
          <text class="day">{{ chipText }}</text>
        </view>
        <view class="cnt">
          <text class="cnt-b">{{ items.length }}</text>
          <text class="cnt-s">个技能任务</text>
          <text class="cnt-m">{{ gateMeta }}</text>
        </view>
        <view v-for="(it, i) in displayItems" :key="it.id || i" class="gitem" :class="{ opt: it._elective }">
          <view class="n">{{ it._elective ? '选' : String(i + 1) }}</view>
          <text class="gn">{{ gateItemLabel(it) }}</text>
          <text class="st">{{ it._status }}</text>
        </view>

        <!-- 选修开关：对齐演示稿视觉 + 旧版 toggleElectiveItem -->
        <view v-if="plan?.plan_id" class="opts">
          <text class="ot">{{ electiveBoxTitle }}</text>
          <view
            v-for="es in electiveSkills"
            :key="es.skill"
            class="opt"
            :class="{ on: es.inPlan }"
          >
            <view class="opt-main">
              <view class="opt-text">
                <text class="on_name">{{ es.label }}</text>
                <text class="od">{{ es.desc }}</text>
                <text v-if="es.inPlan && es.rankCN" class="opt-tip">已置顶为第 {{ es.rankCN }} 关 √</text>
              </view>
              <view
                class="sw"
                :class="{ on: es.inPlan, dim: electiveBusy }"
                @click="toggleElective(es.skill)"
              >
                <view class="sw-knob" />
              </view>
            </view>
          </view>
        </view>
      </view>
      <view class="confirm" :class="{ dim: confirmBusy }" @click="confirmPlan">
        {{ confirmBusy ? '开启中…' : '确认 · 开启今日挑战' }}
        <text class="sub">今日 {{ fmtClock(plannedMins) }} · 打卡后不可再改</text>
      </view>
      <view class="editline">
        <text @click="phase = 'setup'">↩ 重选时长</text>
        <text
          class="edit-muted"
          :class="{ 'edit-on': canCustomizePlan }"
          @click="openPlanEditor"
        >编辑方案</text>
      </view>
    </view>

    <!-- Step3：闯关地图 -->
    <view v-else class="block">
      <view class="plan2">
        <view class="ph">
          <text class="pt">今日修炼挑战</text>
          <text class="chip-gold">{{ phase === 'expired' ? '已结束' : '已确认 ✓' }}</text>
        </view>

        <!-- 紧凑倒计时：嵌在演示卡结构里，不另起大块 -->
        <view class="timer-row" :class="{ expired: phase === 'expired' }">
          <view class="timer-row-main">
            <text class="timer-lab">{{ phase === 'expired' ? '今日训练' : '剩余时间' }}</text>
            <text class="timer-val">{{ countdownLabel }}</text>
          </view>
          <text class="timer-sub">
            {{ phase === 'expired' ? '时长已到 · 音视频锁定 · 仍可补打卡' : `计划 ${plannedDurationLabel}` }}
          </text>
          <view v-if="phase === 'running' && plannedDurationSec > 0" class="timer-track">
            <view class="timer-fill" :style="{ width: timerRemainPct + '%' }" />
          </view>
        </view>

        <view class="count">
          <text class="cnt-b">{{ items.length }}</text>
          <text class="cnt-s">个技能任务</text>
          <text class="cnt-m">完成当前任务解锁新任务</text>
        </view>
        <view class="bar"><view class="bar-i" :style="{ width: progressPct + '%' }" /></view>

        <!-- 演示稿能量塔 -->
        <view class="t9in">
          <view class="t9h">
            <text class="t9t">能量塔</text>
            <text class="t9stage">{{ towerStageLabel }}</text>
          </view>
          <view class="t9segs">
            <view
              v-for="(seg, si) in towerSegs"
              :key="si"
              class="t9seg"
              :class="seg"
            />
          </view>
        </view>
      </view>

      <view class="dayu">
        <view class="bear" />
        <view class="bubble">
          <text class="b">{{ phase === 'expired' ? '计时已结束' : '先过当前关' }}</text>
          {{ phase === 'expired' ? '，音视频已锁定，仍可补打卡。' : '，再继续下一关。点卡片可播放或打卡。' }}
        </view>
      </view>

      <view
        v-for="(it, i) in displayItems"
        :key="it.id || i"
        class="stage2"
        :class="it._state"
        :style="i === 0 ? 'margin-top:26px' : ''"
      >
        <view class="orb">{{ it._state === 'locked' ? '🔒' : (skillMeta(it._skill).emoji) }}</view>
        <view class="lv-card">
          <view class="simg">
            <video
              v-if="it.video_url && inlineVideoId === String(it.id) && inlineVideoSrc"
              class="simg-video"
              :src="inlineVideoSrc"
              controls
              autoplay
              :poster="skillMeta(it._skill).img"
              @timeupdate="onMediaTime"
              @ended="onMediaEnded"
            />
            <image
              v-else
              class="simg-poster"
              :src="skillMeta(it._skill).img"
              mode="aspectFill"
            />
            <view v-if="inlineVideoId !== String(it.id)" class="simg-shade" />
            <text class="slv">任务 {{ i + 1 }} / {{ items.length }} · {{ it._status }}</text>
            <text class="smj">秘籍 · {{ skillMeta(it._skill).mj }}</text>
            <view class="sname">
              <text class="sn">{{ it._skill }}</text>
              <text v-if="it._done" class="tag">已完成</text>
            </view>
            <view
              v-if="it.video_url && inlineVideoId !== String(it.id) && it._state !== 'locked' && !isMediaLocked"
              class="simg-tap"
              @click="openMedia(it, 'video')"
            >
              <text class="simg-tap-ic">▶</text>
              <text class="simg-tap-t">点此播放秘籍剧情</text>
            </view>
            <view
              v-else-if="isMediaLocked && it._state !== 'locked' && inlineVideoId !== String(it.id)"
              class="simg-tap media-locked"
            >
              <text class="simg-tap-ic">🔒</text>
              <text class="simg-tap-t">时长已到 · 音视频已锁定</text>
            </view>
          </view>
          <view class="sbody">
            <text class="ssub">{{ it.duration_min ? `约${it.duration_min}分钟` : '按方案训练' }}{{ it._elective ? ' · 选修' : '' }}</text>
            <view class="skl">
              <view class="skl-h">
                <text>⚡ 进度 · {{ it._skill }}</text>
                <text class="pct" :class="{ zero: !it._pct }">{{ it._pct }}%</text>
              </view>
              <view class="skl-bar"><view class="skl-fill" :style="{ width: it._pct + '%' }" /></view>
            </view>
            <view class="weapon" :class="{ 'media-locked': isMediaLocked && it._state !== 'locked' }" @click="openMedia(it, 'train')">
              <view class="ic">{{ isMediaLocked && it._state !== 'locked' ? '🔒' : '▶' }}</view>
              <view>
                <text class="wb">{{ weaponTitle(it) }}</text>
                <text class="ws">{{ weaponSub(it) }}</text>
              </view>
            </view>
            <view class="vids">
              <view
                class="vid mj"
                :class="{ disabled: it._state === 'locked' || !it.video_url || isMediaLocked }"
                @click="openMedia(it, 'video')"
              >
                <text>📜</text>
                <view>
                  <text class="vb">秘籍剧情</text>
                  <text class="vs">{{ isMediaLocked ? '已锁定' : (it.video_url ? '配套讲解视频' : '暂无视频') }}</text>
                </view>
              </view>
              <view class="vid zd" @click="openCheckin(it)">
                <text>✅</text>
                <view>
                  <text class="vb">过关指导</text>
                  <text class="vs">{{ guideSub(it) }}</text>
                </view>
              </view>
            </view>
          </view>
        </view>
      </view>
    </view>

    <!-- 底栏 -->
    <view class="foot">
      <view v-for="tab in tabs" :key="tab.key" class="fi" :class="{ on: tab.key === 'train' }" @click="switchMainTab(tab.path)">
        <image class="fic" :src="tab.icon" mode="aspectFit" />
        <text>{{ tab.label }}</text>
      </view>
    </view>

    <!-- 音频迷你播放器（视频在卡片内播） -->
    <view v-if="mediaOpen" class="overlay audio-overlay">
      <view class="audio-mask" @click="closeMedia" />
      <view class="audio-sheet" @click.stop>
        <view class="audio-handle" />
        <view class="audio-head">
          <image class="audio-cover" :src="audioCover" mode="aspectFill" />
          <view class="audio-meta">
            <text class="audio-title">{{ mediaTitle }}</text>
            <text class="audio-sub">{{ audioStatusText }}</text>
          </view>
        </view>

        <view class="audio-progress">
          <view class="audio-bar">
            <view class="audio-fill" :style="{ width: audioUiPct + '%' }" />
            <view class="audio-knob" :style="{ left: audioUiPct + '%' }" />
          </view>
          <view class="audio-times">
            <text>{{ formatMediaTime(audioUiCurrent) }}</text>
            <text class="audio-pct">已听 {{ audioListenPctLabel }}</text>
            <text>{{ formatMediaTime(audioUiDuration) }}</text>
          </view>
        </view>

        <view class="audio-controls">
          <view class="ac-side" @click="stopAudio">
            <text class="ac-ic">⏹</text>
            <text class="ac-lab">停止</text>
          </view>
          <view class="ac-main" :class="{ on: audioPlaying }" @click="toggleAudio">
            <text class="ac-main-ic">{{ audioPlaying ? '⏸' : '▶' }}</text>
          </view>
          <view class="ac-side" @click="closeMedia">
            <text class="ac-ic">✕</text>
            <text class="ac-lab">结束</text>
          </view>
        </view>

        <text class="audio-tip">打卡看训练音频进度 · 满 90% 后可过关</text>
      </view>
    </view>

    <!-- 打卡弹层 -->
    <view v-if="checkinOpen" class="overlay" @click="closeCheckin">
      <view class="sheet checkin-sheet" @click.stop>
        <text class="sheet-t">{{ checkinEditing ? '修改打卡' : '打卡' }} · {{ checkinSkill }}</text>
        <view class="field" @click.stop>
          <text class="fl">用时(分钟)</text>
          <input
            class="fi-input"
            type="digit"
            :value="form.time"
            placeholder="如：20"
            :focus="checkinFocus"
            @input="onFormInput('time', $event)"
            @click.stop
            @mousedown.stop
            @touchstart.stop
          />
        </view>
        <view v-if="showWord" class="field" @click.stop>
          <text class="fl">字数</text>
          <input
            class="fi-input"
            type="digit"
            :value="form.wordCount"
            placeholder="完成字数"
            @input="onFormInput('wordCount', $event)"
            @click.stop
            @mousedown.stop
            @touchstart.stop
          />
        </view>
        <view v-if="showAcc" class="field" @click.stop>
          <text class="fl">准确率(%)</text>
          <input
            class="fi-input"
            type="digit"
            :value="form.accuracy"
            placeholder="0-100"
            @input="onFormInput('accuracy', $event)"
            @click.stop
            @mousedown.stop
            @touchstart.stop
          />
        </view>
        <view class="field" @click.stop>
          <text class="fl">备注</text>
          <input
            class="fi-input"
            type="text"
            :value="form.note"
            placeholder="可选"
            @input="onFormInput('note', $event)"
            @click.stop
            @mousedown.stop
            @touchstart.stop
          />
        </view>
        <view class="field" @click.stop>
          <text class="fl">态度 {{ form.attitude }}%</text>
          <slider :value="form.attitude" min="0" max="100" @changing="onAttitude" @change="onAttitude" />
        </view>
        <view class="btn block" :class="{ dim: checkinBusy }" @click="submitCheckin">
          {{ checkinSubmitLabel }}
        </view>
        <view class="link" @click="closeCheckin">取消</view>
      </view>
    </view>

    <!-- 编辑方案：替换必修技能（对齐旧版 customizePlan，片选适配大宇风） -->
    <view v-if="showPlanEditor" class="overlay editor-overlay" @click="closePlanEditor">
      <view class="sheet editor-sheet" @click.stop>
        <view class="editor-handle" />
        <text class="sheet-t">编辑今日方案</text>
        <text class="editor-hint">仅可改一次 · 打卡后不可再改 · 选修请用上方开关</text>
        <scroll-view v-if="editableItems.length" scroll-y class="editor-scroll">
          <view
            v-for="(item, idx) in editableItems"
            :key="item.id"
            class="editor-card"
          >
            <view class="editor-card-h">
              <text class="editor-label">必修 {{ idx + 1 }}</text>
              <text class="editor-cur">{{ editorDisplayTitle(item) }}</text>
            </view>
            <view class="editor-chips">
              <view
                v-for="sk in allReplacableSkills"
                :key="sk"
                class="editor-chip"
                :class="{ on: editorSkillName(item) === sk }"
                @click="pickEditorSkill(idx, sk)"
              >
                <text class="ec-mj">{{ skillMeta(sk).mj }}</text>
                <text class="ec-sk">{{ sk }}</text>
              </view>
            </view>
          </view>
        </scroll-view>
        <view v-else class="editor-empty">无可编辑的训练项目</view>
        <view v-if="editableItems.length" class="editor-actions">
          <view class="editor-btn ghost" @click="closePlanEditor">取消</view>
          <view class="editor-btn primary" :class="{ dim: customizeBusy }" @click="confirmCustomize">
            {{ customizeBusy ? '提交中…' : '确认修改' }}
          </view>
        </view>
        <view v-else class="link" @click="closePlanEditor">关闭</view>
      </view>
    </view>

    <!-- 编辑方案二次确认 -->
    <view v-if="showCustomizeConfirm" class="overlay editor-overlay" @click="cancelCustomizeConfirm">
      <view class="sheet editor-sheet editor-confirm-sheet" @click.stop>
        <text class="sheet-t">确认修改方案</text>
        <text class="editor-confirm-text">每个训练日仅可修改一次，打卡后不可再改。修改后将按所选技能重新匹配训练内容，请谨慎操作。确定继续吗？</text>
        <view class="editor-actions">
          <view class="editor-btn ghost" @click="cancelCustomizeConfirm">取消</view>
          <view class="editor-btn primary" :class="{ dim: customizeBusy }" @click="doCustomize">
            {{ customizeBusy ? '提交中…' : '确定修改' }}
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
/**
 * 今日修炼（大宇新版 UI + 老版训练链路）
 * 选时长 → POST /api/training/schedule → 确认闸门 → setTrainingWindow → 闯关/打卡
 */
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import {
  requirePageAuth,
  ensureChildUser,
  resolveTrainingStreamUrl,
  fetchTrainingEntry,
  fetchTrainingToday,
  scheduleTrainingPlan,
  setTrainingWindow,
  clearTrainingWindow,
  markPlanMediaExhausted,
  submitTrainingCheckin,
  updateTrainingCheckin,
  postTrainingWatchProgress,
  fetchTodayCheckins,
  fetchDevTrainingStatus,
  devResetTodayTraining,
  devResetTrainingProgress,
  devResetAllTraining,
  devSimulateNextDay,
  devSimulate4amCutoff,
  devResetTalent,
  devResetClock,
  refreshTrainingReport,
  toggleElectiveItem,
  customizePlan,
  fetchUsageSummary,
  formatTokenCount,
} from '@/utils/userApi.js'
import { ensureTalentState, hasEffectiveTalent, clearTalentState, refreshTalentState } from '@/utils/talentState.js'
import { resolvePlanItemSkill, ELECTIVE_ABILITIES } from '@/utils/trainingCardDisplay.js'
import { MAIN_TABS, switchMainTab } from '@/utils/mainTabs.js'
import { getDevMode, isDevToolsAvailable, setDevMode } from '@/utils/devMode.js'

const MIN = 20
const MAX = 720
const tabs = MAIN_TABS

const presets = [
  { m: 30, label: '30分钟' },
  { m: 60, label: '1小时' },
  { m: 120, label: '2小时' },
  { m: 240, label: '4小时' },
  { m: 360, label: '6小时' },
  { m: 480, label: '8小时' },
  { m: 600, label: '10小时' },
  { m: 40, label: '40分钟' },
]

const SKILL_META = {
  超脑阅读: { emoji: '📖', img: '/static/dayu/assets/miji/mj-cnyd.jpg', mj: '吸照大法' },
  影像追忆: { emoji: '🧠', img: '/static/dayu/assets/miji/mj-yxzj.jpg', mj: '无相神功' },
  扫描速记: { emoji: '🌸', img: '/static/dayu/assets/miji/mj-gxzy.jpg', mj: '昙花宝典' },
  极速运算: { emoji: '⚡', img: '/static/dayu/assets/miji/mj-jsys.jpg', mj: '太极神功' },
  极速学习: { emoji: '🚀', img: '/static/dayu/assets/miji/mj-bddt.jpg', mj: '九阳绝学' },
  难题专练: { emoji: '🎯', img: '/static/dayu/assets/miji/sys-contest.jpg', mj: '难题专练' },
  文科扫书: { emoji: '📚', img: '/static/dayu/assets/miji/mj-cnyd.jpg', mj: '文科扫书' },
  理科扫书: { emoji: '🔬', img: '/static/dayu/assets/miji/sys-contest.jpg', mj: '理科扫书' },
  高效作业: { emoji: '✏️', img: '/static/dayu/assets/miji/mj-yxdy.jpg', mj: '左右同搏' },
  多元感知: { emoji: '🎧', img: '/static/dayu/assets/miji/mj-tfsd.jpg', mj: '六感神剑' },
  感知力: { emoji: '🎧', img: '/static/dayu/assets/miji/mj-tfsd.jpg', mj: '六感神剑' },
  开口窍: { emoji: '🗣️', img: '/static/dayu/assets/miji/mj-scyj.jpg', mj: '心门九剑' },
  精力恢复: { emoji: '🍃', img: '/static/dayu/assets/miji/mj-jlhf.jpg', mj: '呼吸打坐' },
}
const DEFAULT_META = { emoji: '⚔️', img: '/static/dayu/assets/miji/mj-tfsd.jpg', mj: '今日修炼' }

const mins = ref(40)
const plan = ref(null)
const phase = ref('setup') // setup | confirm | running | expired | need_assessment
const talentLabel = ref('')
const dayNum = ref(1)
const scheduleBusy = ref(false)
const confirmBusy = ref(false)
const electiveBusy = ref(false)
const customizeBusy = ref(false)
const showPlanEditor = ref(false)
const showCustomizeConfirm = ref(false)
const editorSkills = ref([])
const pendingCustomize = ref(null)
const allReplacableSkills = ['超脑阅读', '影像追忆', '扫描速记', '极速运算', '极速学习']

/** 训练窗倒计时（仅 UI / 本地 tick，不改媒体锁等规则） */
const remainingSeconds = ref(0)
const plannedDurationSec = ref(0)
let timerEndAtMs = 0
let timerTickId = null

const devToolsAvailable = isDevToolsAvailable()
const devMode = ref(getDevMode())
const devStatusText = ref('')
const usageLine = ref('')

const mediaOpen = ref(false)
const mediaSrc = ref('')
const mediaKind = ref('audio')
const mediaTitle = ref('')
const audioPlaying = ref(false)
const audioUiCurrent = ref(0)
const audioUiDuration = ref(0)
const audioCover = ref('/static/dayu/assets/miji/mj-tfsd.jpg')
const inlineVideoId = ref('')
const inlineVideoSrc = ref('')
let innerAudio = null
let activeWatchItem = null
let watchTimer = null
let mediaPeakSec = 0
let mediaDurationSec = 0
/** 打开音频后待 seek 的续播秒数（停止/结束再进从进度续播） */
let audioResumePendingSec = 0

const audioUiPct = computed(() => {
  const d = audioUiDuration.value
  if (d <= 0) return 0
  return Math.max(0, Math.min(100, (audioUiCurrent.value / d) * 100))
})
const audioListenPctLabel = computed(() => {
  const d = audioUiDuration.value || mediaDurationSec
  const w = Math.max(audioUiCurrent.value, mediaPeakSec)
  if (d <= 0) return '0%'
  return `${Math.min(100, Math.round((w / d) * 1000) / 10)}%`
})
const audioStatusText = computed(() => {
  if (audioPlaying.value) return '训练音频播放中'
  if (audioUiCurrent.value > 0) return '已暂停 · 可继续播放'
  return '准备播放训练音频'
})

function formatMediaTime(sec) {
  const n = Math.max(0, Math.floor(Number(sec) || 0))
  const m = Math.floor(n / 60)
  const s = n % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

const checkinOpen = ref(false)
const checkinFocus = ref(false)
const checkinItemId = ref(null)
const checkinSkill = ref('')
const checkinBusy = ref(false)
/** item_id -> 今日打卡记录（二次打开回填 / 修改） */
const checkinByItemId = ref({})
const form = reactive({ time: '', wordCount: '', accuracy: '', note: '', attitude: 60 })

const showWord = computed(() => ['超脑阅读', '影像追忆', '扫描速记'].includes(checkinSkill.value))
const showAcc = computed(() => checkinSkill.value === '影像追忆')
const checkinEditing = computed(() => {
  const id = checkinItemId.value
  if (id == null) return false
  return !!checkinByItemId.value[String(id)]
})
const checkinSubmitLabel = computed(() => {
  if (checkinBusy.value) return '提交中…'
  return checkinEditing.value ? '保存修改' : '提交打卡'
})

const items = computed(() => plan.value?.items || [])
const plannedMins = computed(() => Number(plan.value?.planned_minutes || mins.value) || mins.value)
const chipText = computed(() => `${talentLabel.value || '学员'} · 第 ${dayNum.value || 1} 天`)
const countdownLabel = computed(() => formatCountdown(remainingSeconds.value))
const plannedDurationLabel = computed(() => {
  const sec = plannedDurationSec.value > 0
    ? plannedDurationSec.value
    : Math.max(0, plannedMins.value) * 60
  return formatCountdown(sec)
})
const timerRemainPct = computed(() => {
  const total = plannedDurationSec.value
  if (total <= 0) return 0
  return Math.max(0, Math.min(100, (remainingSeconds.value / total) * 100))
})

/** 音视频锁定：计时结束 / 后端 media_exhausted（DEV 可跳过）；打卡仍可用至训练日截止 */
const isMediaLocked = computed(() => {
  if (devMode.value) return false
  if (phase.value === 'expired') return true
  if (plan.value?.media_exhausted) return true
  return false
})

/** 九段能量塔：优先用方案 overall_tier，缺省 1 */
const overallTier = computed(() => {
  const n = Number(plan.value?.overall_tier || 1)
  return Math.max(1, Math.min(9, Number.isFinite(n) ? n : 1))
})
const TOWER_PERIODS = [
  { duan: '一段', period: '铸基期' },
  { duan: '二段', period: '铸基期' },
  { duan: '三段', period: '铸基期' },
  { duan: '四段', period: '开光期' },
  { duan: '五段', period: '开光期' },
  { duan: '六段', period: '开光期' },
  { duan: '七段', period: '通神期' },
  { duan: '八段', period: '通神期' },
  { duan: '九段', period: '通神期' },
]
const towerStageLabel = computed(() => {
  const meta = TOWER_PERIODS[overallTier.value - 1] || TOWER_PERIODS[0]
  return `当前 ${meta.duan} · ${meta.period}`
})
const towerSegs = computed(() => {
  const cur = overallTier.value
  return Array.from({ length: 9 }, (_, i) => {
    const n = i + 1
    if (n < cur) return 'lit'
    if (n === cur) return 'half'
    return ''
  })
})

function formatCountdown(totalSec) {
  const sec = Math.max(0, Math.floor(Number(totalSec) || 0))
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  if (h > 0) {
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function clearTimerTick() {
  if (timerTickId != null) {
    clearInterval(timerTickId)
    timerTickId = null
  }
}

function expireLocalTimer(silent = false) {
  clearTimerTick()
  remainingSeconds.value = 0
  timerEndAtMs = 0
  if (phase.value === 'running') phase.value = 'expired'
  // 立刻关掉正在播的音视频
  try { closeMedia() } catch (_) { /* ignore */ }
  if (plan.value) plan.value.media_exhausted = true
  ensureChildUser()
    .then((uid) => markPlanMediaExhausted(uid))
    .then((res) => {
      if (res?.data && plan.value) Object.assign(plan.value, res.data)
    })
    .catch(() => {})
  if (!silent) {
    uni.showToast({ title: '训练时长已到，音视频已锁定，仍可打卡', icon: 'none', duration: 2800 })
  }
}

function tickTimer() {
  if (!timerEndAtMs) {
    clearTimerTick()
    return
  }
  const left = Math.max(0, Math.ceil((timerEndAtMs - Date.now()) / 1000))
  remainingSeconds.value = left
  if (left <= 0) expireLocalTimer(false)
}

function startTimerTick() {
  clearTimerTick()
  if (phase.value !== 'running' || !timerEndAtMs) return
  tickTimer()
  if (phase.value === 'running' && remainingSeconds.value > 0) {
    timerTickId = setInterval(tickTimer, 1000)
  }
}

/** 从今日方案同步倒计时终点；running 时开本地 tick */
function syncTimerFromPlan(data) {
  const plannedMin = Number(data?.planned_minutes || mins.value) || 0
  if (plannedMin > 0) plannedDurationSec.value = plannedMin * 60

  const tp = data?.timer_phase
  if (tp === 'expired' || phase.value === 'expired') {
    clearTimerTick()
    remainingSeconds.value = 0
    timerEndAtMs = 0
    try { closeMedia() } catch (_) { /* ignore */ }
    return
  }

  if (tp === 'running' || phase.value === 'running') {
    const endIso = data?.timer_end_at
    const rem = Number(data?.timer_remaining_seconds)
    if (endIso) {
      const endMs = new Date(endIso).getTime()
      timerEndAtMs = Number.isFinite(endMs) ? endMs : 0
    } else if (Number.isFinite(rem) && rem > 0) {
      timerEndAtMs = Date.now() + rem * 1000
    } else if (plannedDurationSec.value > 0 && !timerEndAtMs) {
      timerEndAtMs = Date.now() + plannedDurationSec.value * 1000
    }

    if (!timerEndAtMs) {
      remainingSeconds.value = Math.max(0, Number.isFinite(rem) ? rem : plannedDurationSec.value)
      clearTimerTick()
      return
    }

    const left = Math.max(0, Math.ceil((timerEndAtMs - Date.now()) / 1000))
    remainingSeconds.value = left
    if (left <= 0) {
      expireLocalTimer(true)
      return
    }
    startTimerTick()
    return
  }

  clearTimerTick()
  timerEndAtMs = 0
  remainingSeconds.value = plannedDurationSec.value || plannedMin * 60
}

function onFormInput(key, e) {
  const v = e?.detail?.value ?? e?.target?.value ?? ''
  form[key] = v
}
function onAttitude(e) {
  form.attitude = Number(e?.detail?.value ?? 60) || 60
}
function closeCheckin() {
  checkinOpen.value = false
  checkinFocus.value = false
  checkinItemId.value = null
  checkinSkill.value = ''
}

function skillMeta(name) {
  return SKILL_META[name] || DEFAULT_META
}

function fmtClock(m) {
  const n = Math.max(0, Number(m) || 0)
  const h = Math.floor(n / 60)
  const mm = n % 60
  return `${String(h).padStart(2, '0')}:${String(mm).padStart(2, '0')}:00`
}

function adj(d) {
  mins.value = Math.max(MIN, Math.min(MAX, mins.value + d))
}

function skillOf(item) {
  if (!item) return ''
  const raw = item.instructions
  if (raw && typeof raw === 'object' && raw.skill) return String(raw.skill)
  if (typeof raw === 'string' && raw.trim().startsWith('{')) {
    try {
      const j = JSON.parse(raw)
      if (j.skill) return String(j.skill)
    } catch (_) { /* ignore */ }
  }
  return resolvePlanItemSkill(item) || item.title || '训练'
}

function isElective(item) {
  if (!item) return false
  if (item.item_type === 'elective' || item.item_type === 'perception') return true
  return ELECTIVE_ABILITIES.includes(skillOf(item))
}

function itemDone(item) {
  if (!item) return false
  if (item.checkin_status === 'done') return true
  return itemPct(item) >= 100
}

/** 与后端 is_item_media_complete 一致：有 audio_url 时只看音频进度 */
function itemNeedsAudioListen(item) {
  if (!item) return false
  if (item.item_type === 'perception' || item.item_type === 'placeholder') return false
  return !!item.audio_url
}

function audioWatchPct(item) {
  const wp = item?.watch_progress
  if (!wp || typeof wp !== 'object') return 0
  const audio = wp.audio && typeof wp.audio === 'object' ? wp.audio : null
  if (audio) return Math.max(0, Math.min(100, Number(audio.pct || 0)))
  return Math.max(0, Math.min(100, Number(wp.pct || 0)))
}

function itemPct(item) {
  if (!item) return 0
  if (item.checkin_status === 'done') return 100
  // 打卡门槛只看音频：展示也与门槛对齐，避免「视频 90% 却打不了卡」
  if (itemNeedsAudioListen(item)) return audioWatchPct(item)
  const wp = item.watch_progress
  if (!wp || typeof wp !== 'object') return 0
  const video = wp.video && typeof wp.video === 'object' ? wp.video : null
  const v = Number(video?.pct ?? 0)
  const a = Number(wp.pct || 0)
  return Math.max(0, Math.min(100, Math.max(a, v)))
}

function isListenReady(item) {
  if (!itemNeedsAudioListen(item)) return true
  return audioWatchPct(item) >= 90
}

function weaponSub(it) {
  if (it._state === 'locked') return '关卡逐个解锁'
  if (isMediaLocked.value) return '时长已到 · 音视频已锁定'
  if (it._done) return '已打卡，可回看训练'
  if (itemNeedsAudioListen(it)) {
    const p = audioWatchPct(it)
    if (p >= 90) return '训练音频已达 90%，可去「过关指导」打卡'
    return `听训练音频达 90% 可打卡（当前 ${p.toFixed(0)}%）`
  }
  if (it.video_url) return '播放训练视频'
  if (it.audio_url) return '播放训练音频'
  return '暂无媒体，可直接打卡'
}

function guideSub(it) {
  if (it._done) return '已完成 · 可再查看 / 修改'
  if (isMediaLocked.value) return '时长已到 · 仍可补打卡'
  if (itemNeedsAudioListen(it) && !isListenReady(it)) {
    return `听满 90% 后打卡（${audioWatchPct(it).toFixed(0)}%）`
  }
  return '提交打卡 · 记录今日完成'
}

function weaponTitle(it) {
  if (it._state === 'locked') return '🔒 先完成上一关'
  if (isMediaLocked.value) return '🔒 时长已到 · 不可再听看'
  if (it._done) return '再练一遍 / 查看'
  return '拔出超级武器 · 开始训练'
}

const firstActiveIdx = computed(() => {
  const list = items.value
  for (let i = 0; i < list.length; i++) {
    if (!itemDone(list[i])) return i
  }
  return list.length ? list.length - 1 : 0
})

const displayItems = computed(() => {
  const fa = firstActiveIdx.value
  return items.value.map((it, i) => {
    const done = itemDone(it)
    const pct = itemPct(it)
    let state = 'locked'
    let status = '待解锁'
    if (done) {
      state = 'done'
      status = '已完成 ✓'
    } else if (i === fa) {
      state = 'active'
      status = pct > 0 ? `进行中 · ${pct}%` : '当前任务'
    } else if (i < fa) {
      state = 'done'
      status = '已完成 ✓'
    }
    return {
      ...it,
      _skill: skillOf(it),
      _elective: isElective(it),
      _done: done,
      _pct: pct,
      _state: state,
      _status: status,
    }
  })
})

const gateMeta = computed(() => {
  const list = displayItems.value
  const elect = list.filter((i) => i._elective).length
  const core = list.length - elect
  return `必闯${core}关 · 选修${elect}关 · ≈${plannedMins.value}分钟`
})

const CN_NUM = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']

function parseItemInstructions(instructions) {
  if (instructions && typeof instructions === 'object') return instructions
  if (typeof instructions === 'string' && instructions.trim().startsWith('{')) {
    try { return JSON.parse(instructions) } catch (_) { /* ignore */ }
  }
  return {}
}

/** 确认闸门：多元感知 / 开口窍 开关（与旧版同一 API） */
const electiveSkills = computed(() => {
  const items = plan.value?.items || []
  const sorted = [...items].sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))

  function skillInPlan(skill) {
    return items.some((item) => parseItemInstructions(item.instructions).skill === skill)
  }
  function skillDurationMin(skill, fallback) {
    const item = items.find((i) => parseItemInstructions(i.instructions).skill === skill)
    return (item && item.duration_min) ? item.duration_min : fallback
  }
  function skillRank(skill) {
    const idx = sorted.findIndex((i) => parseItemInstructions(i.instructions).skill === skill)
    return idx >= 0 ? idx + 1 : 0
  }

  const ganDuration = skillDurationMin('感知力', 12)
  const kaiqiaoDuration = skillDurationMin('开口窍', 30)
  const list = [
    {
      skill: '感知力',
      label: '多元感知',
      inPlan: skillInPlan('感知力'),
      desc: `感知力音频训练 · 约${ganDuration}分钟`,
      rank: skillRank('感知力'),
    },
    {
      skill: '开口窍',
      label: '开口窍 🎬',
      inPlan: skillInPlan('开口窍'),
      desc: `视频训练 · 表达力开口练习 · 约${kaiqiaoDuration}分钟`,
      rank: skillRank('开口窍'),
    },
  ]
  return list.map((es) => ({
    ...es,
    rankCN: es.rank > 0 ? CN_NUM[Math.min(es.rank, CN_NUM.length - 1)] : '',
  }))
})

const electiveBoxTitle = computed(() => {
  const on = electiveSkills.value.filter((e) => e.inPlan)
  if (!on.length) return '🛠️ 选修 · 可开关置顶'
  const pinned = on.find((e) => e.rank === 1)
  if (pinned) return `🛠️ 选修 · 开了置顶第1关`
  return `🛠️ 选修 · 已开 ${on.length} 项`
})

function gateItemLabel(it) {
  const skill = it._skill || skillOf(it)
  const mj = skillMeta(skill).mj
  const dur = it.duration_min ? ` · 约${it.duration_min}分钟` : ''
  if (mj && mj !== skill && mj !== '今日修炼') return `${mj} · ${skill}${dur}`
  return `${skill}${dur}`
}

/** 可替换的必修项（未打卡、非选修；与旧版 editableItems 一致） */
const editableItems = computed(() => {
  const list = plan.value?.items || []
  return list.filter((i) => {
    if (i.checkin_status === 'done') return false
    if (isElective(i)) return false
    const inst = parseItemInstructions(i.instructions)
    if (inst.item_type === 'elective') return false
    if (inst.blocks_next === false) return false
    return true
  })
})

const canCustomizePlan = computed(() => !!plan.value?.can_customize_plan)

function editorSkillName(item) {
  const idx = editorSkills.value.findIndex((s) => s.startsWith(`${item.id}:`))
  if (idx >= 0) return editorSkills.value[idx].split(':')[1]
  return skillOf(item) || '训练'
}

function editorDisplayTitle(item) {
  const sk = editorSkillName(item)
  const mj = skillMeta(sk).mj
  if (mj && mj !== sk && mj !== '今日修炼') return `${mj} · ${sk}`
  return sk
}

function pickEditorSkill(itemIdx, skill) {
  const item = editableItems.value[itemIdx]
  if (!item || !skill) return
  editorSkills.value[itemIdx] = `${item.id}:${skill}`
}

function openPlanEditor() {
  if (electiveBusy.value || confirmBusy.value || customizeBusy.value) return
  if (!canCustomizePlan.value) {
    const reason = plan.value?.plan_customized
      ? '今日方案已编辑过，不可再次修改'
      : plan.value?.has_checkin
        ? '已有打卡记录，无法编辑方案'
        : '当前不可编辑方案'
    uni.showToast({ title: reason, icon: 'none' })
    return
  }
  editorSkills.value = editableItems.value.map((item) => {
    const sk = skillOf(item) || '训练'
    return `${item.id}:${sk}`
  })
  showPlanEditor.value = true
}

function closePlanEditor() {
  if (customizeBusy.value) return
  showPlanEditor.value = false
}

function cancelCustomizeConfirm() {
  if (customizeBusy.value) return
  showCustomizeConfirm.value = false
  pendingCustomize.value = null
}

function confirmCustomize() {
  if (customizeBusy.value) return
  const planId = plan.value?.plan_id
  if (!planId) {
    uni.showToast({ title: '方案不存在', icon: 'none' })
    return
  }
  const skills = editorSkills.value.map((s) => s.split(':')[1])
  if (!skills.length || skills.length !== editableItems.value.length) {
    uni.showToast({ title: '请为每项选择技能', icon: 'none' })
    return
  }
  pendingCustomize.value = { planId, skills }
  showCustomizeConfirm.value = true
}

async function doCustomize() {
  const c = pendingCustomize.value
  if (!c || customizeBusy.value) return
  customizeBusy.value = true
  try {
    const uid = await ensureChildUser()
    const data = await customizePlan(uid, c.planId, c.skills)
    showCustomizeConfirm.value = false
    showPlanEditor.value = false
    pendingCustomize.value = null
    applyPlan(data)
    phase.value = 'confirm'
    await hydrateCheckins(uid)
    uni.showToast({ title: '方案已更新', icon: 'none' })
  } catch (e) {
    const detail = e?.data?.detail || e?.message || '修改失败'
    const msg = Array.isArray(detail)
      ? detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
      : detail
    uni.showToast({ title: String(msg), icon: 'none', duration: 3000 })
  } finally {
    customizeBusy.value = false
  }
}

async function toggleElective(skill) {
  if (electiveBusy.value || confirmBusy.value) return
  if (!plan.value?.plan_id) {
    uni.showToast({ title: '方案不存在', icon: 'none' })
    return
  }
  const row = electiveSkills.value.find((e) => e.skill === skill)
  const inPlan = !!row?.inPlan
  const action = inPlan ? 'remove' : 'add'
  electiveBusy.value = true
  try {
    const uid = await ensureChildUser()
    const data = await toggleElectiveItem(uid, plan.value.plan_id, skill, action)
    // 接口返回今日方案；保持确认闸门
    applyPlan(data)
    phase.value = 'confirm'
    await hydrateCheckins(uid)
    uni.showToast({
      title: inPlan ? `已移除 ${row?.label || skill}` : `已添加 ${row?.label || skill}`,
      icon: 'none',
    })
  } catch (e) {
    const msg = e?.data?.detail || e?.message || '操作失败'
    uni.showToast({
      title: Array.isArray(msg) ? msg.map((d) => d.msg || JSON.stringify(d)).join('; ') : String(msg),
      icon: 'none',
      duration: 3000,
    })
  } finally {
    electiveBusy.value = false
  }
}

const progressPct = computed(() => {
  const list = items.value
  if (!list.length) return 4
  const done = list.filter(itemDone).length
  return Math.max(4, Math.round((done / list.length) * 100))
})

function formatWindowTime(ms) {
  const s = new Date(ms).toLocaleString('sv-SE', { timeZone: 'Asia/Shanghai' })
  const timePart = s.split(' ')[1] || '00:00:00'
  const [hh, mm, ss = '00'] = timePart.split(':')
  return `${hh}:${mm}:${ss}`
}

function applyPlan(data) {
  plan.value = data
  const tp = data?.timer_phase
  if (data?.day_locked) {
    phase.value = 'setup'
  } else if (tp === 'running') {
    phase.value = 'running'
  } else if (tp === 'expired') {
    phase.value = 'expired'
  } else if (data?.plan_id && (data.items || []).length) {
    const started = (data.items || []).some(
      (i) => i.checkin_status === 'done' || itemPct(i) > 0,
    )
    phase.value = started ? 'running' : 'confirm'
  } else {
    phase.value = 'setup'
  }
  if (Number(data?.planned_minutes) >= MIN) mins.value = Number(data.planned_minutes)
  if (data?.training_day_number || data?.lesson_day) {
    dayNum.value = data.training_day_number || data.lesson_day || 1
  }
  syncTimerFromPlan(data)
}

async function hydrateCheckins(uid) {
  try {
    const records = await fetchTodayCheckins(uid)
    const map = {}
    for (const r of records || []) {
      if (r.item_id == null) continue
      map[String(r.item_id)] = r
    }
    checkinByItemId.value = map
    if (plan.value?.items) {
      for (const it of plan.value.items) {
        if (map[String(it.id)]) it.checkin_status = 'done'
      }
    }
  } catch (_) { /* ignore */ }
}

function fillCheckinFormFromRecord(record, fallbackItem) {
  const card = Array.isArray(record?.cards) && record.cards.length
    ? record.cards[0]
    : null
  form.time = String(
    card?.time
    ?? record?.time_spent
    ?? (fallbackItem?.duration_min != null ? fallbackItem.duration_min : '')
    ?? '',
  )
  form.wordCount = String(card?.wordCount ?? card?.word_count ?? '')
  form.accuracy = String(card?.accuracy ?? '')
  form.note = String(card?.note ?? record?.note ?? '')
  const att = Number(record?.attitude_pct)
  form.attitude = Number.isFinite(att) && att > 0 ? att : 60
}

async function bootstrap() {
  const auth = await requirePageAuth('student')
  if (!auth) return
  const uid = await ensureChildUser()
  let needAssessment = false
  try {
    const talent = await ensureTalentState(uid)
    talentLabel.value = talent?.talent_tag || ''
    if (!hasEffectiveTalent(talent) || talent.needs_assessment) {
      const entry = await fetchTrainingEntry(uid).catch(() => null)
      if (!entry || entry.needs_assessment) needAssessment = true
      if (entry?.talent_tag) talentLabel.value = entry.talent_tag
    }
  } catch (_) {
    const entry = await fetchTrainingEntry(uid).catch(() => null)
    if (entry?.needs_assessment) needAssessment = true
    if (entry?.talent_tag) talentLabel.value = entry.talent_tag
  }

  if (needAssessment) {
    phase.value = 'need_assessment'
    return
  }

  const result = await fetchTrainingToday(uid, { skipAi: true })
  if (result.error === 'assessment') {
    phase.value = 'need_assessment'
    return
  }
  if (result.error) {
    uni.showToast({ title: result.message || '加载失败', icon: 'none' })
    return
  }
  applyPlan(result.data)
  if (result.data?.plan_id) await hydrateCheckins(uid)
}

/** 对应老页 startTrainingWithPrefer：只排课，不开计时 */
async function genPlan() {
  if (scheduleBusy.value) return
  if (mins.value < MIN) {
    uni.showToast({ title: `至少 ${MIN} 分钟`, icon: 'none' })
    return
  }
  scheduleBusy.value = true
  try {
    uni.showLoading({ title: '排课中' })
    const uid = await ensureChildUser()
    const result = await scheduleTrainingPlan(uid, mins.value)
    if (result.error) throw new Error(result.message || '排课失败')
    applyPlan(result.data)
    phase.value = 'confirm'
    await hydrateCheckins(uid)
    uni.showToast({ title: '方案已生成，请确认后开始', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '排课失败', icon: 'none' })
  } finally {
    uni.hideLoading()
    scheduleBusy.value = false
  }
}

/** 对应老页 confirmPlan：开计时窗后进闯关 */
async function confirmPlan() {
  if (confirmBusy.value || !plan.value?.plan_id) {
    uni.showToast({ title: '请先生成方案', icon: 'none' })
    return
  }
  confirmBusy.value = true
  try {
    uni.showLoading({ title: '开启中' })
    const uid = await ensureChildUser()
    const pm = Number(plan.value.planned_minutes || mins.value)
    const nowMs = Date.now()
    const endAt = nowMs + pm * 60 * 1000
    await setTrainingWindow(uid, formatWindowTime(nowMs), formatWindowTime(endAt))
    const synced = await fetchTrainingToday(uid, { skipAi: true })
    if (!synced.error && synced.data) {
      applyPlan(synced.data)
      await hydrateCheckins(uid)
      if (phase.value === 'setup' || phase.value === 'confirm') phase.value = 'running'
      // 若后端尚未带回 end_at，用本地窗口兜底开倒计时
      if (phase.value === 'running' && !timerEndAtMs) {
        plannedDurationSec.value = pm * 60
        timerEndAtMs = endAt
        remainingSeconds.value = Math.max(0, Math.ceil((endAt - Date.now()) / 1000))
        startTimerTick()
      }
    } else {
      phase.value = 'running'
      plannedDurationSec.value = pm * 60
      timerEndAtMs = endAt
      remainingSeconds.value = pm * 60
      startTimerTick()
    }
    uni.showToast({ title: '训练已开始', icon: 'none' })
  } catch (e) {
    const msg = e?.message || '开启失败'
    uni.showToast({
      title: msg === 'HTTP 500' ? '服务异常，请重试或重启后端' : msg,
      icon: 'none',
      duration: 3000,
    })
  } finally {
    uni.hideLoading()
    confirmBusy.value = false
  }
}

function goTalent() {
  uni.navigateTo({ url: '/pages/talent/index' })
}

function destroyInnerAudio() {
  if (!innerAudio) return
  try {
    innerAudio.stop()
    innerAudio.destroy()
  } catch (_) { /* ignore */ }
  innerAudio = null
  audioPlaying.value = false
  audioResumePendingSec = 0
}

function applyAudioResumeSeek() {
  if (!innerAudio || audioResumePendingSec <= 0.5) return
  const d = Number(innerAudio.duration || audioUiDuration.value || 0)
  const target = d > 0
    ? Math.min(audioResumePendingSec, Math.max(0, d - 0.35))
    : audioResumePendingSec
  if (target <= 0.5) {
    audioResumePendingSec = 0
    return
  }
  try { innerAudio.seek(target) } catch (_) { /* ignore */ }
  audioUiCurrent.value = target
  audioResumePendingSec = 0
}

function stopInlineVideo() {
  inlineVideoId.value = ''
  inlineVideoSrc.value = ''
}

/**
 * forceType:
 * - train  开始训练：有音频播音频（打卡进度），否则卡片内播视频
 * - video  秘籍剧情：卡片封面区播配套视频
 * - audio  强制音频弹层
 */
function openMedia(it, forceType = 'train') {
  if (!it || it._state === 'locked') {
    uni.showToast({ title: '请先完成上一关', icon: 'none' })
    return
  }
  if (isMediaLocked.value) {
    uni.showToast({ title: '训练时长已到，音视频已锁定', icon: 'none' })
    return
  }
  if (!devMode.value && phase.value !== 'running') {
    uni.showToast({ title: '请先确认开启挑战', icon: 'none' })
    return
  }

  let prefer = forceType
  if (forceType === 'train') {
    prefer = it.audio_url ? 'audio' : (it.video_url ? 'video' : 'none')
  }
  if (prefer === 'video' && !it.video_url) {
    uni.showToast({ title: '本关暂无配套视频', icon: 'none' })
    return
  }
  if (prefer === 'audio' && !it.audio_url) {
    uni.showToast({ title: '本关暂无训练音频', icon: 'none' })
    return
  }
  if (prefer === 'none') {
    uni.showToast({ title: '暂无媒体，可直接打卡', icon: 'none' })
    openCheckin(it)
    return
  }

  ensureChildUser().then(async (uid) => {
    activeWatchItem = findItem(it.id) || it

    if (prefer === 'audio') {
      // 音频：弹层；先停掉卡片内视频
      stopInlineVideo()
      destroyInnerAudio()
      mediaKind.value = 'audio'
      mediaSrc.value = resolveTrainingStreamUrl(it.audio_url, uid)
      mediaPeakSec = Number(
        activeWatchItem?.watch_progress?.audio?.watched_sec
        || activeWatchItem?.watch_progress?.watched_sec
        || 0,
      )
      mediaDurationSec = Number(
        activeWatchItem?.watch_progress?.audio?.duration_sec
        || activeWatchItem?.watch_progress?.duration_sec
        || 0,
      )
      audioResumePendingSec = mediaPeakSec
      audioUiCurrent.value = mediaPeakSec
      audioUiDuration.value = mediaDurationSec
      audioCover.value = skillMeta(skillOf(it)).img
      innerAudio = uni.createInnerAudioContext()
      innerAudio.src = mediaSrc.value
      innerAudio.onPlay(() => {
        audioPlaying.value = true
        // 续播 seek 放在 play 后，避免部分端把位置重置回 0
        applyAudioResumeSeek()
      })
      innerAudio.onPause(() => { audioPlaying.value = false })
      innerAudio.onStop(() => { audioPlaying.value = false })
      innerAudio.onCanplay(() => {
        const d = Number(innerAudio.duration || 0)
        if (d > 0) audioUiDuration.value = d
      })
      innerAudio.onEnded(() => {
        audioPlaying.value = false
        if (audioUiDuration.value > 0) audioUiCurrent.value = audioUiDuration.value
        onMediaEnded()
      })
      innerAudio.onTimeUpdate(() => {
        const cur = innerAudio.currentTime || 0
        const dur = innerAudio.duration || 0
        audioUiCurrent.value = cur
        if (dur > 0) audioUiDuration.value = dur
        onMediaTime({
          detail: { currentTime: cur, duration: dur },
        })
      })
      try { innerAudio.play() } catch (_) { /* ignore */ }
      mediaTitle.value = `${skillOf(it)} · 训练音频`
      mediaOpen.value = true
    } else {
      // 视频：在卡片封面区播放，不再弹层
      destroyInnerAudio()
      mediaOpen.value = false
      mediaKind.value = 'video'
      const src = resolveTrainingStreamUrl(it.video_url, uid)
      mediaSrc.value = src
      mediaPeakSec = Number(activeWatchItem?.watch_progress?.video?.watched_sec || 0)
      mediaDurationSec = Number(activeWatchItem?.watch_progress?.video?.duration_sec || 0)
      mediaTitle.value = `${skillOf(it)} · 秘籍剧情`
      inlineVideoSrc.value = src
      inlineVideoId.value = String(it.id)
    }

    if (it.item_type === 'perception' && prefer === 'audio') {
      try {
        const res = await postTrainingWatchProgress(uid, it.id, {
          watched_sec: 1,
          duration_sec: 1,
          media: 'audio',
        })
        applyWatchProgressLocal(it.id, res?.watch_progress || { pct: 100, watched_sec: 1, duration_sec: 1 })
      } catch (_) { /* ignore */ }
    }
  })
}

function toggleAudio() {
  if (!innerAudio) return
  if (audioPlaying.value) innerAudio.pause()
  else innerAudio.play()
}

/** 停止：暂停并保留位置（再次播放/再次进入从此续播）；结束才关面板 */
async function stopAudio() {
  if (!innerAudio) return
  try {
    const cur = Number(innerAudio.currentTime || audioUiCurrent.value || 0)
    if (cur > mediaPeakSec) mediaPeakSec = cur
    audioUiCurrent.value = cur > 0 ? cur : audioUiCurrent.value
    innerAudio.pause()
  } catch (_) { /* ignore */ }
  audioPlaying.value = false
  await flushWatchProgress()
}

function applyWatchProgressLocal(itemId, wp) {
  if (!wp) return
  const raw = findItem(itemId)
  if (raw) raw.watch_progress = { ...wp }
  if (activeWatchItem && String(activeWatchItem.id) === String(itemId)) {
    activeWatchItem.watch_progress = { ...wp }
  }
}

function onMediaTime(e) {
  const it = activeWatchItem
  if (!it?.id) return
  const cur = Number(e?.detail?.currentTime || 0)
  const dur = Number(e?.detail?.duration || 0)
  if (cur > mediaPeakSec) mediaPeakSec = cur
  if (dur > 0) mediaDurationSec = dur
  if (mediaDurationSec > 0) {
    const pct = Math.min(100, Math.round((mediaPeakSec / mediaDurationSec) * 1000) / 10)
    const kind = mediaKind.value === 'video' ? 'video' : 'audio'
    const chunk = {
      watched_sec: mediaPeakSec,
      duration_sec: mediaDurationSec,
      pct,
    }
    const prev = { ...(it.watch_progress || {}) }
    prev[kind] = chunk
    // 音频进度同步到顶层，与后端打卡门槛一致
    if (kind === 'audio') {
      prev.watched_sec = chunk.watched_sec
      prev.duration_sec = chunk.duration_sec
      prev.pct = chunk.pct
    }
    applyWatchProgressLocal(it.id, prev)
  }
  if (watchTimer) return
  watchTimer = setTimeout(() => {
    watchTimer = null
    flushWatchProgress()
  }, 2500)
}

async function flushWatchProgress() {
  const it = activeWatchItem
  if (!it?.id) return
  if (mediaPeakSec <= 0 && mediaDurationSec <= 0) return
  const watched = mediaDurationSec > 0
    ? Math.min(mediaPeakSec, mediaDurationSec)
    : mediaPeakSec
  const kind = mediaKind.value === 'video' ? 'video' : 'audio'
  try {
    const uid = await ensureChildUser()
    const res = await postTrainingWatchProgress(uid, it.id, {
      watched_sec: watched,
      duration_sec: mediaDurationSec > 0 ? mediaDurationSec : undefined,
      media: kind,
    })
    if (res?.watch_progress) applyWatchProgressLocal(it.id, res.watch_progress)
  } catch (_) { /* ignore */ }
}

function onMediaEnded() {
  if (mediaDurationSec > 0) mediaPeakSec = mediaDurationSec
  else if (mediaPeakSec <= 0) mediaPeakSec = 1
  if (mediaDurationSec <= 0) mediaDurationSec = Math.max(mediaPeakSec, 1)
  const it = activeWatchItem
  if (it?.id) {
    applyWatchProgressLocal(it.id, {
      ...(it.watch_progress || {}),
      watched_sec: mediaPeakSec,
      duration_sec: mediaDurationSec,
      pct: 100,
    })
  }
  flushWatchProgress()
}

/** 结束：刷进度并关掉面板；再次进入仍从已存进度续播 */
async function closeMedia() {
  if (watchTimer) {
    clearTimeout(watchTimer)
    watchTimer = null
  }
  if (innerAudio) {
    try {
      const cur = Number(innerAudio.currentTime || audioUiCurrent.value || 0)
      if (cur > mediaPeakSec) mediaPeakSec = cur
    } catch (_) { /* ignore */ }
  }
  await flushWatchProgress()
  destroyInnerAudio()
  stopInlineVideo()
  mediaOpen.value = false
  mediaSrc.value = ''
  activeWatchItem = null
  mediaPeakSec = 0
  mediaDurationSec = 0
  audioUiCurrent.value = 0
  audioUiDuration.value = 0
  audioPlaying.value = false
}

async function openCheckin(it) {
  if (!it || it._state === 'locked') {
    uni.showToast({ title: '请先完成上一关', icon: 'none' })
    return
  }
  if (!devMode.value && phase.value !== 'running' && phase.value !== 'expired') {
    uni.showToast({ title: '请先确认开启挑战', icon: 'none' })
    return
  }
  // 提交前先把播放进度刷到后端，避免本地 90% 服务端仍不足
  if (activeWatchItem && String(activeWatchItem.id) === String(it.id)) {
    await flushWatchProgress()
  }
  const raw = findItem(it.id) || it
  const existing = checkinByItemId.value[String(it.id)]
  // 已打卡再次打开：回填上次内容，不再卡 90% 门槛
  if (!existing && !devMode.value && !isListenReady(raw)) {
    uni.showToast({
      title: `请先听完训练音频（需达到 90%，当前 ${audioWatchPct(raw).toFixed(0)}%）`,
      icon: 'none',
      duration: 2500,
    })
    return
  }
  checkinItemId.value = it.id
  checkinSkill.value = skillOf(it)
  if (existing) {
    fillCheckinFormFromRecord(existing, raw)
  } else {
    form.time = it.duration_min ? String(it.duration_min) : ''
    form.wordCount = ''
    form.accuracy = ''
    form.note = ''
    form.attitude = 60
  }
  checkinOpen.value = true
  checkinFocus.value = false
  setTimeout(() => { checkinFocus.value = true }, 80)
}

async function submitCheckin() {
  if (!checkinItemId.value || checkinBusy.value || !plan.value?.plan_id) return
  checkinBusy.value = true
  try {
    if (activeWatchItem && String(activeWatchItem.id) === String(checkinItemId.value)) {
      await flushWatchProgress()
    }
    const uid = await ensureChildUser()
    const skill = checkinSkill.value || '训练'
    const raw = findItem(checkinItemId.value)
    const existing = checkinByItemId.value[String(checkinItemId.value)]
    if (!existing && !devMode.value && raw && !isListenReady(raw)) {
      throw new Error(`请先听完训练音频（需达到 90%，当前 ${audioWatchPct(raw).toFixed(0)}%）`)
    }
    if (showWord.value && !String(form.wordCount || '').trim()) {
      throw new Error('请填写字数')
    }
    if (showAcc.value && !String(form.accuracy || '').trim()) {
      throw new Error('请填写准确率')
    }
    const payload = {
      ability_type: skill,
      content: form.note || `${skill}打卡`,
      attitude_pct: form.attitude,
      cards: [{
        name: skill,
        time: form.time,
        wordCount: form.wordCount,
        accuracy: form.accuracy,
        note: form.note,
        completed: true,
      }],
    }
    let res
    if (existing?.id) {
      res = await updateTrainingCheckin(uid, existing.id, payload)
    } else {
      res = await submitTrainingCheckin(uid, {
        plan_id: plan.value.plan_id,
        item_id: checkinItemId.value,
        ...payload,
      })
    }
    if (raw) raw.checkin_status = 'done'
    if (plan.value && res.plan_status) plan.value.status = res.plan_status
    // 立刻写回本地缓存，二次打开可立刻看到刚填的内容
    const itemKey = String(checkinItemId.value)
    checkinByItemId.value = {
      ...checkinByItemId.value,
      [itemKey]: {
        ...(existing || {}),
        id: res?.record_id || existing?.id,
        item_id: checkinItemId.value,
        attitude_pct: form.attitude,
        note: form.note,
        content: payload.content,
        cards: payload.cards,
      },
    }
    closeCheckin()
    const synced = await fetchTrainingToday(uid, { skipAi: true })
    if (!synced.error && synced.data) {
      const keep = phase.value
      applyPlan(synced.data)
      if (keep === 'running' || keep === 'expired') phase.value = keep
      await hydrateCheckins(uid)
    }
    uni.showToast({ title: existing ? '已保存修改' : '打卡成功', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '打卡失败', icon: 'none', duration: 2800 })
  } finally {
    checkinBusy.value = false
  }
}

function findItem(id) {
  return (plan.value?.items || []).find((i) => String(i.id) === String(id))
}

function toggleDevMode() {
  if (!devToolsAvailable) return
  devMode.value = !devMode.value
  setDevMode(devMode.value)
  uni.showToast({
    title: devMode.value ? '开发者模式已开启' : '开发者模式已关闭',
    icon: 'none',
  })
  if (devMode.value) loadDevStatus()
  else {
    devStatusText.value = ''
    usageLine.value = ''
  }
}

async function loadDevStatus() {
  if (!devMode.value) return
  try {
    const uid = await ensureChildUser()
    const s = await fetchDevTrainingStatus(uid)
    const tag = s.talent_tag || '?'
    const clock = s.dev_time_override
      ? ` · 虚拟 ${String(s.dev_time_override).slice(0, 16).replace('T', ' ')}`
      : ''
    devStatusText.value = `主线 ${s.main_line ?? 'A'} · 第 ${s.training_day_number ?? 1} 天 · ${tag} · 计划 ${s.plan_count} 条 · 打卡 ${s.record_count} 条${clock}`
  } catch (_) {
    devStatusText.value = 'dev 状态拉取失败（检查后端 JNAO_DEV_MODE=1）'
  }
  try {
    const u = await fetchUsageSummary()
    const me = u?.me || {}
    const fam = u?.billing?.total_tokens
    const parts = [
      `⚡ 已用 ${formatTokenCount(me.total_tokens || 0)} tok`,
      `${me.call_count || 0} 次`,
    ]
    if (fam != null) parts.push(`家计 ${formatTokenCount(fam)}`)
    const by = (me.by_provider || []).map((p) => `${p.provider}:${formatTokenCount(p.total_tokens)}`).join(' ')
    if (by) parts.push(by)
    usageLine.value = parts.join(' · ')
  } catch (_) {
    usageLine.value = '⚡ 用量拉取失败（需登录）'
  }
}

async function devResetToday() {
  if (!devMode.value) return
  try {
    uni.showLoading({ title: '重置今日...' })
    const uid = await ensureChildUser()
    await devResetTodayTraining(uid)
    try { await clearTrainingWindow(uid) } catch (_) { /* ignore */ }
    plan.value = null
    phase.value = 'setup'
    closeCheckin()
    closeMedia()
    await bootstrap()
    await loadDevStatus()
    uni.showToast({ title: '今日方案已清空', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '重置失败', icon: 'none' })
  } finally {
    uni.hideLoading()
  }
}

async function devResetTimer(silent = false) {
  if (!devMode.value) return
  try {
    const uid = await ensureChildUser()
    await clearTrainingWindow(uid)
  } catch (_) { /* ignore */ }
  clearTimerTick()
  timerEndAtMs = 0
  remainingSeconds.value = plannedDurationSec.value || plannedMins.value * 60
  if (plan.value?.items?.length) phase.value = 'confirm'
  else phase.value = 'setup'
  if (!silent) uni.showToast({ title: '计时已重置', icon: 'none' })
}

function devSimulateExpire() {
  if (!devMode.value) return
  if (!plan.value?.items?.length) {
    uni.showToast({ title: '暂无方案', icon: 'none' })
    return
  }
  expireLocalTimer(true)
  phase.value = 'expired'
  uni.showToast({ title: '已模拟计时结束', icon: 'none' })
}

async function devSimulate4am() {
  if (!devMode.value) return
  try {
    uni.showLoading({ title: '模拟4点...' })
    const uid = await ensureChildUser()
    const res = await devSimulate4amCutoff(uid)
    await bootstrap()
    await loadDevStatus()
    uni.showToast({ title: res.message || '已模拟凌晨4点截止', icon: 'none' })
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
    await bootstrap()
    await loadDevStatus()
    uni.showToast({ title: res.message || '已进入下一天', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '模拟失败', icon: 'none' })
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
    await bootstrap()
    await loadDevStatus()
    uni.showToast({ title: res.message || '已回归实际日期', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '失败', icon: 'none' })
  } finally {
    uni.hideLoading()
  }
}

async function devResetMainLine() {
  if (!devMode.value) return
  try {
    uni.showLoading({ title: '回到主线A...' })
    const uid = await ensureChildUser()
    await devResetTrainingProgress(uid)
    await bootstrap()
    await loadDevStatus()
    uni.showToast({ title: '训练进度已重置', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '失败', icon: 'none' })
  } finally {
    uni.hideLoading()
  }
}

async function devRefreshAi() {
  if (!devMode.value) return
  try {
    uni.showLoading({ title: '刷新 AI...' })
    const uid = await ensureChildUser()
    const result = await refreshTrainingReport(uid, true)
    if (result.error) throw new Error(result.message)
    applyPlan(result.data)
    phase.value = 'confirm'
    await loadDevStatus()
    uni.showToast({ title: 'AI 方案已刷新', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '刷新失败', icon: 'none' })
  } finally {
    uni.hideLoading()
  }
}

async function devClearAll() {
  if (!devMode.value) return
  try {
    uni.showLoading({ title: '清空中...' })
    const uid = await ensureChildUser()
    await devResetAllTraining(uid)
    plan.value = null
    phase.value = 'setup'
    closeCheckin()
    closeMedia()
    await bootstrap()
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
    clearTalentState()
    await refreshTalentState(uid)
    plan.value = null
    phase.value = 'need_assessment'
    closeCheckin()
    await loadDevStatus()
    uni.showToast({ title: '天赋测评已重置', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: e.message || '重置失败', icon: 'none' })
  } finally {
    uni.hideLoading()
  }
}

onMounted(() => {
  bootstrap().then(() => {
    if (devMode.value) loadDevStatus()
  })
})
onShow(() => {
  if (checkinOpen.value || mediaOpen.value) return
  if (plan.value && (phase.value === 'running' || phase.value === 'expired' || phase.value === 'confirm')) {
    bootstrap()
  }
})
onUnmounted(() => {
  clearTimerTick()
  closeMedia()
  closeCheckin()
})
</script>

<style scoped>
.phone {
  width: 100%;
  max-width: var(--app-max-width, 480px);
  height: 100vh;
  height: 100dvh;
  margin: 0 auto;
  background: linear-gradient(180deg, #101623 0%, #0b0e14 30%);
  position: relative;
  padding-bottom: 96px;
  box-sizing: border-box;
  color: #edebe4;
  overflow-x: hidden;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.phone::-webkit-scrollbar { display: none; width: 0; height: 0; }
.block { padding-bottom: 8px; }

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px 4px;
}
.top-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.nav-dev {
  font-size: 11px;
  font-weight: 800;
  padding: 4px 8px;
  border-radius: 8px;
  border: 1.5px solid #5a6274;
  color: #8b93a5;
}
.nav-dev.active {
  border-color: #c9a869;
  color: #c9a869;
  background: rgba(201, 168, 105, 0.12);
}
.dev-panel {
  margin: 10px 18px;
  background: #131926;
  border: 1.5px dashed #c9a869;
  border-radius: 14px;
  padding: 12px 14px;
}
.dev-panel-label {
  display: block;
  font-size: 14px;
  font-weight: 900;
  color: #c9a869;
  margin-bottom: 8px;
}
.dev-status {
  font-size: 11px;
  color: #8b93a5;
  line-height: 1.5;
  margin-bottom: 8px;
  word-break: break-all;
}
.dev-section-label {
  display: block;
  font-size: 11px;
  font-weight: 800;
  color: #5a6274;
  margin: 8px 0 6px;
}
.dev-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.dev-action {
  background: #1e2a44;
  color: #d8dce6;
  font-size: 12px;
  font-weight: 700;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid #2a3040;
}
.dev-action.primary {
  background: rgba(46, 107, 230, 0.25);
  border-color: #2e6be6;
  color: #8fb4ff;
}
.dev-action.danger {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.45);
  color: #fca5a5;
}
.dev-panel-hint {
  display: block;
  margin-top: 10px;
  font-size: 10px;
  color: #5a6274;
  line-height: 1.4;
}
.brand { display: flex; align-items: center; gap: 10px; }
.logo {
  width: 44px; height: 44px; border-radius: 50%;
  background: url('/static/dayu/assets/avatar_sizhe.jpg') center/cover;
  border: 2px solid #6fcf8e;
  box-shadow: 0 0 10px rgba(111, 207, 142, 0.4);
}
.t1 { display: block; font-size: 19px; font-weight: 800; color: #edebe4; }
.t2 { display: block; font-size: 10px; color: #5a6274; letter-spacing: 2px; }
.chip-g {
  background: rgba(111, 207, 142, 0.12);
  border: 1.5px solid #6fcf8e;
  color: #6fcf8e;
  font-size: 13px;
  font-weight: 700;
  padding: 5px 11px;
  border-radius: 999px;
}
.chip-gold {
  background: rgba(201, 168, 105, 0.12);
  border: 1.5px solid #c9a869;
  color: #c9a869;
  font-size: 11px;
  font-weight: 700;
  padding: 5px 11px;
  border-radius: 999px;
}

.tpick {
  margin: 12px 18px;
  background: linear-gradient(160deg, #1a2233, #101623 70%);
  border: 1.5px solid #2e6be6;
  border-radius: 18px;
  padding: 18px 16px;
}
.tt {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 20px;
  font-weight: 900;
  color: #edebe4;
}
.st8 {
  margin-left: auto;
  font-size: 11px;
  font-weight: 800;
  color: #7fa7ef;
  border: 1px solid #2e6be6;
  padding: 3px 10px;
  border-radius: 99px;
}
.big {
  display: block;
  font-size: 56px;
  font-weight: 900;
  color: #4ea0d8;
  text-align: center;
  margin: 16px 0 4px;
  letter-spacing: 2px;
}
.cap {
  display: block;
  text-align: center;
  font-size: 12.5px;
  color: #8b93a5;
  margin-bottom: 14px;
}
.quick {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-bottom: 14px;
}
.q {
  background: #131926;
  border: 1.5px solid #232b3d;
  border-radius: 12px;
  padding: 11px 0;
  text-align: center;
  font-size: 14.5px;
  font-weight: 800;
  color: #8b93a5;
}
.q.on {
  border-color: #2e6be6;
  color: #7fa7ef;
  background: rgba(46, 107, 230, 0.12);
}
.step {
  display: flex;
  justify-content: center;
  gap: 26px;
  align-items: center;
  margin-bottom: 6px;
}
.col { text-align: center; }
.lab { display: block; font-size: 12px; color: #5a6274; margin-top: 4px; }
.round {
  width: 44px; height: 44px; border-radius: 50%;
  background: #1e2a44; color: #7fa7ef;
  font-size: 22px; font-weight: 900;
  display: flex; align-items: center; justify-content: center;
  margin: 0 auto;
}
.val { font-size: 30px; font-weight: 900; color: #edebe4; min-width: 64px; }

.goPlan, .confirm {
  margin: 14px 18px 4px;
  background: #2e6be6;
  color: #fff;
  border-radius: 16px;
  padding: 17px;
  font-size: 19px;
  font-weight: 900;
  text-align: center;
}
.goPlan .sub, .confirm .sub {
  display: block;
  font-size: 12px;
  font-weight: 600;
  opacity: 0.75;
  margin-top: 3px;
}
.dim { opacity: 0.55; pointer-events: none; }

.dayu {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  margin: 12px 18px;
}
.bear {
  width: 52px; height: 52px; border-radius: 50%;
  background: url('/static/dayu/assets/avatar_sizhe.jpg') center/cover;
  border: 2px solid #6fcf8e;
  box-shadow: 0 0 14px rgba(111, 207, 142, 0.45);
  flex: none;
}
.bubble {
  background: #161d2b;
  border: 1px solid #2a3040;
  border-radius: 14px 14px 14px 4px;
  padding: 10px 14px;
  font-size: 14px;
  color: #d8dce6;
  line-height: 1.55;
  flex: 1;
}
.b { color: #6fcf8e; font-weight: 800; }

.gate, .plan2 {
  margin: 12px 18px;
  background: linear-gradient(160deg, #1a2233, #101623 70%);
  border: 1.5px solid #c9a869;
  border-radius: 18px;
  padding: 16px;
}
.gt {
  font-size: 21px;
  font-weight: 900;
  color: #edebe4;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.day {
  font-size: 12px;
  font-weight: 800;
  color: #c9a869;
  border: 1px solid rgba(201, 168, 105, 0.5);
  padding: 3px 10px;
  border-radius: 999px;
}
.cnt, .count {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 8px 0 10px;
}
.cnt-b { font-size: 36px; font-weight: 900; color: #c9a869; line-height: 1; }
.cnt-s { font-size: 15px; font-weight: 700; color: #edebe4; }
.cnt-m { font-size: 12px; color: #8b93a5; margin-left: auto; }
.gitem {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 15.5px;
  color: #d8dce6;
  font-weight: 600;
  padding: 7px 0;
  border-top: 1px dashed #232b3d;
}
.gitem:first-of-type { border-top: none; }
.n {
  width: 24px; height: 24px; border-radius: 7px;
  background: #1e2a44; color: #7fa7ef;
  font-size: 12px; font-weight: 800;
  display: flex; align-items: center; justify-content: center; flex: none;
}
.gitem.opt .n { background: rgba(201, 168, 105, 0.15); color: #c9a869; }
.gn { flex: 1; }
.st { margin-left: auto; font-size: 11.5px; color: #5a6274; font-weight: 700; }
.editline {
  margin: 0 18px 10px;
  font-size: 12px;
  color: #5a6274;
  display: flex;
  justify-content: space-between;
}
.editline text:first-child { color: #7fa7ef; font-weight: 700; }
.edit-muted { color: #5a6274; font-weight: 600; }
.edit-muted.edit-on { color: #c9a869; font-weight: 700; }

/* 编辑方案弹层（片选，不用系统 picker） */
.editor-overlay {
  align-items: flex-end;
  z-index: 10020;
}
.editor-sheet {
  margin-bottom: 56px;
  max-height: min(78vh, 640px);
  display: flex;
  flex-direction: column;
  padding-top: 10px;
}
.editor-confirm-sheet {
  max-height: none;
}
.editor-handle {
  width: 42px;
  height: 4px;
  border-radius: 99px;
  background: rgba(255, 255, 255, 0.18);
  margin: 0 auto 12px;
  flex: none;
}
.editor-hint {
  display: block;
  font-size: 11.5px;
  color: #8b93a5;
  line-height: 1.45;
  margin: -2px 0 12px;
  flex: none;
}
.editor-scroll {
  flex: 1;
  max-height: 46vh;
  margin: 0 -4px;
  padding: 0 4px 4px;
}
.editor-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid #2a3040;
  border-radius: 14px;
  padding: 12px;
  margin-bottom: 10px;
}
.editor-card-h {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}
.editor-label {
  font-size: 12px;
  font-weight: 800;
  color: #c9a869;
  flex: none;
}
.editor-cur {
  flex: 1;
  text-align: right;
  font-size: 13px;
  font-weight: 800;
  color: #edebe4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.editor-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.editor-chip {
  width: calc(50% - 4px);
  box-sizing: border-box;
  padding: 9px 10px;
  border-radius: 11px;
  background: #1a2233;
  border: 1.5px solid #2a3040;
  transition: border-color 0.15s, background 0.15s;
}
.editor-chip.on {
  background: rgba(201, 168, 105, 0.12);
  border-color: #c9a869;
}
.ec-mj {
  display: block;
  font-size: 13px;
  font-weight: 800;
  color: #edebe4;
  line-height: 1.2;
}
.editor-chip.on .ec-mj { color: #e8d5a8; }
.ec-sk {
  display: block;
  margin-top: 2px;
  font-size: 10.5px;
  font-weight: 600;
  color: #8b93a5;
}
.editor-chip.on .ec-sk { color: #c9a869; }
.editor-empty {
  padding: 20px 8px;
  text-align: center;
  color: #8b93a5;
  font-size: 13px;
}
.editor-confirm-text {
  display: block;
  font-size: 13px;
  line-height: 1.55;
  color: #a8b0c0;
  margin: 4px 0 16px;
}
.editor-actions {
  display: flex;
  gap: 10px;
  margin-top: 10px;
  flex: none;
}
.editor-btn {
  flex: 1;
  text-align: center;
  padding: 12px 10px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 800;
}
.editor-btn.ghost {
  background: #1a2233;
  border: 1px solid #2a3040;
  color: #a8b0c0;
}
.editor-btn.primary {
  background: linear-gradient(135deg, #c9a869, #a8844a);
  color: #1a1408;
}
.editor-btn.dim { opacity: 0.55; pointer-events: none; }

/* 选修开关（确认闸门） */
.opts {
  margin-top: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px dashed #2a3040;
  border-radius: 14px;
  padding: 12px 14px;
}
.ot {
  display: block;
  font-size: 13px;
  font-weight: 800;
  color: #c9a869;
  margin-bottom: 8px;
}
.opt { padding: 8px 0; }
.opt + .opt { border-top: 1px dashed #232b3d; }
.opt-main {
  display: flex;
  align-items: center;
  gap: 10px;
}
.opt-text { flex: 1; min-width: 0; }
.on_name {
  display: block;
  font-size: 16px;
  font-weight: 800;
  color: #edebe4;
}
.od {
  display: block;
  font-size: 11.5px;
  color: #8b93a5;
  margin-top: 2px;
}
.opt-tip {
  display: block;
  margin-top: 4px;
  font-size: 10.5px;
  font-weight: 700;
  color: #6fcf8e;
}
.sw {
  width: 52px;
  height: 30px;
  border-radius: 99px;
  background: #2a3040;
  position: relative;
  flex: none;
  transition: 0.2s;
}
.sw-knob {
  position: absolute;
  left: 4px;
  top: 4px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #8b93a5;
  transition: 0.2s;
}
.sw.on {
  background: #30904f;
}
.sw.on .sw-knob {
  left: 26px;
  background: #ebeef4;
}
.sw.dim { opacity: 0.55; pointer-events: none; }

.ph { display: flex; align-items: center; justify-content: space-between; }

/* 紧凑倒计时行：保留演示卡骨架，不盖住能量塔 */
.timer-row {
  margin-top: 12px;
  padding: 10px 12px 9px;
  border-radius: 12px;
  background: rgba(46, 107, 230, 0.08);
  border: 1px solid rgba(46, 107, 230, 0.22);
}
.timer-row.expired {
  background: rgba(201, 168, 105, 0.08);
  border-color: rgba(201, 168, 105, 0.32);
}
.timer-row-main {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}
.timer-lab {
  font-size: 12px;
  font-weight: 800;
  color: #8b93a5;
  letter-spacing: 0.06em;
}
.timer-val {
  font-size: 26px;
  font-weight: 900;
  letter-spacing: 0.05em;
  font-variant-numeric: tabular-nums;
  color: #6fcf8e;
  line-height: 1;
}
.timer-row.expired .timer-val {
  color: #c9a869;
}
.timer-sub {
  display: block;
  margin-top: 4px;
  font-size: 11.5px;
  font-weight: 700;
  color: #8b93a5;
}
.timer-track {
  margin-top: 8px;
  height: 5px;
  border-radius: 99px;
  background: rgba(255, 255, 255, 0.08);
  overflow: hidden;
}
.timer-fill {
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, #2e6be6, #6fcf8e);
  transition: width 0.4s linear;
}

/* 能量塔（对齐 train.html 演示） */
.t9in {
  margin-top: 12px;
  padding-top: 11px;
  border-top: 1px dashed rgba(201, 168, 105, 0.35);
}
.t9h {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}
.t9t {
  font-size: 15.5px;
  font-weight: 900;
  color: #e4d8ff;
}
.t9stage {
  font-size: 11px;
  font-weight: 800;
  color: #b39de0;
  border: 1px solid rgba(150, 110, 230, 0.5);
  border-radius: 99px;
  padding: 3px 10px;
}
.t9segs {
  display: flex;
  gap: 4px;
  margin: 11px 0 2px;
}
.t9seg {
  flex: 1;
  height: 10px;
  border-radius: 4px;
  background: #241e33;
  border: 1px solid #322a45;
}
.t9seg.lit {
  background: linear-gradient(180deg, #c9a869, #8a6bf0);
  border-color: transparent;
  box-shadow: 0 0 8px rgba(150, 110, 230, 0.55);
}
.t9seg.half {
  background: linear-gradient(90deg, #8a6bf0 35%, #241e33 35%);
  border-color: #322a45;
}
.pt { font-size: 21px; font-weight: 900; color: #edebe4; }
.bar {
  height: 9px; border-radius: 99px;
  background: rgba(255, 255, 255, 0.08);
  overflow: hidden; margin-top: 4px;
}
.bar-i {
  display: block; height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, #c9a869, #6fcf8e);
}

.stage2 { position: relative; margin: 0 18px 18px; }
.orb {
  position: absolute; left: 50%; top: -23px; transform: translateX(-50%);
  width: 46px; height: 46px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; z-index: 3;
  background: #161d2b; border: 2.5px solid #2a3040; color: #5a6274;
}
.stage2.active .orb {
  border-color: #6fcf8e; color: #6fcf8e;
  box-shadow: 0 0 0 5px rgba(111, 207, 142, 0.12), 0 0 16px rgba(111, 207, 142, 0.5);
}
.stage2.done .orb { background: linear-gradient(135deg, #2c9064, #4fae72); border-color: #6fcf8e; }
.lv-card {
  border-radius: 18px; overflow: hidden;
  background: #131926; border: 1.5px solid #232b3d;
}
.stage2.active .lv-card {
  border-color: #6fcf8e;
  box-shadow: 0 0 0 1px rgba(111, 207, 142, 0.35), 0 10px 26px rgba(0, 0, 0, 0.45);
}
.stage2.done .lv-card { border-color: rgba(111, 207, 142, 0.55); }
.stage2.locked .lv-card { opacity: 0.42; filter: saturate(0.3); }
.simg {
  position: relative;
  aspect-ratio: 16 / 8.2;
  overflow: hidden;
  background: #0e1420;
}
.simg-poster,
.simg-video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  z-index: 0;
}
.simg-video {
  object-fit: contain;
  background: #000;
  z-index: 1;
}
.simg-shade {
  position: absolute;
  inset: 0;
  z-index: 2;
  pointer-events: none;
  background: linear-gradient(180deg, rgba(10, 14, 22, 0.08) 40%, rgba(10, 14, 22, 0.88));
}
.simg-tap {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -42%);
  z-index: 5;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  border-radius: 14px;
  background: rgba(11, 14, 20, 0.55);
  border: 1.5px solid rgba(201, 168, 105, 0.55);
}
.simg-tap.media-locked {
  border-color: rgba(139, 147, 165, 0.45);
  background: rgba(11, 14, 20, 0.72);
}
.simg-tap.media-locked .simg-tap-ic {
  background: #5a6274;
  color: #c8ceda;
}
.simg-tap-ic {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: #c9a869;
  color: #101623;
  font-size: 16px;
  font-weight: 900;
  display: flex;
  align-items: center;
  justify-content: center;
}
.simg-tap-t {
  font-size: 11px;
  font-weight: 800;
  color: #f0dfb8;
}
.slv {
  position: absolute; left: 12px; top: 10px; z-index: 4;
  font-size: 11px; font-weight: 800; letter-spacing: 1px; color: #c9d4e8;
  background: rgba(11, 14, 20, 0.62); border: 1px solid #2a3040;
  border-radius: 8px; padding: 4px 10px;
  pointer-events: none;
}
.stage2.active .slv { color: #0b0e14; background: #6fcf8e; border-color: #6fcf8e; }
.smj {
  position: absolute; right: 12px; top: 10px; z-index: 4;
  font-size: 10.5px; font-weight: 900; color: #ffe1a0;
  background: rgba(60, 40, 8, 0.55); border: 1px solid rgba(220, 180, 100, 0.55);
  border-radius: 8px; padding: 4px 10px;
  pointer-events: none;
}
.sname {
  position: absolute; left: 14px; bottom: 10px; z-index: 4;
  display: flex; align-items: center; gap: 8px;
  pointer-events: none;
}
.sn { font-size: 22px; font-weight: 900; color: #fff; text-shadow: 0 2px 10px rgba(0, 0, 0, 0.7); }
.tag {
  font-size: 10px; font-weight: 700; padding: 1px 7px; border-radius: 99px;
  background: rgba(201, 168, 105, 0.15); color: #c9a869;
  border: 1px solid rgba(201, 168, 105, 0.4);
}
.sbody { padding: 12px 14px 14px; }
.ssub { display: block; font-size: 12.5px; color: #8b93a5; margin-bottom: 10px; }
.skl {
  margin-top: 0; margin-bottom: 8px;
  background: rgba(0, 0, 0, 0.28);
  border: 1px solid rgba(78, 160, 216, 0.22);
  border-radius: 10px; padding: 7px 10px 9px;
}
.skl-h {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 10px; color: #7fa8c9; font-weight: 800; margin-bottom: 5px;
}
.pct { font-size: 11px; color: #6fd3a7; }
.pct.zero { color: #5c6b7f; }
.skl-bar {
  height: 7px; border-radius: 99px;
  background: rgba(255, 255, 255, 0.07); overflow: hidden;
}
.skl-fill {
  display: block; height: 100%; border-radius: 99px;
  background: linear-gradient(90deg, #2c6e9e, #4ea0d8, #6fd3a7);
}
.weapon {
  display: flex; align-items: center; gap: 10px;
  background: linear-gradient(135deg, rgba(201, 168, 105, 0.16), rgba(201, 168, 105, 0.05));
  border: 1.5px solid rgba(201, 168, 105, 0.55);
  border-radius: 13px; padding: 11px 12px;
}
.weapon.media-locked {
  border-style: dashed;
  border-color: #5a6274;
  background: rgba(255, 255, 255, 0.03);
  opacity: 0.85;
}
.weapon.media-locked .ic {
  background: #232b3d;
  color: #8b93a5;
}
.weapon.media-locked .wb { color: #8b93a5; }
.weapon.media-locked .ws { color: #5a6274; }
.weapon .ic {
  width: 36px; height: 36px; border-radius: 50%;
  background: #c9a869; color: #101623;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; flex: none;
}
.wb { display: block; font-size: 15.5px; font-weight: 900; color: #f0dfb8; }
.ws { display: block; font-size: 10.5px; font-weight: 600; color: #a89668; margin-top: 2px; }
.stage2.locked .weapon { border-style: dashed; background: rgba(255, 255, 255, 0.03); }
.stage2.locked .weapon .ic { background: #232b3d; color: #5a6274; }
.stage2.locked .wb { color: #6b7385; }
.vids { display: flex; gap: 8px; margin-top: 9px; }
.vid {
  flex: 1; display: flex; align-items: center; gap: 8px;
  border-radius: 12px; padding: 9px 10px;
  border: 1.5px solid #2a3040; background: #0e1420;
}
.vid.mj { border-color: rgba(201, 168, 105, 0.45); background: rgba(201, 168, 105, 0.07); }
.vid.zd { border-color: rgba(46, 107, 230, 0.5); background: rgba(46, 107, 230, 0.08); }
.vid.disabled { opacity: 0.45; }
.vb { display: block; font-size: 13px; font-weight: 900; color: #d8dce6; }
.vid.mj .vb { color: #e8ce9a; }
.vid.zd .vb { color: #8fb4ff; }
.vs { display: block; font-size: 9.5px; color: #5a6274; margin-top: 1px; font-weight: 600; }

.foot {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  width: 100%;
  max-width: var(--app-max-width, 480px);
  margin: 0 auto;
  background: rgba(11, 14, 20, 0.94);
  backdrop-filter: blur(12px);
  border-top: 1px solid #232b3d;
  padding: 8px 10px calc(8px + env(safe-area-inset-bottom, 0px));
  display: flex;
  justify-content: space-around;
  z-index: 50;
  box-sizing: border-box;
}
.fi {
  text-align: center; color: #5a6274; font-size: 11px; flex: 1;
  display: flex; flex-direction: column; align-items: center;
}
.fi.on { color: #6fcf8e; font-weight: 700; }
.fic { display: block; width: 38px; height: 38px; margin: 0 auto 1px; }

.overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(5, 8, 16, 0.72);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: 16px;
  padding-bottom: calc(16px + env(safe-area-inset-bottom, 0px));
}
.sheet {
  width: 100%;
  max-width: var(--app-max-width, 480px);
  background: #131926;
  border: 1.5px solid #232b3d;
  border-radius: 18px 18px 12px 12px;
  padding: 16px;
  position: relative;
  z-index: 10000;
  pointer-events: auto;
}
.checkin-sheet {
  margin-bottom: 56px;
}
.sheet-t {
  display: block; font-size: 17px; font-weight: 900; color: #edebe4; margin-bottom: 10px;
}
.player {
  width: 100%; height: 200px; background: #000; border-radius: 10px; margin-bottom: 10px;
}
.audio-overlay {
  align-items: flex-end;
  background: transparent;
  padding: 0;
}
.audio-mask {
  position: absolute;
  inset: 0;
  background: rgba(5, 8, 16, 0.45);
}
.audio-sheet {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: var(--app-max-width, 480px);
  margin: 0 auto;
  background: linear-gradient(180deg, #1a2233 0%, #101623 70%);
  border: 1.5px solid #2a3040;
  border-bottom: none;
  border-radius: 22px 22px 0 0;
  padding: 10px 16px calc(14px + env(safe-area-inset-bottom, 0px));
  box-shadow: 0 -12px 40px rgba(0, 0, 0, 0.45);
}
.audio-handle {
  width: 42px;
  height: 4px;
  border-radius: 99px;
  background: rgba(255, 255, 255, 0.18);
  margin: 2px auto 14px;
}
.audio-head {
  display: flex;
  align-items: center;
  gap: 12px;
}
.audio-cover {
  width: 64px;
  height: 64px;
  border-radius: 14px;
  border: 1.5px solid rgba(201, 168, 105, 0.45);
  flex: none;
  background: #0e1420;
}
.audio-meta { flex: 1; min-width: 0; }
.audio-title {
  display: block;
  font-size: 16px;
  font-weight: 900;
  color: #edebe4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.audio-sub {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  font-weight: 700;
  color: #8b93a5;
}
.audio-progress { margin-top: 16px; }
.audio-bar {
  position: relative;
  height: 6px;
  border-radius: 99px;
  background: rgba(255, 255, 255, 0.08);
  overflow: visible;
}
.audio-fill {
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, #2c6e9e, #4ea0d8, #6fd3a7);
  box-shadow: 0 0 10px rgba(111, 211, 167, 0.35);
}
.audio-knob {
  position: absolute;
  top: 50%;
  width: 14px;
  height: 14px;
  margin-left: -7px;
  margin-top: -7px;
  border-radius: 50%;
  background: #edebe4;
  border: 2px solid #6fd3a7;
  box-shadow: 0 0 8px rgba(111, 211, 167, 0.5);
  pointer-events: none;
}
.audio-times {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  font-size: 11px;
  font-weight: 700;
  color: #5a6274;
  font-variant-numeric: tabular-nums;
}
.audio-pct { color: #6fd3a7; }
.audio-controls {
  display: flex;
  align-items: center;
  justify-content: space-around;
  margin-top: 18px;
  padding: 0 10px;
}
.ac-side {
  width: 64px;
  text-align: center;
  color: #8b93a5;
}
.ac-ic { display: block; font-size: 18px; line-height: 1.2; }
.ac-lab { display: block; font-size: 11px; font-weight: 700; margin-top: 4px; }
.ac-main {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: #2e6be6;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 0 6px rgba(46, 107, 230, 0.18), 0 10px 24px rgba(46, 107, 230, 0.35);
}
.ac-main.on {
  background: #6fcf8e;
  color: #0b0e14;
  box-shadow: 0 0 0 6px rgba(111, 207, 142, 0.18), 0 10px 24px rgba(111, 207, 142, 0.35);
}
.ac-main-ic { font-size: 26px; font-weight: 900; line-height: 1; }
.audio-tip {
  display: block;
  text-align: center;
  margin-top: 14px;
  font-size: 11px;
  font-weight: 700;
  color: #5a6274;
}
.row { display: flex; gap: 8px; }
.btn {
  flex: 1; text-align: center; background: #2e6be6; color: #fff;
  border-radius: 12px; padding: 12px; font-weight: 800; font-size: 14px;
}
.btn.ghost { background: transparent; border: 1.5px solid #2a3040; color: #d8dce6; }
.btn.block { width: 100%; margin-top: 8px; flex: none; }
.field { margin-top: 10px; position: relative; z-index: 1; }
.fl { display: block; font-size: 12px; color: #8b93a5; margin-bottom: 6px; }
.fi-input {
  background: #161d2b;
  border: 1.5px solid #2a3040;
  border-radius: 10px;
  padding: 10px 12px;
  color: #edebe4;
  width: 100%;
  box-sizing: border-box;
  font-size: 15px;
  height: 44px;
  line-height: 22px;
  pointer-events: auto;
}
/* uni-app H5 内层输入色 */
.fi-input :deep(.uni-input-input),
:deep(.fi-input) {
  color: #edebe4 !important;
  -webkit-text-fill-color: #edebe4;
  background: transparent;
}
.link { text-align: center; margin-top: 12px; color: #8b93a5; font-size: 13px; }
</style>
