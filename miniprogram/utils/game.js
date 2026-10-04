// 与桌面规则共用导出的配置、固定题号和物品池。
const {config:BASE_CONFIG,catalog:BASE_CATALOG,campaign:CAMPAIGN}=require('../data/rules');
const ECONOMY=require('../data/shop_config');
const C={...BASE_CONFIG,drop_percent:ECONOMY.boss_drop_percent,rarities:{...BASE_CONFIG.rarities,...ECONOMY.rarities}};
const WONDERS=require('../data/wonders');
const Skills=require('./skills');
const Finance=require('./finance');
const postcardArt=commission=>{const act=Finance.CONFIG.acts?.find(a=>a.id===commission.act_id);return Finance.CONFIG.npcs?.find(n=>n.id===(act?.npc_id||act?.npc))?.asset;};
const financeItems=[{...Finance.CONFIG.hero,category:'skin',rarity:'common',character:'xiaobao',price:0,starter:true},...(Finance.CONFIG.outfits||[]).map(i=>({...i,category:'skin'})),...(Finance.CONFIG.props||[]).map(i=>({...i,category:'collection',rarity:i.rarity||(i.price>=600?'epic':i.price>=300?'rare':'common')})),...(Finance.CONFIG.companions||[]).map(i=>({...i,category:'companion',rarity:i.rarity||'rare',story_only:true})),...(Finance.CONFIG.commissions||[]).map(i=>({id:i.postcard||'postcard_'+i.id,name:i.name+' · 明信片',category:'collection',rarity:'common',price:0,starter:true,earned_only:true,asset:i.asset||postcardArt(i)}))];
const CATALOG={...BASE_CATALOG,...Object.fromEntries(WONDERS.items.map(i=>[i.id,i])),...Object.fromEntries(financeItems.filter(i=>i.id).map(i=>[i.id,i]))};
const {meta:META}=require('../data/questions');
const SUBJECTIVE=['计算分析题','综合题','简答题','论述题','案例分析题'];
const copy=o=>JSON.parse(JSON.stringify(o));
const subjective=q=>SUBJECTIVE.includes(q.type)||Finance.structured(q)||q.type==='计算或情境案例';
const seconds=()=>Date.now()/1000;
function random(seed){
  let s=2166136261;
  for(const ch of seed) s=Math.imul(s^ch.charCodeAt(0),16777619)>>>0;
  return ()=>{s+=0x6D2B79F5;let t=Math.imul(s^(s>>>15),1|s);t^=t+Math.imul(t^(t>>>7),61|t);return ((t^(t>>>14))>>>0)/4294967296;};
}
const pick=(items,rng)=>items[Math.floor(rng()*items.length)];
function shuffle(items,rng=Math.random){const out=items.slice();for(let i=out.length-1;i>0;i--){const j=Math.floor(rng()*(i+1));[out[i],out[j]]=[out[j],out[i]];}return out;}
function defaultProgress(){return {schema_version:1,answered:{},wrong_book:[],favorites:[],theme:'light',practice:null,game:{
  schema_version:1,campaign:copy(CAMPAIGN),results:{},active:null,paused:{},last_result:null,coins:0,xp:0,
  inventory:['xiaoyuan','orange_adventurer','xiaobao'],equipment:{xp:null,coins:null,wonder:null},skin:'xiaoyuan',outfit:null,title:null,growth_version:2,wishlist:'wonder_broom',skill_state:{schema_version:1,purchased:{},used:{},queued:{},ink:0},
  world:'accounting',expedition_round:1,expedition_stages:{},expedition_unlocked:false,badges:[],finance_expansion:{version:1,schema_version:1,materials:0,chapter_claims:{},buildings:{},companion:null,story_seen:[],commission_claims:{},diary:[],formula_seen:[],tools:{scratch:'',focus_started_at:null,focus_seconds:1500}}}};}
