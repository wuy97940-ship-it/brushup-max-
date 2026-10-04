import {useCallback,useEffect,useRef,useState} from 'react';
import {KeyboardAvoidingView, Platform, Pressable, TextInput, View} from 'react-native';
import {router,useFocusEffect,useLocalSearchParams} from 'expo-router';
import {Actor} from '../components/Actor';
import {StructuredQuestion} from '../components/StructuredQuestion';
import {DeepAnalysis} from '../components/Analysis';
import {StudyText} from '../components/StudyText';
import {Bar,Button,Card,Row,Screen,Txt,usePalette} from '../components/ui';
import {answerCorrect,G,mercyClear,questions,Skills} from '../services/rules';
import {useAdventure} from '../state/AdventureProvider';

export default function Quiz(){
 const params=useLocalSearchParams<{practice?:string}>(),practice=params.practice==='1';
 const {p,run,act,report}=useAdventure(),c=usePalette();const g=p.game,a=practice?p.practice:g.active;
 const q=a?questions[a.qids[a.index]]:null,key=(a?.id||'')+':'+(q?.id||'');
 const [choice,setChoice]=useState<{key:string;values:string[]}>({key:'',values:[]}),[writing,setWriting]=useState({key:'',value:''}),[animation,setAnimation]=useState({key:'',pose:''});
 const selected=choice.key===key?choice.values:[],draft=writing.key===key?writing.value:a?.drafts[q?.id||'']||'',motion=animation.key===key?animation.pose:'';
 const setSelected=(values:string[])=>setChoice({key,values}),setDraft=(value:string)=>setWriting({key,value}),setMotion=(pose:string)=>setAnimation({key,pose});
 const timers=useRef<ReturnType<typeof setTimeout>[]>([]),draftQueue=useRef<Promise<unknown>>(Promise.resolve()),saveMessage=useRef(false);
 const clear=useCallback(()=>{timers.current.forEach(clearTimeout);timers.current=[];setAnimation({key:'',pose:''});},[]);
 useFocusEffect(useCallback(()=>()=>clear(),[clear]));
 useEffect(()=>{timers.current.forEach(clearTimeout);timers.current=[];draftQueue.current=Promise.resolve();saveMessage.current=false;},[key]);
 const victoryId=a?.result?.attempt_id||a?.id,won=!!a?.result?.passed,bossFirst=!!a?.result?.first_clear&&!practice&&a?.stage_id&&G.levelFor(g,a.stage_id)?.kind==='boss';
 useEffect(()=>{
   if(!won||p.reduce_motion)return;
   const later=(fn:()=>void,ms:number)=>{timers.current.push(setTimeout(fn,ms));};
   const pose=(value:string)=>setAnimation({key,pose:value});
   if(bossFirst){later(()=>pose('attack'),0);later(()=>pose('chest'),650);later(()=>pose('celebrate'),1500);}
   else later(()=>pose('celebrate'),0);
   later(()=>pose(''),2300);return ()=>{timers.current.forEach(clearTimeout);timers.current=[];};
 },[victoryId,won,bossFirst,key,p.reduce_motion]);
 if(!a||!q)return <Screen title="挑战已保存" header={false}><Card><Txt>当前没有进行中的挑战，去地图开启一段新冒险吧。</Txt><Button label="返回冒险" onPress={()=>router.replace('/')}/></Card></Screen>;
 const lvl=practice?{name:a.name,chapter_title:'自由刷题',kind:'practice'}:G.levelFor(g,a.stage_id),rec=a.answers[q.id];
 const structured=G.Finance.structured(q),subjective=G.subjective(q),multiple=q.type==='多选题'||q.type==='不定项题',reference=a.references.includes(q.id),r=a.result;
 const total=a.qids.length,answered=Object.keys(a.answers).length,correct=Object.values(a.answers).filter((v:any)=>v.correct).length;
 const eliminated:string[]=a.hints?.[q.id]||[],mercy=practice?{eligible:false}:Skills.mercyStatus(g,a,lvl);
 const options=q.type==='判断题'?{正确:'正确',错误:'错误'}:q.options;
 const attempt=(v:any)=>practice?v.practice:v.game.active;
 const saveDraft=(value:string)=>{
   setDraft(value);const attemptId=a.id,qid=q.id;
   draftQueue.current=draftQueue.current.catch(()=>{}).then(()=>run((v:any)=>{const target=attempt(v);if(target?.id===attemptId&&!target.settled&&!target.answers[qid])target.drafts[qid]=value;}));
   void draftQueue.current.catch((e:Error)=>{if(!saveMessage.current){saveMessage.current=true;report(e.message);}});
 };
 const leave=()=>{void act(async()=>{await draftQueue.current.catch(()=>{});if(subjective&&!structured&&!rec&&!a.settled)await run((v:any)=>{attempt(v).drafts[q.id]=draft;});router.replace('/');});};
 const submit=(selfCorrect?:boolean)=>{void act(async()=>{
   const answer=subjective?draft:selected.slice().sort().join(''),ok=subjective?!!selfCorrect:answerCorrect(q,answer);
   await draftQueue.current.catch(()=>{});
   await run((v:any)=>{if(subjective)attempt(v).drafts[q.id]=draft;return G.submit(v,q,answer,ok,practice);});
   clear();if(!p.reduce_motion){setMotion(ok?'attack':'hurt');timers.current.push(setTimeout(()=>setMotion(''),650));}
 });};
 const finish=()=>{void act(async()=>{await run((v:any)=>{
   if(!practice)return G.settle(v);
   return G.finishPractice(v);
 });});};
 const next=()=>{if(!rec){report('请先提交本题答案。');return;}if(a.index===total-1){finish();return;}void act(async()=>{clear();await run((v:any)=>{attempt(v).index++;});});};
 const retry=()=>{void act(async()=>{clear();await run((v:any)=>practice?G.restartPractice(v):G.start(v,a.stage_id,true));});};
 const nextStage=()=>{void act(async()=>{clear();await run((v:any)=>{const sid=a.stage_id.startsWith('expedition:')?G.expedition(v).id:G.nextStage(v.game,a.stage_id);if(!sid)throw Error('本科主线已全部通关！返回地图继续另一科，或三科通关后开启远征。');return G.start(v,sid);});});};
 const pose=motion||(a.settled?r?.passed?'celebrate':'hurt':rec?rec.correct?'happy':'hurt':'think');
 return <KeyboardAvoidingView style={{flex:1}} behavior={Platform.OS==='ios'?'padding':undefined}>
 <Screen title={lvl.name} sub={q.chapter} header={false} scrollKey={key+(a.settled?':result':'')}>
  <Button label="返回冒险 · 保留本轮" secondary onPress={leave}/>
  <Card style={{backgroundColor:c.soft}}><Row><Actor size={115} pose={pose}/><View style={{flex:1,gap:8}}><Txt kind="h2">{lvl.kind==='boss'?'♜ 守关Boss':practice?'学习时光':'一路向前'}</Txt><Txt>作答 {answered} / {total} · 答对 {correct}</Txt><Bar value={answered/total*100}/>{lvl.kind==='boss'&&<><Txt kind="small">Boss能量 {r?.passed?0:Math.round((1-correct/total)*100)}%</Txt><Bar color={c.bad} value={r?.passed?0:(1-correct/total)*100}/></>}
    {!practice&&<Txt kind="small">真实正确率决定星级 · 70%通关</Txt>}
    {a.skills_used?.length>0&&<Txt kind="small">本轮魔法：{a.skills_used.map((id:string)=>Skills.DEFINITIONS[id].name).join('、')}</Txt>}
  </View></Row></Card>
  {a.settled&&r?<>
   <Card><Txt kind="title">{practice?r.quality||'复习完成':r.assisted?'瞒天过海，继续冒险！':r.stars>=2?'高质量'+(lvl.kind==='boss'?'击败 Boss':'通关'):r.passed?lvl.kind==='boss'?'Boss 击败！':'下一关点亮！':'再试一次，喵'}</Txt>
    {!practice&&<Txt style={{fontSize:28,color:c.accent}}>{'★'.repeat(r.stars)+'☆'.repeat(3-r.stars)}</Txt>}
    <Txt>真实正确 {r.correct} / {r.total} · {Math.floor(r.correct*100/r.total)}%</Txt>
    {!practice&&<><Txt>经验 +{r.xp} · 金币 +{r.coins}</Txt>{r.assisted&&<Txt kind="small">技能辅助解锁，真实成绩保持 {Math.floor(r.correct*100/r.total)}%，不属于高质量通关。</Txt>}
      {r.first_clear&&lvl.kind==='boss'&&<Txt style={{color:c.accent}}>{motion==='attack'?'Boss被击败…':motion==='chest'?'宝箱开启中…':'宝箱：'+(r.loot?.name||'基础奖励')+(r.loot?.duplicate?' · 重复兑换'+r.loot.coins+'金币':'')}</Txt>}
      {r.growth?.map((i:any,index:number)=><Txt key={index} kind="small">惊喜 · {i.name}{i.duplicate?' · 重复兑换'+i.coins+'金币':''}</Txt>)}
      {r.finance_rewards?.map((reward:any)=><Txt key={reward.chapter}>完成财管第{reward.chapter}章 · 建材 +{reward.materials}</Txt>)}
      {r.new_skills?.length>0&&<Txt>新学会：{r.new_skills.map((id:string)=>Skills.DEFINITIONS[id].name).join('、')}</Txt>}
    </>}
    {mercy.eligible&&<Button label={'使用瞒天过海 · 剩余'+mercy.available+'次'} disabled={!mercy.available} onPress={()=>{void act(async()=>{await run((v:any)=>mercyClear(v));});}}/>}
    {!practice&&r.passed&&<Button label="进入下一关 →" onPress={nextStage}/>}
    <Button label={practice?'再复习一轮':'重新挑战全部题目'} secondary onPress={retry}/><Button label="返回地图" secondary onPress={()=>router.replace('/map')}/>
   </Card>
   <Card><Txt kind="h2">本轮复盘</Txt>{a.qids.map((id:string,index:number)=><View key={id} style={{paddingVertical:10,borderBottomWidth:1,borderBottomColor:c.line}}><Txt kind="label" style={{color:a.answers[id].correct?c.good:c.bad}}>{index+1}. {a.answers[id].correct?'掌握了':'需要再练'} · {questions[id].type}</Txt><StudyText text={questions[id].stem} small/><StudyText text={questions[id].explanation} small/></View>)}</Card>
  </>:<>
    <Card><Row style={{justifyContent:'space-between'}}><Txt kind="small">第 {a.index+1} / {total} 题 · {q.type}</Txt><Button label={p.favorites.includes(q.id)?'已收藏':'收藏本题'} secondary onPress={()=>{void act(async()=>{await run((v:any)=>{v.favorites=v.favorites.includes(q.id)?v.favorites.filter((id:string)=>id!==q.id):[...v.favorites,q.id];});});}}/></Row><StudyText text={q.stem} testID="question-stem"/>
    {structured?<StructuredQuestion key={key} q={q} a={a} practice={practice}/>:subjective?<>
      <TextInput testID="subjective-draft" accessibilityLabel="填写我的答案" placeholder="写下你的计算、结论和理由…" placeholderTextColor={c.muted} multiline value={draft} editable={!rec} onChangeText={saveDraft} style={{minHeight:140,textAlignVertical:'top',backgroundColor:c.soft,color:c.text,padding:16,borderRadius:14,fontSize:16,lineHeight:26}}/>
      {!reference&&<Button label="查看参考答案 · 保存我的作答" disabled={!draft.trim()} onPress={()=>{void act(async()=>{await draftQueue.current.catch(()=>{});await run((v:any)=>{const target=attempt(v);target.drafts[q.id]=draft;if(!draft.trim())throw Error('请先写下自己的答案');if(!target.references.includes(q.id))target.references.push(q.id);});});}}/>}
      {reference&&<Card style={{backgroundColor:c.soft}}><Txt kind="h2">参考答案</Txt><StudyText text={q.answer}/><Txt kind="small">请逐项核对核心结论与关键理由；仅看完答案不代表已经掌握。</Txt>
        {a.outlines?.[q.id]?a.outlines[q.id].map((line:string,index:number)=><Txt key={index}>{index+1}. {line}</Txt>):<Button label={'妙笔生花 · 整理答题卡（'+Skills.available(g,'outline')+'次）'} secondary disabled={!Skills.available(g,'outline')} onPress={()=>{void act(async()=>{await run((v:any)=>Skills.outline(v,q,practice));});}}/>}
      </Card>}
      {reference&&!rec&&<Row><Button label="对照自评 · 掌握了" onPress={()=>submit(true)}/><Button label="对照自评 · 还没掌握" secondary onPress={()=>submit(false)}/></Row>}
    </>:<>
      {multiple&&<Txt kind="small">多选题，全部选对才记为正确。</Txt>}
      {Object.entries(options).map(([key,text])=>{const removed=eliminated.includes(key),right=rec&&(q.type==='判断题'?q.answer===key:q.answer.includes(key)),chosen=selected.includes(key);return <Pressable key={key} testID={'option-'+key} accessibilityRole="button" accessibilityLabel={key+' '+text} accessibilityState={{selected:chosen,disabled:!!rec||removed}} disabled={!!rec||removed} onPress={()=>setSelected(multiple?chosen?selected.filter(v=>v!==key):[...selected,key]:[key])} style={{minHeight:52,borderRadius:14,padding:15,gap:4,borderWidth:2,borderColor:right?c.good:chosen?c.blue:c.line,backgroundColor:chosen?c.soft:c.card,opacity:removed?0.4:1}}><Txt>{key}. {text}{removed?'（已排除）':''}</Txt></Pressable>;})}
      {!rec&&<><Button label="提交答案" disabled={!selected.length} onPress={()=>submit()}/>{Object.keys(q.options).length>=3&&!a.hint_used&&<Button label={'灵光一现 · 排除一个错项（'+Skills.available(g,'insight')+'次）'} secondary disabled={!Skills.available(g,'insight')} onPress={()=>{void act(async()=>{const removed=await run<string[]>((v:any)=>Skills.hint(v,q,practice));setSelected(selected.filter(k=>!removed.includes(k)));});}}/>}</>}
    </>}
    {(rec||a.structured_submissions?.[q.id])&&<DeepAnalysis analysis={q.analysis}/> }
    {rec&&<Card style={{backgroundColor:c.soft}}><Txt kind="h2" style={{color:rec.correct?c.good:c.bad}}>{rec.correct?'答对了，漂亮一击！':'先记下来，复盘后再战。'}</Txt>{!subjective&&<Txt kind="label">正确答案：{q.answer}</Txt>}<StudyText text={q.explanation}/><Txt kind="small">本轮只计第一次提交。错题继续保存在学习小屋。</Txt></Card>}
    <Button label={a.index===total-1?'完成本轮 · 查看结算':'下一题 →'} disabled={!rec} onPress={next}/>
    </Card>
  </>}
 </Screen></KeyboardAvoidingView>;
}
