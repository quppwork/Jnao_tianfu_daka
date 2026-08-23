<template>
  <view class="app">
    <view class="nav">
      <view class="nav-back" @click="goBack">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#8b949e" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      </view>
      <view class="nav-title-wrap">
        <text class="nav-title">成长里程碑</text>
        <text class="nav-sub">段位与打卡</text>
      </view>
      <view class="nav-spacer"></view>
    </view>

    <scroll-view class="body" scroll-y :show-scrollbar="false" :enhanced="true">
      <!-- 骨架屏：数据加载前显示，消除空白闪烁 -->
      <view v-if="loading" class="skeleton">
        <view class="sk-hero"><view class="sk-line w40"></view><view class="sk-line w60"></view><view class="sk-bar"></view><view class="sk-row"><view class="sk-stat"></view><view class="sk-stat"></view><view class="sk-stat"></view><view class="sk-stat"></view></view></view>
        <view class="sk-title"></view>
        <view class="sk-showcase"><view class="sk-slot"></view><view class="sk-slot"></view><view class="sk-slot"></view></view>
        <view class="sk-title"></view>
        <view class="sk-path"><view class="sk-dot"></view><view class="sk-dot"></view><view class="sk-dot"></view><view class="sk-dot"></view><view class="sk-dot"></view><view class="sk-dot"></view></view>
        <view class="sk-title"></view>
        <view class="sk-badges"><view v-for="i in 8" :key="'b'+i" class="sk-badge"></view></view>
        <view class="sk-title"></view>
        <view v-for="i in 3" :key="'tl'+i" class="sk-tl"><view class="sk-dot sm"></view><view class="sk-lines"><view class="sk-line w50"></view><view class="sk-line w30"></view></view></view>
      </view>

      <template v-else>
      <!-- 0a. 荣誉卡上方：天赋头像（只显示头部）+ 成长历程碑 / MILESTONES + 段位椭圆 -->
      <view v-if="summary" class="hero-idbar">
        <view class="hero-idbar-avatar" :style="{ borderColor: talentColor, backgroundImage: 'url(' + talentAvatarImg + ')' }"></view>
        <view class="hero-idbar-main">
          <text class="hero-idbar-title">成长历程碑</text>
          <text class="hero-idbar-en">段位与打卡</text>
        </view>
        <view class="hero-tier-pill">
          <text class="hero-tier-pill-num">{{ tierCN }}阶</text>
          <text class="hero-tier-pill-sep"> / </text>
          <text class="hero-tier-pill-total">九阶</text>
        </view>
      </view>

      <!-- 0. 荣誉 Hero 卡（传承特使大卡片，在最顶部） -->
      <view v-if="summary" class="hero-card">
        <view class="hero-top">
          <view class="hero-id">
            <text class="hero-honor">{{ summary.honor_level }}</text>
            <text class="hero-nick">
              <text v-if="summary.nickname">{{ summary.nickname }}</text>
              <text v-if="summary.talent_primary" class="hero-nick-talent"> · {{ summary.talent_primary }}</text>
              <text v-if="memberDays"> · 加入 {{ memberDays }} 天</text>
            </text>
          </view>
          <view class="hero-tier">
            <text class="hero-tier-num">第{{ overallTier }}段</text>
            <text class="hero-tier-total"> / 九段</text>
          </view>
        </view>
        <view class="tier-bar"><view class="tier-fill" :style="{ width: tierPercent + '%' }"></view></view>
        <view v-if="summary.checkin_streak >= 3" class="streak-pill">
          <view class="streak-ic" v-html="ic('flame', 12)"></view>
          <text>已连续 {{ summary.checkin_streak }} 天</text>
        </view>
        <view class="hero-stats">
          <view class="hero-stat"><text class="hs-num">{{ summary.total_checkins }}</text><text class="hs-lbl">累计打卡</text></view>
          <view class="hero-stat"><text class="hs-num">{{ summary.checkin_streak }}</text><text class="hs-lbl">连续天数</text></view>
          <view class="hero-stat"><text class="hs-num">{{ summary.qa_questions }}</text><text class="hs-lbl">学科提问</text></view>
          <view class="hero-stat"><text class="hs-num">{{ summary.badges_earned }}/{{ summary.badges_total }}</text><text class="hs-lbl">徽章</text></view>
        </view>
        <text class="hero-talent">🏆 已获积分 {{ summary.points ?? 0 }}</text>
      </view>

      <!-- 1. 进阶之路 + 九段（合并成一张大卡：节点在上、九段进度在下） -->
      <view class="sec-title">
        <text class="sec-emoji">📈</text>
        <text>进阶之路</text>
        <text v-if="nextTitleInfo" class="sec-sub">再进 {{ nextTitleInfo.need }} 阶解锁「{{ nextTitleInfo.name }}」</text>
      </view>
      <view class="path-card">
        <!-- 6 称号阶梯（每个节点独立方框） -->
        <view class="path-steps">
          <view v-for="(t, i) in honorPath" :key="t.name"
            class="path-step"
            :class="{ cur: i === currentTitleIndex, done: i < currentTitleIndex, locked: i > currentTitleIndex }">
            <view class="path-step-badge"><text>{{ t.badge }}</text></view>
            <text class="path-step-name">{{ t.name }}</text>
            <text class="path-step-tag">{{ honorStepTag(t) }}</text>
          </view>
        </view>

        <!-- 九段进度（技能等级 1-9）：独立圆角方块 -->
        <view class="tier9-divider"></view>
        <view class="tier9-steps">
          <view v-for="(s, idx) in duanNineSteps" :key="idx"
                class="tier9-step"
                :class="[
                  'g' + s.group,
                  { done: (idx + 1) < curTier, cur: (idx + 1) === curTier, next: (idx + 1) === curTier + 1 }
                ]">
            <view class="tier9-cell">
              <text class="tier9-cell-num">{{ s.num }}</text>
            </view>
          </view>
        </view>
        <view class="tier9-foot">
          <text class="tier9-hint">连续达标 <b>{{ tier?.advance_pass || 3 }}</b> 次，单项升 1 段</text>
          <view class="tier9-info-btn" @click="showTierRules = true">
            <text class="tier9-info-label">ⓘ 晋级规则</text>
          </view>
        </view>
      </view>

      <!-- 学业规划入口 -->
      <view class="plan-entry-card" @click="openAcademicPlan(false)">
        <view class="plan-entry-ic">🎯</view>
        <view class="plan-entry-body">
          <text class="plan-entry-title">AI 学业规划</text>
          <text class="plan-entry-desc">基于你的训练数据，智能生成个性化学业规划报告</text>
        </view>
        <view class="plan-entry-arrow" v-html="ic('chev-r', 18)"></view>
      </view>

      <!-- 新用户空态引导 -->
      <view v-if="isFreshUser" class="fresh-card">
        <view class="fresh-ic" v-html="ic('flame', 18)"></view>
        <view class="fresh-body">
          <text class="fresh-title">开启你的成长之旅</text>
          <text class="fresh-desc">完成首次训练打卡，点亮第一枚徽章</text>
        </view>
        <view class="fresh-btn" @click="goTrain"><text>去训练</text></view>
      </view>

      <!-- 2. 荣誉徽章 -->
      <view class="sec-title"><text class="sec-emoji">🏅</text><text>荣誉徽章</text></view>
      <view class="badge-grid">
        <view v-for="b in sortedBadges" :key="b.name" class="badge-item" :class="{ locked: !b.earned }">
          <view v-if="isNewBadge(b)" class="badge-new"><text>NEW</text></view>
          <view class="badge-circle" :class="{ pulse: isNewBadge(b) }" v-html="ic(BADGE_ICONS[b.name] || 'star', 20)"></view>
          <text class="badge-name">{{ b.name }}</text>
          <text v-if="b.earned && b.earned_at" class="badge-date">{{ b.earned_at.slice(5) }} 获得</text>
          <template v-else-if="!b.earned && badgeProgress(b)">
            <view class="badge-bar"><view class="badge-bar-fill" :style="{ width: badgeProgress(b).pct + '%' }"></view></view>
            <text class="badge-prog">{{ b.progress }}</text>
          </template>
          <text v-else class="badge-cond">{{ b.cond }}</text>
        </view>
      </view>

      <!-- 4. 下一个目标 -->
      <template v-if="goalCards.length">
        <view class="sec-title"><text class="sec-emoji">🎯</text><text>下一个目标</text></view>
        <view v-for="(g, i) in goalCards" :key="'g'+i" class="goal-card" :class="{ clickable: !!g.route }" @click="goGoal(g)">
          <view class="goal-ic" v-html="ic('target', 15)"></view>
          <view class="goal-body">
            <view class="goal-head">
              <text class="goal-title">{{ g.title }}</text>
              <text v-if="g.progressText" class="goal-prog-text">{{ g.progressText }}</text>
            </view>
            <view v-if="g.pct !== null" class="goal-bar"><view class="goal-bar-fill" :style="{ width: g.pct + '%' }"></view></view>
            <text class="goal-desc">{{ g.desc }}</text>
          </view>
          <view v-if="g.route" class="goal-arrow">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="9 18 15 12 9 6"/></svg>
          </view>
        </view>
      </template>

      <!-- 5. 成长足迹 -->
      <view v-if="calendarDays.length" class="sec-title"><text class="sec-emoji">🕐</text><text>成长足迹</text></view>

      <!-- 成长足迹：年月周视图（点年切月/点月看日历/点周看长条） -->
      <view v-if="calendarDays.length" class="cal-card">
        <view class="cal-head">
          <view class="cal-crumb" @click="showMonthGrid = true">
            <text>{{ calYear }}年</text><view class="cal-caret" v-html="ic('chev-down', 12)"></view>
          </view>
          <text class="cal-sep">›</text>
          <view class="cal-crumb" :class="{ 'cal-crumb-on': viewLevel === 'month' }" @click="viewLevel = 'month'">
            <text>{{ calMonth }}月</text>
          </view>
          <text class="cal-sep">›</text>
          <view class="cal-crumb" :class="{ 'cal-crumb-on': viewLevel === 'week' }" @click="viewLevel = 'week'">
            <text>第{{ currentWeek + 1 }}周</text>
          </view>
        </view>

        <!-- 周视图：周一~周日长条 -->
        <view v-if="viewLevel === 'week'" class="wk-list">
          <view v-for="(d, i) in weekDays" :key="d.date" class="wk-item" :class="{ 'wk-today': d.isToday }">
            <view class="wk-left">
              <text class="wk-weekday" :class="{ 'wk-today-txt': d.isToday }">{{ WEEK_NAMES[i] }}</text>
              <text class="wk-date" :class="{ 'wk-today-txt': d.isToday }">{{ d.month }}/{{ d.day }}</text>
            </view>
            <view class="wk-body">
              <template v-if="d.items.length">
                <!-- 周视图：技能项横向排列 -->
                <view v-for="(ev, j) in d.items" :key="j" class="wk-ev">
                  <text class="wk-ev-txt">{{ ev.type === 'skill' ? simplifySkillTitle(ev.title) : ev.title }}</text>
                </view>
              </template>
              <text v-else class="wk-empty">休息</text>
            </view>
          </view>
        </view>

        <!-- 月视图：格子日历 -->
        <view v-else class="cal-month">
          <view class="cal-mhead">
            <view class="cal-arrow" @click="shiftMonth(-1)"><view class="cal-arrow-ic" v-html="ic('chev-l', 16)"></view></view>
            <text class="cal-mtitle">{{ calYear }}年{{ calMonth }}月</text>
            <view class="cal-arrow" @click="shiftMonth(1)"><view class="cal-arrow-ic" v-html="ic('chev-r', 16)"></view></view>
          </view>
          <view class="cal-week">
            <text v-for="w in ['日', '一', '二', '三', '四', '五', '六']" :key="w" class="cal-week-cell">{{ w }}</text>
          </view>
          <view class="cal-grid">
            <view v-for="c in calCells" :key="c.key" class="cal-cell"
              :class="{ 'cal-empty': !c.day, 'cal-has': c.hasEvent, 'cal-today': c.isToday, 'cal-sel': c.date === selectedDate }"
              @click="c.day && selectDate(c.date)">
              <text class="cal-num">{{ c.day || '' }}</text>
              <view v-if="c.hasEvent" class="cal-dot"></view>
            </view>
          </view>
          <view v-if="selectedDate" class="cal-detail">
            <text class="cal-detail-title">{{ selectedDateText }}</text>
            <view v-if="selectedItems.length" class="cal-events">
              <view v-for="(ev, i) in selectedItems" :key="i" class="cal-ev">
                <view class="cal-ev-ic" v-html="ic(TL_ICON_NAMES[ev.type] || 'calendar', 13)"></view>
                <text class="cal-ev-txt">{{ ev.title }}</text>
              </view>
            </view>
            <text v-else class="cal-detail-empty">这一天没有记录，继续加油！</text>
          </view>
        </view>
      </view>

      <!-- 6. 分享 -->
      <view class="share-card">
        <view class="share-poster">
          <text class="sp-honor">{{ summary?.honor_level || '成长中' }}</text>
          <text class="sp-name">{{ summary?.nickname || '学员' }} 的成长成就</text>
          <view class="sp-tier">
            <view class="sp-tier-top">
              <text class="sp-tier-name">{{ tier?.title || summary?.honor_level || '新学员' }}</text>
              <text class="sp-tier-num">第 {{ overallTier }} 段</text>
            </view>
            <view class="sp-tier-bar"><view class="sp-tier-fill" :style="{ width: tierPercent + '%' }"></view></view>
            <text class="sp-tier-hint">{{ tier?.next_title ? '距「' + tier.next_title + '」还差 ' + tier.need + ' 阶' : '已达成最高段位 🎉' }}</text>
          </view>
          <view class="sp-stats">
            <text class="sp-stat">打卡 {{ summary?.total_checkins || 0 }} 次</text>
            <text class="sp-stat">徽章 {{ summary?.badges_earned || 0 }} 枚</text>
          </view>
        </view>
        <text class="share-hint">复制成长成就文案，分享到微信/朋友圈</text>
        <view class="share-btn" @click="copyShare"><view class="share-btn-ic" v-html="ic('share', 14)"></view><text>{{ sharing ? '复制中...' : '复制分享文案' }}</text></view>
      </view>
      </template>

      <view style="height:40px;"></view>
    </scroll-view>

    <!-- 选择月份弹层（点顶部「年」弹出，12 个月份格子） -->
    <view v-if="showMonthGrid" class="modal-mask" @click="showMonthGrid = false">
      <view class="modal-content month-modal" @click.stop>
        <view class="mg-head">
          <view class="mg-arrow" @click="shiftYear(-1)"><view class="mg-arrow-ic" v-html="ic('chev-l', 16)"></view></view>
          <text class="mg-title">{{ calYear }}年</text>
          <view class="mg-arrow" @click="shiftYear(1)"><view class="mg-arrow-ic" v-html="ic('chev-r', 16)"></view></view>
        </view>
        <view class="month-grid">
          <view v-for="m in 12" :key="m" class="month-cell"
            :class="{ 'month-cell-on': m === calMonth }"
            @click="pickMonth(m)">
            <text>{{ m }}月</text>
          </view>
        </view>
      </view>
    </view>
  </view>
  <!-- 晋级规则说明 Modal -->
  <tier-rules-modal v-model="showTierRules" :advance-pass="tier?.advance_pass || 3" />

  <!-- 学业规划报告 Modal（AI 学业规划报告设计稿版） -->
  <view v-if="showPlanModal" class="plan-modal-mask" @click="closePlanModal">
    <view class="plan-modal" @click.stop>
      <!-- 顶部导航 -->
      <view class="plan-nav">
        <view class="plan-nav-btn" @click="closePlanModal" v-html="ic('chev-l', 20)"></view>
        <text class="plan-nav-title">学业规划结果</text>
        <view class="plan-nav-btn" @click="closePlanModal" v-html="ic('x', 18)"></view>
      </view>

      <view v-if="!planLoading && academicPlan" class="plan-modal-body">
        <!-- 学生信息卡 -->
        <view class="plan-id-card">
          <view class="plan-id-left">
            <view class="plan-avatar">{{ planAvatar }}</view>
            <view class="plan-id-info">
              <view class="plan-id-name-row">
                <text class="plan-id-name">{{ academicPlan.student?.nickname || '学员' }}</text>
                <text class="plan-id-badge">生成于 {{ planTestDate }}</text>
              </view>
              <text class="plan-id-sub">{{ planLearnerLine }}</text>
            </view>
          </view>
          <view class="plan-id-boost">
            <text class="plan-id-boost-num">{{ planBoostTotal }}</text>
            <text class="plan-id-boost-label">最高提升</text>
          </view>
        </view>

        <!-- 状态总结（蓝卡） -->
        <view class="plan-status">
          <view class="plan-status-num-box">
            <text class="plan-status-num">{{ planBoostTotal }}</text>
            <text class="plan-status-unit">分</text>
          </view>
          <view class="plan-status-info">
            <text class="plan-status-label">最高提升空间</text>
            <text class="plan-status-title">{{ planStatusTitle }}</text>
            <text class="plan-status-desc">{{ planStatusDesc }}</text>
          </view>
        </view>

        <!-- 能力提分（原「学科成绩」，因系统无真实各科成绩，改为真实能力提分数据） -->
        <view v-if="planSubjects.length" class="plan-card">
          <text class="plan-card-title">能力提分</text>
          <view class="plan-subjects-grid">
            <view v-for="(s, i) in planSubjects" :key="i" class="plan-subject-cell">
              <text class="plan-subject-name">{{ s.subject }}</text>
              <text class="plan-subject-boost">+{{ s.boost }} 分</text>
            </view>
          </view>
        </view>

        <!-- 提分目标（按总提分切成三档） -->
        <view v-if="planBoostTotal > 0">
          <view class="plan-section-head">
            <text class="plan-section-title">提分目标</text>
            <text class="plan-section-sub">分阶段突破，越努力越接近满分</text>
          </view>
          <view
            v-for="(t, i) in planTiers"
            :key="i"
            class="plan-tier-card"
            :class="{ open: expandedTiers[i] }"
            @click="toggleTier(i)"
          >
            <view class="plan-tier-main">
              <view class="plan-tier-ic" v-html="ic(t.icon, 20)"></view>
              <view class="plan-tier-info">
                <text class="plan-tier-name">{{ t.title }}</text>
                <text class="plan-tier-desc">{{ t.desc }}</text>
              </view>
              <text class="plan-tier-score">{{ t.score }}</text>
              <text class="plan-chev">{{ expandedTiers[i] ? '▾' : '›' }}</text>
            </view>
            <text v-if="expandedTiers[i] && t.hint" class="plan-tier-hint">{{ t.hint }}</text>
          </view>
        </view>

        <!-- 规划要点 -->
        <view v-if="planNotes.length" class="plan-card">
          <text class="plan-card-title">规划要点</text>
          <view
            v-for="(n, i) in planNotes"
            :key="i"
            class="plan-note-row"
            :class="{ open: expandedNotes[i] }"
            @click="toggleNote(i)"
          >
            <view class="plan-note-ic" v-html="ic(n.icon, 14)"></view>
            <view class="plan-note-info">
              <view class="plan-note-head">
                <text class="plan-note-name">{{ n.title }}</text>
                <text class="plan-chev">{{ expandedNotes[i] ? '▾' : '›' }}</text>
              </view>
              <text class="plan-note-text">{{ expandedNotes[i] ? n.full : n.preview }}</text>
            </view>
          </view>
        </view>

        <view v-if="academicPlan.report_content" class="plan-card" @click="showFullReport = !showFullReport">
          <view class="plan-note-head">
            <text class="plan-card-title" style="margin-bottom:0;">完整报告</text>
            <text class="plan-chev">{{ showFullReport ? '▾' : '›' }}</text>
          </view>
          <view v-if="showFullReport" class="plan-full-report">
            <text v-for="(line, i) in planFullLines" :key="i" class="plan-full-line" :class="line.type">{{ line.text }}</text>
          </view>
        </view>

        <!-- 重要提示 -->
        <view class="plan-tip">
          <view class="plan-tip-ic" v-html="ic('info', 16)"></view>
          <text class="plan-tip-text">重要提示：坚持打卡、及时复盘，才能让规划真正变成分数。</text>
        </view>
      </view>

      <view v-if="planLoading" class="plan-modal-loading">
        <view class="plan-loading-spinner"></view>
        <text class="plan-loading-text">AI 正在为你生成学业规划...</text>
      </view>

      <!-- 底部刷新按钮 -->
      <view class="plan-footer">
        <view class="plan-refresh-btn" @click="openAcademicPlan(true)">
          <view class="plan-refresh-ic" v-html="ic('refresh-cw', 16)"></view>
          <text>刷新报告</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  ensureChildUser,
  fetchGrowthBadges,
  fetchGrowthTimeline,
  fetchGrowthCalendar,
  fetchGrowthSummary,
  fetchGrowthTier,
  fetchGrowthShare,
  fetchAcademicPlan,
} from '@/utils/userApi.js'
import {
  talentAvatarUrl,
  talentThemeColor,
  duanCN,
  decorateHonorPath,
  honorPathIndex,
  honorStepTag,
  duanNineSteps as buildDuanNineSteps,
} from '@/utils/talentState.js'

