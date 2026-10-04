const G=require('../../utils/game');
const Skills=require('../../utils/skills');
const Shop=require('../../utils/shop');
const F=G.Finance;
const Art=require('../../utils/assets');
const {books:BOOKS}=require('../../data/questions');
const categories={skin:'形象与装扮',equipment:'装备',collection:'收藏'};
const equipped=(g,id)=>[g.skin,g.outfit,g.title,...Object.values(g.equipment)].includes(id);
const display=value=>typeof value==='string'?value:Array.isArray(value)?value.map(display).join('；'):value&&typeof value==='object'?Object.entries(value).map(([k,v])=>k+'：'+display(v)).join('；'):value==null?'':String(value);
Page({
 data:{screen:'home',bagTab:'owned',shopFilter:'all',selectedItem:'',chapterIndex:0,bookIndex:0,typeIndex:0,practiceChapterIndex:0},
 onShow(){this.refresh();this.focusTick=setInterval(()=>this.refreshFocus(),1000);void getApp().loadFinanceArt().then(()=>this.refresh()).catch(()=>this.setData({artError:true}));},
 onHide(){clearInterval(this.focusTick);},onUnload(){clearInterval(this.focusTick);},
 refresh(){
  const store=getApp().store,p=store.progress,g=p.game,w=g.campaign.worlds.find(w=>w.id===g.world),s=G.stats(g);
  const worlds=g.campaign.worlds.map(w=>({...w,...G.stats(g,w.id),selected:w.id===g.world}));
  const chapters=w.chapters.map((c,index)=>({...c,index,open:G.canPlay(g,c.stages[0]),completed:c.stages.every(id=>G.cleared(g,id)),biomeName:G.C.biomes.find(b=>b.id===c.biome).name}));
  let index=Math.min(this.data.chapterIndex,chapters.length-1);const chapter=chapters[index];
  const stages=chapter.stages.map((id,i)=>{const l=G.levelFor(g,id),r=g.results[id]||{};return {...l,open:G.canPlay(g,id),passed:!!r.cleared,stars:'★'.repeat(r.best_stars||0)+'☆'.repeat(3-(r.best_stars||0)),quality:(r.best_stars||0)>=2,position:i%2?'right':'left',total:l.qids.length};});
  const shop=Shop.view(g,this.data.shopFilter,this.data.selectedItem),artReady=!!getApp().financeArtReady,icon=i=>i?{...i,icon:Art.readyImage(i.icon,artReady)}:i;
  for(const key of ['items','ownedItems','shopItems','collectionItems'])shop[key]=shop[key].map(icon);shop.shopDetail=icon(shop.shopDetail);shop.goal=icon(shop.goal);
  const scope=G.META.filter(q=>q.book_id.startsWith(w.prefix));
  const books=[{id:'',name:'全部教材'},...Array.from(new Set(scope.map(q=>q.book_id))).map(id=>({id,name:BOOKS[id]||'教材'}))];
  const types=['全部题型',...new Set(scope.map(q=>q.type))];
  const pc=['全部章节',...new Set(scope.map(q=>q.chapter))];
  const learning={total:G.META.length,answered:Object.keys(p.answered).length,correct:Object.values(p.answered).filter(a=>a.correct).length,wrong:p.wrong_book.length,favorites:p.favorites.length};learning.rate=learning.answered?Math.floor(learning.correct*1000/learning.answered)/10:0;
  const finance=F.view(g);finance.buildings=finance.buildings.map(b=>({...b,image:Art.readyImage('/assets/'+b.assets[Math.max(0,b.level-1)],artReady),levelName:b.level?b.levels[b.level-1]:'等待建设'}));finance.companions=finance.companions.map(b=>({...b,image:Art.readyImage('/assets/'+b.asset,artReady)}));finance.acts=finance.acts.map(b=>({...b,image:Art.readyImage('/assets/'+(b.npc_asset||b.asset),artReady)}));finance.props=finance.props.map(b=>({...b,image:Art.readyImage('/assets/'+b.asset,artReady),owned:g.inventory.includes(b.id)}));
  const rescueIds=F.rescueQuestions(p,G.META),formulaChapters=F.formulas(g).map(c=>({...c,formulas:(c.formulas||[]).map(f=>({...f,expression:display(f.formula||f.expression||f),symbolsText:display(f.symbols),conditionsText:display(f.conditions||f.condition),pitfallsText:display(f.pitfalls||f.pitfall)}))}));
  const friend=F.companionGuide(p,G.META);
  this.setData({g,world:w,worlds,chapters,chapter,chapterIndex:index,stages,stats:s,...shop,finance,friend,rescueCount:rescueIds.length,formulaChapters,badges:g.badges.length,theme:p.theme,loadError:store.loadError,saveError:store.pending,books,bookNames:books.map(b=>b.name),types,practiceChapters:pc,bookIndex:Math.min(this.data.bookIndex,books.length-1),typeIndex:Math.min(this.data.typeIndex,types.length-1),practiceChapterIndex:Math.min(this.data.practiceChapterIndex,pc.length-1),learning,hasActive:!!(g.active&&!g.active.settled),hasPractice:!!(p.practice&&!p.practice.settled),expeditionOpen:G.expeditionAvailable(g),xpProgress:g.xp%500/5});this.refreshFocus();
 },
 act(change,next){try{getApp().store.commit(change);this.refresh();if(next)next();}catch(e){wx.showModal({title:'操作暂未完成',content:e.message,showCancel:false});this.refresh();}},
 retrySave(){try{const store=getApp().store;if(store.pending)store.retry();else if(store.loadError)store.load();this.refresh();if(store.loadError)throw Error(store.loadError);wx.showToast({title:'已恢复',icon:'success'});}catch(e){wx.showToast({title:e.message,icon:'none'});}},
 retryArt(){void getApp().loadFinanceArt().then(()=>{this.setData({artError:false});this.refresh();}).catch(e=>wx.showToast({title:e.message,icon:'none'}));},
 nav(e){this.setData({screen:e.currentTarget.dataset.screen,selectedItem:''});wx.pageScrollTo({scrollTop:0,duration:200});this.refresh();},
 chooseWorld(e){this.setData({chapterIndex:0,bookIndex:0,typeIndex:0,practiceChapterIndex:0});this.act(p=>{p.game.world=e.currentTarget.dataset.id;});},
 chooseChapter(e){const index=Number(e.currentTarget.dataset.index);if(!this.data.chapters[index].open){wx.showToast({title:'击败前章全部 Boss 后开放',icon:'none'});return;}this.setData({chapterIndex:index});this.refresh();},
 continueAdventure(){this.act(p=>G.start(p,G.nextStage(p.game)),()=>getApp().challenge());},
 resume(){getApp().challenge();},
 play(e){const sid=e.currentTarget.dataset.id;if(!G.canPlay(getApp().store.progress.game,sid)){wx.showToast({title:'先完成前一关，70% 即可解锁',icon:'none'});return;}this.act(p=>G.start(p,sid),()=>getApp().challenge());},
 expedition(){this.act(p=>{const s=G.expedition(p);G.start(p,s.id);},()=>getApp().challenge());},
 bagTab(e){this.setData({bagTab:e.currentTarget.dataset.tab,selectedItem:''});this.refresh();},
 filterShop(e){this.setData({shopFilter:e.currentTarget.dataset.id});this.refresh();},
 openItem(e){this.setData({selectedItem:e.currentTarget.dataset.id});this.refresh();},
 closeItem(){this.setData({selectedItem:''});this.refresh();},
 noop(){},
 itemAction(e){const id=e.currentTarget.dataset.id,skillId=id.startsWith('skill:')?id.slice(6):null,g=getApp().store.progress.game;if(!skillId&&g.inventory.includes(id)){this.act(p=>G.equip(p,id));return;}if(this.purchaseBusy)return;const item=skillId?Skills.DEFINITIONS[skillId]:G.CATALOG[id];if(!item)return;this.purchaseBusy=true;wx.showModal({title:'兑换'+item.name+(skillId?'卷轴':''),content:'花费 '+item.price+' 金币'+(skillId?'，补充一次使用机会。':'，物品加入背包。'),success:r=>{if(r.confirm)this.act(p=>skillId?Skills.refill(p,skillId):G.buy(p,id),()=>wx.showToast({title:skillId?'技能已补充':'已加入背包',icon:'success'}));},complete:()=>{this.purchaseBusy=false;}});},
 setWish(e){const id=e.currentTarget.dataset.id;if(G.CATALOG[id])this.act(p=>{p.game.wishlist=id;},()=>wx.showToast({title:'已设为攒钱目标',icon:'success'}));},
 queueSkill(e){this.act(p=>Skills.queue(p,e.currentTarget.dataset.id));},
 refillInk(e){this.act(p=>Skills.refill(p,e.currentTarget.dataset.id,true),()=>wx.showToast({title:'技能次数 +1',icon:'success'}));},
 openShop(){this.setData({screen:'bag',bagTab:'shop',selectedItem:''});this.refresh();wx.pageScrollTo({scrollTop:0,duration:150});},
 selectBook(e){this.setData({bookIndex:Number(e.detail.value)});},
 selectType(e){this.setData({typeIndex:Number(e.detail.value)});},
 selectPracticeChapter(e){this.setData({practiceChapterIndex:Number(e.detail.value)});},
 practice(e){const mode=e.currentTarget.dataset.mode,p=getApp().store.progress,book=this.data.books[this.data.bookIndex].id,type=this.data.types[this.data.typeIndex],chapter=this.data.practiceChapters[this.data.practiceChapterIndex];const ids=G.META.filter(q=>q.book_id.startsWith(this.data.world.prefix)&&(!book||q.book_id===book)&&(type==='全部题型'||type===q.type)&&(chapter==='全部章节'||chapter===q.chapter)&&(mode!=='wrong'||p.wrong_book.includes(q.id))&&(mode!=='favorites'||p.favorites.includes(q.id))).map(q=>q.id);this.act(p=>G.startPractice(p,ids,mode==='wrong'?'错题复习':mode==='favorites'?'收藏复习':'自由刷题'),()=>getApp().challenge(true));},
 resumePractice(){getApp().challenge(true);},
 openTown(){this.setData({screen:'town',selectedItem:''});this.refresh();wx.pageScrollTo({scrollTop:0,duration:150});},
 openFormulas(){this.setData({screen:'formulas'});this.refresh();wx.pageScrollTo({scrollTop:0,duration:150});},
 seeFormulas(e){this.act(p=>F.seeFormulas(p,e.currentTarget.dataset.chapter));},
 viewStory(e){const id=e.currentTarget.dataset.id;this.act(p=>F.seeStory(p,id),()=>{const info=F.storyFor(getApp().store.progress.game,id);this.setData({townStory:{name:info.act.name,lines:[...info.story,...(info.completed?info.completion_story:[])]}});});},
 closeStory(){this.setData({townStory:null});},
 buildTown(e){this.act(p=>F.upgradeBuilding(p,e.currentTarget.dataset.id),()=>wx.showToast({title:'小镇建筑升级了！',icon:'success'}));},
 recruitSpirit(e){this.act(p=>F.recruit(p,e.currentTarget.dataset.id));},
 equipSpirit(e){this.act(p=>F.equipCompanion(p,e.currentTarget.dataset.id));},
 commission(e){this.act(p=>G.startCommission(p,e.currentTarget.dataset.id),()=>getApp().challenge(true));},
 claimCommission(e){this.act(p=>F.claimCommission(p,e.currentTarget.dataset.id),()=>wx.showToast({title:'收到NPC明信片',icon:'success'}));},
 rescue(){if(!this.data.rescueCount){wx.showToast({title:'当前科目救援已完成！',icon:'success'});return;}this.act(p=>G.startRescue(p),()=>getApp().challenge(true));},
 utility(e){const utility=e.currentTarget.dataset.utility;if(utility==='town'){this.openTown();return;}if(utility==='formulas'){this.openFormulas();return;}if(utility==='review'){this.setData({screen:'study'});this.refresh();return;}this.setData({screen:'tools',tool:utility});this.refresh();},
 scratch(e){this.act(p=>{F.ensureExpansion(p.game).tools.scratch=e.detail.value;});},
 startFocus(){this.act(p=>{const t=F.ensureExpansion(p.game).tools;t.focus_started_at=Date.now()/1000;t.focus_seconds=1500;});},
 stopFocus(){this.act(p=>{F.ensureExpansion(p.game).tools.focus_started_at=null;});},
 refreshFocus(){const t=getApp().store.progress.game.finance_expansion?.tools;if(!t)return;const remaining=t.focus_started_at?Math.max(0,t.focus_seconds-Math.floor(Date.now()/1000-t.focus_started_at)):t.focus_seconds;this.setData({focusRemaining:remaining,focusText:String(Math.floor(remaining/60)).padStart(2,'0')+':'+String(remaining%60).padStart(2,'0'),focusStarted:!!t.focus_started_at});},
 toggleTheme(){this.act(p=>{p.theme=p.theme==='dark'?'light':'dark';});},
 exportBackup(){try{const text=getApp().store.export(),path=wx.env.USER_DATA_PATH+'/小圆冒险存档.json';wx.getFileSystemManager().writeFile({filePath:path,data:text,encoding:'utf8',success:()=>{if(wx.shareFileMessage)wx.shareFileMessage({filePath:path,fail:()=>wx.showToast({title:'备份已保存到小程序本地',icon:'none'})});else wx.setClipboardData({data:text});},fail:()=>wx.showToast({title:'备份保存失败',icon:'none'})});}catch(e){wx.showToast({title:e.message,icon:'none'});}},
 importBackup(){wx.chooseMessageFile({count:1,type:'file',extension:['json'],success:r=>wx.getFileSystemManager().readFile({filePath:r.tempFiles[0].path,encoding:'utf8',success:f=>wx.showModal({title:'恢复备份',content:'这会替换当前手机进度。请先导出当前备份。',success:d=>{if(d.confirm){try{getApp().store.import(f.data);this.refresh();wx.showToast({title:'恢复成功',icon:'success'});}catch(e){wx.showToast({title:e.message,icon:'none'});}}}}),fail:()=>wx.showToast({title:'备份文件无法读取',icon:'none'})}),fail:()=>{}});}
});
