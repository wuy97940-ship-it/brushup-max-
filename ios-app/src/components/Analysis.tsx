import {Card,Txt} from './ui';
import {Analysis as AnalysisData} from '../services/rules';
export function DeepAnalysis({analysis}:{analysis?:AnalysisData}){
 if(!analysis)return null;
 return <Card><Txt kind="h2">深入理解</Txt>{analysis.position&&<Txt kind="label">考点 · {analysis.position}</Txt>}{analysis.principle&&<Txt selectable>{analysis.principle}</Txt>}
  {analysis.formulas?.length>0&&<Txt kind="label">公式与适用条件</Txt>}{analysis.formulas?.map((line,index)=><Txt key={'formula'+index} selectable>{line}</Txt>)}
  {analysis.steps?.length>0&&<Txt kind="label">逐步推导</Txt>}{analysis.steps?.map((line,index)=><Txt key={'step'+index} selectable>{index+1}. {line}</Txt>)}
  {Object.entries(analysis.option_analysis||{}).map(([key,text])=><Txt key={key} selectable>{key}. {text}</Txt>)}
  {analysis.units&&<Txt kind="small">单位与精度 · {analysis.units}</Txt>}
  {analysis.pitfalls?.length>0&&<Txt kind="label">容易错在哪里</Txt>}{analysis.pitfalls?.map((line,index)=><Txt key={'pitfall'+index} selectable>• {line}</Txt>)}
  {analysis.memory&&<Txt kind="label">记忆提示 · {analysis.memory}</Txt>}
 </Card>;
}
