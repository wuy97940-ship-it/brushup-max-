// 6.0新局入口。旧规则仅供旧格式的隔离回归，生产新局使用独立命名空间。
const Base=require('./game');
const H=require('./growth600');
const A=Base.Adventure;
const Hunting=require('./hunting600');
const modern=g=>g.ruleset==='6.0.0';
const CATALOG={...Base.CATALOG,...Object.fromEntries(Object.values(Hunting.SPIRITS).map(s=>[s.id,{...s,category:'companion',rarity:s.rarity,price:0,story_only:true,earned_only:true,capture_only:true}])),...Object.fromEntries(A.C.heroes.map(h=>[h.id,{...Base.CATALOG[h.id],...h,category:'skin',character:h.id,starter:false}]))};
function bonuses(g){const base=Base.bonuses(g),bond=modern(g)?A.bond(g):{xp:0,coins:0};return {xp:base.xp+bond.xp,coins:base.coins+bond.coins};}
function buy(p,id){const g=p.game;if(!modern(g))return Base.buy(p,id);if(!g.starter_claimed)throw Error('请先选择免费初始伙伴。');H.login(g);const hero=A.C.heroes.find(h=>h.id===id);if(hero){Hunting.guard(g);if(Hunting.state(g).hero_qualifications[id])throw Error('已通过考核，请支付保留资格的尾款。');if(g.inventory.includes(id))throw Error('已拥有这位主角。');if(g.coins<hero.price)throw Error('金币不足。');const s=A.ensure(g);s.hero_profiles[id]=A.newHero(g);g.coins-=hero.price;g.inventory.push(id);H.enroll(g,id);return CATALOG[id];}if(Hunting.SPIRITS[id])throw Error('请到精灵猎场收服这只精灵。');const base=A.heroId(id);if(base&&!g.inventory.includes(base))throw Error('请先解锁对应主角。');return Base.buy(p,id);}
function equip(p,id){const g=p.game;if(!modern(g))return Base.equip(p,id);const item=CATALOG[id];if(!item||!g.inventory.includes(id))throw Error('尚未拥有该物品。');if(Hunting.SPIRITS[id])return Hunting.equipSpirit(p,id);const target=item.character?A.heroId(id):item.fit_character;if(target){if(!g.inventory.includes(target))throw Error('请先解锁对应主角。');if(target!==A.heroId(g.skin))Hunting.guard(g);A.switchHero(g,target);}return Base.equip(p,id);}
function defaultProgress600(){const p=Base.defaultProgress(),g=p.game;g.ruleset='6.0.0';g.starter_claimed=false;g.inventory=[];g.skin=null;g.wishlist='mood_plush';g.growth600=H.initial();g.product600={chapter_claims:{},coin_units:0};return p;}
function restartNewGame(p){if(!modern(p.game))throw Error('请使用6.0新局入口。');const next=defaultProgress600();next.game.campaign=p.game.campaign;if(p.bank_family)next.bank_family=p.bank_family;for(const key of Object.keys(p))delete p[key];Object.assign(p,next);return {reset:true};}
function requireAction(g){if(modern(g)){if(!g.starter_claimed)throw Error('请先选择一位初始伙伴。');H.login(g);}A.requireEnergy(g);}
function claimStarter(p,id){const g=p.game;if(!modern(g)||!A.C.heroes.some(h=>h.id===id))throw Error('请选择有效的初始伙伴。');if(g.starter_claimed){if(g.skin===id)return id;throw Error('免费初始伙伴已经领取。');}if(g.inventory.length||g.xp||g.coins||Object.keys(p.answered).length)throw Error('欢迎状态异常，请恢复有效备份。');g.inventory.push(id);g.skin=id;g.starter_claimed=true;H.enroll(g,id);return id;}
function start(p,sid,restart=false,rng=Math.random){if(!modern(p.game))return Base.start(p,sid,restart,rng);const g=p.game;requireAction(g);Hunting.guard(g);if(!Base.canPlay(g,sid))throw Error('请先通关前一关。');if(g.active?.stage_id===sid&&!g.active.settled&&!restart)return g.active;if(g.active&&!g.active.settled&&g.active.stage_id!==sid)g.paused[g.active.stage_id]=g.active;const saved=g.paused[sid];delete g.paused[sid];if(saved&&!restart){g.active=saved;return saved;}const a={id:Date.now().toString(36)+'-'+Math.random().toString(36).slice(2)+'-'+Math.random().toString(36).slice(2),stage_id:sid,qids:Base.shuffle(Base.levelFor(g,sid).qids,rng),answers:{},drafts:{},references:[],index:0,bonuses:bonuses(g),settled:false,result:null};H.prepare(g,a,{kind:Base.levelFor(g,sid).kind});g.active=a;return a;}
function startPractice(p,ids,name,mode='basic'){if(!modern(p.game))return Base.startPractice(p,ids,name);requireAction(p.game);Hunting.guard(p.game);const a=Base.startPractice(p,ids,name);a.bonuses=bonuses(p.game);H.prepare(p.game,a,{mode});return a;}
function current(p,practice){return practice?p.practice:p.game.active;}
function primary(p,q,draft,practice=false,now=Date.now()){const a=current(p,practice);if(!modern(p.game))return null;requireAction(p.game);return H.submitPrimary(p,a,q,draft,now);}
function startTimer(p,q,practice=false,now=Date.now()){if(!modern(p.game))return null;requireAction(p.game);return H.startTimer(p.game,current(p,practice),q,now);}
function answerCoins(p,a,q,correct,assisted,now,timeout){
 const g=p.game;if(!correct||assisted||timeout||Base.subjective(q))return 0;
 const key=a.primary_submissions[q.id]?.day,d=H.day(g,now,key).value;
 if(!d.coin_qids)d.coin_qids={};if(d.coin_qids[q.id])return 0;d.coin_qids[q.id]=true;
 d.coins=d.coins||0;const remaining=A.C.rewards.daily_answer_coins_ceiling-d.coins;if(remaining<=0)return 0;
 const s=g.product600,numerator=s.coin_units+Math.round(A.C.rewards.answer_coins*10000*(100+(a.bonuses?.coins||0))/100),coins=Math.min(remaining,Math.floor(numerator/10000));s.coin_units=numerator%10000;g.coins+=coins;d.coins+=coins;return coins;
}
function recordAction(p,a,q,answer,correct,{practice=false,now=Date.now(),timeout=false}={}){
 requireAction(p.game);if(!a||a.settled||a.qids[a.index]!==q.id)throw Error('题目不属于当前正在显示的挑战。');
 if(a.answers[q.id])return false;
 if(timeout){const t=a.timers[q.id];if(!H.timed(a)||!t||t.status!=='running'||now<t.deadline||a.primary_submissions[q.id])throw Error('本题尚未超时或已经提交。');correct=false;}
 else H.checkDeadline(a,q,now);
 const assisted=(a.assisted_qids||[]).includes(q.id)||!!a.hints?.[q.id],xp=H.award(p,a,q,{correct,assisted,now,timeout}),resources=A.answer(p,a,q,correct,{practice:practice&&!a.arena610,now}),protection=H.protect(p.game,a,q,{correct,timeout});
 const coins=answerCoins(p,a,q,correct,assisted,now,timeout);
 const rec={...protection,user_answer:answer,ts:now/1000,assisted,self_assessed:Base.subjective(q),xp,coins,resources};
 a.answers[q.id]=rec;Base.record(p,q.id,answer,correct);if(a.timers[q.id])a.timers[q.id].status=timeout?'timeout':'graded';return rec;
}
function submit(p,q,answer,correct,practice=false,options={}){if(!modern(p.game))return Base.submit(p,q,answer,correct,practice);const a=current(p,practice);if(a?.answers[q.id])return false;if(!String(answer).trim())throw Error('请先填写或选择答案。');if(Base.Finance.structured(q))throw Error('请提交各小问并完成过程自评。');if(Base.subjective(q)&&(!a?.primary_submissions[q.id]||!a.references.includes(q.id)))throw Error('请先提交自己的作答并对照参考自评。');return recordAction(p,a,q,String(answer),correct,{...options,practice});}
function timeout(p,q,draft='',practice=false,now=Date.now()){const a=current(p,practice);if(a?.answers[q.id])return a.answers[q.id];return recordAction(p,a,q,String(draft),false,{practice,now,timeout:true});}
function prepareStructured(p,q,practice=false,now=Date.now()){const a=current(p,practice);if(!modern(p.game))return Base.Finance.prepareSubmission(a,q);requireAction(p.game);if(!a.answers[q.id])H.checkDeadline(a,q,now);const sub=Base.Finance.prepareSubmission(a,q);if(!a.answers[q.id]){const text=q.subquestions.map(s=>sub.draft.process[s.id]).join('\n')+'\n'+Object.values(sub.draft.values).join('\n');primary(p,q,text,practice,now);}return sub;}
function gradeStructured(p,q,practice=false,now=Date.now()){
 if(!modern(p.game))return Base.gradeStructured(p,q,practice);const a=current(p,practice);requireAction(p.game);const r=Base.Finance.grade(a,q);if(r.first){delete a.answers[q.id];Object.assign(r.record,recordAction(p,a,q,r.record.user_answer,r.record.correct,{practice,now}));a.answers[q.id]=r.record;}return r;
}
function settle(p,rng,surpriseRng){
 const g=p.game;if(!modern(g))return Base.settle(p,rng,surpriseRng);const a=g.active;if(!a)throw Error('当前没有挑战。');if(a.settled)return a.result;requireAction(g);if(a.qids.some(id=>!a.answers[id]))throw Error('请完成全部题目后结算。');
 const level=Base.levelFor(g,a.stage_id),total=a.qids.length,records=a.qids.map(id=>a.answers[id]),correct=records.filter(r=>r.correct).length,gameCorrect=records.filter(r=>r.game_correct).length,assisted=records.some(r=>r.assisted||r.protected),selfAssessed=records.some(r=>r.self_assessed),passed=gameCorrect*100>=total*a.challenge_rules.pass_percent,stars=passed?(selfAssessed?1:correct===total&&!assisted?3:2):0,prev=g.results[a.stage_id]||{},first=passed&&!prev.cleared;
 let xp=first?(a.challenge_rules.boss?A.C.boss.first_stage_xp:A.C.rewards.first_stage_xp):0,coins=first?(a.challenge_rules.boss?A.C.boss.first_stage_coins:A.C.rewards.first_stage_coins):0,materials=0;
 if(passed){g.results[a.stage_id]={...prev,cleared:true,best_stars:Math.max(prev.best_stars||0,stars),best_correct:Math.max(prev.best_correct||0,correct),best_game_correct:Math.max(prev.best_game_correct||0,gameCorrect),total,first_attempt_id:first?a.id:prev.first_attempt_id,assisted:assisted||!!prev.assisted};
  for(const w of g.campaign.worlds)for(const ch of w.chapters)if(ch.stages.every(id=>Base.cleared(g,id))&&!g.product600.chapter_claims[ch.id]){g.product600.chapter_claims[ch.id]={attempt_id:a.id};xp+=A.C.rewards.first_chapter_xp;coins+=A.C.rewards.first_chapter_coins;materials+=A.C.rewards.first_chapter_materials;if(!g.badges.includes(ch.id))g.badges.push(ch.id);}
  if(level.kind==='expedition')g.expedition_round=Math.max(g.expedition_round,level.round+1);
 }
 xp=Math.floor(xp*(100+(a.bonuses.xp||0))/100);coins=Math.floor(coins*(100+(a.bonuses.coins||0))/100);g.xp+=xp;g.coins+=coins;
 if(materials){const s=Base.Finance.ensureExpansion(g);s.materials=Math.min(60,s.materials+materials);}
 if(Base.complete(g))g.expedition_unlocked=true;A.settle(g,a,passed);A.ensure(g);
 const result={attempt_id:a.id,stage_id:a.stage_id,passed,stars,quality:passed?assisted?'技能助力':selfAssessed?'自评通关':'通关':'未通关',assisted,correct,game_correct:gameCorrect,total,xp:xp+a.xp_earned,answer_xp:a.xp_earned,settlement_xp:xp,coins,materials,first_clear:first,loot:null,growth:[],new_skills:[],pass_percent:a.challenge_rules.pass_percent,level_before:a.challenge_rules.level,level_after:A.level(g),wrong_qids:a.qids.filter(id=>!a.answers[id].correct),protected_qids:a.qids.filter(id=>a.answers[id].protected)};
 a.settled=true;a.result=result;g.last_result=result;return result;
}
function finishPractice(p){if(!modern(p.game))return Base.finishPractice(p);if(p.practice?.arena610)return require('./arena610').finish(p);const a=p.practice;if(!a||a.qids.some(id=>!a.answers[id]))throw Error('请完成全部题目后结束。');if(a.settled)return a.result;const correct=a.qids.filter(id=>a.answers[id].correct).length,total=a.qids.length,passed=!a.commission_id||correct*100>=total*80;a.result={passed,quality:a.commission_id?passed?'经营委托完成':'委托还需复习':'复习完成',stars:0,correct,total,xp:a.xp_earned,coins:0};a.settled=true;Base.Finance.finishPractice(p,a,80);return a.result;}
function startCommission(p,id){if(!modern(p.game))return Base.startCommission(p,id);const c=Base.Finance.view(p.game).commissions.find(x=>x.id===id);if(!c?.open)throw Error('经营委托尚未开放。');const a=startPractice(p,Base.Finance.commissionQuestions(Base.META,id),c.name);a.commission_id=id;return a;}
function startRescue(p){if(!modern(p.game))return Base.startRescue(p);const ids=Base.Finance.rescueQuestions(p,Base.META);if(!ids.length)throw Error('当前科目没有待救援错题。');const a=startPractice(p,ids,'精灵错题救援','review');a.rescue=p.game.world;return a;}
function restartPractice(p){if(!modern(p.game))return Base.restartPractice(p);const old=p.practice;if(!old)throw Error('当前没有练习。');if(old.arena610)return require('./arena610').start(p,{...old.arena610,mode:old.product_mode,ids:old.qids,target:old.target});const a=startPractice(p,old.qids,old.name,old.product_mode);for(const key of ['commission_id','rescue'])if(old[key])a[key]=old[key];return a;}
function stats(g,wid){return {...Base.stats(g,wid),...(modern(g)?{level:A.level(g)}:{})};}
function uiGame(g){return modern(g)?{skin:g.skin,outfit:g.outfit,title:g.title,equipment:g.equipment,coins:g.coins,xp:g.xp,wishlist:g.wishlist,starter_claimed:g.starter_claimed,companions:(g.product600.companions||[g.finance_expansion?.companion].filter(Boolean)).slice(0,A.bond(g).limit),finance_expansion:{companion:g.finance_expansion?.companion||null}}:g;}
module.exports={...Base,CATALOG,Hunting,bonuses,answerCoins,LegacyCATALOG:Base.CATALOG,Growth600:H,modern,buy,equip,defaultProgress600,restartNewGame,requireAction,claimStarter,start,startPractice,primary,startTimer,submit,timeout,prepareStructured,gradeStructured,settle,finishPractice,startCommission,startRescue,restartPractice,stats,uiGame};