// 线性 SVG 图标（与首页/答疑页同一风格：24 视窗、currentColor 描边）
const ICON_PATHS = {
  star: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
  flame: '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>',
  zap: '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
  trophy: '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>',
  calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><polyline points="8 14 11.5 17 16 14"/>',
  message: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  gem: '<path d="M6 3h12l4 6-10 13L2 9Z"/><path d="M2 9h20"/><path d="M9 3 7 9l5 13 5-13-2-6"/>',
  crown: '<path d="M3 18 2.5 8 8 12.5 12 4l4 8.5L21.5 8 21 18Z"/><line x1="4" y1="21" x2="20" y2="21"/>',
  brain: '<path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/><path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/>',
  target: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
  trending: '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
  medal: '<circle cx="12" cy="8" r="7"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/>',
  clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
  check: '<polyline points="20 6 9 17 4 12"/>',
  'chev-l': '<polyline points="15 18 9 12 15 6"/>',
  'chev-r': '<polyline points="9 18 15 12 9 6"/>',
  'chev-down': '<polyline points="6 9 12 15 18 9"/>',
  share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>',
  x: '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
  'help-circle': '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
  'book-open': '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
  'flask': '<path d="M10 2v7.31L4.94 20.03A2 2 0 0 0 6.77 23h10.46a2 2 0 0 0 1.83-2.97L14 9.31V2"/><path d="M8.5 2h7"/><line x1="7.5" y1="15" x2="16.5" y2="15"/>',
  info: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
  'refresh-cw': '<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>',
}

