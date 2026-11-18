// 6.0共用资源规则；纯数据操作必须由store.commit统一持久化。
const C=require('../data/adventure600');
const SPIRITS=new Set(require('../data/hunting600').config.spirits.map(s=>s.id));
const ITEMS=Object.fromEntries(C.items.map(i=>[i.id,{...i,category:'consumable',rarity:'common',asset:'mood/'+i.id+'.png'}]));
const round=n=>Math.round(n*100)/100;
const clamp=(n,max)=>Math.max(0,Math.min(max,n));
function threshold(l){return 120*l+25*l*(l-1)/2+(l-1)*l*(2*l-1)/6;}
function level(g){const xp=g.xp??0;if(!Number.isSafeInteger(xp)||xp<0)throw Error('经验数据无效，请恢复有效备份。');let lo=0,hi=1;while(threshold(hi)<=xp)hi*=2;while(hi-lo>1){const n=Math.floor((lo+hi)/2);if(threshold(n)<=xp)lo=n;else hi=n;}return lo;}
const unlockLevel=()=>Math.min(...C.growth.skills.filter(s=>s.kind!=='passive').map(s=>s.level));
function bond(g){const d=C.growth.skills.find(s=>s.id==='spirit_bond'),learned=g.growth600?.skills.spirit_bond||0,rank=Math.max(0,Math.min(learned,4,Math.floor((level(g)-d.level)/10)+1)),ids=g.product600?.companions||[g.finance_expansion?.companion].filter(Boolean),active=ids.some(id=>SPIRITS.has(id)&&g.inventory.includes(id));return {rank,limit:rank?d.companions[rank-1]:1,coins:rank&&active?d.coins_percent[rank-1]:0,xp:rank&&active?d.xp_percent[rank-1]:0,mana:rank&&active?d.mana_percent[rank-1]:0};}
function manaMaximum(g){const lv=level(g);return lv<unlockLevel()?0:Math.floor(Math.min(C.mana.base_ceiling,C.mana.base_maximum+(lv-unlockLevel())*C.mana.per_level)*(100+bond(g).mana)/100);}
function initial(){return {version:6,mood:C.mood.initial,energy:C.energy.initial_points,mana:0,mana_unlocked:false,stock:{},days:{},rest_at:null,rest_started:null,wrong_streak:[],correct_streak:0,failures:{}};}
const HERO_FIELDS=['mood','energy','mana','mana_unlocked','energy_maximum','mana_maximum','wrong_streak','correct_streak','rest_started'];
const heroId=skin=>C.heroes.some(h=>h.id===skin)?skin:/^orange_(mage|knight)$/.test(skin)?'orange_adventurer':null;
function refreshHero(s,lv,manaBonus=0){
 s.wrong_streak=s.wrong_streak||[];s.correct_streak=s.correct_streak||0;if(s.rest_started===undefined)s.rest_started=null;
 s.energy_maximum=Math.min(C.energy.capacity_ceiling,C.energy.initial_points+lv*C.energy.level_capacity_points);s.energy=clamp(s.energy,s.energy_maximum);
 s.mana_maximum=lv<unlockLevel()?0:Math.floor(Math.min(C.mana.base_ceiling,C.mana.base_maximum+(lv-unlockLevel())*C.mana.per_level)*(100+manaBonus)/100);
 if(!s.mana_maximum){s.mana=0;s.mana_unlocked=false;}else if(!s.mana_unlocked){s.mana=C.mana.initial;s.mana_unlocked=true;}
 s.mana=clamp(s.mana,s.mana_maximum);s.mood=clamp(s.mood,C.mood.maximum);return s;
}
function ensure(g){if(!g.adventure600)g.adventure600=initial();const s=g.adventure600,lv=level(g),bonus=bond(g).mana;s.failures=s.failures||{};s.hero_profiles=s.hero_profiles||{};refreshHero(s,lv,bonus);Object.values(s.hero_profiles).forEach(h=>refreshHero(h,lv,bonus));return s;}
const snapshot=s=>Object.fromEntries(HERO_FIELDS.map(k=>[k,Array.isArray(s[k])?s[k].slice():s[k]]));
function newHero(g){const s=refreshHero(initial(),level(g),bond(g).mana);s.energy=s.energy_maximum;return snapshot(s);}
function switchHero(g,id){const s=ensure(g),old=heroId(g.skin);if(old===id)return;if(s.energy<=0)throw Error('体力为0，请先还魂或重新开始，不能切换伙伴绕过。');if(!s.hero_profiles[id])throw Error('这位主角尚未解锁。');const next=s.hero_profiles[id];s.hero_profiles[old]=snapshot(s);delete s.hero_profiles[id];Object.assign(s,next);g.skin=id;}
function day(g,now=Date.now()){const s=ensure(g),d=new Date(now),key=[d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');if(!s.days[key])s.days[key]={mood_energy:0,mood_mana:0,mana_qids:{}};return s.days[key];}
function view(g){const current=g.adventure600||initial(),s=ensure({...g,adventure600:{...current,hero_profiles:Object.fromEntries(Object.entries(current.hero_profiles||{}).map(([id,h])=>[id,{...h}]))}});return {value:s.mood,maximum:C.mood.maximum,low:s.mood<=C.mood.low_threshold,color:s.mood<=C.mood.low_threshold?'#475569':'#EC6FA9',label:s.mood<=C.mood.low_threshold?'低落':s.mood>=80?'开心':s.mood>=50?'平稳':'有点疲惫',energy:s.energy,energyMaximum:s.energy_maximum,mana:s.mana,manaMaximum:s.mana_maximum,manaVisible:s.mana_maximum>0,unlockLevel:unlockLevel()};}
function requireEnergy(g){if(ensure(g).energy<=0)throw Error('体力已耗尽，请先恢复体力后继续。');}
function answer(p,a,q,correct,{practice=false,now=Date.now(),energyPoints=null,suppressMood=false}={}){
 const g=p.game,s=ensure(g);a.resource_actions=a.resource_actions||{};if(a.resource_actions[q.id])return a.resource_actions[q.id];
 requireEnergy(g);const d=day(g,now),before=s.mood,low=!suppressMood&&before<=C.mood.low_threshold&&!a.focus_shield;
 const base=energyPoints===null?C.energy.answer_points+(!correct&&!practice?(g.campaign.levels[a.stage_id]?.kind==='boss'?C.energy.boss_wrong_points:C.energy.wrong_points):0):energyPoints;
 const extra=low?Math.min(C.energy.low_mood_extra_points,Math.max(0,C.energy.low_mood_daily_ceiling-d.mood_energy)):0;
 const spent=Math.min(s.energy,base+extra),actualExtra=Math.max(0,spent-Math.min(s.energy,base));s.energy=round(s.energy-spent);d.mood_energy=round(d.mood_energy+actualExtra);
 const manaSpent=low?Math.min(s.mana,C.mood.extra_mana,Math.max(0,C.mood.daily_mana_ceiling-d.mood_mana)):0;s.mana-=manaSpent;d.mood_mana+=manaSpent;
 const assisted=!!a.hints?.[q.id]||(a.assisted_qids||[]).includes(q.id);
 if(correct){s.wrong_streak=[];s.correct_streak=assisted?0:s.correct_streak+1;if(!assisted)s.mood=clamp(s.mood+C.mood.correct_gain,C.mood.maximum);if(s.correct_streak>=5)s.mood=Math.max(s.mood,C.mood.rally_floor);}
 else {s.correct_streak=0;if(!s.wrong_streak.includes(q.id)){s.wrong_streak.push(q.id);s.mood=clamp(s.mood-C.mood.wrong_loss,C.mood.maximum);}if(s.wrong_streak.length>=C.energy.wrong_streak_threshold)s.mood=Math.min(s.mood,C.mood.low_threshold);}
 let manaRestored=0;
 if(correct&&!assisted&&s.mana_maximum&&!d.mana_qids[q.id]){manaRestored=Math.min(C.mana.correct_restore,s.mana_maximum-s.mana);s.mana+=manaRestored;d.mana_qids[q.id]=true;}
 const result={moodBefore:before,moodAfter:s.mood,energySpent:round(spent),extraEnergy:round(actualExtra),extraMana:manaSpent,manaRestored};a.resource_actions[q.id]=result;return result;
}
function recover(s,amount,floor=0){s.mood=Math.max(floor,clamp(s.mood+amount,C.mood.maximum));if(s.mood>C.mood.low_threshold){s.wrong_streak=[];s.correct_streak=0;s.rest_started=null;}return s.mood;}
function settle(g,a,passed){if(a.mood_settled)return a.mood_settled;const s=ensure(g),before=s.mood;if(passed){delete s.failures[a.stage_id];recover(s,C.mood.stage_clear_gain);}else{s.failures[a.stage_id]=(s.failures[a.stage_id]||0)+1;if(s.failures[a.stage_id]>=C.energy.stage_failure_threshold)s.mood=Math.min(s.mood,C.mood.low_threshold);s.mood=clamp(s.mood-C.mood.stage_failure_loss,C.mood.maximum);}a.mood_settled={before,after:s.mood,passed};return a.mood_settled;}
function buy(p,id){const item=ITEMS[id],g=p.game,s=ensure(g);if(!item)throw Error('没有这件心情商品。');if(g.coins<item.price)throw Error('金币不足。');g.coins=round(g.coins-item.price);s.stock[id]=(s.stock[id]||0)+1;return item;}
function use(p,id){
 const item=ITEMS[id],s=ensure(p.game);if(!item||!(s.stock[id]>0))throw Error('背包里没有这件商品。');
 let key,maximum,amount;
 if(item.kind==='calm'){key='mood';maximum=C.mood.maximum;amount=item.restore_mood;}
 else if(item.kind==='food'){if(s.energy<=0)throw Error('休眠时需先使用还魂丹。');key='energy';maximum=s.energy_maximum;amount=item.restore_points||maximum*item.restore_percent/100;}
 else if(item.kind==='mana'){if(s.energy<=0||!s.mana_maximum)throw Error('魔法未解锁或伙伴休眠，暂时不能使用。');key='mana';maximum=s.mana_maximum;amount=item.restore_mana;}
 else if(item.kind==='revive'){if(s.energy>0)throw Error('伙伴尚未休眠，不需要还魂丹。');key='energy';maximum=s.energy_maximum;amount=maximum*item.restore_percent/100;}
 else throw Error('这件商品不能使用。');
 if(s[key]>=maximum)throw Error((key==='mood'?'心情':key==='energy'?'体力':'魔法')+'已经满了，留到需要时再用吧。');
 const before=s[key];if(key==='mood')recover(s,amount);else s[key]=round(clamp(before+amount,maximum));s.stock[id]--;
 if(item.kind==='revive')recover(s,0,C.mood.revive_floor);
 return {id,name:item.name,resource:key,before,after:s[key],restored:round(s[key]-before),overflow:round(amount-(s[key]-before))};
}
function restStatus(g,now=Date.now()){const s=g.adventure600||initial(),started=s.rest_started;return {started:started!==null&&started!==undefined,remaining:started===null||started===undefined?C.energy.calm_rest_seconds:Math.max(0,Math.ceil(C.energy.calm_rest_seconds-(now-started)/1000))};}
function rest(p,now=Date.now()){const s=ensure(p.game);if(s.mood>=C.mood.maximum)throw Error('心情已经满了。');if(p.game.ruleset==='6.0.0'){if(s.rest_started===null)s.rest_started=now;const status=restStatus(p.game,now),before=s.mood;if(!status.remaining){recover(s,C.mood.rest_restore,C.mood.rally_floor);s.rest_started=null;}return {before,after:s.mood,ready:!status.remaining,remaining:status.remaining};}if(s.rest_at!==null&&now-s.rest_at<C.energy.calm_rest_seconds*1000)throw Error('休息恢复每10分钟可用一次。');s.rest_at=now;const before=s.mood;s.mood=clamp(s.mood+C.mood.rest_restore,C.mood.maximum);return {before,after:s.mood};}
module.exports={C,ITEMS,initial,ensure,day,view,threshold,level,unlockLevel,bond,manaMaximum,heroId,newHero,switchHero,requireEnergy,answer,settle,recover,buy,use,restStatus,rest};
