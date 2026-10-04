const G=require('./game');
const F=G.Finance;
const Skills=require('./skills');
const art=require('../data/shop_art');
const {routes}=require('../data/questions');
module.exports=function createQuiz(bank){return {
 data:{practice:false,selected:[],draft:'',pose:'think',animation:'',reveal:true},
 onLoad(options){this.setData({practice:options.practice==='1'});this.timers=[];},
 onShow(){this.setData({reveal:true,animation:''});this.refresh();},
 onHide(){this.cancelTimers();},onUnload(){this.cancelTimers();},
 cancelTimers(){(this.timers||[]).forEach(clearTimeout);this.timers=[];},
 later(fn,ms){this.timers.push(setTimeout(fn,ms));},
 attempt(){const p=getApp().store.progress;return this.data.practice?p.practice:p.game.active;},
 refresh(){
  const store=getApp().store,p=store.progress,g=p.game,a=this.attempt();if(!a){getApp().returnHome();return;}
  const level=this.data.practice?{name:a.name,chapter_title:'自由刷题',kind:'practice',biome:'forest'}:G.levelFor(g,a.stage_id);
  const q=bank[a.qids[Math.min(a.index,a.qids.length-1)]];
  if(!q){getApp().challenge(this.data.practice,true);return;}
  const rec=a.answers[q.id],isSubjective=G.subjective(q),reference=a.references.includes(q.id);
  const isStructured=F.structured(q),structuredDraft=a.structured_drafts?.[q.id]||{process:{},values:{},units:{}},submission=a.structured_submissions?.[q.id]||null;
  const structuredEditable=isStructured&&(!rec||a.correction_edit?.[q.id])&&!submission;
  const subquestions=(q.subquestions||[]).map(s=>({...s,process:structuredDraft.process[s.id]||'',self:submission?.process?.[s.id],hasSelf:typeof submission?.process?.[s.id]==='boolean',checks:(q.numeric_checks||[]).filter(c=>(s.checks||[]).includes(c.key)).map(c=>{const choices=['元','万元'].includes(c.unit)?['元','万元']:['%','小数'].includes(c.unit)?['%','小数']:[c.unit||'无单位'];const unit=structuredDraft.units[c.key]||c.unit||'无单位';return {...c,input:structuredDraft.values[c.key]||'',unitChoices:choices,unitIndex:Math.max(0,choices.indexOf(unit)),inputUnit:unit,result:submission?.checks.find(x=>x.key===c.key)||null};})}));
  const analysis=q.analysis||{},optionAnalysis=Object.entries(analysis.option_analysis||{}).map(([option,text])=>({option,text}));
  const eliminated=a.hints?.[q.id]||[];
  let options=Object.entries(q.options||{}).map(([key,text])=>({key,text,eliminated:eliminated.includes(key),selected:this.data.selected.includes(key),state:rec?(String(q.answer).includes(key)?'correct':String(rec.user_answer).includes(key)?'incorrect':''):''}));
  if(q.type==='判断题')options=[{key:'正确',text:'正确'},{key:'错误',text:'错误'}].map(o=>({...o,selected:this.data.selected.includes(o.key),state:rec?(o.key===q.answer?'correct':o.key===rec.user_answer?'incorrect':''):''}));
  const total=a.qids.length,answered=Object.keys(a.answers).length,correct=Object.values(a.answers).filter(r=>r.correct).length;
  const result=a.result?{...a.result,rate:Math.floor(a.result.correct*100/a.result.total),starText:'★'.repeat(a.result.stars)+'☆'.repeat(3-a.result.stars),lootText:a.result.loot?a.result.loot.name+(a.result.loot.duplicate?' · 重复兑换 '+a.result.loot.coins+' 金币':''):'',heading:a.result.assisted?'瞒天过海，继续冒险！':a.result.stars>=2?'高质量'+(level.kind==='boss'?'击败 Boss':'通关'):a.result.passed?level.kind==='boss'?'Boss 击败！':'通关，继续前进！':'再试一次，喵',growthRewards:(a.result.growth||[]).map(i=>({...i,icon:art.wonders[i.id]?.icon||'',label:i.kind==='ink'?'魔法墨水 +'+i.amount:i.duplicate?'重复兑换 '+i.coins+' 金币':'新奇物 · '+i.name})),learnedSkills:(a.result.new_skills||[]).map(id=>Skills.DEFINITIONS[id].name)}:null;
  const mercy=this.data.practice?{eligible:false}:Skills.mercyStatus(g,a,level);
  const hintCharges=Skills.available(g,'insight'),outlineCharges=Skills.available(g,'outline');
  this.setData({g,level,question:q,options,eliminated,mercy,hintCharges,outlineCharges,structured:isStructured,structuredEditable,subquestions,submission,analysis,optionAnalysis,correctionCount:a.corrections?.[q.id]?.length||0,canHint:!isSubjective&&!rec&&!a.hint_used&&options.length>=3,outlineCards:a.outlines?.[q.id]||[],canOutline:isSubjective&&reference&&!a.outlines?.[q.id],skillLevel:Skills.level(g),activeSkills:(a.skills_used||[]).map(id=>Skills.DEFINITIONS[id].name),subjective:isSubjective,multiple:q.type==='多选题'||q.type==='不定项题',rec:rec||null,reference,draft:a.drafts[q.id]||'',index:a.index,total,answered,correct,progress:answered*100/total,bossHP:a.settled&&a.result&&a.result.passed?0:Math.max(0,100-correct/total*100),theme:p.theme,saveError:store.pending,loadError:store.loadError,settled:!!a.settled,result,favorite:p.favorites.includes(q.id),atEnd:a.index>=total-1,canNext:!!rec,canReference:isSubjective&&!!(a.drafts[q.id]||'').trim(),pose:a.settled?a.result&&a.result.passed?'celebrate':'hurt':rec?rec.correct?'happy':'hurt':'think'});
 },
 commit(change,next){try{getApp().store.commit(change);this.refresh();if(next)next();}catch(e){wx.showModal({title:'暂未保存',content:e.message,showCancel:false});this.refresh();}},
 retrySave(){try{const r=getApp().store.retry();this.refresh();if(r&&r.attempt_id&&r.passed)this.victory();}catch(e){wx.showToast({title:e.message,icon:'none'});}},
 select(e){if(this.data.rec||this.data.settled)return;const key=e.currentTarget.dataset.key,old=this.data.selected;if(this.data.eliminated.includes(key))return;this.setData({selected:this.data.multiple?old.includes(key)?old.filter(k=>k!==key):old.concat(key):[key]});this.refresh();},
 useHint(){const q=this.data.question;this.commit(p=>Skills.hint(p,q,this.data.practice),()=>{this.setData({selected:this.data.selected.filter(k=>!this.data.eliminated.includes(k))});this.refresh();wx.showToast({title:'已排除一个错误选项',icon:'none'});});},
 useOutline(){this.commit(p=>Skills.outline(p,this.data.question,this.data.practice));},
 useMercy(){this.commit(p=>G.useMercy(p),()=>{wx.pageScrollTo({scrollTop:0,duration:0});this.victory();});},
 input(e){const value=e.detail.value,qid=this.data.question.id;this.commit(p=>{const a=this.data.practice?p.practice:p.game.active;if(!a.answers[qid])a.drafts[qid]=value;});},
 structuredInput(e){const {kind,key}=e.currentTarget.dataset;this.commit(p=>F.saveDraft(this.data.practice?p.practice:p.game.active,this.data.question,kind,key,e.detail.value));},
 structuredUnit(e){const {key,choices}=e.currentTarget.dataset;const value=choices[Number(e.detail.value)];this.commit(p=>F.saveDraft(this.data.practice?p.practice:p.game.active,this.data.question,'units',key,value));},
 submitStructured(){this.commit(p=>F.prepareSubmission(this.data.practice?p.practice:p.game.active,this.data.question));},
 processGrade(e){this.commit(p=>F.setProcess(this.data.practice?p.practice:p.game.active,this.data.question,e.currentTarget.dataset.id,e.currentTarget.dataset.correct==='yes'));},
 gradeStructured(){this.commit(p=>G.gradeStructured(p,this.data.question,this.data.practice));},
 correctStructured(){this.commit(p=>F.beginCorrection(this.data.practice?p.practice:p.game.active,this.data.question));},
 previewImage(e){const src=e.currentTarget.dataset.src,urls=[...(this.data.question.stem_images||[]),...((this.data.rec||this.data.submission||this.data.reference)?this.data.question.reference_images||[]:[])];wx.previewImage({current:src,urls});},
 showReference(){const qid=this.data.question.id;this.commit(p=>{const a=this.data.practice?p.practice:p.game.active;if(!(a.drafts[qid]||'').trim())throw Error('请先填写自己的答案。');if(!a.references.includes(qid))a.references.push(qid);});},
 submit(e){
  const q=this.data.question;if(this.data.rec||this.data.settled)return;
  let answer,correct;if(this.data.subjective){answer=this.data.draft;correct=e.currentTarget.dataset.correct==='yes';}else{answer=this.data.selected.slice().sort().join('');correct=answer===String(q.answer).replace(/[,，、\s]/g,'').split('').sort().join('');if(q.type==='判断题')correct=answer===q.answer;}
  this.commit(p=>G.submit(p,q,answer,correct,this.data.practice),()=>{this.setData({pose:correct?'attack':'hurt',animation:correct?'attack':'hurt'});if(wx.vibrateShort)wx.vibrateShort({type:correct?'light':'medium',fail:()=>{}});this.later(()=>this.setData({pose:correct?'happy':'hurt',animation:''}),650);});
 },
 favorite(){const id=this.data.question.id;this.commit(p=>{if(p.favorites.includes(id))p.favorites=p.favorites.filter(x=>x!==id);else p.favorites.push(id);});},
 next(){const a=this.attempt();if(!a.answers[this.data.question.id]){wx.showToast({title:'请先提交本题答案',icon:'none'});return;}if(a.index===a.qids.length-1){this.finish();return;}this.cancelTimers();this.setData({selected:[],animation:''});this.commit(p=>{const target=this.data.practice?p.practice:p.game.active;target.index++;},()=>wx.pageScrollTo({scrollTop:0,duration:150}));},
 finish(){if(this.data.practice){this.commit(p=>G.finishPractice(p),()=>wx.pageScrollTo({scrollTop:0,duration:0}));}else this.commit(p=>G.settle(p),()=>{wx.pageScrollTo({scrollTop:0,duration:0});if(this.data.result.passed)this.victory();});},
 victory(){this.cancelTimers();if(this.data.level.kind==='boss'&&this.data.result.first_clear){this.setData({animation:'defeated',pose:'attack',reveal:false});this.later(()=>this.setData({animation:'chest',pose:'chest'}),650);this.later(()=>this.setData({animation:'reveal',pose:'celebrate',reveal:true}),1500);}else{this.setData({animation:'reveal',pose:'celebrate',reveal:true});}this.later(()=>this.setData({animation:''}),2300);},
 retry(){this.cancelTimers();this.setData({selected:[],animation:'',reveal:true});if(this.data.practice){this.commit(p=>G.restartPractice(p),()=>wx.pageScrollTo({scrollTop:0,duration:0}));}else this.commit(p=>G.start(p,p.game.active.stage_id,true),()=>wx.pageScrollTo({scrollTop:0,duration:0}));},
 nextStage(){if(this.data.practice){this.home();return;}this.cancelTimers();this.setData({selected:[],animation:'',reveal:true});this.commit(p=>{const g=p.game,old=g.active.stage_id;let sid=G.nextStage(g,old);if(old.startsWith('expedition:'))sid=G.expedition(p).id;if(!sid)throw Error('本科全部通关啦！可以返回地图挑战另一科。');G.start(p,sid);},()=>wx.pageScrollTo({scrollTop:0,duration:0}));},
 home(){if(getApp().store.pending){wx.showToast({title:'请先重试保存',icon:'none'});return;}getApp().returnHome();}
};};
