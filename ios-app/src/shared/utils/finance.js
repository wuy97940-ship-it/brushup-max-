// 财管数值核对、剧情与小镇规则；苹果和网页由准备脚本复制同一源文件。
const CONFIG=require('../data/finance_config');
const KNOWLEDGE=require('../data/finance_knowledge');
const clone=x=>JSON.parse(JSON.stringify(x));
const object=x=>!!x&&typeof x==='object'&&!Array.isArray(x);
const time=()=>Date.now()/1000;
function state(g){
 if(!object(g.finance_expansion))g.finance_expansion={version:1};
 const s=g.finance_expansion;
 const defaults={schema_version:1,materials:0,chapter_claims:{},buildings:{},companion:null,story_seen:[],commission_claims:{},diary:[],formula_seen:[],tools:{scratch:'',focus_started_at:null,focus_seconds:1500}};
 for(const [k,v]of Object.entries(defaults))if(s[k]===undefined)s[k]=clone(v);
 return s;
}
const structured=q=>Array.isArray(q.subquestions)&&q.subquestions.length>0;
const units={'元':{kind:'money',power:0},'万元':{kind:'money',power:4},'%':{kind:'ratio',power:-2},'小数':{kind:'ratio',power:0},'件':{kind:'count',power:0},'年':{kind:'years',power:0},'无单位':{kind:'scalar',power:0}};
// 十进制字符串整数避免浮点舍入，也兼容没有 BigInt 的微信运行环境。
// 每次只对一位数字做运算；金额和精度始终保留为完整十进制。
const digitsOnly=v=>v.replace(/^0+(?=\d)/,'');
function compareDigits(a,b){return a.length===b.length?(a===b?0:a<b?-1:1):a.length<b.length?-1:1;}
function addDigits(a,b){
 let result='',carry=0;
 for(let i=a.length-1,j=b.length-1;i>=0||j>=0||carry;i--,j--){
  const sum=(i>=0?Number(a[i]):0)+(j>=0?Number(b[j]):0)+carry;
  result=String(sum%10)+result;carry=Math.floor(sum/10);
 }
 return digitsOnly(result);
}
// 调用者保证 a >= b。
function subtractDigits(a,b){
 let result='',borrow=0;
 for(let i=a.length-1,j=b.length-1;i>=0;i--,j--){
  let value=Number(a[i])-(j>=0?Number(b[j]):0)-borrow;
  borrow=value<0?1:0;if(borrow)value+=10;result=String(value)+result;
 }
 return digitsOnly(result);
}
function decimal(value){
 const raw=String(value??'').trim().replace(/−/g,'-').replace(/[，,]/g,'');
 if(!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(raw))throw Error('请输入有限十进制数值。');
 const negative=raw.startsWith('-'),v=raw.replace(/^[+-]/,''),parts=v.split('.'),digits=(parts[0]||'0')+(parts[1]||'');
 if(digits.length>100)throw Error('数值过长，请检查输入。');
 const normalized=digitsOnly(digits),places=(parts[1]||'').length;
 return {digits:normalized,negative:negative&&normalized!=='0',power:-places,places};
}
function scale(v,power){return {...v,power:v.power+power};}
function withinPrecision(actual,wanted,exact,places){
 const power=Math.min(actual.power,wanted.power,exact?0:-places-1);
 const a=digitsOnly(actual.digits+'0'.repeat(actual.power-power));
 const b=digitsOnly(wanted.digits+'0'.repeat(wanted.power-power));
 const order=compareDigits(a,b);
 const delta=actual.negative!==wanted.negative?addDigits(a,b):order>=0?subtractDigits(a,b):subtractDigits(b,a);
 if(exact)return delta==='0';
 const halfUnit='5'+'0'.repeat(-places-1-power);
 return compareDigits(delta,halfUnit)<=0;
}
function checkNumber(check,input,inputUnit){
 try{
  const expectedUnit=check.unit||'无单位';let text=String(input??'').trim(),unit=inputUnit||expectedUnit;
  const suffix=text.match(/(万元|元|小数|件|年|%|％)$/);
  if(suffix){unit=suffix[1]==='％'?'%':suffix[1];text=text.slice(0,-suffix[1].length).trim();}
  const target=units[expectedUnit],source=units[unit];
  if(!target||!source||target.kind!==source.kind)return {key:check.key,label:check.label,correct:false,message:'单位不匹配',expected:check.value,unit:expectedUnit};
  const wanted=decimal(check.value),actual=scale(decimal(text),source.power-target.power);
  const places=Number.isInteger(check.decimals)?check.decimals:wanted.places;
  if(!check.exact&&(places<0||places>30))throw Error('参考答案精度无效。');
  const correct=withinPrecision(actual,wanted,!!check.exact,places);
  return {key:check.key,label:check.label,correct,message:correct?'数值通过':'请核对公式、代入与单位',expected:String(check.value),unit:expectedUnit};
 }catch{return {key:check.key,label:check.label,correct:false,message:'请输入有效数值',expected:String(check.value),unit:check.unit||'无单位'};}
}
function draft(a,q){
 if(!a.structured_drafts)a.structured_drafts={};
 if(!a.structured_drafts[q.id])a.structured_drafts[q.id]={process:{},values:{},units:{}};
 return a.structured_drafts[q.id];
}
function saveDraft(a,q,kind,key,value){
 if(!a||a.settled)throw Error('本轮已结束。');
 if(!['process','values','units'].includes(kind))throw Error('草稿字段无效。');
 const pending=a.structured_submissions?.[q.id];if(pending&&!pending.graded)throw Error('已提交，请完成过程自评。');
 if(a.answers[q.id]&&!a.correction_edit?.[q.id])throw Error('先点击重新核对再修改。');
 draft(a,q)[kind][key]=String(value??'');
}
function prepareSubmission(a,q){
 if(!a||a.settled||!a.qids.includes(q.id))throw Error('题目不属于当前挑战。');
 const prior=a.structured_submissions?.[q.id];if(prior&&!prior.graded)return prior;
 if(a.answers[q.id]&&!a.correction_edit?.[q.id])throw Error('首次成绩已保存，点击重新核对可继续练习。');
 const d=draft(a,q);
 if(q.subquestions.some(s=>!(d.process[s.id]||'').trim()))throw Error('请填写每个小问的计算过程或理由。');
 if((q.numeric_checks||[]).some(c=>!(d.values[c.key]||'').trim()))throw Error('请填写所有可核对的关键数值。');
 const checks=(q.numeric_checks||[]).map(c=>checkNumber(c,d.values[c.key],d.units[c.key]||c.unit));
 const submission={draft:clone(d),checks,process:{},submitted_at:time(),graded:false,correction:!!a.answers[q.id]};
 if(!a.structured_submissions)a.structured_submissions={};a.structured_submissions[q.id]=submission;
 if(!a.references.includes(q.id))a.references.push(q.id);
 return submission;
}
function setProcess(a,q,id,correct){
 const submission=a.structured_submissions?.[q.id];if(!submission||submission.graded)throw Error('请先提交小问答案。');
 if(!q.subquestions.some(s=>s.id===id))throw Error('小问不存在。');
 submission.process[id]=!!correct;
}
function grade(a,q){
 const submission=a.structured_submissions?.[q.id];if(!submission)throw Error('请先提交各小问。');
 if(submission.graded)return {first:false,record:submission.record};
 if(q.subquestions.some(s=>typeof submission.process[s.id]!=='boolean'))throw Error('请对照参考逐个完成过程自评。');
 const correct=submission.checks.every(c=>c.correct)&&q.subquestions.every(s=>submission.process[s.id]===true);
 const user_answer=q.subquestions.map(s=>'（'+s.id+'）'+submission.draft.process[s.id]).join('\n')+'\n'+(q.numeric_checks||[]).map(c=>c.label+'：'+submission.draft.values[c.key]+' '+(submission.draft.units[c.key]||c.unit||'')).join('\n');
 const record={correct,user_answer,ts:time(),numeric_results:clone(submission.checks),process:clone(submission.process)};
 const first=!a.answers[q.id];
 if(first)a.answers[q.id]=record;
 else {if(!a.corrections)a.corrections={};if(!a.corrections[q.id])a.corrections[q.id]=[];a.corrections[q.id].push(record);}
 submission.graded=true;submission.record=record;if(a.correction_edit)delete a.correction_edit[q.id];
 return {first,record};
}
function beginCorrection(a,q){
 if(!a.answers[q.id]||a.settled)throw Error('本轮结束前可以重新核对，结束后请开启新的练习。');
 if(!a.correction_edit)a.correction_edit={};a.correction_edit[q.id]=true;
 if(a.structured_submissions)delete a.structured_submissions[q.id];
}
const chapters=g=>g.campaign.worlds.find(w=>w.id==='finance')?.chapters||[];
const cleared=(g,c)=>c.stages.length>0&&c.stages.every(id=>g.results[id]?.cleared);
function awardChapters(g){
 const s=state(g),awards=[];
 for(const c of chapters(g))if(c.number>=1&&c.number<=20&&cleared(g,c)&&!s.chapter_claims[String(c.number)]){s.chapter_claims[String(c.number)]=true;s.materials+=3;awards.push({chapter:c.number,materials:3});}
 return awards;
}
function actComplete(g,a){const cs=chapters(g);return a.chapters.every(n=>{const c=cs.find(x=>x.number===n);return !!c&&cleared(g,c);});}
function actOpen(g,a){const cs=chapters(g),first=cs.find(c=>c.number===a.chapters[0]);return !!first&&Array.from({length:a.chapters[0]-1},(_,i)=>i+1).every(n=>{const c=cs.find(x=>x.number===n);return !!c&&cleared(g,c);});}
function companionOpen(g,c){const chapter=chapters(g).find(x=>x.number===c.unlock_chapter);return !!chapter&&cleared(g,chapter);}
function view(g){
 const s=state(g);
 const acts=(CONFIG.acts||[]).map(a=>{const npc=CONFIG.npcs.find(n=>n.id===(a.npc_id||a.npc));return {...a,npc_name:npc?.name||'',npc_asset:npc?.asset||'',open:actOpen(g,a),completed:actComplete(g,a),seen:s.story_seen.includes(a.id)};});
 const buildings=(CONFIG.buildings||[]).map(b=>{const level=s.buildings[b.id]||0,cost=[1,3,6][level];return {...b,level,cost:cost??0,canBuild:level<3&&s.materials>=cost};});
 const companions=(CONFIG.companions||[]).map(c=>({...c,owned:g.inventory.includes(c.id),equipped:s.companion===c.id,unlocked:companionOpen(g,c),canBuy:companionOpen(g,c)&&!g.inventory.includes(c.id)&&g.coins>=c.price}));
 const commissions=(CONFIG.commissions||[]).map(c=>({...c,open:acts.find(a=>a.id===c.act_id)?.open||false,claimed:!!s.commission_claims[c.id]?.claimed,ready:!!s.commission_claims[c.id]?.completed&&!s.commission_claims[c.id]?.claimed}));
 return {state:s,acts,buildings,companions,commissions,props:CONFIG.props||[],npcs:CONFIG.npcs||[]};
}
function build(p,id){const b=(CONFIG.buildings||[]).find(x=>x.id===id);if(!b)throw Error('建筑不存在。');const s=state(p.game),level=s.buildings[id]||0;if(level>=3)throw Error('建筑已达到三级。');const cost=[1,3,6][level];if(s.materials<cost)throw Error('建材不足，每章首次完成获得3份。');s.materials-=cost;s.buildings[id]=level+1;return {id,level:level+1,cost};}
function seeStory(p,id){const a=(CONFIG.acts||[]).find(x=>x.id===id);if(!a||!actOpen(p.game,a))throw Error('完成前面的章节后开放剧情。');const s=state(p.game);if(!s.story_seen.includes(id))s.story_seen.push(id);return a;}
function recruit(p,id){const g=p.game,c=(CONFIG.companions||[]).find(x=>x.id===id);if(!c)throw Error('伙伴不存在。');if(g.inventory.includes(id))return c;if(!companionOpen(g,c))throw Error('完成财管第'+c.unlock_chapter+'章后可以招募这位伙伴。');if(g.coins<c.price)throw Error('金币不足。');g.coins-=c.price;g.inventory.push(id);return c;}
function companion(p,id){if(id&&!p.game.inventory.includes(id))throw Error('请先招募伙伴。');if(id&&!(CONFIG.companions||[]).some(x=>x.id===id))throw Error('伙伴不存在。');state(p.game).companion=state(p.game).companion===id?null:id;return state(p.game).companion;}
function commissionQuestions(meta,id){
 const c=(CONFIG.commissions||[]).find(x=>x.id===id);if(!c)throw Error('经营委托不存在。');
 const a=(CONFIG.acts||[]).find(x=>x.id===c.act_id),subjective=c.kind==='subjective'||c.type==='subjective';
 const pool=meta.filter(q=>(q.world_id==='finance'||q.book_id.startsWith('cpa_cg_')||q.book_id.startsWith('cg_'))&&a.chapters.includes(q.chapter_no)&&structuredType(q)===subjective);
 const wanted=subjective?1:3,offset=(c.sequence||0)%Math.max(1,pool.length);const selected=pool.slice(offset).concat(pool.slice(0,offset)).slice(0,wanted).map(q=>q.id);
 if(selected.length!==wanted)throw Error('该委托题目仍待题库准备。');return selected;
}
const structuredType=q=>['计算分析题','综合题','简答题','论述题','案例分析题','计算或情境案例'].includes(q.type);
function finishPractice(p,attempt,passPercent=70){
 if(!attempt.qids?.length||!attempt.qids.every(id=>attempt.answers[id]))throw Error('请完成全部委托或复习题目。');
 const s=state(p.game);if(attempt.finance_finished)return;attempt.finance_finished=true;
 const correct=attempt.qids.filter(id=>attempt.answers[id]?.correct).length,passed=correct*100>=attempt.qids.length*passPercent;
 if(attempt.commission_id&&passed&&!s.commission_claims[attempt.commission_id]?.claimed)s.commission_claims[attempt.commission_id]={completed:true,claimed:false,attempt_id:attempt.id};
 if(attempt.rescue){s.diary.push({kind:'rescue',id:attempt.id,world:attempt.rescue,correct,total:attempt.qids.length,companion:s.companion,ts:time()});}
}
function claimCommission(p,id,attempt){const c=(CONFIG.commissions||[]).find(x=>x.id===id),s=state(p.game);if(!c||!actOpen(p.game,CONFIG.acts.find(a=>a.id===c.act_id)))throw Error('经营委托尚未开放。');if(attempt&&attempt.commission_id===id&&attempt.settled)finishPractice(p,attempt);const status=s.commission_claims[id];if(!status?.completed)throw Error('先完成该委托的题目。');if(status.claimed)return {id,already_claimed:true};status.claimed=true;const card=c.postcard||c.postcard_id||'postcard_'+id;if(!p.game.inventory.includes(card))p.game.inventory.push(card);return {id,postcard:card};}
function rescueQuestions(p,meta,world){const w=p.game.campaign.worlds.find(x=>x.id===(world||p.game.world));return w?meta.filter(q=>q.book_id.startsWith(w.prefix)&&p.wrong_book.includes(q.id)).slice(0,5).map(q=>q.id):[];}
function formulas(g){const collection=Array.isArray(KNOWLEDGE)?KNOWLEDGE:KNOWLEDGE.chapters||[],cs=chapters(g),s=state(g);return collection.map(c=>{const number=Number(c.chapter_no||c.number||c.chapter),chapter=cs.find(x=>x.number===number);return {...c,chapter_no:number,seen:s.formula_seen.includes('chapter:'+number),open:!!chapter&&Array.from({length:number-1},(_,i)=>i+1).every(n=>{const prior=cs.find(x=>x.number===n);return !!prior&&cleared(g,prior);})};});}
function seeFormulas(p,number){const chapter=formulas(p.game).find(c=>c.chapter_no===Number(number));if(!chapter?.open)throw Error('完成前面的财管章节后开放本章公式。');const seen=state(p.game).formula_seen,key='chapter:'+chapter.chapter_no;if(!seen.includes(key))seen.push(key);return chapter;}
function storyFor(g,id){const a=(CONFIG.acts||[]).find(x=>x.id===id);if(!a||!actOpen(g,a))throw Error('完成前面的章节后开放剧情。');return {act:a,story:a.story||[],completion_story:a.completion_story||[],completed:view(g).acts.find(x=>x.id===id).completed};}
function evaluateNumeric(checks,values){return checks.map(c=>{const v=values[c.key];return checkNumber(c,object(v)?v.value:v,object(v)?v.unit:c.unit);});}
function companionGuide(p,meta){
 const friend=CONFIG.companions.find(c=>c.id===state(p.game).companion);if(!friend)return null;
 const count=rescueQuestions(p,meta).length;
 const messages={spirit_deer:count?'当前科目还有'+count+'道错题需要照顾，我们一起复习吧。':'错题已清空，露露会继续记住你的学习足迹。',spirit_owl:'先认清公式的符号和适用条件，再代入数字。公式图鉴一直为你打开。',spirit_otter:'看看经营委托：把知识放进小镇的现金流、成本和预算里。',spirit_hedgehog:'一道错题只是下一次进步的线索。先整理思路，我陪你再试一次。'};
 return {...friend,message:messages[friend.id]||friend.story,utility:friend.id==='spirit_owl'?'formulas':friend.id==='spirit_otter'?'town':'review'};
}
module.exports={CONFIG,KNOWLEDGE,state,ensureExpansion:state,structured,checkNumber,numericCheck:checkNumber,evaluateNumeric,draft,saveDraft,prepareSubmission,setProcess,grade,beginCorrection,chapters,awardChapters,claimChapters:p=>awardChapters(p.game),view,build,upgradeBuilding:build,seeStory,storyFor,recruit,companion,equipCompanion:companion,companionGuide,commissionQuestions,finishPractice,claimCommission,rescueQuestions,formulas,seeFormulas};
