import {useState} from 'react';
import {router} from 'expo-router';
import {Modal, ScrollView, View} from 'react-native';
import {SafeAreaView} from 'react-native-safe-area-context';
import {Actor, ItemImage} from '../../components/Actor';
import {Bar, Button, Card, Columns, Row, Screen, Txt, usePalette} from '../../components/ui';
import {G, Shop, Skills} from '../../services/rules';
import {useAdventure} from '../../state/AdventureProvider';

export default function Bag(){
 const {p,run,act}=useAdventure(),c=usePalette();const [mode,setMode]=useState('shop'),[filter,setFilter]=useState('all'),[selected,setSelected]=useState('');
 const g=p.game,shop=Shop.view(g,filter,selected),item=shop.shopDetail;
 const equip=(id:string)=>{void act(async()=>{await run((v:any)=>G.equip(v,id));});};
 const purchase=()=>{if(!item)return;void act(async()=>{await run((v:any)=>item.isSkill?Skills.refill(v,item.skillId):G.buy(v,item.id));});};
 const list=mode==='shop'?shop.shopItems:mode==='bag'?shop.ownedItems:shop.collectionItems;
 return <Screen title="旅行小铺" sub="攒下的努力，换成下一份期待。">
  <Card><Row><Actor size={138} pose="celebrate"/><View style={{flex:1,minWidth:140,gap:8}}><Txt kind="h2">我的冒险装备</Txt><Txt kind="small">经验护符 · {G.CATALOG[g.equipment.xp]?.name||'未装备'}</Txt><Txt kind="small">金币铃铛 · {G.CATALOG[g.equipment.coins]?.name||'未装备'}</Txt><Txt kind="small">魔法奇物 · {G.CATALOG[g.equipment.wonder]?.name||'未装备'}</Txt><Txt style={{color:c.blue}}>经验 +{shop.bonuses.xp}% · 金币 +{shop.bonuses.coins}%</Txt></View></Row></Card>
  <Row>{[['bag','背包'],['shop','金币商城'],['collection','收藏图鉴']].map(([id,label])=><Button key={id} label={label} secondary={mode!==id} onPress={()=>setMode(id)}/>)}</Row>
  {mode==='shop'&&<><Row>{shop.shopCategories.map((cat:any)=><Button key={cat.id} label={cat.name} secondary={filter!==cat.id} onPress={()=>setFilter(cat.id)}/>)}</Row><Txt kind="small">普通、稀有、史诗、传说 · 所有金币都来自学习通关。商品可先试穿，再决定是否兑换。</Txt></>}
  {mode==='collection'&&<Columns>{shop.themeSets.map((set:any)=><Card key={set.id}><Row><ItemImage path={set.icon} size={58}/><View style={{flex:1}}><Txt kind="label">{set.name}套装</Txt><Txt kind="small">装扮 + 纪念品 · {set.count} / 2</Txt></View></Row><Bar value={set.count*50}/></Card>)}</Columns>}
  <Columns>{list.map((i:any)=><Card key={i.id} style={{borderWidth:1,borderColor:i.rarity==='legendary'?'#d4a347':c.line}}>
    <View style={{alignItems:'center'}}>{i.hasActorPreview?<Actor size={125} preview={i.preview}/>:<ItemImage path={i.icon} size={100}/>}</View>
    <Txt kind="h2">{i.name}</Txt><Txt kind="small" style={{color:G.C.rarities[i.rarity]?.color||c.blue}}>{i.rarityName} · {i.categoryName}</Txt><Txt kind="small">{i.effect}</Txt>
    <Button label={i.equipped?'正在使用 · 查看':i.owned?'已拥有 · 查看':i.isSkill?i.price+' 金币 · 补充一次':i.price+' 金币 · 试穿看看'} secondary testID={'item-'+i.id.replace(':','-')} onPress={()=>setSelected(i.id)}/>
    {i.unlockText&&<Txt kind="small">{i.unlockText}</Txt>}
  </Card>)}</Columns>
  <Modal visible={!!item} animationType="slide" onRequestClose={()=>setSelected('')}>
    <SafeAreaView style={{flex:1,backgroundColor:c.bg}}><ScrollView contentContainerStyle={{padding:24,alignItems:'center'}}><View style={{width:'100%',maxWidth:560,gap:18}}>
      <Button label="关闭商品详情" secondary onPress={()=>setSelected('')}/>
      {item&&<Card><View style={{alignItems:'center'}}>{item.hasActorPreview||item.slot?<Actor size={210} pose="idle" preview={item.preview}/>:<ItemImage path={item.icon} size={150}/>}</View>
        <Txt kind="title">{item.name}</Txt><Txt style={{color:G.C.rarities[item.rarity]?.color||c.blue}}>{item.rarityName} · {item.price} 金币</Txt><Txt>{item.story}</Txt><Txt kind="label">{item.effect}</Txt>
        {item.isSkill&&<Txt kind="small">Lv.{item.level} 解锁 · 剩余 {item.charges} 次 · 魔法墨水 {shop.ink} 瓶</Txt>}
        {!item.owned&&<><Txt kind="small">{item.unlockText||'已上架'} · 还差 {item.remaining} 金币</Txt><Bar value={item.progress||Math.min(100,g.coins/item.price*100)}/>
          <Button label={'确认兑换 · '+item.price+' 金币'} disabled={!item.canBuy} onPress={purchase}/>
          {item.isSkill&&<Button label="用1瓶魔法墨水补充" secondary disabled={!item.unlocked||shop.ink<1} onPress={()=>{void act(async()=>{await run((v:any)=>Skills.refill(v,item.skillId,true));});}}/>}
        </>}
        {item.owned&&item.wearable&&<Button label={item.equipped?'卸下或保持当前伙伴':'立即使用'} onPress={()=>equip(item.id)}/>}
        {!item.isSkill&&!item.owned&&<Button label={g.wishlist===item.id?'已设为我的心愿':'设为我的心愿'} secondary onPress={()=>{void act(async()=>{await run((v:any)=>{v.game.wishlist=item.id;});});}}/>}
        {item.kind==='tool'&&<Button label="打开学习工具" secondary onPress={()=>{setSelected('');if(item.utility==='formulas')router.push('/formulas');else if(item.utility==='review')router.push('/practice');else router.push({pathname:'/town',params:{tool:item.utility}});}}/>}
        {item.slot&&<Txt kind="small">收益加成在挑战开始时固定，换装会在下一场新挑战生效。</Txt>}
      </Card>}
    </View></ScrollView></SafeAreaView>
  </Modal>
 </Screen>;
}
