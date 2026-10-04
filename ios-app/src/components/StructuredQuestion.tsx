import {useRef,useState} from 'react';
import {TextInput,View} from 'react-native';
import {Button,Card,Row,Txt,usePalette} from './ui';
import {Finance,G,Question} from '../services/rules';
import {useAdventure} from '../state/AdventureProvider';
import {StudyText} from './StudyText';

export function StructuredQuestion({q,a,practice}:{q:Question;a:any;practice:boolean}){
 const {run,act,report}=useAdventure(),c=usePalette(),queue=useRef<Promise<unknown>>(Promise.resolve());
 const [local,setLocal]=useState<Record<string,string>>({});
 const d=a.structured_drafts?.[q.id]||{process:{},values:{},units:{}},submission=a.structured_submissions?.[q.id],rec=a.answers[q.id];
 const editable=(!rec||a.correction_edit?.[q.id])&&!submission;
 const target=(v:any)=>practice?v.practice:v.game.active;
 const value=(kind:string,key:string)=>local[kind+':'+key]??d[kind][key]??'';
 function write(kind:string,key:string,text:string){
  setLocal(old=>({...old,[kind+':'+key]:text}));const attemptId=a.id;
  queue.current=queue.current.catch(()=>{}).then(()=>run((v:any)=>{const current=target(v);if(current?.id===attemptId)Finance.saveDraft(current,q,kind,key,text);}));
  void queue.current.catch((e:Error)=>report(e.message));
 }
 const change=(fn:(v:any)=>unknown)=>{void act(async()=>{await queue.current;await run(fn);});};
 const inputStyle={minHeight:120,textAlignVertical:'top' as const,backgroundColor:c.soft,color:c.text,padding:14,borderRadius:12,fontSize:16,lineHeight:26};
 return <View style={{gap:16}}>
  <Txt kind="small">按小问保存过程和关键数值。提交后展示参考，完成过程自评后才保存成绩；纠正练习独立记录。</Txt>
  {q.subquestions?.map(part=><Card key={part.id}>
   <Txt kind="h2">（{part.id}）{part.prompt}</Txt>
   <TextInput testID={'process-'+part.id} accessibilityLabel={'第'+part.id+'小问计算过程'} placeholder="写下公式、代入、单位与结论…" placeholderTextColor={c.muted} multiline value={value('process',part.id)} editable={editable} onChangeText={text=>write('process',part.id,text)} style={inputStyle}/>
   {(q.numeric_checks||[]).filter(check=>part.checks?.includes(check.key)).map(check=>{
    const choices=['元','万元'].includes(check.unit)?['元','万元']:['%','小数'].includes(check.unit)?['%','小数']:[check.unit||'无单位'];
    const unit=value('units',check.key)||check.unit,result=submission?.checks?.find((r:any)=>r.key===check.key);
    return <View key={check.key} style={{gap:8}}><Txt kind="label">{check.label}</Txt><TextInput testID={'numeric-'+check.key} accessibilityLabel={check.label+'数值'} placeholder="填写关键数值" placeholderTextColor={c.muted} value={value('values',check.key)} editable={editable} onChangeText={text=>write('values',check.key,text)} style={{...inputStyle,minHeight:48}}/>
      <Row>{choices.map(choice=><Button key={choice} label={choice} secondary={unit!==choice} disabled={!editable} onPress={()=>write('units',check.key,choice)}/>)}</Row>
      {submission&&result&&<Txt testID={'check-'+check.key} style={{color:result.correct?c.good:c.bad}}>{result.correct?'✓ 数值通过':'需要再核对'} · 参考 {result.expected} {result.unit} · {result.message}</Txt>}
    </View>;
   })}
   {(submission||rec)&&<><Txt kind="label">本小问参考</Txt><StudyText text={part.reference}/>{part.process_checklist?.map((line,index)=><Txt key={index} kind="small">• {line}</Txt>)}</>}
   {submission&&!submission.graded&&<><Txt kind="small">对照公式、计算过程与结论自评</Txt><Row><Button label="过程正确" secondary={submission.process[part.id]!==true} onPress={()=>change(v=>Finance.setProcess(target(v),q,part.id,true))}/><Button label="还需复习" secondary={submission.process[part.id]!==false} onPress={()=>change(v=>Finance.setProcess(target(v),q,part.id,false))}/></Row></>}
  </Card>)}
  {editable&&<Button label="提交各小问 · 核对数值" testID="submit-structured" onPress={()=>change(v=>Finance.prepareSubmission(target(v),q))}/>}
  {submission&&!submission.graded&&<Button label="完成过程自评 · 保存结果" testID="grade-structured" onPress={()=>change(v=>G.gradeStructured(v,q,practice))}/>}
  {(submission||rec)&&<Card><Txt kind="h2">完整参考答案</Txt><StudyText text={q.answer}/></Card>}
  {rec&&submission?.graded&&<Button label="重新核对 · 保留首次成绩" secondary onPress={()=>{setLocal({});change(v=>Finance.beginCorrection(target(v),q));}}/>}
  {!!a.corrections?.[q.id]?.length&&<Txt kind="small">已完成 {a.corrections[q.id].length} 次纠正练习，首次成绩保持不变。</Txt>}
 </View>;
}
