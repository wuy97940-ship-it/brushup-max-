// 6.0永久成长、施法与持久化计时。所有改变通过store.commit提交后再展示。
const A=require('./adventure600');
const C=A.C.growth;
const Questions=require('./questions600');
const DEFINITIONS=Object.fromEntries(C.skills.map(s=>[s.id,s]));
const clone=x=>JSON.parse(JSON.stringify(x));
const passive=id=>DEFINITIONS[id]?.kind==='passive';
const subjective=q=>['计算分析题','综合题','简答题','论述题','案例分析题','计算或情境案例'].includes(q.type)||!!q.subquestions?.length;
const dayKey=now=>{const d=new Date(now);if(!Number.isFinite(d.getTime()))throw Error('时间数据无效。');return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');};
function initial(){return {version:6,skills:{},loadout:[],transactions:{},days:{},xp_remainder:0,last_seen_day:''};}
function state(g){if(!g.growth600)g.growth600=initial();return g.growth600;}
function day(g,now=Date.now(),key){const s=state(g),today=dayKey(now);s.last_seen_day=s.last_seen_day>today?s.last_seen_day:today;key=key||s.last_seen_day;if(!s.days[key])s.days[key]={active_qids:{},xp_qids:{}};return {key,value:s.days[key]};}
const ordinal=key=>Date.parse(key+'T12:00:00Z')/86400000;
function login(g,now=Date.now()){
 const s=state(g),today=[s.last_seen_day,dayKey(now)].sort().pop();
 if(!s.settled_through){s.settled_through=today;s.enrollment=s.enrollment||{};s.streak=s.streak||0;s.best_streak=s.best_streak||0;s.streak_last_day=s.streak_last_day||null;s.badges=s.badges||[];}
 const start=ordinal(s.settled_through)+1,end=ordinal(today)-1;
 if(end<start){s.last_seen_day=today;day(g,now,today);return {days:0,points:0,heroes:{}};}
 const qualified=Object.entries(s.days).filter(([,d])=>Object.keys(d.active_qids).length>=C.daily_target).map(([k])=>ordinal(k));
 const summary={days:Math.max(0,end-start+1)-qualified.filter(n=>n>=start&&n<=end).length,points:0,heroes:{}};
 if(end>=start&&g.starter_claimed){const current=A.heroId(g.skin),a=A.ensure(g),heroes={...a.hero_profiles,[current]:a};for(const [id,h]of Object.entries(heroes)){const enrollment=s.enrollment[id]||today,from=Math.max(start,ordinal(enrollment)+1),count=Math.max(0,end-from+1)-qualified.filter(n=>n>=from&&n<=end).length,loss=Math.min(h.energy,Math.max(0,count)*C.missed_day_points);h.energy=Math.round((h.energy-loss)*100)/100;if(loss){summary.heroes[id]=loss;summary.points+=loss;}}}
 if(ordinal(today)>ordinal(s.settled_through))s.settled_through=new Date((ordinal(today)-1)*86400000).toISOString().slice(0,10);
 s.last_seen_day=today;day(g,now,today);if(summary.days>0)s.offline_summary=summary;return summary;
}
function enroll(g,id,now=Date.now()){login(g,now);const s=state(g);s.enrollment[id]=s.enrollment[id]||s.last_seen_day;}
function activity(g,qid,key){const s=state(g),d=s.days[key];d.active_qids[qid]=true;if(Object.keys(d.active_qids).length<C.daily_target||d.qualified)return;d.qualified=true;s.streak=s.streak_last_day&&ordinal(key)-ordinal(s.streak_last_day)===1?s.streak+1:1;s.streak_last_day=key;s.best_streak=Math.max(s.best_streak||0,s.streak);for(const n of [3,7,30])if(s.streak>=n&&!s.badges.includes(n))s.badges.push(n);}
function dailyView(g,now=Date.now()){const s=g.growth600||initial(),today=[s.last_seen_day,dayKey(now)].sort().pop(),count=Object.keys(s.days[today]?.active_qids||{}).length;return {count,target:C.daily_target,qualified:count>=C.daily_target,remaining:Math.max(0,C.daily_target-count),streak:s.streak_last_day&&ordinal(today)-ordinal(s.streak_last_day)<=1?s.streak||0:0,bestStreak:s.best_streak||0,badges:s.badges||[],offline:s.offline_summary||null};}
function view(g){const level=A.level(g),s=g.growth600||initial(),within=g.xp-A.threshold(level),required=A.threshold(level+1)-A.threshold(level);return {level,within,required,progress:within*100/required,title:[...C.honors].reverse().find(h=>level>=h.level)?.name||'初来乍到',skills:C.skills.map(d=>{const rank=s.skills[d.id]||0,requiredLevel=d.level+rank*10,price=d.price*2**rank;return {...d,rank,requiredLevel,price,maxed:rank===4,equipped:!passive(d.id)&&s.loadout.includes(d.id),passive:passive(d.id),unlocked:level>=d.level,canLearn:rank<4&&level>=requiredLevel&&g.coins>=price,xpRemaining:Math.max(0,A.threshold(requiredLevel)-g.xp)};})};}
function learn(p,id,operation){const g=p.game,s=state(g);if(typeof operation!=='string'||!operation.trim()||operation.length>160)throw Error('学习交易编号无效。');const prior=s.transactions[operation];if(prior){if(prior.skill_id!==id)throw Error('交易编号与技能不一致。');return prior;}const row=view(g).skills.find(r=>r.id===id);if(!row?.canLearn)throw Error('尚未达到学习等级、金币不足或技能已满阶。');g.coins-=row.price;s.skills[id]=row.rank+1;if(!passive(id)&&s.loadout.length<3&&!s.loadout.includes(id))s.loadout.push(id);const result={skill_id:id,rank:row.rank+1,coins:row.price};s.transactions[operation]=result;A.ensure(g);return result;}
function equip(p,id){const s=state(p.game);if(passive(id))throw Error('精灵羁绊自动生效，不占主动技能位置。');if(!s.skills[id])throw Error('请先学习这项技能。');if(s.loadout.includes(id))s.loadout=s.loadout.filter(x=>x!==id);else {if(s.loadout.length>=3)throw Error('最多携带三项主动技能，请先卸下一项。');s.loadout.push(id);}return s.loadout.slice();}
function prepare(g,a,{mode='adventure',kind='normal'}={}){if(a.ruleset==='6.0.0')return a;const s=state(g),lv=A.level(g),boss=kind==='boss',b=A.C.boss;
 a.bond_snapshot=A.bond(g);a.companions_snapshot=(g.product600?.companions||[g.finance_expansion?.companion].filter(Boolean)).slice(0,a.bond_snapshot.limit);
 Object.assign(a,{ruleset:'6.0.0',product_mode:mode,skill_snapshot:Object.fromEntries(s.loadout.filter(id=>s.skills[id]&&!passive(id)).slice(0,3).map(id=>[id,s.skills[id]])),skill_targets:[],skill_uses:{},skill_results:{},timers:{},primary_submissions:{},xp_earned:0,challenge_rules:{version:'6.0.0',level:lv,boss,pass_percent:boss?b.pass_percent:A.C.pass_percent||80,objective_seconds:boss?b.objective_seconds:C.timer.objective_seconds,objective_per_level:boss?b.objective_per_level:C.timer.objective_per_level,objective_ceiling:boss?b.objective_ceiling:null,subjective_seconds:C.timer.subjective_seconds,subjective_per_level:C.timer.subjective_per_level,skill_costs:Object.fromEntries(C.skills.filter(d=>!passive(d.id)).map(d=>[d.id,d.mana_costs.slice()]))}});
 if(mode==='arena')a.skill_snapshot={};return a;
}
const timed=a=>C.timer.timed_modes.includes(a.product_mode);
function duration(g,a,q){const r=a.challenge_rules,kind=subjective(q)?'subjective':'objective',lv=r.boss?r.level:A.level(g),seconds=r[kind+'_seconds']+r[kind+'_per_level']*lv;return Math.min(seconds,r[kind+'_ceiling']??seconds);}
function startTimer(g,a,q,now=Date.now()){if(!timed(a)||a.settled||a.answers[q.id]||a.primary_submissions[q.id])return null;A.requireEnergy(g);if(a.qids[a.index]!==q.id)throw Error('仅对实际显示的当前题开始计时。');if(a.timers[q.id])return a.timers[q.id];const seconds=duration(g,a,q);a.timers[q.id]={started_at:now,deadline:now+seconds*1000,duration:seconds,extension:0,status:'running'};return a.timers[q.id];}
function checkDeadline(a,q,now=Date.now()){if(!timed(a))return;const t=a.timers[q.id];if(!t)throw Error('题目尚未显示并开始计时。');if(t.status==='running'&&now>=t.deadline)throw Error('本题已超时，请先保存超时记录。');}
function award(p,a,q,{correct=false,assisted=false,timeout=false,now=Date.now()}={}){if(timeout)return 0;const g=p.game;login(g,now);const s=state(g),entry=day(g,now,a.primary_submissions[q.id]?.day),d=entry.value;activity(g,q.id,entry.key);const credit=d.xp_qids[q.id]||(d.xp_qids[q.id]={completion:0,correct:0}),weight=C.mode_weights[a.product_mode]??80,kind=subjective(q)?'subjective':'objective',completion=C.question_xp[kind]*weight,bonus=correct&&!assisted?C.question_xp[kind+'_correct']*weight:0,delta=Math.max(0,completion-credit.completion)+Math.max(0,bonus-credit.correct);credit.completion=Math.max(completion,credit.completion);credit.correct=Math.max(bonus,credit.correct);const numerator=delta*(100+(a.bonuses?.xp||0))+s.xp_remainder,xp=Math.floor(numerator/10000);s.xp_remainder=numerator%10000;g.xp+=xp;a.xp_earned+=xp;A.ensure(g);return xp;}
function submitPrimary(p,a,q,draft,now=Date.now()){if(a.primary_submissions[q.id])return a.primary_submissions[q.id];A.requireEnergy(p.game);if(a.settled||a.qids[a.index]!==q.id||a.answers[q.id])throw Error('当前题不能再次提交。');checkDeadline(a,q,now);if(!String(draft).trim())throw Error('请先填写自己的作答。');const result={draft:clone(draft),day:day(p.game,now).key,submitted_at:now,xp:0};a.primary_submissions[q.id]=result;result.xp=award(p,a,q,{now});if(a.timers[q.id])a.timers[q.id].status='submitted';return result;}
const clues=(q,id)=>{const raw=q.learning_hints?.[id==='outline'?'outline':'memory'];return (Array.isArray(raw)?raw:typeof raw==='string'?[raw]:[]).filter(x=>typeof x==='string'&&x.trim());};
function cost(a,id){const rank=a.skill_snapshot[id]||0;return rank?a.challenge_rules.skill_costs[id]?.[rank-1]||0:0;}
function status(g,a,q,id,now=Date.now()){
 const rank=a?.skill_snapshot?.[id]||0,mana=A.view(g).mana,manaCost=a?cost(a,id):0;let reason='';
 if(!DEFINITIONS[id]||passive(id))reason='被动技能无需施法';
 else if(!a||a.settled||a.qids[a.index]!==q.id)reason='请在当前场次的当前题上施法';
 else if(['hero_trial','spirit_hunt','arena'].includes(a.product_mode))reason='本场禁用辅助技能';
 else if(!rank)reason='本场未携带';
 else if(A.view(g).energy<=0)reason='体力为零，请先还魂';
 else if(a.answers[q.id]||a.primary_submissions[q.id])reason='本题已提交';
 else if(a.skill_targets.includes(id+':'+q.id))reason='本题已使用';
 else if(id==='clock'&&!timed(a))reason='不限时练习无需延时';
 else if(timed(a)&&!a.timers[q.id])reason='本题尚未开始计时';
 else if(timed(a)&&a.timers[q.id].status==='running'&&now>=a.timers[q.id].deadline)reason='本题已超时';
 else if(mana<manaCost)reason='魔法不足';
 else if(['memory','outline'].includes(id)&&!clues(q,id).length)reason='本题暂无可靠线索';
 else if(id==='outline'&&!subjective(q))reason='仅适用于主观题';
 else if(id==='insight'&&(q.type!=='单选题'||Object.keys(Questions.options(q)).length<3||!Object.hasOwn(Questions.options(q),String(q.answer).trim().toUpperCase())))reason='本题不适合排除选项';
 return {allowed:!reason,reason,rank,cost:manaCost,mana};
}
function use(p,a,q,id,now=Date.now()){const key=id+':'+q.id;if(a.skill_results[key])return a.skill_results[key];const v=status(p.game,a,q,id,now);if(!v.allowed||id==='mercy')throw Error(v.reason||'瞒天过海在错误时自动施展。');let result;
 if(id==='clock'){const seconds=DEFINITIONS.clock[subjective(q)?'subjective':'objective'][v.rank-1],t=a.timers[q.id];t.deadline+=seconds*1000;t.duration+=seconds;t.extension+=seconds;result={seconds};}
 else if(id==='insight'){const right=String(q.answer).trim().toUpperCase(),wrong=Object.keys(Questions.options(q)).filter(x=>x!==right).sort(),count=Math.min(DEFINITIONS.insight.exclude[v.rank-1],Object.keys(Questions.options(q)).length-2);const excluded=wrong.slice(0,count);(a.hints||(a.hints={}))[q.id]=excluded;result={excluded};}
 else {const lines=clues(q,id).slice(0,id==='outline'?DEFINITIONS.outline.lines[v.rank-1]:1);(a.growth_clues||(a.growth_clues={}))[q.id]=lines;result={lines};}
 if(id!=='clock'&&!(a.assisted_qids||[]).includes(q.id))(a.assisted_qids||(a.assisted_qids=[])).push(q.id);a.skill_targets.push(key);a.skill_uses[id]=(a.skill_uses[id]||0)+1;A.ensure(p.game).mana-=v.cost;result.mana_spent=v.cost;a.skill_results[key]=result;return result;
}
function protect(g,a,q,{correct=false,timeout=false}={}){const key='mercy:'+q.id;if(a.skill_results[key])return a.skill_results[key];const s=A.ensure(g),manaCost=cost(a,'mercy'),protectedAnswer=!correct&&!!a.skill_snapshot.mercy&&a.product_mode!=='arena'&&s.energy>0&&s.mana>=manaCost;const result={correct:!!correct,game_correct:!!correct||protectedAnswer,protected:protectedAnswer,timeout:!!timeout,mana_spent:protectedAnswer?manaCost:0};if(protectedAnswer){s.mana-=manaCost;a.skill_targets.push(key);a.skill_uses.mercy=(a.skill_uses.mercy||0)+1;}a.skill_results[key]=result;return result;}
module.exports={C,DEFINITIONS,initial,state,dayKey,day,login,enroll,activity,dailyView,subjective,view,learn,equip,prepare,timed,duration,startTimer,checkDeadline,award,submitPrimary,clues,cost,status,use,protect};
