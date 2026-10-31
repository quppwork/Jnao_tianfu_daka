/* ===== 生日档案模块（全站共用） =====
   规则：每个孩子终身只能录入一次生日，录入即锁定，前端不可修改。
   注意：当前为纯前端版本，生日数据仅保存在本机浏览器（localStorage）。
   正式上线需接入后端：录入写入服务器并返回锁定凭证，后台统一汇总。 */
const BD=(function(){
  const KEY='jn_birthday_v1';      // 生日档案 {y,m,d,ts,serial}
  const REG='jn_birthday_registry';// 本机登记副本（模拟后台汇总）
  function get(){try{return JSON.parse(localStorage.getItem(KEY));}catch(e){return null;}}
  function isSet(){const b=get();return !!(b&&b.m&&b.d);}
  /* 距离下一个生日的天数；今天生日返回0 */
  function daysUntil(){
    const b=get(); if(!b)return null;
    const now=new Date(); const t=new Date(now.getFullYear(),b.m-1,b.d);
    if(t<new Date(now.getFullYear(),now.getMonth(),now.getDate())) t.setFullYear(t.getFullYear()+1);
    return Math.round((t-new Date(now.getFullYear(),now.getMonth(),now.getDate()))/86400000);
  }
  function isToday(){const b=get();if(!b)return false;const n=new Date();return b.m===n.getMonth()+1&&b.d===n.getDate();}
  /* 录入：仅允许一次，已锁定直接拒绝 */
  function lock(y,m,d){
    if(isSet())return {ok:false,msg:'生日已锁定，终身不可修改'};
    if(!y||!m||!d)return {ok:false,msg:'请完整选择出生年月日'};
    const yr=+y,mm=+m,dd=+d;
    const dt=new Date(yr,mm-1,dd);
    if(dt.getFullYear()!==yr||dt.getMonth()!==mm-1||dt.getDate()!==dd)return {ok:false,msg:'这个日期不存在，请检查'};
    if(dt>new Date())return {ok:false,msg:'生日不能是未来日期'};
    const serial='JN-'+yr+String(mm).padStart(2,'0')+String(dd).padStart(2,'0')+'-'+Math.random().toString(36).slice(2,6).toUpperCase();
    const rec={y:yr,m:mm,d:dd,ts:Date.now(),serial};
    localStorage.setItem(KEY,JSON.stringify(rec));
    /* 模拟后台汇总登记（正式版由服务器统一收集，供线下大会按月份调取） */
    try{
      const reg=JSON.parse(localStorage.getItem(REG)||'[]');
      reg.push({serial,month:mm,day:dd,ts:Date.now(),src:'本机录入'});
      localStorage.setItem(REG,JSON.stringify(reg));
    }catch(e){}
    return {ok:true,rec};
  }
  function fmt(){const b=get();return b?`${b.y}年${b.m}月${b.d}日`:'';}
  return {get,isSet,daysUntil,isToday,lock,fmt,KEY,REG};
})();
