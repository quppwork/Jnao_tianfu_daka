<template>
  <view v-if="visible" class="trm-mask" @tap="close">
    <view class="trm-card" @tap.stop>
      <view class="trm-head">
        <text class="trm-title">晋升段位规则说明</text>
        <view class="trm-close" @tap="close">
          <text>×</text>
        </view>
      </view>

      <view class="trm-body">
        <view class="trm-section">
          <view class="trm-step"><text class="trm-step-num">1</text></view>
          <view class="trm-content">
            <text class="trm-h">什么是「达标」</text>
            <text class="trm-p">
              每天打卡时，5 个训练项目各有各自的「通关标准」，在训练页「技能段位」一行右侧会实时显示（例如 每分钟≥333字 / 准确率≥80% / 完成速算题 等）。
            </text>
            <text class="trm-p">
              打卡后你填的结果达到或超过该标准 → 当天这项就算<text class="trm-b">达标</text>。
            </text>
            <view class="trm-note">
              <text>· 标准会按学段、当前段位自动匹配，不会一样</text>
            </view>
          </view>
        </view>

        <view class="trm-section">
          <view class="trm-step"><text class="trm-step-num">2</text></view>
          <view class="trm-content">
            <text class="trm-h">什么是「连续 {{ n }} 次」</text>
            <text class="trm-p">
              同一个训练项目，<text class="trm-b">连着几天打卡都达标</text>，才算「连续」。
            </text>
            <view class="trm-warn">
              <text>⚠️ 重点：如果某一天没达标，之前的连续计数会<text class="trm-b">清零</text>，要重新开始攒。</text>
            </view>
            <text class="trm-p">
              训练页每行右侧的 <text class="trm-dots-demo">● ● ○ 2/{{ n }}</text> 就是你当前连续达标的进度。
            </text>
          </view>
        </view>

        <view class="trm-section">
          <view class="trm-step"><text class="trm-step-num">3</text></view>
          <view class="trm-content">
            <text class="trm-h">什么是「单项升 1 段」</text>
            <text class="trm-p">
              5 个必修项目<text class="trm-b">各自独立计算</text>，互不影响：
            </text>
            <view class="trm-list">
              <text>· 超脑阅读</text>
              <text>· 影像追忆</text>
              <text>· 扫描速记</text>
              <text>· 极速运算</text>
              <text>· 极速学习</text>
            </view>
            <text class="trm-p">
              当某项攒够连续 {{ n }} 次达标，这项就从 1 段 → 2 段（或 2 段 → 3 段，依此类推）。
            </text>
            <view class="trm-note">
              <text>· 升段后，连续计数会<text class="trm-b">清零</text>，重新开始攒</text>
              <text>· 升段后通关标准也会<text class="trm-b">变难</text>（贴合你当前能力）</text>
            </view>
          </view>
        </view>

        <view class="trm-section">
          <view class="trm-step"><text class="trm-step-num">4</text></view>
          <view class="trm-content">
            <text class="trm-h">九段与荣誉称号的关系</text>
            <text class="trm-p">
              你的「九段」段位 = 5 项训练里<text class="trm-b">段位最低的那一项</text>（木桶效应）。
            </text>
            <text class="trm-p">称号按九段直接映射：</text>
            <view class="trm-table">
              <view class="trm-tr trm-tr-head">
                <text class="trm-td">九段</text>
                <text class="trm-td">荣誉称号</text>
              </view>
              <view class="trm-tr">
                <text class="trm-td">1 – 4 段</text>
                <text class="trm-td">传承特使</text>
              </view>
              <view class="trm-tr">
                <text class="trm-td">5 – 7 段</text>
                <text class="trm-td">劲脑学神</text>
              </view>
              <view class="trm-tr">
                <text class="trm-td">8 – 9 段</text>
                <text class="trm-td">专利精英 🎉</text>
              </view>
            </view>
            <view class="trm-note">
              <text>· 想升称号？优先把<text class="trm-b">段位最低</text>的那一项提上来就对啦</text>
            </view>
          </view>
        </view>

        <view class="trm-section trm-example">
          <text class="trm-h trm-h-example">📅 举个例子：超脑阅读的 7 天</text>
          <view class="trm-table trm-table-dense">
            <view class="trm-tr trm-tr-head">
              <text class="trm-td">天数</text>
              <text class="trm-td">是否达标</text>
              <text class="trm-td">连续计数</text>
              <text class="trm-td">结果</text>
            </view>
            <view class="trm-tr">
              <text class="trm-td">第 1 天</text>
              <text class="trm-td fail">❌ 未达标</text>
              <text class="trm-td">0</text>
              <text class="trm-td fail">不变</text>
            </view>
            <view class="trm-tr">
              <text class="trm-td">第 2 天</text>
              <text class="trm-td pass">✅ 达标</text>
              <text class="trm-td">1</text>
              <text class="trm-td">1/{{ n }} 继续</text>
            </view>
            <view class="trm-tr">
              <text class="trm-td">第 3 天</text>
              <text class="trm-td pass">✅ 达标</text>
              <text class="trm-td">2</text>
              <text class="trm-td">2/{{ n }} 加油</text>
            </view>
            <view class="trm-tr">
              <text class="trm-td">第 4 天</text>
              <text class="trm-td fail">❌ 未达标</text>
              <text class="trm-td fail">0（清零）</text>
              <text class="trm-td fail">😭 重新开始</text>
            </view>
            <view class="trm-tr">
              <text class="trm-td">第 5 天</text>
              <text class="trm-td pass">✅ 达标</text>
              <text class="trm-td">1</text>
              <text class="trm-td">重来第 1 次</text>
            </view>
            <view class="trm-tr">
              <text class="trm-td">第 6 天</text>
              <text class="trm-td pass">✅ 达标</text>
              <text class="trm-td">2</text>
              <text class="trm-td">继续坚持</text>
            </view>
            <view class="trm-tr">
              <text class="trm-td">第 7 天</text>
              <text class="trm-td pass">✅ 达标</text>
              <text class="trm-td">{{ n }} → 0</text>
              <text class="trm-td pass">🎉 升段成功！</text>
            </view>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  advancePass: { type: Number, default: 3 },
})