const levelFor=(g,sid)=>g.campaign.levels[sid]||g.expedition_stages[sid];
const cleared=(g,sid)=>!!(g.results[sid]&&g.results[sid].cleared);
const worldStages=(g,wid)=>g.campaign.worlds.find(w=>w.id===wid).chapters.flatMap(c=>c.stages);
const complete=g=>Object.keys(g.campaign.levels).every(sid=>cleared(g,sid));
const expeditionAvailable=g=>!!g.expedition_unlocked||complete(g);
function canPlay(g,sid){const level=levelFor(g,sid);if(!level)return false;if(level.kind==='expedition')return expeditionAvailable(g);const order=worldStages(g,level.world_id),i=order.indexOf(sid);return i===0||i>0&&cleared(g,order[i-1]);}
function nextStage(g,sid,wid){if(sid&&sid.startsWith('expedition:'))return null;const order=worldStages(g,wid||(sid?levelFor(g,sid).world_id:g.world));if(sid){return order[order.indexOf(sid)+1]||null;}return order.find(s=>!cleared(g,s))||order[order.length-1];}
const bonuses=g=>{const extra=CATALOG[g.equipment.wonder]||{};return {xp:(CATALOG[g.equipment.xp]?.bonus_percent||0)+(extra.xp_percent||0),coins:(CATALOG[g.equipment.coins]?.bonus_percent||0)+(extra.coins_percent||0)};};
function start(p,sid,restart=false,rng=Math.random){
 const g=p.game;if(!canPlay(g,sid))throw Error('请先通关前一关。');
 const a=g.active;if(a&&a.stage_id===sid&&!a.settled&&!restart)return a;
 if(a&&!a.settled&&a.stage_id!==sid)g.paused[a.stage_id]=a;
 const saved=g.paused[sid];delete g.paused[sid];if(saved&&!restart){g.active=saved;return saved;}
 g.active={id:Date.now().toString(36)+'-'+Math.random().toString(36).slice(2)+'-'+Math.random().toString(36).slice(2),stage_id:sid,qids:shuffle(levelFor(g,sid).qids,rng),answers:{},drafts:{},references:[],index:0,bonuses:bonuses(g),settled:false,result:null};
 Skills.applyBoosts(g,g.active,levelFor(g,sid));
 return g.active;
}
function record(p,qid,answer,correct){p.answered[qid]={correct:!!correct,user_answer:answer,ts:seconds()};p.wrong_book=p.wrong_book.filter(id=>id!==qid);if(!correct)p.wrong_book.push(qid);}
function submit(p,q,answer,correct,practice=false){const a=practice?p.practice:p.game.active;if(!a||a.settled)throw Error('当前没有进行中的挑战。');if(!a.qids.includes(q.id))throw Error('题目不属于当前挑战。');if(a.answers[q.id])return false;if(Finance.structured(q))throw Error('请提交分小问作答并完成过程自评。');if(!answer.trim())throw Error('请先填写或选择答案。');if(subjective(q)&&!a.references.includes(q.id))throw Error('请先查看参考答案再对照自评。');a.answers[q.id]={correct:!!correct,user_answer:answer,ts:seconds()};record(p,q.id,answer,correct);return true;}
function stars(correct,total){if(!total||correct<0||correct>total)return 0;if(correct===total)return 3;if(correct*100>=total*C.two_star_percent)return 2;if(correct*100>=total*C.pass_percent)return 1;return 0;}
function weighted(weights,rng){let n=Math.floor(rng()*Object.values(weights).reduce((a,b)=>a+b,0));for(const [key,w]of Object.entries(weights)){if(n<w)return key;n-=w;}throw Error('概率配置为空');}
function loot(g,rng){if(Math.floor(rng()*100)>=C.drop_percent)return {kind:'none',name:'这次没有额外掉落',coins:0,xp:0};const kind=weighted(C.category_weights,rng);if(kind==='xp'||kind==='coins')return {kind,name:kind==='xp'?'经验补给':'金币补给',xp:kind==='xp'?C.bonus_xp:0,coins:kind==='coins'?C.bonus_coins:0};let rarity=weighted(ECONOMY.rarity_weights,rng);let pool=Object.values(CATALOG).filter(i=>i.category===kind&&i.rarity===rarity&&!i.starter&&!i.story_only&&!i.earned_only);if(!pool.length){rarity='epic';pool=Object.values(CATALOG).filter(i=>i.category===kind&&i.rarity===rarity&&!i.starter&&!i.story_only&&!i.earned_only);}const item=pick(pool,rng);const duplicate=g.inventory.includes(item.id);if(!duplicate)g.inventory.push(item.id);return {kind,name:item.name,item_id:item.id,rarity,duplicate,coins:duplicate?C.rarities[rarity].duplicate_coins:0,xp:0};}
function surprise(g,rng){if(rng()*100>=ECONOMY.surprise_percent)return [];if(weighted(ECONOMY.surprise_kind_weights,rng)==='ink'){Skills.state(g).ink++;return [{kind:'ink',name:'魔法墨水',amount:1}];}const rarity=weighted(ECONOMY.surprise_rarity_weights,rng),item=pick(WONDERS.items.filter(i=>i.rarity===rarity),rng),duplicate=g.inventory.includes(item.id),coins=duplicate?C.rarities[rarity].duplicate_coins:0;if(!duplicate)g.inventory.push(item.id);g.coins+=coins;return [{kind:'item',id:item.id,name:item.name,rarity,duplicate,coins}];}
function settle(p,rng,surpriseRng){
 const g=p.game,a=g.active;if(!a)throw Error('当前没有挑战');if(a.settled)return a.result;
 if(!a.qids.every(id=>a.answers[id]))throw Error('请完成全部题目后再结算。');
 const total=a.qids.length,correct=a.qids.filter(id=>a.answers[id].correct).length,realStars=stars(correct,total),level=levelFor(g,a.stage_id);
 const assisted=a.skill_clear==='mercy'&&Skills.config.mercy_kinds.includes(level.kind)&&correct>=Skills.config.mercy_min_correct&&correct===Math.ceil(total*C.pass_percent/100)-Skills.config.mercy_extra_wrong;
 const s=realStars||(assisted?1:0),passed=s>0,prev=g.results[a.stage_id]||{},first=passed&&!prev.cleared;
 let xp=Math.max(0,s-(prev.best_stars||0))*C.star_xp,coins=Math.max(0,Math.max(0,s-1)-Math.max(0,(prev.best_stars||0)-1))*ECONOMY.quality_star_coins,drop=null;
 if(first){xp+=level.kind==='boss'?C.boss_xp:C.normal_xp;coins+=level.kind==='boss'?C.boss_coins:level.kind==='expedition'?ECONOMY.expedition_coins:ECONOMY.normal_coins;if(level.kind==='boss'){drop=loot(g,rng||random(a.id));xp+=drop.xp;coins+=drop.coins;}}
 const levelBefore=Skills.level(g);xp=Math.floor(xp*(100+(a.bonuses.xp||0))/100);coins=Math.floor(coins*(100+(a.bonuses.coins||0))/100);g.xp+=xp;g.coins+=coins;
 if(passed){g.results[a.stage_id]={cleared:true,best_stars:Math.max(s,prev.best_stars||0),best_correct:Math.max(correct,prev.best_correct||0),total,first_loot:first?drop:prev.first_loot,first_attempt_id:first?a.id:prev.first_attempt_id,assisted:assisted||!!prev.assisted};if(level.kind==='expedition')g.expedition_round=Math.max(g.expedition_round,level.round+1);for(const w of g.campaign.worlds)for(const c of w.chapters)if(c.stages.every(sid=>cleared(g,sid))&&!g.badges.includes(c.id))g.badges.push(c.id);}
 const growth=first&&level.kind!=='expedition'?surprise(g,surpriseRng||random(a.id+':surprise')):[];
 const finance_rewards=passed?Finance.claimChapters(p):[];
 if(Object.keys(g.campaign.levels).every(sid=>cleared(g,sid)))g.expedition_unlocked=true;
 if(first)g.results[a.stage_id].first_surprise=growth;
 const r={attempt_id:a.id,stage_id:a.stage_id,passed,stars:s,quality:assisted?'技能通关':s>=2?'高质量通关':s===1?'通关':'未通关',assisted,skill_name:assisted?'瞒天过海':'',correct,total,xp,coins,first_clear:first,loot:drop,growth,finance_rewards,level_before:levelBefore,level_after:Skills.level(g),new_skills:Skills.config.definitions.filter(s=>s.level>levelBefore&&s.level<=Skills.level(g)).map(s=>s.id),wrong_qids:a.qids.filter(id=>!a.answers[id].correct)};
 a.settled=true;a.result=r;g.last_result=r;return r;
}
function useMercy(p){const g=p.game,a=g.active;if(a?.result?.assisted)return a.result;const status=Skills.mercyStatus(g,a,a?levelFor(g,a.stage_id):{});if(!status.eligible)throw Error(status.reason);Skills.use(g,'mercy');a.skill_clear='mercy';a.settled=false;a.result=null;return settle(p);}
function growthStatus(g){const n=stats(g).cleared;return WONDERS.milestones.map(m=>({...m,itemInfo:CATALOG[m.item],owned:g.inventory.includes(m.item),unlocked:n>=m.clears,progress:Math.min(100,n*100/m.clears),remaining:Math.max(0,m.clears-n)}));}
function needsGrowth(p){return p.game.growth_version!==2;}
function claimGrowth(p){const g=p.game;g.growth_version=2;if(!Object.hasOwn(g.equipment,'wonder'))g.equipment.wonder=null;if(!g.wishlist)g.wishlist='wonder_broom';Skills.state(g);return [];}
function buy(p,id){const g=p.game,i=CATALOG[id];if(i?.earned_only)throw Error('完成对应委托后领取这张明信片。');if(!i||i.starter||g.inventory.includes(id))throw Error('已拥有该物品。');if(i.category==='companion')return Finance.recruit(p,id);const unlock=WONDERS.milestones.find(m=>m.item===id);if(unlock&&stats(g).cleared<unlock.clears)throw Error('首次通关 '+unlock.clears+' 个主线关卡后上架');if(g.coins<i.price)throw Error('金币不足，去闯关积累金币吧。');g.coins-=i.price;g.inventory.push(id);return i;}
function equip(p,id){const g=p.game,i=CATALOG[id];if(!i||!g.inventory.includes(id))throw Error('尚未拥有该物品。');if(i.category==='companion')return Finance.equipCompanion(p,id);if(i.category==='equipment')g.equipment[i.slot]=g.equipment[i.slot]===id?null:id;else if(i.character){g.skin=id;const o=CATALOG[g.outfit];if(o?.fit_character&&o.fit_character!==i.character)g.outfit=null;}else if(i.outfit){if(i.fit_character){const hero=Object.values(CATALOG).find(c=>c.character===i.fit_character&&g.inventory.includes(c.id));if(!hero)throw Error('请先选择该装扮对应的主角。');g.skin=hero.id;}g.outfit=g.outfit===id?null:id;}else if(i.title)g.title=g.title===id?null:id;}
function gradeStructured(p,q,practice=false){const a=practice?p.practice:p.game.active,r=Finance.grade(a,q);if(r.first)record(p,q.id,r.record.user_answer,r.record.correct);return r;}
function finishPractice(p){const a=p.practice;if(!a||!a.qids.every(id=>a.answers[id]))throw Error('请完成全部题目后结束。');if(a.settled)return a.result;const correct=a.qids.filter(id=>a.answers[id].correct).length,passed=!a.commission_id||correct*100>=a.qids.length*C.pass_percent;a.result={passed,quality:a.commission_id?passed?'经营委托完成':'委托还需复习':'复习完成',stars:0,correct,total:a.qids.length,xp:0,coins:0};a.settled=true;Finance.finishPractice(p,a,C.pass_percent);return a.result;}
function startCommission(p,id){const c=Finance.view(p.game).commissions.find(x=>x.id===id);if(!c?.open)throw Error('经营委托尚未开放。');const a=startPractice(p,Finance.commissionQuestions(META,id),c.name);a.commission_id=id;return a;}
function startRescue(p){const ids=Finance.rescueQuestions(p,META);if(!ids.length)throw Error('当前科目没有错题，救援已完成！');const a=startPractice(p,ids,'精灵错题救援');a.rescue=p.game.world;return a;}
function expedition(p,rng=Math.random){const g=p.game;if(!expeditionAvailable(g))throw Error('三科全部通关后开启无尽远征。');const n=g.expedition_round,sid='expedition:'+String(n).padStart(6,'0');if(g.expedition_stages[sid])return g.expedition_stages[sid];const valid=new Set(META.map(q=>q.id)),wrong=p.wrong_book.filter(id=>valid.has(id)),selected=shuffle(wrong,rng).slice(0,6),wrongSet=new Set(wrong),scores={};for(const q of META){const a=p.answered[q.id];if(a){const key=q.book_id+':'+q.chapter_no;if(!scores[key])scores[key]=[];scores[key].push(a.correct?1:0);}}
 const rate=q=>{const arr=scores[q.book_id+':'+q.chapter_no]||[];return arr.length?arr.reduce((a,b)=>a+b,0)/arr.length:-1;};const rank=(a,b)=>rate(a)-rate(b)||((p.answered[a.id]||{}).ts||0)-((p.answered[b.id]||{}).ts||0);
 selected.push(...shuffle(META.filter(q=>!wrongSet.has(q.id)),rng).sort(rank).slice(0,10-selected.length).map(q=>q.id));if(selected.length<10)selected.push(...shuffle(META.filter(q=>!selected.includes(q.id)),rng).sort(rank).slice(0,10-selected.length).map(q=>q.id));
 const stage={id:sid,world_id:'expedition',chapter_id:'expedition',chapter_no:n,chapter_title:'无尽远征',biome:C.biomes[(n-1)%6].id,kind:'expedition',name:'远征第 '+n+' 关',qids:selected,round:n};g.expedition_stages[sid]=stage;return stage;}