function ic(name, size = 14) {
  const body = ICON_PATHS[name] || ICON_PATHS.star
  return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`
}

// 徽章名 → 图标（徽章名为后端 growth_service 固定定义）
const BADGE_ICONS = {
  首次测评: 'star',
  初露锋芒: 'flame',
  持之以恒: 'zap',
  百炼成钢: 'trophy',
  连续一周: 'calendar',
  答疑新星: 'message',
  知识达人: 'gem',
  全能王者: 'crown',
}

// 时间线事件类型 → 图标
const TL_ICON_NAMES = { assessment: 'star', checkin: 'calendar', streak: 'flame', skill: 'brain', qa: 'message', goal: 'target' }

const badges = ref([])
const events = ref([])
const summary = ref(null)
const tier = ref(null) // 🆕 六级九段（分享卡片用）
const sharePreview = ref('')
const sharing = ref(false)
const showTierRules = ref(false)

// 学业规划
const showPlanModal = ref(false)
const academicPlan = ref(null)
const planLoading = ref(false)
const expandedNotes = ref({})
const expandedTiers = ref({})
const showFullReport = ref(false)

function toggleNote(i) {
  expandedNotes.value = { ...expandedNotes.value, [i]: !expandedNotes.value[i] }
}
function toggleTier(i) {
  expandedTiers.value = { ...expandedTiers.value, [i]: !expandedTiers.value[i] }
}

// ── 成长足迹：年月周三级周视图 ──
const calendarDays = ref([]) // 后端返回：[{ date: 'YYYY-MM-DD', items: [{type,title,icon}] }]
const now = new Date()
const calYear = ref(now.getFullYear())
const calMonth = ref(now.getMonth() + 1)
const currentWeek = ref(0) // 选中 calWeeks 中的第几个自然周
const WEEK_NAMES = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const viewLevel = ref('week') // 'week' 周视图（长条） / 'month' 月视图（格子日历）
const showMonthGrid = ref(false) // 点顶部「年」弹出 12 个月份
const selectedDate = ref('') // 月视图里选中的某天

function pad2(n) { return String(n).padStart(2, '0') }
function dateStr(y, m, d) { return `${y}-${pad2(m)}-${pad2(d)}` }

function hasCalendarEvent(date) {
  return calendarDays.value.some((day) => day.date === date)
}

function dayItems(date) {
  return calendarDays.value.find((day) => day.date === date)?.items || []
}

// 该月覆盖的所有自然周（周一起始，可能跨到上月/下月）
function weeksOfMonth(y, m) {
  const first = new Date(y, m - 1, 1)
  const lastDay = new Date(y, m, 0)
  const dow = (first.getDay() + 6) % 7 // 周一 = 0
  const monday = new Date(y, m - 1, 1 - dow)
  const weeks = []
  let cursor = new Date(monday)
  while (cursor <= lastDay) {
    const start = new Date(cursor)
    const end = new Date(cursor)
    end.setDate(end.getDate() + 6)
    weeks.push({
      start,
      end,
      startLabel: `${start.getMonth() + 1}/${start.getDate()}`,
      endLabel: `${end.getMonth() + 1}/${end.getDate()}`,
    })
    cursor.setDate(cursor.getDate() + 7)
  }
  return weeks
}

const calWeeks = computed(() => weeksOfMonth(calYear.value, calMonth.value))

// 默认定位到包含"今天"的那一周
function defaultWeekIndex() {
  const today = new Date()
  const idx = calWeeks.value.findIndex((w) => w.start <= today && today <= w.end)
  return idx >= 0 ? idx : calWeeks.value.length - 1
}

// 选中周：周一~周日 7 天
const weekDays = computed(() => {
  const w = calWeeks.value[currentWeek.value]
  if (!w) return []
  const today = dateStr(now.getFullYear(), now.getMonth() + 1, now.getDate())
  const days = []
  for (let i = 0; i < 7; i++) {
    const d = new Date(w.start)
    d.setDate(d.getDate() + i)
    const ds = dateStr(d.getFullYear(), d.getMonth() + 1, d.getDate())
    days.push({ date: ds, month: d.getMonth() + 1, day: d.getDate(), items: dayItems(ds), isToday: ds === today })
  }
  return days
})

// 月视图：格子日历
const calCells = computed(() => {
  const y = calYear.value
  const m = calMonth.value
  const firstWeekday = new Date(y, m - 1, 1).getDay() // 0 = 周日
  const daysInMonth = new Date(y, m, 0).getDate()
  const cells = []
  for (let i = 0; i < firstWeekday; i++) cells.push({ key: `pad-l-${i}`, day: null })
  const today = dateStr(now.getFullYear(), now.getMonth() + 1, now.getDate())
  for (let d = 1; d <= daysInMonth; d++) {
    const ds = dateStr(y, m, d)
    cells.push({ key: ds, day: d, date: ds, hasEvent: hasCalendarEvent(ds), isToday: ds === today })
  }
  while (cells.length % 7 !== 0) cells.push({ key: `pad-r-${cells.length}`, day: null })
  return cells
})

const selectedItems = computed(() => dayItems(selectedDate.value))
const selectedDateText = computed(() => {
  if (!selectedDate.value) return ''
  const [y, m, d] = selectedDate.value.split('-').map(Number)
  const week = ['日', '一', '二', '三', '四', '五', '六'][new Date(y, m - 1, d).getDay()]
  return `${y}年${m}月${d}日 周${week}`
})

// 月视图默认选中：今天有活动就今天，否则最近有活动的天
function defaultSelectedDate() {
  const today = dateStr(now.getFullYear(), now.getMonth() + 1, now.getDate())
  if (hasCalendarEvent(today)) return today
  const past = calendarDays.value.filter((d) => d.date < today).pop()
  return past ? past.date : ''
}

function selectDate(date) {
  selectedDate.value = date
}

// 月视图内切换月份
function shiftMonth(delta) {
  let m = calMonth.value + delta
  let y = calYear.value
  if (m < 1) { m = 12; y-- }
  if (m > 12) { m = 1; y++ }
  calYear.value = y
  calMonth.value = m
  currentWeek.value = defaultWeekIndex()
  const monthPrefix = `${y}-${pad2(m)}`
  const inMonth = calendarDays.value.filter((d) => d.date.startsWith(monthPrefix))
  selectedDate.value = inMonth.length ? inMonth[0].date : ''
}

// 12 个月弹层：切年
function shiftYear(delta) {
  calYear.value += delta
}

// 12 个月弹层：选月 → 切月并进入月视图
function pickMonth(m) {
  calMonth.value = m
  currentWeek.value = defaultWeekIndex()
  viewLevel.value = 'month'
  selectedDate.value = defaultSelectedDate()
  showMonthGrid.value = false
}
const loading = ref(true)

const overallTier = computed(() => tier.value?.overall_tier || summary.value?.overall_tier || 1)
const tierPercent = computed(() => Math.round((overallTier.value / 9) * 100))
const curTier = computed(() => overallTier.value)

const talentAvatarImg = computed(() => talentAvatarUrl(summary.value?.talent_primary))
const talentColor = computed(() => talentThemeColor(summary.value?.talent_primary))
const tierCN = computed(() => duanCN(overallTier.value))
const honorPath = computed(() => decorateHonorPath(tier.value?.path))
const duanNineSteps = buildDuanNineSteps()

const memberDays = computed(() => {
  const since = summary.value?.member_since
  if (!since) return null
  const diff = Date.now() - new Date(`${since}T00:00:00`).getTime()
  if (Number.isNaN(diff) || diff < 0) return null
  return Math.floor(diff / 86400000) + 1
})

// 当前点按 /tier.honor_level 落在进阶之路上，门槛只认接口
const currentTitleIndex = computed(() =>
  honorPathIndex(tier.value?.honor_level || summary.value?.honor_level, tier.value?.path),
)

const nextTitleInfo = computed(() => {
  const t = tier.value
  if (t?.next_title && t.need) return { name: t.next_title, need: t.need }
  return null
})

const masteryChips = computed(() => {
  const target = summary.value?.mastery_skills_target || []
  const done = new Set(summary.value?.mastery_skills_done || [])
  return target.map((name) => ({ name, done: done.has(name) }))
})
const masteryDoneCount = computed(() => (summary.value?.mastery_skills_done || []).length)

const goalEvents = computed(() => events.value.filter((e) => !e.done))

// 徽章陈列：已获得（最新在前）> 进行中（完成度高优先）> 未开始
const sortedBadges = computed(() =>
  badges.value.slice().sort((a, b) => {
    if (!!a.earned !== !!b.earned) return a.earned ? -1 : 1
    if (a.earned && b.earned) return (b.earned_at || '').localeCompare(a.earned_at || '')
    return (badgeProgress(b)?.pct || 0) - (badgeProgress(a)?.pct || 0)
  })
)

// 近 7 天新获得的徽章：NEW 角标 + 呼吸光环
function isNewBadge(b) {
  if (!b.earned || !b.earned_at) return false
  const t = new Date(`${b.earned_at}T00:00:00`).getTime()
  if (Number.isNaN(t)) return false
  return Date.now() - t <= 7 * 86400000
}

// 新用户：无打卡且无徽章 → 展示空态引导
const isFreshUser = computed(() => {
  if (!summary.value) return false
  return !summary.value.total_checkins && !summary.value.badges_earned
})

// 目标卡：量化进度 + 可点击跳转到对应页
const goalCards = computed(() =>
  goalEvents.value.map((e) => {
    const g = { ...e, route: '', pct: null, progressText: '' }
    if (/打卡/.test(e.title)) {
      g.route = '/pages/training/index'
      const m = e.title.match(/(\d+)/)
      if (m) {
        const target = +m[1]
        const cur = summary.value?.total_checkins || 0
        g.pct = Math.min(100, Math.round((cur / target) * 100))
        g.progressText = `${Math.min(cur, target)}/${target}`
      }
    } else if (/核心能力/.test(e.title)) {
      g.route = '/pages/training/index'
      const total = masteryChips.value.length
      if (total) {
        g.pct = Math.round((masteryDoneCount.value / total) * 100)
        g.progressText = `${masteryDoneCount.value}/${total}`
      }
    } else if (/提问|答疑/.test(e.title)) {
      g.route = '/pages/qa/index'
    }
    return g
  })
)

function goGoal(g) {
  if (!g.route) return
  uni.navigateTo({ url: g.route })
}

function goTrain() {
  uni.navigateTo({ url: '/pages/training/index' })
}

function badgeProgress(b) {
  if (!b.progress) return null
  const m = String(b.progress).match(/(\d+)\/(\d+)/)
  if (!m) return null
  const cur = +m[1]
  const total = +m[2]
  if (!total) return null
  return { cur, total, pct: Math.round((cur / total) * 100) }
}

async function loadGrowth() {
  loading.value = true
  try {
    const uid = await ensureChildUser()
    const [b, t, s, sh, cal, ti] = await Promise.all([
      fetchGrowthBadges(uid),
      fetchGrowthTimeline(uid),
      fetchGrowthSummary(uid).catch(() => null),
      fetchGrowthShare(uid).catch(() => null),
      fetchGrowthCalendar(uid).catch(() => []),
      fetchGrowthTier(uid).catch(() => null),
    ])
    badges.value = b
    events.value = t
    summary.value = s
    sharePreview.value = sh?.text || ''
    calendarDays.value = cal || []
    tier.value = ti || null
    currentWeek.value = defaultWeekIndex()
  } catch (e) {
    badges.value = []
    events.value = []
  }
  loading.value = false
}

onMounted(loadGrowth)

function goBack() { uni.navigateBack({ delta: 1 }) }

async function copyShare() {
  if (sharing.value) return
  sharing.value = true
  // 🆕 分享文案带上段位（六级九段）
  const t = tier.value
  const tierLine = t ? `【${t.title || t.honor_level || '新学员'} · 第${t.overall_tier}段】` : ''
  const text = (sharePreview.value || '我在劲脑天赋成长平台坚持学习，一起来打卡吧！') + (tierLine ? '\n' + tierLine : '')
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    uni.showToast({ title: '已复制到剪贴板', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: '复制失败，请手动复制', icon: 'none' })
  }
  sharing.value = false
}

// 打开学业规划报告
async function openAcademicPlan(refresh = false) {
  showPlanModal.value = true
  if (academicPlan.value && !refresh) return
  
  planLoading.value = true
  try {
    const uid = await ensureChildUser()
    const plan = await fetchAcademicPlan(uid, refresh)
    academicPlan.value = plan
    expandedNotes.value = {}
    expandedTiers.value = {}
    showFullReport.value = false
  } catch (e) {
    console.error('Failed to load academic plan:', e)
    uni.showToast({ title: '加载失败，请重试', icon: 'none' })
  }
  planLoading.value = false
}

function closePlanModal() {
  showPlanModal.value = false
}

// 简化周视图中的训练项标题（如"学者极速学习3阶段1"→"极速学习"）
function simplifySkillTitle(title) {
  if (!title) return '训练'
  // 去掉"学者"前缀和后面的阶段号
  return title
    .replace(/^学者/, '')
    .replace(/\d+阶段\d+$/, '')
    .replace(/训练$/, '')
    .trim() || title
}

// 格式化报告内容（简单的Markdown-like渲染）
function formatReportContent(content) {
  if (!content) return []
  const lines = content.split('\n')
  return lines.map(line => {
    let trimmed = line.trim()
    if (!trimmed) return { type: 'spacer', text: '' }
    
    // 处理标题 (# / ## / ###)
    if (trimmed.startsWith('### ')) {
      return { type: 'section', text: trimmed.substring(4) }
    }
    if (trimmed.startsWith('## ')) {
      return { type: 'section', text: trimmed.substring(3) }
    }
    if (trimmed.startsWith('# ')) {
      return { type: 'title', text: trimmed.substring(2) }
    }
    
    // 处理有序列表 (1. 2. 3.) - 作为bullet显示，保留文本
    if (/^\d+\.\s/.test(trimmed)) {
      return { type: 'bullet', text: trimmed.replace(/\*\*/g, '') }
    }
    
    // 处理无序列表 (- / * / •)
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ') || trimmed.startsWith('• ')) {
      return { type: 'bullet', text: trimmed.substring(2).replace(/\*\*/g, '') }
    }
    
    // 处理带粗体的普通文本：去除**标记，保留文字
    // 包含emoji开头的视为小节标题
    if (/^[📈📅💡🔥🎯📊📝✨🌟💪]/.test(trimmed.replace(/\*\*/g, ''))) {
      return { type: 'section', text: trimmed.replace(/\*\*/g, '') }
    }
    
    // 普通文本：去除**标记
    return { type: 'text', text: trimmed.replace(/\*\*/g, '') }
  })
}

// ── 学业规划报告（设计稿版）数据映射 ──

// 头像：取昵称首字
const planAvatar = computed(() => {
  const n = academicPlan.value?.student?.nickname || '学'
  return n.trim().charAt(0)
})

// 测试日期：2026-08-15 → 2026.08.15
const planTestDate = computed(() => {
  const d = academicPlan.value?.generated_at
  if (!d) return ''
  return String(d).slice(0, 10).replace(/-/g, '.')
})

const planLearnerLine = computed(() => {
  const s = academicPlan.value?.student || {}
  const bits = ['学业规划报告']
  if (s.grade) bits.push(s.grade)
  if (s.age) bits.push(`${s.age}岁`)
  return bits.join(' · ')
})

const planFullLines = computed(() => formatReportContent(academicPlan.value?.report_content || ''))

// 最高提升空间（总提分）
const planBoostTotal = computed(() => academicPlan.value?.score_projection?.total_estimated_boost || 0)

// 状态卡主标题：根据提分空间给出分段文案
const planStatusTitle = computed(() => {
  const b = planBoostTotal.value
  if (b >= 20) return '潜力巨大，未来可期'
  if (b >= 10) return '还有很大进步空间'
  if (b > 0) return '稳步提升，稳扎稳打'
  return '开始训练，解锁提分空间'
})

// 状态卡描述：从报告「现状评估」小节取第一条要点
const planStatusDesc = computed(() => {
  const s = planNotes.value.find(n => n.type === 'status')
  if (s) return s.preview || s.text
  const c = academicPlan.value?.student?.total_checkins || 0
  return c > 0 ? `已累计打卡 ${c} 天，坚持训练还能再进一步。` : '完成第一次打卡，AI 将为你规划提分路径。'
})

// 能力提分列表（原「学科成绩」，取真实数据：能力维度 + 预计提分）
const planSubjects = computed(() => {
  const items = academicPlan.value?.score_projection?.items || []
  return items.map(it => ({ subject: it.subject, boost: it.estimated_boost }))
})

function previewText(full, limit = 42) {
  const t = String(full || '').replace(/\s+/g, ' ').trim()
  if (!t) return ''
  return t.length > limit ? `${t.slice(0, limit)}…` : t
}

const planTiers = computed(() => {
  const api = academicPlan.value?.goal_stages
  if (api?.length) return api
  const total = planBoostTotal.value
  if (total <= 0) return []
  const third = Math.max(1, Math.round(total / 3))
  const two = Math.max(third + 1, Math.round((total * 2) / 3))
  return [
    { icon: 'zap', title: '三档提分', desc: '先拿下基础分', score: `1-${third} 分`, hint: '每天先完成必修打卡，把基础动作做稳。' },
    { icon: 'target', title: '二档提分', desc: '再冲一程', score: `${third + 1}-${two} 分`, hint: '连续训练，把方法用到当天作业里。' },
    { icon: 'trophy', title: '一档提分', desc: '挑战最高目标', score: `${two + 1}-${total} 分`, hint: '冲击更高正确率和速度。' },
  ]
})

const NOTE_META = [
  { key: 'status', icon: 'help-circle', title: '问题描述', type: 'status', match: /现状|评估/ },
  { key: 'motto', icon: 'zap', title: '行动寄语', type: 'motto', match: /寄语|加油|坚持/ },
  { key: 'plan', icon: 'book-open', title: '规划建议', type: 'plan', match: /规划|建议|目标/ },
  { key: 'talent', icon: 'flask', title: '天赋发挥', type: 'talent', match: /天赋/ },
]

const planNotes = computed(() => {
  const plan = academicPlan.value
  if (!plan) return []
  const sections = plan.sections || {}
  const fromApi = NOTE_META.map((m) => {
    const full = (sections[m.key] || '').trim()
    if (!full) return null
    return { ...m, full, preview: previewText(full), text: full }
  }).filter(Boolean)
  if (fromApi.length) return fromApi.slice(0, 4)

  const lines = formatReportContent(plan.report_content)
  const collected = {}
  let curTitle = ''
  for (const line of lines) {
    if (line.type === 'title' || line.type === 'section') {
      curTitle = line.text
      continue
    }
    if (line.type !== 'text' && line.type !== 'bullet') continue
    const clean = line.text.trim()
    if (!clean) continue
    const meta = NOTE_META.find((m) => m.match.test(curTitle))
    if (!meta) continue
    if (!collected[meta.title]) collected[meta.title] = { ...meta, parts: [] }
    collected[meta.title].parts.push(clean)
  }
  return NOTE_META.map((m) => {
    const row = collected[m.title]
    if (!row) return null
    const full = row.parts.join('\n')
    return { ...m, full, preview: previewText(full), text: full }
  }).filter(Boolean)
})
</script>

<style scoped>
.app { height:100vh;height:100dvh; max-width:var(--app-max-width, 480px); margin:0 auto; background:var(--bg); font-family:-apple-system,"PingFang SC",sans-serif; display:flex; flex-direction:column; position:relative; overflow:hidden; box-sizing:border-box; }
.nav { display:flex; align-items:center; padding:14px 14px 0; }
.nav-back { width:36px; height:36px; border-radius:50%; background:var(--bg-card); display:flex; align-items:center; justify-content:center; cursor:pointer; flex-shrink:0; }
.nav-title-wrap { flex:1; display:flex; flex-direction:column; align-items:center; }
.nav-title { color:var(--text); font-size:17px; font-weight:700; line-height:1.2; }
.nav-sub { color:var(--text-dim); font-size:10px; font-weight:500; letter-spacing:1px; margin-top:2px; }
.nav-spacer { width:36px; flex-shrink:0; }
.body { flex:1; overflow-y:auto; overflow-x:hidden; padding:12px 14px 0; box-sizing:border-box; width:100%; scrollbar-width:none; -ms-overflow-style:none; }
:deep(uni-scroll-view) ::-webkit-scrollbar,
:deep(.uni-scroll-view) ::-webkit-scrollbar,
.body *::-webkit-scrollbar,
.body::-webkit-scrollbar { display:none; width:0; height:0; }
.sec-title { color:var(--text); font-size:16px; font-weight:700; display:flex; align-items:center; gap:8px; margin:0 0 12px; }
.sec-emoji { font-size:18px; line-height:1; flex-shrink:0; }
.sec-sub { color:var(--text-dim); font-size:12px; font-weight:400; margin-left:auto; flex-shrink:0; }

/* 1. 荣誉 Hero 卡 */
.hero-card {
  /* 沿用 --focus-bg：与「成长成就」分享海报同底色，白色/夜间模式自动适配 */
  background: var(--focus-bg);
  border: 1px solid rgba(59,130,246,0.35);
  border-radius:24px; padding:20px 18px 16px; margin-bottom:20px;
  box-sizing:border-box;
  box-shadow: 0 0 30px rgba(59,130,246,0.12), inset 0 1px 0 rgba(255,255,255,0.08);
  position:relative;
  overflow:hidden;
}
/* 白色主题：荣誉卡背景已随 --focus-bg 自动切换（与成长成就海报同色），
   蓝底上把次要文字提亮保证可读（与分享海报的白色文字一致） */
[data-theme="white"] .hero-card .hero-nick,
[data-theme="white"] .hero-card .hero-since,
[data-theme="white"] .hero-card .hs-lbl,
[data-theme="white"] .hero-card .hero-tier-total { color:rgba(255,255,255,0.85); }
/* 科技感横线纹理 */
.hero-card::before {
  content:''; position:absolute; inset:0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 3px,
    rgba(59,130,246,0.03) 3px,
    rgba(59,130,246,0.03) 4px
  );
  pointer-events:none;
}
/* 右上角光效 */
.hero-card::after {
  content:''; position:absolute; top:-40px; right:-40px;
  width:160px; height:160px; border-radius:50%;
  background: radial-gradient(circle, rgba(34,197,94,0.08) 0%, transparent 70%);
  pointer-events:none;
}
/* 荣誉卡上方信息行：天赋头像（只显示头部）+ 成长历程碑 / MILESTONES + 段位椭圆 */
.hero-idbar {
  display:flex; align-items:center; gap:12px;
  padding:4px 2px 14px; position:relative; z-index:1;
}
/* 圆形头像：背景图放大只显示头部，边框颜色由天赋动态绑定（思者=绿） */
.hero-idbar-avatar {
  width:52px; height:52px; border-radius:50%; overflow:hidden; flex-shrink:0;
  border:2px solid var(--border);
  background-color:var(--bg-card);
  background-size: auto 230%;       /* 高度放大到容器的2.3倍，聚焦头部 */
  background-position:50% 26%;      /* 垂直定位到脸部（数值增大=脸往下移） */
  background-repeat:no-repeat;
  box-shadow:var(--card-glow);
}
.hero-idbar-main { flex:1; min-width:0; }
.hero-idbar-title { color:var(--text); font-size:17px; font-weight:800; display:block; letter-spacing:1px; }
.hero-idbar-en {
  color:var(--text-dim); font-size:10px; font-weight:600;
  letter-spacing:3px; display:block; margin-top:3px; text-transform:uppercase;
}
/* 当前段位椭圆：金色（偏深、与已获积分同色系）、无底色，显示 一阶/九阶 */
.hero-tier-pill {
  flex-shrink:0; border-radius:999px; text-align:center;
  padding:8px 12px;
  border:1px solid #f5c842;
  background:transparent;
}
.hero-tier-pill-num { color:#f5c842; font-size:15px; font-weight:800; }
.hero-tier-pill-sep { color:#f5c842; font-size:12px; font-weight:600; opacity:0.7; }
.hero-tier-pill-total { color:#f5c842; font-size:13px; font-weight:700; opacity:0.85; }

/* 荣誉 Hero 卡（卡片内部，原有内容） */
.hero-top { display:flex; align-items:flex-start; justify-content:space-between; position:relative; z-index:1; }
.hero-id { min-width:0; }
.hero-honor { color:#fff; font-size:32px; font-weight:900; display:block; letter-spacing:2px; text-shadow:0 2px 12px rgba(0,0,0,0.4); }
.hero-nick { color:rgba(148,163,184,0.9); font-size:13px; display:block; margin-top:6px; }
.hero-nick-talent { color:#ffd666; font-weight:600; }
[data-theme="white"] .hero-card .hero-nick .hero-nick-talent { color:#ffd666; }
.hero-since { color:rgba(148,163,184,0.7); }
.hero-talent-tag { color:var(--gold); font-weight:600; }
.hero-tier { text-align:right; flex-shrink:0; }
.hero-tier-num { color:#ffd666; font-size:22px; font-weight:800; text-shadow:0 0 10px rgba(245,200,66,0.3); }
.hero-tier-total { color:rgba(148,163,184,0.7); font-size:14px; font-weight:600; }
.tier-bar { height:8px; border-radius:4px; background:rgba(255,255,255,0.1); margin:14px 0 16px; overflow:hidden; position:relative; z-index:1; }
.tier-fill { height:100%; border-radius:4px; background:linear-gradient(90deg,#3b82f6 0%,#22c55e 100%); transition:width 0.6s ease; box-shadow:0 0 8px rgba(59,130,246,0.5); }
.streak-pill {
  display:inline-flex; align-items:center; gap:4px;
  background:rgba(34,197,94,0.15); border:1px solid rgba(34,197,94,0.35);
  color:var(--green); border-radius:999px; padding:4px 10px;
  font-size:11px; font-weight:600; margin:-6px 0 14px;
}
.streak-ic { display:flex; align-items:center; }
.hero-stats { display:flex; justify-content:space-around; position:relative; z-index:1; }
.hs-num { color:#fff; font-size:20px; font-weight:800; display:block; text-align:center; }
.hs-lbl { color:rgba(148,163,184,0.8); font-size:11px; display:block; text-align:center; margin-top:4px; }
.hero-talent { color:#ffd666; font-size:13px; font-weight:600; display:block; margin-top:14px; text-align:center; position:relative; z-index:1; text-shadow:0 0 8px rgba(245,200,66,0.2); }

/* 新用户空态引导 */
.fresh-card {
  display:flex; align-items:center; gap:10px;
  background:linear-gradient(135deg, var(--accent-bg), transparent);
  border:1px solid var(--accent);
  border-radius:16px; padding:14px; margin-bottom:20px; box-sizing:border-box;
}
.fresh-ic {
  width:36px; height:36px; border-radius:10px; flex-shrink:0;
  background:var(--accent-bg); color:var(--accent);
  display:flex; align-items:center; justify-content:center;
}
.fresh-body { flex:1; min-width:0; }
.fresh-title { color:var(--text); font-size:14px; font-weight:700; display:block; }
.fresh-desc { color:var(--text-dim); font-size:11px; display:block; margin-top:2px; }
.fresh-btn { background:var(--accent); border-radius:999px; padding:8px 16px; flex-shrink:0; cursor:pointer; }
.fresh-btn text { color:#fff; font-size:12px; font-weight:600; }
.fresh-btn:active { opacity:0.85; }

/* 2. 进阶之路 */
/* 弹窗基础样式（月份选择器使用） */
.modal-mask { position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.6); display:flex; align-items:center; justify-content:center; z-index:1000; padding:20px; }
.modal-content { background:var(--bg-card); border-radius:20px; width:100%; max-width:400px; max-height:80vh; display:flex; flex-direction:column; overflow:hidden; }
.path-card { background:var(--bg-card); border:1px solid var(--border); border-radius:20px; padding:18px 14px 16px; margin-bottom:20px; box-sizing:border-box; box-shadow: var(--card-glow); }
.tier9-head { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:18px; }
.tier9-title { display:flex; align-items:center; gap:8px; min-width:0; }
.tier9-medal { display:flex; color:var(--gold); flex-shrink:0; font-size:18px; }
.tier9-name { color:var(--text); font-size:18px; font-weight:800; white-space:nowrap; }
.tier9-num { color:var(--accent); font-size:12px; font-weight:600; background:var(--accent-bg); border:1px solid rgba(59,130,246,0.3); border-radius:999px; padding:3px 12px; flex-shrink:0; }
.tier9-next { color:var(--text-dim); font-size:12px; font-weight:500; white-space:nowrap; }
.tier9-next.top { color:var(--gold); }
.path-steps {
  display:flex; align-items:stretch;
  background:transparent;
  gap:0;
  position:relative;
}
.path-step {
  flex:1 1 0; min-width:0;
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  gap:6px; padding:10px 2px 6px;
  transition:none;
  position:relative;
  z-index:1;
}
/* 节点之间的分段连线：每个节点（除最后一个）右侧画一段线到相邻节点 */
.path-step:not(:last-child)::after {
  content:''; position:absolute;
  top:calc(10px + 24px - 1px); /* 10px 上内边距 + 徽章半高(24px) - 线半高，让线穿过徽章中心 */
  left:calc(50% + 24px);
  right:calc(-50% + 24px);
  height:2px;
  background:rgba(255,255,255,0.1);
  z-index:0;
}
/* 已完成节点右侧连线变绿色 */
.path-step.done:not(:last-child)::after {
  background:var(--green);
  box-shadow:0 0 6px rgba(34,197,94,0.4);
}
.path-step-badge {
  width:48px; height:48px; border-radius:50%;
  display:flex; align-items:center; justify-content:center;
  background:rgba(15,26,46,0.9);
  border:2px solid rgba(255,255,255,0.1);
  line-height:1;
  transition:all 0.3s;
}
.path-step-badge text { font-size:22px; line-height:1; filter:grayscale(1); opacity:0.4; }
.path-step-name {
  color:var(--text-dim); font-size:11px; font-weight:700;
  text-align:center; line-height:1.2;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
  max-width:100%;
}
.path-step-tag {
  color:var(--text-hint); font-size:9px; font-weight:500;
  line-height:1;
}
/* 已达成节点：蓝色边框，彩色图标 */
.path-step.done .path-step-badge {
  border-color:var(--accent);
  background:rgba(59,130,246,0.1);
  box-shadow:0 0 12px rgba(59,130,246,0.2);
}
.path-step.done .path-step-badge text { filter:none; opacity:1; }
.path-step.done .path-step-name { color:var(--accent); }
.path-step.done .path-step-tag { color:var(--accent); opacity:.75; }

/* 当前节点：绿色发光圆形 */
.path-step.cur .path-step-badge {
  border-color:var(--green);
  background:var(--green);
  box-shadow:0 0 20px rgba(34,197,94,0.5), 0 0 40px rgba(34,197,94,0.2);
  animation: curNodePulse 2s ease-in-out infinite;
}
.path-step.cur .path-step-badge text { filter:none; opacity:1; }
.path-step.cur .path-step-name { color:var(--green); font-weight:800; }
.path-step.cur .path-step-tag { color:var(--green); }
@keyframes curNodePulse {
  0%, 100% { box-shadow:0 0 20px rgba(34,197,94,0.5), 0 0 40px rgba(34,197,94,0.2); }
  50% { box-shadow:0 0 25px rgba(34,197,94,0.6), 0 0 50px rgba(34,197,94,0.3); }
}

/* 未解锁节点：灰暗 */
.path-step.locked .path-step-badge { border-color:rgba(148,163,184,0.4); background:rgba(148,163,184,0.12); }
.path-step.locked .path-step-badge text { filter:grayscale(1); opacity:.3; }
.path-step.locked .path-step-name { color:var(--text-hint); opacity:0.6; }
.path-step.locked .path-step-tag { color:var(--text-hint); opacity:.4; }

/* 九段（技能等级 1-9）：并入进阶之路大卡 */
.tier9-divider { height:1px; background:var(--border); margin:16px 0 14px; }
.tier9-steps {
  display:flex; align-items:stretch;
  gap:12px;
  background:transparent;
  border:none;
  border-radius:0;
  overflow:visible;
  margin-bottom:14px;
}
/* 九段：竖向拉长的长方形 + 平行四边形（skewX 向右倾斜）。
   未点亮（2-9）用背景浅色底（不用蓝色），仅当前段点亮为浅蓝渐变 */
.tier9-step {
  flex:1 1 0; min-width:0;
  display:flex; align-items:center; justify-content:center;
  padding:13px 0;
  border:1px solid rgba(148,163,184,0.25);
  border-radius:5px;
  transform:skewX(-8deg);
  transition:all 0.3s;
  background:rgba(148,163,184,0.10); /* 背景底色，不用蓝色 */
}
.tier9-cell {
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  gap:2px;
  transform:skewX(8deg); /* 反向倾斜，保证数字正立 */
}
.tier9-cell-num {
  font-size:15px; font-weight:700; line-height:1;
  color:rgba(148,163,184,0.85);
}
.tier9-cell-duan {
  font-size:0px;
}
/* 未达：背景底色，灰字（next 由下面绿边规则接管） */
.tier9-step:not(.done):not(.cur):not(.next) .tier9-cell-num { color:rgba(148,163,184,0.7); }
/* 已达：背景底色 + 淡蓝描边标记，浅蓝字 */
.tier9-step.done {
  border-color:rgba(96,165,250,0.55);
  background:rgba(148,163,184,0.10);
}
.tier9-step.done .tier9-cell-num { color:#60a5fa; opacity:1; }
/* 当前段：中蓝渐变 + 白字加粗 + 渐变亮端色清晰外框，无阴影 */
.tier9-step.cur {
  border:2px solid #93c5fd;
  background:linear-gradient(135deg, #3b82f6 0%, #93c5fd 100%);
  box-shadow:none;
}
.tier9-step.cur .tier9-cell-num { color:#fff; opacity:1; font-weight:800; text-shadow:0 1px 3px rgba(30,64,175,0.45); }
/* 下一段：绿色边框发光（提示即将到达），底色背景底色，绿字 */
.tier9-step.next {
  border-color:var(--green);
  box-shadow:0 0 10px rgba(34,197,94,0.3);
}
.tier9-step.next .tier9-cell-num { color:var(--green); }
.tier9-foot { display:flex; align-items:center; justify-content:center; gap:10px; margin-top:8px; }
.tier9-hint { color:var(--text-dim); font-size:12px; }
.tier9-hint b { color:var(--gold); font-weight:700; }
.tier9-info-btn {
  display:inline-flex; align-items:center; gap:4px;
  padding:4px 10px; border-radius:999px;
  background:transparent;
  border:none;
  cursor:pointer;
}
.tier9-info-btn:active { opacity:0.7; }
.tier9-info-btn text:first-child { color:var(--accent); font-size:12px; line-height:1; font-weight:600; }
.tier9-info-label { color:var(--accent); font-size:12px; font-weight:500; text-decoration:underline; text-underline-offset:2px; }

/* 3. 荣誉徽章 */
.badge-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:20px; }
.badge-item { position:relative; text-align:center; background:var(--bg-card); border:1px solid var(--border); border-radius:14px; padding:10px 4px 8px; box-sizing:border-box; }
.badge-item.locked { opacity:0.55; }
.badge-new {
  position:absolute; top:4px; right:4px; z-index:1;
  background:#f59e0b; border-radius:4px; padding:1px 4px;
}
.badge-new text { color:#fff; font-size:8px; font-weight:700; }
.badge-circle.pulse { animation: badgePulse 2s ease-in-out infinite; }
@keyframes badgePulse {
  0%, 100% { box-shadow:0 0 0 2px rgba(245,200,66,0.45); }
  50% { box-shadow:0 0 0 6px rgba(245,200,66,0.12); }
}
.badge-circle { width:44px; height:44px; border-radius:50%; margin:0 auto 6px; display:flex; align-items:center; justify-content:center; background:var(--bg); color:var(--text-hint); }
.badge-item:not(.locked) .badge-circle { background:var(--gold-bg); color:var(--gold); box-shadow:0 0 0 2px rgba(245,200,66,0.45); }
.badge-name { color:var(--text); font-size:10px; font-weight:600; display:block; }
.badge-date { color:var(--gold); font-size:9px; display:block; margin-top:3px; }
.badge-bar { height:4px; border-radius:2px; background:var(--bg); margin:5px 6px 3px; overflow:hidden; }
.badge-bar-fill { height:100%; border-radius:2px; background:linear-gradient(90deg,var(--gold),#f59e0b); }
.badge-prog { color:var(--text-dim); font-size:9px; display:block; }
.badge-cond { color:var(--text-dim); font-size:9px; display:block; margin-top:3px; }

/* 4. 下一个目标 */
.goal-card { display:flex; align-items:flex-start; gap:10px; background:var(--bg-card); border:1px dashed var(--accent); border-radius:14px; padding:12px 14px; margin-bottom:8px; box-sizing:border-box; }
.goal-card.clickable { cursor:pointer; transition:background 0.15s; }
.goal-card.clickable:active { background:var(--accent-bg); }
.goal-ic { width:30px; height:30px; border-radius:9px; background:var(--accent-bg); color:var(--accent); display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.goal-body { flex:1; min-width:0; }
.goal-head { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.goal-title { color:var(--text); font-size:13px; font-weight:600; }
.goal-prog-text { color:var(--accent); font-size:11px; font-weight:700; flex-shrink:0; }
.goal-bar { height:5px; border-radius:3px; background:var(--bg); margin:7px 0 2px; overflow:hidden; }
.goal-bar-fill { height:100%; border-radius:3px; background:var(--accent); transition:width 0.5s ease; }
.goal-desc { color:var(--text-dim); font-size:11px; display:block; margin-top:3px; }
.goal-arrow { color:var(--text-dim); align-self:center; flex-shrink:0; display:flex; align-items:center; }

/* 5. 成长足迹：年月周周视图 + 大事记 */
.cal-card { background:var(--bg-card); border:1px solid var(--border); border-radius:16px; padding:14px 12px 12px; margin-bottom:16px; box-sizing:border-box; }
.cal-head { display:flex; align-items:center; gap:8px; margin-bottom:14px; flex-wrap:wrap; }
.cal-crumb { display:flex; align-items:center; gap:3px; background:var(--bg); border:1px solid var(--border); border-radius:8px; padding:6px 10px; cursor:pointer; }
.cal-crumb:active { background:var(--accent-bg); border-color:var(--accent); }
.cal-crumb text { font-size:13px; font-weight:600; color:var(--text); }
.cal-caret { display:flex; align-items:center; color:var(--text-dim); }
.cal-sep { color:var(--text-hint); font-size:14px; }
.cal-crumb-on { background:var(--accent-bg); border-color:var(--accent); }
.cal-crumb-on text { color:var(--accent); }
.wk-list { display:flex; flex-direction:column; gap:8px; }
.wk-item { display:flex; align-items:flex-start; gap:12px; background:var(--bg); border:1px solid var(--border); border-radius:12px; padding:10px 12px; box-sizing:border-box; }
.wk-item.wk-today { border-color:var(--accent); background:var(--accent-bg); }
.wk-left { width:44px; flex-shrink:0; display:flex; flex-direction:column; align-items:center; }
.wk-weekday { font-size:12px; font-weight:700; color:var(--text-dim); }
.wk-date { font-size:12px; color:var(--text-hint); margin-top:2px; }
.wk-today-txt { color:var(--accent); }
.wk-body { flex:1; min-width:0; display:flex; flex-direction:row; flex-wrap:wrap; gap:6px 8px; align-items:center; }
.wk-ev { display:flex; align-items:center; gap:4px; background:rgba(139,92,246,0.08); padding:4px 8px; border-radius:6px; }
.wk-ev-ic { width:16px; height:16px; border-radius:4px; color:var(--accent); display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.wk-ev-txt { font-size:11px; color:var(--text); line-height:1.3; white-space:nowrap; }
.wk-ev-more { font-size:11px; color:var(--accent); font-weight:600; background:rgba(139,92,246,0.12); padding:4px 8px; border-radius:6px; }
.wk-empty { font-size:12px; color:var(--text-hint); }

/* 月视图：格子日历 */
.cal-month { padding-top:2px; }
.cal-mhead { display:flex; align-items:center; justify-content:center; gap:16px; margin-bottom:10px; }
.cal-mtitle { color:var(--text); font-size:14px; font-weight:700; min-width:96px; text-align:center; }
.cal-arrow { width:30px; height:30px; border-radius:9px; background:var(--bg); color:var(--text-dim); display:flex; align-items:center; justify-content:center; cursor:pointer; }
.cal-arrow:active { background:var(--accent-bg); color:var(--accent); }
.cal-arrow-ic { display:flex; align-items:center; }
.cal-week { display:flex; }
.cal-week-cell { flex:1; text-align:center; color:var(--text-hint); font-size:11px; padding-bottom:8px; }
.cal-grid { display:flex; flex-wrap:wrap; }
.cal-cell { width:14.2857%; height:38px; display:flex; flex-direction:column; align-items:center; justify-content:center; position:relative; cursor:pointer; border-radius:9px; }
.cal-cell:active { background:var(--bg); }
.cal-empty { cursor:default; }
.cal-empty:active { background:transparent; }
.cal-num { color:var(--text-dim); font-size:13px; font-weight:500; line-height:1; }
.cal-today .cal-num { color:var(--accent); font-weight:700; }
.cal-has .cal-num { color:var(--text); font-weight:700; }
.cal-sel { background:var(--accent); }
.cal-sel .cal-num { color:#fff; }
.cal-dot { width:4px; height:4px; border-radius:50%; background:var(--accent); margin-top:3px; }
.cal-sel .cal-dot { background:#fff; }
.cal-detail { margin-top:12px; border-top:1px solid var(--border); padding-top:10px; }
.cal-detail-title { color:var(--text); font-size:12px; font-weight:700; display:block; margin-bottom:8px; }
.cal-events { display:flex; flex-direction:row; flex-wrap:wrap; gap:6px 8px; }
.cal-ev { display:flex; align-items:center; gap:5px; background:rgba(139,92,246,0.08); padding:5px 10px; border-radius:6px; }
.cal-ev-ic { width:16px; height:16px; border-radius:4px; color:var(--accent); display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.cal-ev-txt { color:var(--text); font-size:12px; line-height:1.4; white-space:nowrap; }
.cal-detail-empty { color:var(--text-hint); font-size:12px; display:block; padding:4px 0; }

/* 12 个月份弹层：弹框加宽，格子留空间 */
.month-modal { max-width:480px; padding:4px 0 20px; }
.mg-head { display:flex; align-items:center; justify-content:center; gap:16px; margin:14px 0 16px; }
.mg-arrow { width:32px; height:32px; border-radius:10px; background:var(--bg); color:var(--text-dim); display:flex; align-items:center; justify-content:center; cursor:pointer; }
.mg-arrow:active { background:var(--accent-bg); color:var(--accent); }
.mg-arrow-ic { display:flex; align-items:center; }
.mg-title { color:var(--text); font-size:17px; font-weight:700; min-width:90px; text-align:center; }
.month-grid { display:flex; flex-wrap:wrap; gap:12px; padding:0 24px; }
.month-cell { width:calc((100% - 24px) / 3); box-sizing:border-box; background:var(--bg); border:1px solid var(--border); border-radius:12px; padding:18px 0; display:flex; align-items:center; justify-content:center; cursor:pointer; }
.month-cell:active { background:var(--accent-bg); }
.month-cell text { font-size:15px; font-weight:600; color:var(--text-dim); }
.month-cell-on { background:var(--accent-bg); border-color:var(--accent); }
.month-cell-on text { color:var(--accent); }

/* 7. 分享 */
.share-card { background:var(--bg-card); border-radius:16px; padding:16px; text-align:center; margin-bottom:20px; border:1px solid var(--border); box-sizing:border-box; }
.share-poster { background:var(--focus-bg); border-radius:14px; padding:18px 14px; margin-bottom:12px; box-shadow:0 6px 18px rgba(37,99,235,0.18); }
.sp-honor { color:#ffd666; font-size:18px; font-weight:800; display:block; }
.sp-name { color:rgba(255,255,255,0.85); font-size:13px; display:block; margin-top:4px; }
.sp-tier { margin-top:12px; background:rgba(255,255,255,0.08); border-radius:12px; padding:10px 12px; }
.sp-tier-top { display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; }
.sp-tier-name { color:#ffd666; font-size:14px; font-weight:700; }
.sp-tier-num { color:rgba(255,255,255,0.85); font-size:12px; font-weight:600; }
.sp-tier-bar { height:6px; background:rgba(255,255,255,0.12); border-radius:999px; overflow:hidden; }
.sp-tier-fill { height:100%; background:linear-gradient(90deg,#fbbf24,#f59e0b); border-radius:999px; }
.sp-tier-hint { display:block; color:rgba(255,255,255,0.6); font-size:10px; margin-top:6px; text-align:center; }
.sp-stats { display:flex; justify-content:center; gap:8px; margin-top:12px; flex-wrap:wrap; }
.sp-stat { color:rgba(255,255,255,0.8); font-size:10px; background:rgba(255,255,255,0.12); border-radius:999px; padding:3px 10px; }
.share-hint { color:var(--text-dim); font-size:11px; display:block; margin-bottom:12px; }
.share-btn { background:var(--accent); border-radius:12px; padding:12px 18px; display:inline-flex; align-items:center; gap:6px; cursor:pointer; color:#fff; }
.share-btn-ic { display:flex; align-items:center; }
.share-btn text { color:#fff; font-size:14px; font-weight:600; }
.share-btn:active { opacity:0.85; }

/* 骨架屏：加载期间显示，消除空白闪烁 */
.skeleton { padding: 0; }
.sk-hero { background:var(--bg-card); border-radius:20px; padding:18px; margin-bottom:20px; }
.sk-bar { height:6px; border-radius:3px; background:var(--bg); margin:12px 0 14px; }
.sk-stat { width:56px; height:40px; background:rgba(255,255,255,0.06); border-radius:8px; }
[data-theme="white"] .sk-stat { background:var(--bg); }
.sk-row { display:flex; justify-content:space-around; background:rgba(255,255,255,0.04); border-radius:12px; padding:10px 0; }
.sk-path { display:flex; justify-content:space-around; background:var(--bg-card); border:1px solid var(--border); border-radius:16px; padding:16px 14px; margin-bottom:20px; }
.sk-showcase { display:flex; gap:12px; margin-bottom:20px; }
.sk-slot { flex:1; aspect-ratio:1; border-radius:14px; background:var(--bg-card); }
.sk-title { width:80px; height:15px; background:var(--bg-card); border-radius:6px; margin:0 0 12px; }
.sk-dot { width:30px; height:30px; border-radius:50%; background:var(--bg); flex-shrink:0; }
.sk-dot.sm { width:22px; height:22px; }
.sk-lines { flex:1; display:flex; flex-direction:column; gap:6px; }
.sk-line { height:12px; background:var(--bg); border-radius:4px; }
.sk-line.w40 { width:40%; }
.sk-line.w50 { width:50%; }
.sk-line.w60 { width:60%; }
.sk-line.w30 { width:30%; }
.sk-badges { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:20px; }
.sk-badge { width:100%; height:88px; border-radius:14px; background:var(--bg-card); }
.sk-tl { display:flex; align-items:flex-start; gap:10px; padding-left:30px; margin-bottom:14px; }
.sk-tl .sk-dot { margin-top:2px; }
.skeleton .sk-hero *,
.skeleton .sk-path *,
.skeleton .sk-slot,
.skeleton .sk-title,
.skeleton .sk-badge,
.skeleton .sk-tl * { animation: skPulse 1.4s ease-in-out infinite; }
@keyframes skPulse { 0%,100% { opacity:0.3; } 50% { opacity:0.7; } }

/* 学业规划入口卡片 */
.plan-entry-card {
  display:flex; align-items:center; gap:12px;
  background:linear-gradient(135deg, rgba(59,130,246,0.1) 0%, rgba(139,92,246,0.08) 100%);
  border:2px solid var(--accent);
  border-radius:14px;
  padding:14px 16px;
  margin:0 0 12px;
  cursor:pointer;
  box-sizing:border-box;
}
.plan-entry-card:active { opacity:0.8; }
.plan-entry-ic { font-size:28px; flex-shrink:0; }
.plan-entry-body { flex:1; min-width:0; display:flex; flex-direction:column; gap:4px; }
.plan-entry-title { color:var(--accent); font-size:16px; font-weight:700; }
.plan-entry-desc { color:var(--text-dim); font-size:12px; line-height:1.4; }
.plan-entry-arrow { color:var(--accent); flex-shrink:0; display:flex; align-items:center; }

/* ── 学业规划报告弹窗（全屏，设计稿版） ── */
.plan-modal-mask {
  position:fixed; inset:0;
  background:rgba(0,0,0,0.6);
  z-index:9999;
  display:flex; justify-content:center;
}
.plan-modal {
  width:100%; max-width:480px; height:100%;
  background:var(--bg);
  display:flex; flex-direction:column;
  overflow:hidden;
  box-sizing:border-box;
}
.plan-modal * { box-sizing:border-box; }
/* 顶部导航 */
.plan-nav {
  display:flex; align-items:center; justify-content:space-between;
  padding:14px 10px 12px;
  flex-shrink:0;
  width:100%;
}
.plan-nav-btn {
  width:38px; height:38px; border-radius:50%;
  display:flex; align-items:center; justify-content:center;
  color:var(--text); cursor:pointer; flex-shrink:0;
}
.plan-nav-btn:active { background:var(--bg-card); }
.plan-nav-title { color:var(--text); font-size:16px; font-weight:600; }

.plan-modal-body { flex:1; overflow-y:auto; overflow-x:hidden; width:100%; min-width:0; padding:0 16px 20px; }

/* 学生信息卡 */
.plan-id-card {
  background:var(--bg-card);
  border:1px solid var(--border);
  border-radius:16px;
  padding:16px;
  margin-bottom:14px;
  display:flex; align-items:center; justify-content:space-between;
  gap:12px;
}
.plan-id-left { display:flex; align-items:center; gap:12px; flex:1; min-width:0; }
.plan-avatar {
  width:52px; height:52px; border-radius:50%;
  background:var(--accent-bg); color:var(--accent);
  display:flex; align-items:center; justify-content:center;
  font-size:22px; font-weight:700; flex-shrink:0;
}
.plan-id-info { flex:1; min-width:0; }
.plan-id-name-row { display:flex; align-items:center; gap:8px; }
.plan-id-name { color:var(--text); font-size:18px; font-weight:700; }
.plan-id-badge { background:var(--bg-input); color:var(--text-dim); font-size:11px; padding:3px 8px; border-radius:999px; flex-shrink:0; }
.plan-id-sub { color:var(--text-dim); font-size:12px; margin-top:4px; }
.plan-id-boost {
  background:var(--accent-bg);
  border-radius:12px;
  padding:10px 12px;
  display:flex; flex-direction:column; align-items:center; flex-shrink:0;
}
.plan-id-boost-num { color:var(--accent); font-size:20px; font-weight:800; line-height:1; }
.plan-id-boost-label { color:var(--accent); font-size:11px; margin-top:4px; }

/* 状态总结（蓝卡） */
.plan-status {
  background:linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  border-radius:16px;
  padding:18px 16px;
  margin-bottom:14px;
  display:flex; align-items:center; gap:14px;
}
.plan-status-num-box {
  width:84px; height:84px; border-radius:16px;
  background:rgba(255,255,255,0.18);
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  flex-shrink:0;
}
.plan-status-num { color:#fff; font-size:32px; font-weight:800; line-height:1; }
.plan-status-unit { color:rgba(255,255,255,0.9); font-size:12px; margin-top:4px; }
.plan-status-info { flex:1; min-width:0; }
.plan-status-label { color:rgba(255,255,255,0.85); font-size:12px; }
.plan-status-title { color:#fff; font-size:20px; font-weight:800; margin-top:2px; }
.plan-status-desc { color:rgba(255,255,255,0.85); font-size:13px; line-height:1.6; margin-top:6px; }

/* 通用白卡 */
.plan-card {
  background:var(--bg-card);
  border:1px solid var(--border);
  border-radius:16px;
  padding:16px;
  margin-bottom:14px;
}
.plan-card-title { color:var(--text); font-size:15px; font-weight:700; margin-bottom:12px; display:block; }

/* 能力提分网格 */
.plan-subjects-grid { display:flex; gap:8px; flex-wrap:wrap; }
.plan-subject-cell {
  flex:1 1 calc(33.33% - 6px); min-width:90px;
  background:var(--bg-input);
  border-radius:12px;
  padding:10px 8px;
  text-align:center;
}
.plan-subject-name { color:var(--text-dim); font-size:12px; display:block; }
.plan-subject-boost { color:var(--accent); font-size:14px; font-weight:700; margin-top:4px; display:block; }

/* 提分目标 */
.plan-section-head { margin-bottom:12px; }
.plan-section-title { color:var(--text); font-size:17px; font-weight:700; display:block; }
.plan-section-sub { color:var(--text-dim); font-size:12px; margin-top:3px; display:block; }
.plan-tier-card {
  background:var(--bg-card);
  border:1px solid var(--border);
  border-radius:16px;
  padding:14px;
  margin-bottom:10px;
  cursor:pointer;
}
.plan-tier-card:active { opacity:0.88; }
.plan-tier-main { display:flex; align-items:center; gap:12px; }
.plan-tier-ic {
  width:44px; height:44px; border-radius:50%;
  background:var(--accent-bg); color:var(--accent);
  display:flex; align-items:center; justify-content:center; flex-shrink:0;
}
.plan-tier-info { flex:1; min-width:0; }
.plan-tier-name { color:var(--text); font-size:15px; font-weight:700; display:block; }
.plan-tier-desc { color:var(--text-dim); font-size:12px; margin-top:2px; display:block; }
.plan-tier-score { color:var(--accent); font-size:14px; font-weight:700; flex-shrink:0; }
.plan-tier-hint {
  display:block; margin-top:10px; padding-top:10px;
  border-top:1px solid var(--border);
  color:var(--text); font-size:13px; line-height:1.65;
  white-space:pre-wrap; word-break:break-word;
}
.plan-chev { color:var(--accent); font-size:16px; flex-shrink:0; width:16px; text-align:center; }

/* 规划要点 */
.plan-note-row { display:flex; gap:10px; padding:11px 0; cursor:pointer; }
.plan-note-row + .plan-note-row { border-top:1px solid var(--border); }
.plan-note-row:active { opacity:0.88; }
.plan-note-ic {
  width:28px; height:28px; border-radius:50%;
  background:var(--accent-bg); color:var(--accent);
  display:flex; align-items:center; justify-content:center; flex-shrink:0;
  margin-top:2px;
}
.plan-note-info { flex:1; min-width:0; }
.plan-note-head { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.plan-note-name { color:var(--text); font-size:14px; font-weight:600; display:block; }
.plan-note-text {
  color:var(--text-dim); font-size:13px; line-height:1.65; margin-top:4px;
  display:block; white-space:pre-wrap; word-break:break-word;
}
.plan-full-report { margin-top:10px; }
.plan-full-line { display:block; color:var(--text); font-size:13px; line-height:1.7; white-space:pre-wrap; word-break:break-word; }
.plan-full-line.section, .plan-full-line.title { color:var(--accent); font-weight:700; margin-top:10px; }
.plan-full-line.spacer { height:6px; }

/* 重要提示 */
.plan-tip {
  background:var(--accent-bg);
  border-radius:16px;
  padding:14px;
  display:flex; align-items:flex-start; gap:10px;
}
.plan-tip-ic { color:var(--accent); flex-shrink:0; margin-top:1px; }
.plan-tip-text { color:var(--text-sub); font-size:13px; line-height:1.6; flex:1; }

/* 底部刷新按钮 */
.plan-footer {
  padding:12px 16px calc(12px + env(safe-area-inset-bottom));
  border-top:1px solid var(--border);
  background:var(--bg);
  flex-shrink:0;
  width:100%;
}
.plan-refresh-btn {
  width:100%; height:48px; border-radius:14px;
  background:var(--accent); color:#fff;
  display:flex; align-items:center; justify-content:center; gap:8px;
  font-size:16px; font-weight:600;
  cursor:pointer;
  box-shadow:0 4px 16px rgba(59,130,246,0.25);
}
.plan-refresh-btn:active { opacity:0.85; transform:scale(0.98); }
.plan-refresh-ic { display:flex; align-items:center; }

/* 加载中 */
.plan-modal-loading { flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; padding:40px 20px; gap:16px; }
.plan-loading-spinner { width:40px; height:40px; border:3px solid var(--border); border-top-color:var(--accent); border-radius:50%; animation:planSpin 0.8s linear infinite; }
@keyframes planSpin { to { transform:rotate(360deg); } }
.plan-loading-text { color:var(--text-dim); font-size:14px; }
</style>
