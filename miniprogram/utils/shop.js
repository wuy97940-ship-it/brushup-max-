const G=require('./game');
const S=require('./skills');
const art=require('../data/shop_art');
const actors=require('../data/characters');
const names={orange_adventurer:'小团 · 蓝围巾冒险者',orange_mage:'小团 · 星蓝法师',orange_knight:'小团 · 蓝盾骑士'};
const stories={forest:'晨光穿过叶片，森林把第一段勇气留在这里。',island:'听见贝壳里的浪声，就想起那次跨海的旅程。',snow:'雪山的晶光，记得你认真攻克过的每一道题。',ruins:'古老的猫爪符石，珍藏遗迹中找回的知识。',sky:'一枚轻盈云羽，记录向更高处出发的自己。',stars:'在银河深处，努力的人会拾到属于自己的星光。'};
const categories=[{id:'all',name:'全部'},{id:'characters',name:'主角'},{id:'companions',name:'精灵'},{id:'outfits',name:'换装'},{id:'tools',name:'学习道具'},{id:'equipment',name:'装备'},{id:'collection',name:'收藏'},{id:'skills',name:'技能卷轴'}];
function viewItem(g,item){
 const unlock=G.growthStatus(g).find(m=>m.item===item.id);
 const spirit=item.category==='companion',financeSpirit=spirit?G.Finance.view(g).companions.find(c=>c.id===item.id):null;
 const owned=g.inventory.includes(item.id),equipped=[g.skin,g.outfit,g.title,...Object.values(g.equipment),g.finance_expansion?.companion].includes(item.id);
 const preview={skin:g.skin,outfit:g.outfit||'',xp:g.equipment.xp||'',coins:g.equipment.coins||'',wonder:g.equipment.wonder||''};
 if(item.character)preview.skin=item.id;
 else if(item.outfit){preview.outfit=item.id;if(item.fit_character)preview.skin=item.fit_character;}
 else if(item.category==='equipment')preview[item.slot]=item.id;
 const icon=art.souvenirs[item.id]||art.wonders[item.id]?.icon||actors.overlays[item.id]||(item.asset?'/assets/'+item.asset:'');
 const effect=spirit?'陪伴职责 · '+item.role:item.kind==='tool'?'打开'+({formulas:'公式图鉴',scratch:'计算草稿',focus:'专注计时',review:'复习清单'}[item.utility]||'学习工具'):item.kind==='decoration'?'星光经营小镇的收藏摆件':item.slot==='wonder'?[item.xp_percent?'经验 +'+item.xp_percent+'%':'',item.coins_percent?'金币 +'+item.coins_percent+'%':''].filter(Boolean).join(' · '):item.slot?(item.slot==='xp'?'经验':'金币')+' +'+item.bonus_percent+'%':item.character?'切换冒险伙伴，所有姿态同步':item.outfit?'地图、战斗、头像同步换装':item.title?'把新称号挂在冒险名片上':'珍藏你的六地图冒险记忆';
 return {...item,name:names[item.id]||item.name,owned,equipped,preview,icon,isCharacter:!!item.character,hasActorPreview:!!(item.character||item.outfit),wearable:!!(item.character||item.outfit||item.slot||item.title||spirit),group:spirit?'companions':item.kind==='tool'?'tools':item.character?'characters':item.outfit?'outfits':item.category,
  rarityName:G.C.rarities[item.rarity]?.name||'普通',categoryName:spirit?'精灵伙伴':item.kind==='tool'?'学习工具':item.kind==='decoration'?'小镇摆件':item.slot==='wonder'?'魔法奇物':item.category==='equipment'?'收益装备':item.character?'冒险主角':item.outfit?'主题装扮':item.title?'冒险称号':'地图纪念品',effect,
  story:item.story||stories[item.biome]||stories[item.id.split('_').slice(1).join('_')]||'每一次认真学习，都让你的冒险收藏多一份光彩。',
  unlocked:owned||(spirit?financeSpirit?.unlocked:!unlock||unlock.unlocked),unlockText:spirit&&!financeSpirit?.unlocked?'完成财管第'+item.unlock_chapter+'章后招募':unlock&&!unlock.unlocked?'通关 '+unlock.clears+' 关上架':'',
  remaining:Math.max(0,(item.price||0)-g.coins),progress:item.price?Math.min(100,Math.floor(g.coins*100/item.price)):100,canBuy:!owned&&(spirit?financeSpirit?.unlocked:!unlock||unlock.unlocked)&&g.coins>=item.price};
}
function view(g,filter='all',selected=''){
 const items=Object.values(G.CATALOG).map(i=>viewItem(g,i));
 const skillItems=S.view(g).map(s=>({...s,id:'skill:'+s.id,skillId:s.id,name:s.name+'卷轴',group:'skills',rarity:'rare',rarityName:'技能',categoryName:'补充一次技能',effect:s.description,story:'等级达到后自动学会。每次补充获得一次使用机会，也可用魔法墨水补充。',isSkill:true,wearable:false,owned:false,remaining:Math.max(0,s.price-g.coins),canBuy:s.unlocked&&g.coins>=s.price,unlockText:s.unlocked?'':'Lv.'+s.level+' 解锁'}));
 const shopItems=[...items.filter(i=>!i.starter).sort((a,b)=>(a.slot==='wonder'?0:1)-(b.slot==='wonder'?0:1)),...skillItems].filter(i=>filter==='all'||i.group===filter);
 const all=[...items,...skillItems],detail=all.find(i=>i.id===selected)||null;
 const themeSets=G.C.biomes.map(b=>{const ids=['outfit_'+b.id,'souvenir_'+b.id];return {...b,icon:art.souvenirs['souvenir_'+b.id],count:ids.filter(id=>g.inventory.includes(id)).length};});
 const skills=S.view(g),nextSkill=skills.find(s=>!s.unlocked);
 const milestones=G.growthStatus(g).map(m=>({...m,name:G.CATALOG[m.item].name,icon:art.wonders[m.item].icon,price:G.CATALOG[m.item].price,rarity:G.CATALOG[m.item].rarity,rarityName:G.C.rarities[G.CATALOG[m.item].rarity].name}));
 const goal=items.find(i=>i.id===g.wishlist)||items.find(i=>i.slot==='wonder'&&!i.owned)||null;
 return {items,ownedItems:items.filter(i=>i.owned),shopItems,collectionItems:items.filter(i=>i.category==='collection'),shopDetail:detail,shopCategories:categories,themeSets,skills,nextSkill:nextSkill||null,milestones,goal,ink:g.skill_state?.ink||0,bossDropPercent:G.C.drop_percent,wonderName:G.CATALOG[g.equipment.wonder]?.name||'奇物槽 · 期待下一件宝贝',bonuses:G.bonuses(g),xpInLevel:g.xp%G.C.xp_per_level,xpToLevel:G.C.xp_per_level-g.xp%G.C.xp_per_level};
}
module.exports={view,viewItem,categories};