function startPractice(p,ids,name){if(!ids.length)throw Error('当前筛选没有题目。');p.practice={id:'practice-'+Date.now()+'-'+Math.random().toString(36).slice(2),qids:ids.slice(),answers:{},drafts:{},references:[],index:0,settled:false,name};return p.practice;}
function restartPractice(p){const old=p.practice;if(!old)throw Error('当前没有待重试的练习。');const a=startPractice(p,old.qids,old.name);for(const key of ['commission_id','rescue'])if(old[key])a[key]=old[key];return a;}
function stats(g,wid){const ids=wid?worldStages(g,wid):Object.keys(g.campaign.levels);return {cleared:ids.filter(id=>cleared(g,id)).length,total:ids.length,stars:ids.reduce((n,id)=>n+((g.results[id]||{}).best_stars||0),0),level:Math.floor(g.xp/C.xp_per_level)+1};}
module.exports={C,ECONOMY,CATALOG,CAMPAIGN,META,Finance,copy,random,shuffle,subjective,defaultProgress,levelFor,cleared,worldStages,complete,expeditionAvailable,canPlay,nextStage,start,submit,record,gradeStructured,finishPractice,startCommission,startRescue,stars,loot,surprise,settle,useMercy,growthStatus,needsGrowth,claimGrowth,buy,equip,expedition,startPractice,restartPractice,stats,bonuses};
