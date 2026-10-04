import { View } from 'react-native';
import { router } from 'expo-router';
import { Actor } from '../../components/Actor';
import { Bar, Button, Card, Columns, Row, Screen, Txt, usePalette } from '../../components/ui';
import { Finance, G, Shop } from '../../services/rules';
import { useAdventure } from '../../state/AdventureProvider';
import { WebInstall } from '../../components/WebInstall';
export default function Home(){const {p,run,act}=useAdventure(),c=usePalette();const g=p.game,shop=Shop.view(g);const all=G.stats(g),friend=Finance.companionGuide(p,G.META);
  const start=()=>{void act(async()=>{await run((v:any)=>{const id=G.nextStage(v.game,null);G.start(v,id);});router.push('/quiz');});};
  return <Screen title="小圆冒险世界" sub="每做一道题，就向前一步。">
    <WebInstall/>
    <Card style={{backgroundColor:c.soft}}><Row><Actor size={155} pose="happy"/><View style={{flex:1,minWidth:140,gap:8}}><Txt kind="small" style={{color:c.blue}}>新的冒险，喵！</Txt><Txt kind="h2">知识会变成你的魔法</Txt><Txt>70% 解锁下一关，90% 高质量通关。</Txt><Txt kind="small">换上新装备，带着小圆、小团和小宝穿过六种地图。</Txt></View></Row></Card>
    <Columns>{g.campaign.worlds.map((w:any)=>{const s=G.stats(g,w.id);return <Card key={w.id} style={{borderWidth:g.world===w.id?2:0,borderColor:c.blue}}><Txt kind="h2">{w.id==='accounting'?'▣':w.id==='finance'?'▤':'⚖'} {w.name}</Txt><Txt>{s.cleared} / {s.total} 关 · {s.stars} 星</Txt><Bar value={s.cleared/s.total*100}/><Button label={'探索'+w.name} secondary={g.world!==w.id} onPress={()=>{void act(async()=>{await run((v:any)=>{v.game.world=w.id;});router.push('/map');});}}/></Card>;})}</Columns>
    <Row><Button label="星光经营小镇" secondary onPress={()=>router.push('/town')}/><Button label="公式图鉴" secondary onPress={()=>router.push('/formulas')}/></Row>
    {friend&&<Card><Txt kind="h2">{friend.name} · {friend.role}</Txt><Txt>{friend.message}</Txt><Button label={friend.utility==='formulas'?'一起打开公式图鉴':friend.utility==='town'?'看看经营委托':'打开复习清单'} secondary onPress={()=>router.push(friend.utility==='formulas'?'/formulas':friend.utility==='town'?'/town':'/practice')}/></Card>}
    <Button label={'继续'+g.campaign.worlds.find((w:any)=>w.id===g.world)?.name+'冒险 →'} onPress={start}/>
    {g.active&&!g.active.settled&&<Button label="恢复未完成挑战" secondary onPress={()=>router.push('/quiz')}/>}
    <Card><Row style={{justifyContent:'space-between'}}><Txt kind="h2">我的下一份期待</Txt><Txt kind="small">{all.cleared} 次主线首通</Txt></Row>{shop.goal&&<><Txt kind="label">{shop.goal.name} · {shop.goal.price} 金币</Txt><Bar value={shop.goal.progress}/><Txt kind="small">{shop.goal.unlockText||'已经上架'} · 还差 {shop.goal.remaining} 金币</Txt></>}<Button label="去旅行小铺试穿" secondary onPress={()=>router.push('/bag')}/></Card>
    <Card><Txt kind="h2">无尽远征</Txt><Txt kind="small">三科主线全部通过后，每轮10题，优先练最多6道当前错题。</Txt><Button label={G.expeditionAvailable(g)?'开始第'+g.expedition_round+'轮远征':'主线全部通关后开启'} disabled={!G.expeditionAvailable(g)} onPress={()=>{void act(async()=>{await run((v:any)=>G.start(v,G.expedition(v).id));router.push('/quiz');});}}/></Card>
    <Txt kind="small">原创题库 · {G.META.length}题 · 本地保存。不限时，无体力限制，失败可立即重试。</Txt>
  </Screen>;
}
