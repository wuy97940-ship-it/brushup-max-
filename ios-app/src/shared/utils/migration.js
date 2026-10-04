// 只接受登记过的题库指纹与固定历史地图。不同题库家族的备份不能互导。
const BASELINE=require('../data/migration_baseline.json');
const F=require('./finance');
const clone=x=>JSON.parse(JSON.stringify(x));
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
function historicalCampaign(c){
 if(!c||!BASELINE.fingerprints.includes(c.bank_fingerprint))return false;
 const candidate=clone(c);candidate.bank_fingerprint=BASELINE.campaign.bank_fingerprint;
 return equal(candidate,BASELINE.campaign);
}
function isAppendOnly(current){
 for(const [id,level]of Object.entries(BASELINE.campaign.levels))if(!equal(current.levels[id],level))return false;
 return BASELINE.campaign.worlds.every(w=>equal(current.worlds.find(x=>x.id===w.id),w));
}
function normalizeProgress(p,G){
 if(!p?.game?.campaign)return p;
 const fingerprint=p.game.campaign.bank_fingerprint,current=G.CAMPAIGN;
 if(p.bank_family&&p.bank_family!==BASELINE.family)return p;
 if(fingerprint!==current.bank_fingerprint&&(!historicalCampaign(p.game.campaign)||!isAppendOnly(current)))return p;
 if(fingerprint===current.bank_fingerprint&&!equal(p.game.campaign,current))return p;
 const candidate=clone(p),g=candidate.game;
 if(fingerprint!==current.bank_fingerprint){
  const oldIds=Object.keys(g.campaign.levels);
  if(oldIds.every(id=>g.results?.[id]?.cleared)||Object.keys(g.expedition_stages||{}).length||g.active?.stage_id?.startsWith('expedition:'))g.expedition_unlocked=true;
  g.campaign=clone(current);
 }
 candidate.bank_family=BASELINE.family;
 F.ensureExpansion(g);
 if(!g.inventory.includes('xiaobao')&&G.CATALOG.xiaobao)g.inventory.push('xiaobao');
 return equal(candidate,p)?p:candidate;
}
function validProgress(p,G){
 const object=x=>!!x&&typeof x==='object'&&!Array.isArray(x);
 if(!object(p)||!object(p.game)||!object(p.answered)||!Array.isArray(p.wrong_book)||!Array.isArray(p.favorites))return false;
 const g=p.game;
 if(p.bank_family&&p.bank_family!==BASELINE.family)return false;
 if(!equal(g.campaign,G.CAMPAIGN)||!Array.isArray(g.inventory)||!object(g.equipment)||!object(g.results)||![g.coins,g.xp].every(n=>Number.isFinite(n)&&n>=0))return false;
 const qids=new Set(G.META.map(q=>q.id)),sids=new Set(Object.keys(G.CAMPAIGN.levels));
 if(!object(g.expedition_stages)||!object(g.paused)||!Array.isArray(g.badges))return false;
 for(const [id,stage]of Object.entries(g.expedition_stages)){
  if(!/^expedition:\d{6}$/.test(id)||stage.id!==id||stage.kind!=='expedition'||!Number.isInteger(stage.round)||stage.round<1||!Array.isArray(stage.qids)||!stage.qids.length||stage.qids.length>10||new Set(stage.qids).size!==stage.qids.length||stage.qids.some(q=>!qids.has(q)))return false;
  sids.add(id);
 }
 if([...p.wrong_book,...p.favorites,...Object.keys(p.answered)].some(id=>!qids.has(id))||Object.keys(g.results).some(id=>!sids.has(id))||g.inventory.some(id=>!G.CATALOG[id]))return false;
 if(!G.CATALOG[g.skin]?.character||!g.inventory.includes(g.skin))return false;
 for(const slot of ['xp','coins','wonder']){const id=g.equipment[slot];if(id&&(!g.inventory.includes(id)||G.CATALOG[id]?.slot!==slot))return false;}
 for(const slot of ['outfit','title']){const id=g[slot];if(id&&(!g.inventory.includes(id)||!G.CATALOG[id]?.[slot]))return false;}
 function attempt(a,practice=false){
  if(!a)return true;
  if(!object(a)||!Array.isArray(a.qids)||!a.qids.length||new Set(a.qids).size!==a.qids.length||a.qids.some(id=>!qids.has(id))||!object(a.answers)||!object(a.drafts)||!Array.isArray(a.references)||!Number.isInteger(a.index)||a.index<0||a.index>=a.qids.length)return false;
  if(Object.keys(a.answers).some(id=>!a.qids.includes(id)||!object(a.answers[id])||typeof a.answers[id].correct!=='boolean'||typeof a.answers[id].user_answer!=='string')||a.references.some(id=>!a.qids.includes(id)))return false;
  if(!practice){if(!sids.has(a.stage_id))return false;const expected=G.levelFor(g,a.stage_id).qids;if(a.qids.length!==expected.length||a.qids.some(id=>!expected.includes(id)))return false;if(!object(a.bonuses)||![a.bonuses.xp,a.bonuses.coins].every(n=>Number.isFinite(n)&&n>=0&&n<=200))return false;}
  for(const field of ['structured_drafts','structured_submissions','corrections','correction_edit'])if(a[field]&&(!object(a[field])||Object.keys(a[field]).some(id=>!a.qids.includes(id))))return false;
  if(practice&&a.commission_id){try{const expected=F.commissionQuestions(G.META,a.commission_id);if(a.qids.length!==expected.length||a.qids.some(id=>!expected.includes(id)))return false;}catch{return false;}}
  if(practice&&a.rescue&&(!G.CAMPAIGN.worlds.some(w=>w.id===a.rescue)||a.qids.length>5))return false;
  return true;
 }
 if(!attempt(g.active)||!Object.values(g.paused).every(a=>attempt(a))||!attempt(p.practice,true))return false;
 const s=g.finance_expansion;
 if(s){if(!object(s)||s.version!==1||!Number.isInteger(s.materials)||s.materials<0||s.materials>60||!object(s.chapter_claims)||!object(s.buildings)||!object(s.commission_claims)||!Array.isArray(s.story_seen)||!Array.isArray(s.diary)||!Array.isArray(s.formula_seen)||!object(s.tools))return false;const buildings=new Set(F.CONFIG.buildings.map(b=>b.id));if(Object.entries(s.buildings).some(([id,level])=>!buildings.has(id)||!Number.isInteger(level)||level<0||level>3))return false;if(s.companion&&(!g.inventory.includes(s.companion)||!F.CONFIG.companions.some(c=>c.id===s.companion)))return false;}
 return true;
}
module.exports={BASELINE,historicalCampaign,isAppendOnly,normalizeProgress,validProgress};
