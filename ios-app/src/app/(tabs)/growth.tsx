import {View} from 'react-native';
import {router} from 'expo-router';
import {Actor, ItemImage} from '../../components/Actor';
import {Bar, Button, Card, Columns, Row, Screen, Txt, usePalette} from '../../components/ui';
import {G, Shop, Skills} from '../../services/rules';
import {useAdventure} from '../../state/AdventureProvider';
export default function Growth(){const {p,run,act}=useAdventure(),c=usePalette(),g=p.game,shop=Shop.view(g);
 return <Screen title="成长手册" sub="不止经验条，更是新技能和新装备。">
  <Card style={{backgroundColor:c.soft}}><Row><Actor size={120} pose="think"/><View style={{flex:1,gap:6}}><Txt kind="h2">Lv.{G.stats(g).level} 的冒险魔法</Txt><Txt>每500经验升级。</Txt><Txt kind="small">{shop.nextSkill?'再获得 '+shop.nextSkill.xpRemaining+' 经验，学会 '+shop.nextSkill.name:'五种魔法已全部学会，继续收集装备。'}</Txt><Txt kind="small">墨水 {shop.ink} 瓶 · 新技能各含1次使用机会。</Txt></View></Row></Card>
  <Txt kind="h2">我的技能树</Txt>
  <Columns>{shop.skills.map((s:any)=><Card key={s.id} style={{borderWidth:1,borderColor:s.unlocked?s.color:c.line}}><Row><Txt kind="title" style={{color:s.color}}>{s.glyph}</Txt><View style={{flex:1}}><Txt kind="h2">{s.name}</Txt><Txt kind="small">Lv.{s.level} · {s.unlocked?'已学会 · 剩余'+s.charges+'次':'还差'+s.xpRemaining+'经验'}</Txt></View></Row><Txt>{s.description}</Txt>
    {s.unlocked&&<><Row><Button label={'补充一次 · '+s.price+' 金币'} secondary disabled={g.coins<s.price} onPress={()=>{void act(async()=>{await run((v:any)=>Skills.refill(v,s.id));});}}/><Button label="用1瓶墨水" secondary disabled={shop.ink<1} onPress={()=>{void act(async()=>{await run((v:any)=>Skills.refill(v,s.id,true));});}}/></Row>
      {s.type==='boost'?<Button label={s.queued?'已预约 · 点击取消':'预约到下一场适用挑战'} disabled={!s.charges&&!s.queued} onPress={()=>{void act(async()=>{await run((v:any)=>Skills.queue(v,s.id));});}}/>:<Txt kind="small">在适用答题页使用；每次消耗一次机会。</Txt>}
    </>}
  </Card>)}</Columns>
  <Txt kind="h2">沿途上架的宝贝</Txt><Txt kind="small">以不同主线关卡的首次通关数量解锁购买资格。低概率惊喜可能赠送，普通通关不会保证赠送。</Txt>
  <Columns>{shop.milestones.map((m:any)=><Card key={m.id}><Row><ItemImage path={m.icon} size={70}/><View style={{flex:1}}><Txt kind="label">{m.name}</Txt><Txt kind="small">{m.rarityName} · {m.price} 金币</Txt><Txt kind="small">{m.owned?'已拥有':m.unlocked?'已经上架':'再首通'+m.remaining+'关上架'}</Txt></View></Row><Bar value={m.progress}/><Button label="去商城看看" secondary onPress={()=>router.push('/bag')}/></Card>)}</Columns>
  <Card><Txt kind="h2">努力怎样换成奖励？</Txt><Txt kind="small">普通关首通50经验、10金币；Boss首胜150经验、30金币。新星级每颗另加10经验，新获第二、第三颗星各加5金币。</Txt><Txt kind="small">固定Boss仅首次击败有15%额外掉落机会，重打不会重抽。主线首通另有10%惊喜机会，其中实际赠送奇物的总概率为2.5%。重复物品按品质兑换金币。</Txt><Txt kind="small">技能不会改写真实正确率。瞒天过海只用于普通关与远征，Boss依然按真实作答判定。</Txt></Card>
 </Screen>;
}
