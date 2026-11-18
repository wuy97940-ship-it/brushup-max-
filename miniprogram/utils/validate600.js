// 读取/导入时验证6.0新增字段；不修补或覆盖无法验证的原档。
const A=require('./adventure600');
const C=A.C.growth;
const definitions=Object.fromEntries(C.skills.map(s=>[s.id,s]));
const object=x=>!!x&&typeof x==='object'&&!Array.isArray(x);
const number=(x,max=Number.MAX_SAFE_INTEGER)=>typeof x==='number'&&Number.isFinite(x)&&x>=0&&x<=max;
const integer=(x,max=Number.MAX_SAFE_INTEGER)=>number(x,max)&&Number.isSafeInteger(x);
const unique=x=>Array.isArray(x)&&new Set(x).size===x.length;
function date(x){if(typeof x!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(x))return false;const d=new Date(x+'T12:00:00Z');return Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===x;}
const record=(x,predicate)=>object(x)&&Object.entries(x).every(([key,value])=>predicate(value,key));
const subset=(x,ids,predicate)=>record(x,(v,k)=>ids.has(k)&&predicate(v,k));
const flags=(x,ids)=>subset(x,ids,v=>v===true);
const rank=(v,k)=>!!definitions[k]&&integer(v,4)&&v>=1;
function resources(s,g,qids){
 if(!object(s)||s.version!==6||!number(s.mood,A.C.mood.maximum)||!number(s.energy,A.C.energy.capacity_ceiling)||!number(s.mana)||typeof s.mana_unlocked!=='boolean')return false;
 const lv=A.level(g),energy=Math.min(A.C.energy.capacity_ceiling,A.C.energy.initial_points+lv*A.C.energy.level_capacity_points),mana=A.manaMaximum(g);
 if(s.energy>energy||s.mana>mana||s.mana>0&&!s.mana_unlocked)return false;
 if(s.energy_maximum!==undefined&&s.energy_maximum!==energy||s.mana_maximum!==undefined&&s.mana_maximum!==mana)return false;
 if(!record(s.stock,(n,id)=>Object.hasOwn(A.ITEMS,id)&&integer(n))||!(s.rest_at===null||number(s.rest_at)))return false;
 if(s.rest_started!==undefined&&!(s.rest_started===null||number(s.rest_started)))return false;
 if(s.wrong_streak!==undefined&&(!unique(s.wrong_streak)||s.wrong_streak.some(id=>!qids.has(id))))return false;
 if(s.correct_streak!==undefined&&!integer(s.correct_streak))return false;
 if(s.failures!==undefined&&!record(s.failures,n=>integer(n)))return false;
 return record(s.days,(d,k)=>date(k)&&object(d)&&number(d.mood_energy,A.C.energy.low_mood_daily_ceiling)&&number(d.mood_mana,A.C.mood.daily_mana_ceiling)&&flags(d.mana_qids,qids));
}
function growth(s,qids){
 if(!object(s)||s.version!==6||!record(s.skills,rank)||!unique(s.loadout)||s.loadout.length>3||s.loadout.some(id=>!s.skills[id]||definitions[id].kind==='passive')||!integer(s.xp_remainder,9999)||!(s.last_seen_day===''||date(s.last_seen_day)))return false;
 if(!record(s.transactions,(v,k)=>k.length>0&&k.length<=160&&object(v)&&rank(v.rank,v.skill_id)&&v.rank<=s.skills[v.skill_id]&&v.coins===definitions[v.skill_id].price*2**(v.rank-1)))return false;
 if(s.settled_through!==undefined&&(!date(s.settled_through)||s.settled_through>s.last_seen_day||!record(s.enrollment,(v,k)=>A.C.heroes.some(h=>h.id===k)&&date(v)&&v<=s.last_seen_day)||!integer(s.streak)||!integer(s.best_streak)||s.best_streak<s.streak||!(s.streak_last_day===null||date(s.streak_last_day)&&s.streak_last_day<=s.last_seen_day)||!unique(s.badges)||s.badges.some(n=>![3,7,30].includes(n))))return false;
 if(s.offline_summary!==undefined){const o=s.offline_summary;if(!object(o)||!integer(o.days)||!number(o.points)||!record(o.heroes,(v,k)=>A.C.heroes.some(h=>h.id===k)&&number(v,A.C.energy.capacity_ceiling))||Math.abs(Object.values(o.heroes).reduce((a,b)=>a+b,0)-o.points)>.000001)return false;}
 return record(s.days,(d,k)=>date(k)&&object(d)&&flags(d.active_qids,qids)&&subset(d.xp_qids,qids,(v,id)=>object(v)&&d.active_qids[id]===true&&integer(v.completion,4000)&&integer(v.correct,800))&&(d.coin_qids===undefined||flags(d.coin_qids,qids))&&(d.coins===undefined||integer(d.coins,A.C.rewards.daily_answer_coins_ceiling)));
}
function attempt(a){
 if(!a)return true;
 const ids=new Set(a.qids),r=a.challenge_rules;
 if(a.ruleset!=='6.0.0'||!Object.hasOwn(C.mode_weights,a.product_mode)||!record(a.skill_snapshot,(v,k)=>rank(v,k)&&definitions[k].kind!=='passive')||Object.keys(a.skill_snapshot).length>3||!unique(a.skill_targets)||!integer(a.xp_earned))return false;
 if(!object(r)||r.version!=='6.0.0'||!integer(r.level)||typeof r.boss!=='boolean'||r.pass_percent!==(r.boss?A.C.boss.pass_percent:A.C.pass_percent||80))return false;
 for(const field of ['objective_seconds','objective_per_level','subjective_seconds','subjective_per_level'])if(!number(r[field]))return false;
 if(!(r.objective_ceiling===null||number(r.objective_ceiling))||!record(r.skill_costs,(v,k)=>!!definitions[k]&&definitions[k].kind!=='passive'&&Array.isArray(v)&&v.length===4&&v.every((n,i)=>n===definitions[k].mana_costs[i]))||C.skills.some(d=>d.kind!=='passive'&&!r.skill_costs[d.id]))return false;
 if(!record(a.skill_uses,(n,k)=>!!a.skill_snapshot[k]&&integer(n,a.qids.length))||!record(a.skill_results,(v,k)=>object(v)&&a.qids.some(id=>[...Object.keys(a.skill_snapshot),'mercy'].some(skill=>k===skill+':'+id))&&(!(k.startsWith('mercy:')&&v.protected)||!!a.skill_snapshot.mercy)))return false;
 if(a.skill_targets.some(k=>!Object.hasOwn(a.skill_results,k)))return false;
 if(!subset(a.drafts,ids,v=>typeof v==='string')||!unique(a.references))return false;
 if(!subset(a.primary_submissions,ids,v=>object(v)&&typeof v.draft==='string'&&date(v.day)&&number(v.submitted_at)&&integer(v.xp)))return false;
 if(!subset(a.timers,ids,(v,id)=>object(v)&&number(v.started_at)&&number(v.deadline)&&number(v.duration)&&v.duration>0&&number(v.extension,v.duration)&&Math.abs(v.deadline-v.started_at-v.duration*1000)<1&&['running','submitted','graded','timeout'].includes(v.status)&&(!a.answers[id]||v.status===(a.answers[id].timeout?'timeout':'graded'))&&(!a.primary_submissions[id]||v.status!=='running')))return false;
 if(!subset(a.answers,ids,v=>['game_correct','protected','timeout','assisted','self_assessed'].every(k=>typeof v[k]==='boolean')&&integer(v.xp)&&integer(v.coins)&&number(v.ts)))return false;
 if(a.assisted_qids!==undefined&&(!unique(a.assisted_qids)||a.assisted_qids.some(id=>!ids.has(id))))return false;
 if(a.resource_actions!==undefined&&!subset(a.resource_actions,ids,v=>object(v)&&['moodBefore','moodAfter','energySpent','extraEnergy','extraMana','manaRestored'].every(k=>number(v[k]))))return false;
 return true;
}
function valid(p,G){
 try{
  const g=p.game;if(g.ruleset!=='6.0.0')return true;
  const ids=new Set(G.META.map(q=>q.id)),chapters=new Set(G.CAMPAIGN.worlds.flatMap(w=>w.chapters.map(ch=>ch.id)));
  if(typeof g.starter_claimed!=='boolean'||!integer(g.xp)||!integer(g.coins)||!resources(g.adventure600,g,ids)||!growth(g.growth600,ids))return false;
  const s=g.adventure600,active=A.heroId(g.skin),heroIds=new Set(A.C.heroes.map(h=>h.id));
  if(g.growth600.settled_through&&g.starter_claimed&&A.C.heroes.some(h=>g.inventory.includes(h.id)&&!g.growth600.enrollment[h.id]))return false;
  if(Object.keys(s.failures||{}).some(id=>!G.CAMPAIGN.levels[id]&&!g.expedition_stages[id]))return false;
  const fields=['mood','energy','mana','mana_unlocked','energy_maximum','mana_maximum','wrong_streak','correct_streak','rest_started'];
  if(s.hero_profiles!==undefined&&!record(s.hero_profiles,(h,id)=>heroIds.has(id)&&id!==active&&g.inventory.includes(id)&&object(h)&&Object.keys(h).length===fields.length&&fields.every(k=>Object.hasOwn(h,k))&&resources({...s,...h},g,ids)))return false;
  if(g.starter_claimed&&(!active||!g.inventory.includes(active)||A.C.heroes.some(h=>h.id!==active&&g.inventory.includes(h.id)&&!s.hero_profiles?.[h.id])))return false;
  if(!object(g.product600)||!integer(g.product600.coin_units,9999)||!subset(g.product600.chapter_claims,chapters,v=>object(v)&&typeof v.attempt_id==='string'&&!!v.attempt_id))return false;
  if(g.product600.settings!==undefined&&(!object(g.product600.settings)||Object.entries(g.product600.settings).some(([k,v])=>!['music','sound','reduced_motion'].includes(k)||typeof v!=='boolean')))return false;
  const companions=g.product600.companions,spirits=new Set(require('../data/hunting600').config.spirits.map(s=>s.id));
  if(companions!==undefined&&(!unique(companions)||companions.length>2||companions.some(id=>!spirits.has(id)||!g.inventory.includes(id))||(g.finance_expansion.companion||null)!==(companions[0]||null)))return false;
  if(!require('./hunting600').valid(g))return false;
  return attempt(g.active)&&Object.values(g.paused).every(attempt)&&attempt(p.practice);
 }catch{return false;}
}
module.exports={valid,attempt};
