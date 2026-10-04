import { View } from 'react-native';
import { router } from 'expo-router';
import { Actor } from '../../components/Actor';
import { Button, Card, Columns, Row, Screen, Txt, usePalette } from '../../components/ui';
import { G } from '../../services/rules';
import { useAdventure } from '../../state/AdventureProvider';
export default function Map(){const {p,run,act}=useAdventure(),c=usePalette();const g=p.game,w=g.campaign.worlds.find((v:any)=>v.id===g.world)||g.campaign.worlds[0];
 const start=(sid:string)=>{void act(async()=>{await run((v:any)=>G.start(v,sid));router.push('/quiz');});};
 return <Screen title="冒险地图" sub="击败守关Boss，下一章就会点亮。">
   <Row>{g.campaign.worlds.map((v:any)=><Button key={v.id} label={v.name} secondary={w.id!==v.id} onPress={()=>{void act(async()=>{await run((p:any)=>{p.game.world=v.id;});});}}/>)}</Row>
   <Card style={{backgroundColor:c.soft}}><Row><Actor size={100} pose="walk"/><View style={{flex:1}}><Txt kind="h2">{w.name}</Txt><Txt kind="small">森林 → 海岛 → 雪山 → 遗迹 → 天空 → 星空</Txt><Txt kind="small">每章一条知识小径，一场案例Boss。</Txt></View></Row></Card>
   <Columns>{w.chapters.map((ch:any)=>{const b=G.C.biomes.find((b:any)=>b.id===ch.biome);return <Card key={ch.id} style={{borderWidth:1,borderColor:c.line}}><Txt kind="small" style={{color:b.color}}>{b.name}</Txt><Txt kind="h2">第{ch.number}章 · {ch.title}</Txt>{ch.stages.map((id:string)=>{const lvl=G.levelFor(g,id),r=g.results[id],open=G.canPlay(g,id);return <View key={id} style={{backgroundColor:c.soft,padding:14,borderRadius:16,gap:6}}><Row style={{justifyContent:'space-between'}}><Txt kind="label">{lvl.kind==='boss'?'♜ 守关 Boss':'● 知识小径'}</Txt><Txt style={{color:c.accent}}>{r?'★'.repeat(r.best_stars)+'☆'.repeat(3-r.best_stars):open?'待挑战':'待解锁'}</Txt></Row><Txt kind="small">{lvl.qids.length} 题 · {lvl.subjective?'原创案例自评':'客观题'}{r?.assisted?' · 曾使用瞒天过海':''}</Txt><Button label={!open?'先通过前一关':r?'重温这一关':'进入挑战'} disabled={!open} testID={'stage-'+id.replace(/:/g,'-')} secondary={!!r} onPress={()=>start(id)}/></View>;})}</Card>;})}</Columns>
 </Screen>;
}
