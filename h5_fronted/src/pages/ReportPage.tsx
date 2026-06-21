import { useState, useMemo } from "react";
import { motion } from "motion/react";
import type { JnaoReportData, TestType } from "../api/types";
import { RadarChart } from "../components/RadarChart";
import { MoodDashboard } from "../components/MoodDashboard";
import { AiGuideCard } from "../components/AiGuideCard";

interface Props {
  reportData: JnaoReportData;
  testType: TestType;
  isBackup: boolean;
  onRestart: () => void;
  onBackupTest: () => void;
}

const TALENT_COLORS: Record<string, string> = {
  "学者": "#12417A", "思者": "#FFB600", "行者": "#A57A1A",
  "赢者": "#960D24", "德者": "#582E1F", "迷者": "#9CA3AF",
};

const TALENT_LOGOS: Record<string, string> = {
  "学者": "/天赋/logos/xue.jpg",
  "思者": "/天赋/logos/si.jpg",
  "赢者": "/天赋/logos/ying.jpg",
  "德者": "/天赋/logos/de.jpg",
  "行者": "/天赋/logos/xing.jpg",
};

const STATE_LABELS = ["相争", "难辨", "牵制", "双生", "本命", "孤显", "无向", "无神"];

function stripHtml(html: string): string {
  if (!html) return "";
  return html.replace(/<[^>]+>/g, "").replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").trim();
}

function parseAdvice(desp: string): { career: string; emotion: string } | null {
  if (!desp) return null;
  const text = stripHtml(desp);
  const careerMatch = text.match(/事业建议[：:]\s*(.+?)(?=情感建议|给你的建议|$)/s);
  const emotionMatch = text.match(/情感建议[：:]\s*(.+?)(?=事业建议|给你的建议|$)/s);
  if (careerMatch || emotionMatch) {
    return {
      career: careerMatch?.[1]?.trim() || "",
      emotion: emotionMatch?.[1]?.trim() || "",
    };
  }
  return null;
}

function parseStateSummary(desp: string): string {
  if (!desp) return "";
  const idx = desp.search(/给你的建议|事业建议|情感建议/);
  return idx > 0 ? desp.slice(0, idx).trim() : desp;
}

/** Split Talent.desp into: ability-desc / words-for-you / golden-advice / rest */
function parseTalentDesp(html: string) {
  if (!html) return { abilityDesc: "", wordsForYou: "", goldenAdvice: [] as string[] };

  const wordsIdx = html.search(/想对你说的话/);
  const goldenIdx = html.search(/三条黄金建议/);
  const restIdx = html.search(/【?综合能力解读】?/);

  let abilityDesc = "";
  let wordsForYou = "";
  const goldenAdvice: string[] = [];

  if (wordsIdx >= 0) {
    abilityDesc = html.slice(0, wordsIdx).replace(/<p[^>]*>\s*<strong>【?天赋能力解读】?<\/strong>\s*<\/p>/gi, "").trim();
    if (goldenIdx >= 0) {
      wordsForYou = html.slice(wordsIdx, goldenIdx).replace(/<[^>]*>\s*想对你说的话\s*<\/[^>]*>/gi, "").trim();
      const goldenEnd = restIdx >= 0 ? restIdx : html.length;
      const goldenBlock = stripHtml(html.slice(goldenIdx, goldenEnd)).replace(/三条黄金建议[：:]?/g, "").trim();
      const items = goldenBlock.split(/(?=\d+\.)/).filter(Boolean);
      for (const item of items) {
        const cleaned = item.replace(/^\d+\.\s*/, "").trim();
        if (cleaned) goldenAdvice.push(cleaned);
      }
    } else {
      wordsForYou = html.slice(wordsIdx).replace(/<p[^>]*>\s*<strong>想对你说的话<\/strong>\s*<\/p>/gi, "").trim();
    }
  } else {
    abilityDesc = html.replace(/<p[^>]*>\s*<strong>【?天赋能力解读】?<\/strong>\s*<\/p>/gi, "").trim();
  }

  return { abilityDesc, wordsForYou, goldenAdvice };
}