const emit = defineEmits(['update:modelValue'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const n = computed(() => props.advancePass || 3)

function close() { visible.value = false }
</script>

<style scoped>
.trm-mask {
  position: fixed; inset: 0; z-index: 9999;
  background: rgba(0, 0, 0, 0.55);
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
}
.trm-card {
  width: 100%; max-width: 420px; max-height: 82vh;
  background: #111827;
  border: 1px solid rgba(0, 210, 255, 0.25);
  border-radius: 20px;
  display: flex; flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
  overflow: hidden;
}
.trm-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}
.trm-title { color: #fff; font-size: 16px; font-weight: 700; }
.trm-close {
  width: 28px; height: 28px; border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
}
.trm-close text { color: #9ca3af; font-size: 18px; line-height: 1; }
.trm-close:active { opacity: 0.7; }

.trm-body { flex: 1 1 auto; min-height: 0; max-height: 100%; padding: 14px 20px 20px; overflow-y: auto; }

.trm-section {
  display: flex; gap: 12px;
  padding: 14px 0;
  border-bottom: 1px dashed rgba(255, 255, 255, 0.08);
}
.trm-section:last-child { border-bottom: none; }
.trm-step {
  flex-shrink: 0;
  width: 26px; height: 26px; border-radius: 50%;
  background: linear-gradient(135deg, #22d3ee, #3b82f6);
  display: flex; align-items: center; justify-content: center;
}
.trm-step-num { color: #fff; font-size: 13px; font-weight: 800; }
.trm-content { flex: 1; min-width: 0; }
.trm-h { display: block; color: #fff; font-size: 14px; font-weight: 700; margin-bottom: 8px; }
.trm-h-example { margin-bottom: 10px; }
.trm-p {
  display: block; color: #cbd5e1; font-size: 13px; line-height: 1.7;
  margin-bottom: 6px;
}
.trm-p b { color: #22d3ee; font-weight: 700; }
.trm-b { display: inline; color: #22d3ee; font-weight: 700; }
.trm-note {
  margin-top: 8px; padding: 8px 10px;
  background: rgba(34, 211, 238, 0.06);
  border: 1px solid rgba(34, 211, 238, 0.15);
  border-radius: 8px;
}
.trm-note text {
  display: block; color: #67e8f9; font-size: 11px; line-height: 1.8;
}
.trm-warn {
  margin: 6px 0 10px; padding: 8px 10px;
  background: rgba(251, 146, 60, 0.08);
  border: 1px solid rgba(251, 146, 60, 0.25);
  border-radius: 8px;
}
.trm-warn text { color: #fb923c; font-size: 12px; line-height: 1.6; font-weight: 500; }
.trm-warn b { color: #fb923c; font-weight: 700; }
.trm-warn .trm-b { color: #fb923c; }
.trm-note .trm-b { color: #22d3ee; }
.trm-list {
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  margin: 4px 0 10px;
}
.trm-list text {
  display: block; color: #94a3b8; font-size: 12px; line-height: 1.9;
}
.trm-dots-demo {
  display: inline; padding: 1px 6px;
  background: rgba(34, 211, 238, 0.1); color: #22d3ee;
  border-radius: 4px; font-family: monospace; font-size: 12px;
}

.trm-table {
  width: 100%; border-collapse: separate; border-spacing: 0;
  margin: 8px 0 4px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.06);
}
.trm-tr { display: flex; }
.trm-tr-head {
  background: rgba(34, 211, 238, 0.12);
}
.trm-tr-head .trm-td { color: #22d3ee; font-weight: 700; font-size: 12px; }
.trm-td {
  flex: 1; padding: 8px 10px;
  color: #cbd5e1; font-size: 12px; line-height: 1.5;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  text-align: center;
}
.trm-tr:last-child .trm-td { border-bottom: none; }
.trm-td.pass { color: #34d399; font-weight: 600; }
.trm-td.fail { color: #fb7185; font-weight: 600; }
.trm-table-dense .trm-td { padding: 6px 6px; font-size: 11px; }
.trm-table-dense .trm-tr-head .trm-td { font-size: 11px; }

.trm-example { flex-direction: column; gap: 0; }

[data-theme="white"] .trm-card { background: #fff; border-color: #e5e7eb; box-shadow: 0 20px 60px rgba(0,0,0,0.18); }
[data-theme="white"] .trm-head { border-bottom-color: #f1f5f9; }
[data-theme="white"] .trm-title { color: #1a1a2e; }
[data-theme="white"] .trm-close { background: #f1f5f9; }
[data-theme="white"] .trm-close text { color: #64748b; }
[data-theme="white"] .trm-section { border-bottom-color: #f1f5f9; }
[data-theme="white"] .trm-h { color: #1a1a2e; }
[data-theme="white"] .trm-p { color: #374151; }
[data-theme="white"] .trm-p b { color: #2563eb; }
[data-theme="white"] .trm-b { color: #2563eb; }
[data-theme="white"] .trm-warn .trm-b { color: #c2410c; }
[data-theme="white"] .trm-note { background: #eff6ff; border-color: #bfdbfe; }
[data-theme="white"] .trm-note text { color: #1d4ed8; }
[data-theme="white"] .trm-warn { background: #fff7ed; border-color: #fed7aa; }
[data-theme="white"] .trm-warn text { color: #c2410c; }
[data-theme="white"] .trm-warn b { color: #c2410c; }
[data-theme="white"] .trm-list { background: #f8fafc; }
[data-theme="white"] .trm-list text { color: #64748b; }
[data-theme="white"] .trm-dots-demo { background: #e0e7ff; color: #4338ca; }
[data-theme="white"] .trm-table { background: #fafafa; border-color: #e5e7eb; }
[data-theme="white"] .trm-tr-head { background: #eef2ff; }
[data-theme="white"] .trm-tr-head .trm-td { color: #4338ca; }
[data-theme="white"] .trm-td { color: #374151; border-bottom-color: #f1f5f9; }
[data-theme="white"] .trm-td.pass { color: #047857; }
[data-theme="white"] .trm-td.fail { color: #be123c; }
</style>