function CollapsibleHtml({ html, className }: { html: string; className?: string }) {
  const [open, setOpen] = useState(false);
  const needsFold = useMemo(() => stripHtml(html).length > 120, [html]);
  return (
    <div>
      <div className={`${className || ""} ${!open && needsFold ? "line-clamp-2" : ""}`}
        dangerouslySetInnerHTML={{ __html: html }} />
      {needsFold && (
        <button type="button" className="block w-full text-center text-[12px] font-medium text-[#888] py-[6px] select-none"
          onClick={() => setOpen((v) => !v)}>
          {open ? "收起" : "展示更多"}
        </button>
      )}
    </div>
  );
}

// ══════════════════════════════════════════
//  ReportPage
// ══════════════════════════════════════════

export function ReportPage({ reportData, testType, isBackup, onRestart, onBackupTest }: Props) {
  const { results, talent, check_talent, id: recordId, create_time, StateIcon } = reportData;
  const { Attribute, State, Talent, TalentType: talentTypeRaw, Ability: abilityRaw } = results;

  const TalentType = Array.isArray(talentTypeRaw) ? talentTypeRaw : [];
  const Ability = Array.isArray(abilityRaw) ? abilityRaw : [];

  const talentColor = TALENT_COLORS[talent] || "#171717";
  const stateSummary = useMemo(() => parseStateSummary(State.desp), [State.desp]);
  const advice = useMemo(() => parseAdvice(State.desp), [State.desp]);
  const { abilityDesc, wordsForYou, goldenAdvice } = useMemo(() => parseTalentDesp(Talent.desp), [Talent.desp]);

  const attrDespText = stripHtml(Attribute.desp);

  const traits = useMemo(() => {
    const list = [...Attribute.attributeList];
    if (!list.find((a) => a.id === Attribute.attribute.id)) list.push(Attribute.attribute);
    return list.sort((a, b) => ["A", "B", "C", "D", "E"].indexOf(a.id) - ["A", "B", "C", "D", "E"].indexOf(b.id));
  }, [Attribute]);

  const traitSuffix = (name: string) => {
    const map: Record<string, string> = { "学者": "智", "思者": "思", "行者": "行", "赢者": "赢", "德者": "德", "迷者": "知" };
    return map[name] || "知";
  };

  const abilityRating = (value: number) => {
    if (value > 70) return { text: "良好", className: "text-[#888]" };
    if (value >= 50) return { text: "正常", className: "text-[#888]" };
    return { text: "待提升", className: "text-[#C06040]" };
  };

  const reportContext = useMemo(() => {
    const parts = [
      `天赋类型：${talent}${check_talent ? `（复核：${check_talent}）` : ""}`,
    ];
    if (TalentType.length) parts.push(`特质类型：${TalentType.map((t) => t.name).join("、")}`);
    if (Talent.abilityName) parts.push(`核心天赋能力：${Talent.abilityName}（等级${Talent.grade}）`);
    if (Ability.length) parts.push(`综合能力：${Ability.map((a) => `${a.abilityName}（等级${a.grade}）`).join("、")}`);
    if (attrDespText) parts.push(`特质描述：${attrDespText.slice(0, 200)}`);
    return parts.join("\n");
  }, [talent, check_talent, TalentType, Talent, Ability, attrDespText]);

  const guideSections = [
    { id: "sec-hero", tip: `你的天赋类型是${check_talent ? `${check_talent} · ` : ""}${talent}。${attrDespText.slice(0, 40)}…问我任何问题深入了解。` },
    { id: "sec-ability-desc", tip: Talent.abilityName ? `核心天赋是${Talent.abilityName}${Talent.value}分。你的优势在于把人和事组织起来。` : "查看你的天赋能力解读，有不懂的可以问我。" },
    { id: "sec-abilities", tip: Ability.length ? `五维能力雷达图展示你的综合能力画像，越突出越强。` : "综合能力雷达图展示五维画像。" },
    { id: "sec-state", tip: `当前能量状态：${State.name}。问我怎么理解和改善。` },
  ];

  return (
    <div className="flex-1 min-h-0 overflow-y-auto no-scrollbar bg-[#FAFAFA] relative" id="scrollArea">
      <motion.div className="flex flex-col bg-white"
        initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}>

        {/* ══ 1. Hero ══ */}
        <div className="px-5 pt-5 pb-4 border-b border-[#EBEBEB] flex gap-[14px] items-stretch" id="sec-hero">
          <div className="shrink-0 w-[54px] rounded-[14px] bg-[#FAFAFA] overflow-hidden flex items-center justify-center">
            {TALENT_LOGOS[talent] ? (
              <img src={TALENT_LOGOS[talent]} alt={talent} className="w-[70%] h-[70%] object-contain" />
            ) : (
              <span className="text-[22px] font-bold text-[#d1d5db]">{talent[0]}</span>
            )}
          </div>
          <div className="flex-1 min-w-0">
            {/* TODO: replace with WeChat nickname when user system is integrated */}
            <p className="text-[11px] font-medium text-[#888] mb-1">天赋者</p>
            <h1 className="text-[20px] font-bold text-[#171717] tracking-[-0.3px] mb-1">
              {check_talent ? `${check_talent} · ` : ""}{talent}
            </h1>
            <p className="text-[12px] text-[#4D4D4D] leading-[1.6]">{attrDespText}</p>
          </div>
        </div>

        {/* ══ 2. Stats Row ══ */}
        <div className="flex border-b border-[#EBEBEB]">
          <div className="flex-1 py-[14px] text-center border-r border-[#EBEBEB]">
            <div className="text-[20px] font-bold text-[#171717] tracking-[-0.2px]">{Talent.value || State.id || "—"}</div>
            <div className="text-[11px] text-[#888] mt-0.5">核心天赋值</div>
          </div>
          <div className="flex-1 py-[14px] text-center border-r border-[#EBEBEB]">
            <div className="text-[20px] font-bold tracking-[-0.2px]" style={{ color: talentColor }}>{talent}</div>
            <div className="text-[11px] text-[#888] mt-0.5">天赋类型</div>
          </div>
          <div className="flex-1 py-[14px] text-center">
            <div className="text-[20px] font-bold text-[#171717] tracking-[-0.2px]">{State.name}</div>
            <div className="text-[11px] text-[#888] mt-0.5">能量状态</div>
          </div>
        </div>

        {/* ══ 3. 天赋特质 ══ */}
        {traits.length > 0 && (
          <div className="border-b border-[#EBEBEB]">
            <div className="px-5 pt-[18px] pb-1">
              <h2 className="text-sm font-semibold text-[#171717] mb-[10px]">天赋特质</h2>
            </div>
            <div className="flex">
              {traits.map((t) => (
                <div key={t.id} className="flex-1 py-[10px] px-1 text-center border-r border-[#EBEBEB] last:border-r-0">
                  <div className="text-[11px] font-semibold text-[#171717]">{t.name}求{traitSuffix(t.name)}</div>
                  <div className="text-[9px] text-[#888] mt-0.5">Lv.{t.grade} · 值 {t.value}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ══ 4. 双重属性详解 ══ */}
        {Attribute.SupplementDesp && (
          <div className="border-b border-[#EBEBEB]">
            <div className="px-5 py-3">
              <div className="text-[12px] font-semibold text-[#888] uppercase tracking-[0.4px] mb-1">
                {check_talent ? `${check_talent} 双重属性详解` : "双重属性详解"}
              </div>
              <CollapsibleHtml html={Attribute.SupplementDesp} className="text-[12px] text-[#4D4D4D] leading-[1.7]" />
            </div>
          </div>
        )}

        {/* ══ 5. 天赋能力解读 ══ */}
        {(abilityDesc || wordsForYou) && (
          <div className="border-b border-[#EBEBEB]" id="sec-ability-desc">
            <div className="px-5 pt-[18px] pb-1">
              <h2 className="text-sm font-semibold text-[#171717] mb-[6px]">天赋能力</h2>
              <p className="text-[11px] text-[#888] mb-[10px]">天赋能力解读</p>
            </div>

            {abilityDesc && (
              <div className="px-5 pb-3">
                <CollapsibleHtml html={abilityDesc} className="text-[12px] text-[#4D4D4D] leading-[1.7]" />
              </div>
            )}

            {wordsForYou && (
              <div className="px-5 pb-3">
                <div className="text-[12px] font-semibold text-[#888] uppercase tracking-[0.4px] mb-1">想对你说的话</div>
                <div className="text-[12px] text-[#4D4D4D] leading-[1.7]"
                  dangerouslySetInnerHTML={{ __html: (() => {
                    const plain = stripHtml(wordsForYou);
                    return plain.replace(/^(\s*想对你说的话\s*)+/i, "").trim().replace(/\n/g, "<br>");
                  })() }} />
              </div>
            )}
          </div>
        )}

        {/* ══ 6. 综合能力 ══ */}
        {Ability.length > 0 && (
          <div className="border-b border-[#EBEBEB]" id="sec-abilities">
            <div className="px-5 pt-[18px] pb-1">
              <h2 className="text-sm font-semibold text-[#171717] mb-[10px]">综合能力</h2>
            </div>
            <div className="pb-2">
              <RadarChart data={Ability} />
            </div>
            <div className="px-5 pb-4">
              {Ability.map((ab) => {
                const rating = abilityRating(ab.value);
                return (
                  <div key={ab.abilityID} className="flex items-center gap-0 py-[5px]">
                    <span className="w-[52px] text-[12px] font-semibold text-[#171717] shrink-0">{ab.abilityName}</span>
                    <div className="flex-1 h-[3px] bg-[#EBEBEB] rounded-[2px] overflow-hidden mx-[10px]">
                      <motion.div
                        className="h-full rounded-[2px]"
                        style={{ backgroundColor: talentColor }}
                        initial={{ width: 0 }}
                        animate={{ width: `${Math.min(ab.value, 100)}%` }}
                        transition={{ delay: 0.3, duration: 0.5, ease: "easeOut" }}
                      />
                    </div>
                    <span className="w-6 text-right text-[12px] font-semibold text-[#171717]">{ab.value}</span>
                    <span className={`w-7 text-right text-[10px] ${rating.className}`}>{rating.text}</span>
                  </div>
                );
              })}
            </div>

            {/* 综合能力解读 */}
            {Ability.some((ab) => ab.desp) && (
              <div className="px-5 pb-4">
                <div className="text-[12px] font-semibold text-[#171717] mb-2">综合能力解读</div>
                {Ability.filter((ab) => ab.desp).map((ab) => {
                  const name = ab.abilityName;
                  const cleaned = (() => {
                    const plain = stripHtml(ab.desp);
                    const deduped = plain.replace(new RegExp(`^(\\s*-?\\s*${name}\\s*-?\\s*)+`, "i"), "").trim();
                    return deduped.replace(/\n/g, "<br>");
                  })();
                  return (
                    <div key={ab.abilityID} className="mb-3 last:mb-0">
                      <div className="text-[12px] font-semibold text-[#171717] mb-1">-{name}-</div>
                      <div className="text-[12px] text-[#4D4D4D] leading-[1.7]"
                        dangerouslySetInnerHTML={{ __html: cleaned }} />
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ══ 7. 当前状态 ══ */}
        {stateSummary && (
          <div className="border-b border-[#EBEBEB]" id="sec-state">
            <div className="px-5 pt-[18px] pb-1">
              <h2 className="text-sm font-semibold text-[#171717] mb-[10px]">当前状态</h2>
            </div>

            {StateIcon && (
              <div className="flex justify-center pb-2">
                <img src={StateIcon} alt={State.name} className="h-11 object-contain" />
              </div>
            )}

            <div className="pb-2">
              <MoodDashboard stateName={State.name} />
            </div>

            <div className="flex justify-between px-5 pb-3">
              {STATE_LABELS.map((label) => {
                const active = label === State.name;
                return (
                  <span key={label} className={`text-[12px] font-semibold ${active ? "" : "text-[#A1A1A1]"}`}
                    style={active ? { color: talentColor } : {}}>
                    {label}
                  </span>
                );
              })}
            </div>

            <div className="px-5 pb-3">
              <CollapsibleHtml html={stateSummary} className="text-[12px] text-[#4D4D4D] leading-[1.7]" />
            </div>
          </div>
        )}

        {/* ══ 8. 给你的建议 ══ */}
        {advice && (
          <div className="border-b border-[#EBEBEB]">
            <div className="px-5 pt-[18px] pb-1">
              <h2 className="text-sm font-semibold text-[#171717] mb-[10px]">给你的建议</h2>
            </div>
            <div className="px-5 pb-3">
              {advice.career && (
                <div className="py-3 border-b border-[#EBEBEB]">
                  <div className="text-[12px] font-semibold text-[#888] mb-1">事业建议</div>
                  <div className="text-[12px] text-[#171717] leading-[1.6]">{advice.career}</div>
                </div>
              )}
              {advice.emotion && (
                <div className="py-3">
                  <div className="text-[12px] font-semibold text-[#888] mb-1">情感建议</div>
                  <div className="text-[12px] text-[#171717] leading-[1.6]">{advice.emotion}</div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ══ 9. 三条黄金建议 ══ */}
        {goldenAdvice.length > 0 && (
          <div className="border-b border-[#EBEBEB]">
            <div className="px-5 pt-[18px] pb-1">
              <h2 className="text-sm font-semibold text-[#171717] mb-[10px]">三条黄金建议</h2>
            </div>
            <div className="px-5 pb-4">
              {goldenAdvice.map((item, i) => (
                <div key={i} className="py-[10px] border-b border-[#EBEBEB] last:border-b-0">
                  <div className="text-[13px] font-semibold text-[#171717] mb-0.5">{i + 1}. {item}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ══ Meta ══ */}
        <div className="px-5 py-4 text-[12px] text-[#A1A1A1] text-center border-b border-[#EBEBEB] flex items-center justify-center gap-3">
          <span>记录 #{recordId} · {create_time}</span>
          <a href={`https://m.jnao.com/h5/parent_test_result.html?id=${recordId}`}
            target="_blank" rel="noopener noreferrer"
            className="text-[#888] underline underline-offset-2 hover:text-[#171717] transition-colors">
            旧版报告
          </a>
        </div>

        {/* ══ Actions ══ */}
        <div className="px-5 py-6 flex flex-col items-center gap-3">
          {testType === "孩子" && !isBackup && (
            <button type="button"
              className="w-full max-w-[300px] h-11 flex items-center justify-center text-[15px] font-medium text-[#f59e0b] border border-[#fbbf24] rounded-xl bg-[#fffbeb] active:bg-[#fef3c7] transition-colors"
              onClick={onBackupTest}>
              深度校准（备用卷）
            </button>
          )}
          <button type="button"
            className="w-full max-w-[300px] h-11 flex items-center justify-center text-[15px] font-medium text-white rounded-xl active:opacity-80 transition-colors"
            style={{ backgroundColor: talentColor || "#171717" }}
            onClick={onRestart}>
            重新测试
          </button>
        </div>

        <div className="pb-20" />
      </motion.div>

      {/* AI Guide Card */}
      <AiGuideCard sections={guideSections} scrollContainerId="scrollArea" reportContext={reportContext} />
    </div>
  );
}
