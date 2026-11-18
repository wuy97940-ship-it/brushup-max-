const G=require('../../utils/game600');
const Skills=require('../../utils/skills');
const Growth=G.Growth600;
const F=G.Finance;
const Art=require('../../utils/assets');
const {books:BOOKS}=require('../../data/questions');
const categories={skin:'形象与装扮',equipment:'装备',collection:'收藏'};
const equipped=(g,id)=>[g.skin,g.outfit,g.title,...Object.values(g.equipment)].includes(id);
const display=value=>typeof value==='string'?value:Array.isArray(value)?value.map(display).join('；'):value&&typeof value==='object'?Object.entries(value).map(([k,v])=>k+'：'+display(v)).join('；'):value==null?'':String(value);
Page({
 data:{screen:'home',upgradePending:true,upgradeInfo:{},guideStep:-1,arenaCountIndex:1,arenaRateIndex:1,arenaWeak:true,bagTab:'owned',shopFilter:'all',selectedItem:'',chapterIndex:0,bookIndex:0,typeIndex:0,practiceChapterIndex:0},
 onShow(){this.homeVisible=true;this.refresh();clearInterval(this.focusTick);this.focusTick=setInterval(()=>this.refreshFocus(),1000);},
 onReady(){getApp().pageReady?.();},
 onHide(){this.homeVisible=false;clearInterval(this.focusTick);},onUnload(){this.homeVisible=false;clearInterval(this.focusTick);},
 refresh(){
  const app=getApp(),store=app.store;
  if(app.cloudSave)this.setData({cloud610:app.cloudSave.view()});
  // 可写store仅在升级事务完成后开放；日常刷新不重复解析整份只读升级快照。
  let upgradeInfo;
  try{upgradeInfo=app.upgrade?(store?{pending:false,hasLocal:true,loadError:'',backups:app.upgrade.listBackups()}:app.upgrade.status()):null;}
  catch(e){upgradeInfo={pending:!store,hasLocal:true,loadError:e.message,backups:[]};}
  if(upgradeInfo){const backups610=upgradeInfo.backups.map(b=>({...b,dateText:new Date(b.createdAt).toLocaleString(),label:b.reason==='new'?'重新开始前':b.reason==='continue'?'升级前':b.reason==='import'?'导入前':b.reason==='cloud-unsent'?'未同步的云候选':'恢复前'}));this.setData({upgradePending:upgradeInfo.pending||!store,upgradeInfo,backups610,update610:app.updates?.view()});if(upgradeInfo.pending||!store)return;}
  const p=store.progress,g=p.game,screen=this.data.screen,w=g.campaign.worlds.find(w=>w.id===g.world),stats=G.stats(g),modern=G.modern(g);
  const worlds=g.campaign.worlds.map(({id,name,prefix})=>({id,name,prefix,...G.stats(g,id),selected:id===g.world}));
  const world={id:w.id,name:w.name,prefix:w.prefix},worldStats=G.stats(g,w.id),growth=modern?Growth.view(g):null;
  const data={g:G.uiGame(g),modern,world,worlds,worldStats,stats,daily600:Growth.dailyView(g),starterHeroes:G.Adventure.C.heroes,mood:G.Adventure.view(g),theme:p.theme,loadError:store.loadError,saveError:store.pending,badges:g.badges.length,hasActive:!!(g.active&&!g.active.settled&&G.levelFor(g,g.active.stage_id).world_id===g.world),hasPractice:!!(p.practice&&!p.practice.settled),hasArena610:!!p.practice?.arena610&&!p.practice.settled,expeditionOpen:G.expeditionAvailable(g),xpProgress:growth?growth.progress:g.xp%500/5,shopDetail:null};
  if(screen==='map'){
   const chapters=w.chapters.map((c,index)=>({...c,index,open:G.canPlay(g,c.stages[0]),completed:c.stages.every(id=>G.cleared(g,id)),biomeName:G.C.biomes.find(b=>b.id===c.biome).name}));
   const index=Math.min(this.data.chapterIndex,chapters.length-1),chapter=chapters[index];
   const stages=chapter.stages.map((id,i)=>{const l=G.levelFor(g,id),r=g.results[id]||{};return {...l,open:G.canPlay(g,id),passed:!!r.cleared,stars:'★'.repeat(r.best_stars||0)+'☆'.repeat(3-(r.best_stars||0)),quality:(r.best_stars||0)>=2,position:i%2?'right':'left',total:l.qids.length};});
   Object.assign(data,{chapters,chapter,chapterIndex:index,stages});
  }
  if(['bag','growth'].includes(screen)){
   const shop=require('../../utils/shop').view(g,this.data.shopFilter,this.data.selectedItem),artReady=!!app.financeArtReady,huntArt=require('../../data/hunting600').art,media=app.huntingMedia;
   const icon=i=>i?{...i,icon:i.capture_only?(media?.isReady(huntArt[i.id].package)?huntArt[i.id].path:''):Art.readyImage(i.icon,artReady)}:i;
   if(screen==='bag'){const visible=this.data.bagTab==='shop'?shop.shopItems:this.data.bagTab==='owned'?shop.ownedItems:shop.collectionItems;this.loadSpiritPictures(visible.concat(shop.shopDetail?[shop.shopDetail]:[]));}
   for(const key of ['items','ownedItems','shopItems','collectionItems'])shop[key]=shop[key].map(icon);shop.shopDetail=icon(shop.shopDetail);shop.goal=icon(shop.goal);Object.assign(data,shop);
  }
  if(['town','formulas','tools'].includes(screen)){
   const finance=F.view(g),artReady=!!app.financeArtReady;
   finance.buildings=finance.buildings.map(b=>({...b,image:Art.readyImage('/assets/'+b.assets[Math.max(0,b.level-1)],artReady),levelName:b.level?b.levels[b.level-1]:'等待建设'}));
   finance.companions=finance.companions.map(b=>({...b,image:Art.readyImage('/assets/'+b.asset,artReady)}));finance.acts=finance.acts.map(b=>({...b,image:Art.readyImage('/assets/'+(b.npc_asset||b.asset),artReady)}));finance.props=finance.props.map(b=>({...b,image:Art.readyImage('/assets/'+b.asset,artReady),owned:g.inventory.includes(b.id)}));data.finance=finance;
  }
  if(screen==='formulas')data.formulaChapters=F.formulas(g).map(c=>({...c,formulas:(c.formulas||[]).map(f=>({...f,expression:display(f.formula||f.expression||f),symbolsText:display(f.symbols),conditionsText:display(f.conditions||f.condition),pitfallsText:display(f.pitfalls||f.pitfall)}))}));
  if(screen==='study'){
   const scope=G.META.filter(q=>q.book_id.startsWith(w.prefix)),books=[{id:'',name:'全部教材'},...Array.from(new Set(scope.map(q=>q.book_id))).map(id=>({id,name:BOOKS[id]||'教材'}))],types=['全部题型',...new Set(scope.map(q=>q.type))],pc=['全部章节',...new Set(scope.map(q=>q.chapter))];
   const learning={total:G.META.length,answered:Object.keys(p.answered).length,correct:Object.values(p.answered).filter(a=>a.correct).length,wrong:p.wrong_book.length,favorites:p.favorites.length};learning.rate=learning.answered?Math.floor(learning.correct*1000/learning.answered)/10:0;
   Object.assign(data,{books,bookNames:books.map(b=>b.name),types,practiceChapters:pc,bookIndex:Math.min(this.data.bookIndex,books.length-1),typeIndex:Math.min(this.data.typeIndex,types.length-1),practiceChapterIndex:Math.min(this.data.practiceChapterIndex,pc.length-1),learning,rescueCount:F.rescueQuestions(p,G.META).length});
  }
  if(screen==='me')data.friend=F.companionGuide(p,G.META);
  this.setData(data);this.refreshFocus();this.ensureViewArt();
 },
 ensureViewArt(){const app=getApp(),g=app.store?.progress.game,lightOutfit=!!require('../../data/outfits610').outfits[g?.outfit],need=['bag','growth','town','formulas','tools'].includes(this.data.screen)||!!g?.outfit&&!lightOutfit||!!g?.equipment?.xp||!!g?.equipment?.coins||!!g?.equipment?.wonder;if(!need||app.financeArtReady||this.artPending)return;this.artPending=true;void app.loadFinanceArt().then(()=>{this.artPending=false;if(this.homeVisible){this.setData({artError:false});this.refresh();}}).catch(()=>{this.artPending=false;if(this.homeVisible&&['bag','growth','town','formulas','tools'].includes(this.data.screen))this.setData({artError:true});});},
 loadSpiritPictures(items){const art=require('../../data/hunting600').art,media=getApp().huntingMedia;if(!media)return;this.pictureLoads=this.pictureLoads||new Set();for(const i of items)if(i.capture_only){const name=art[i.id].package;if(media.isReady(name)||this.pictureLoads.has(name))continue;this.pictureLoads.add(name);void media.load(name).then(()=>{if(this.homeVisible)this.refresh();}).catch(()=>{this.pictureLoads.delete(name);if(this.homeVisible)this.setData({artError:true});});}},
 act(change,next){try{const result=getApp().store.commit(change);this.refresh();if(next)next(result);}catch(e){wx.showModal({title:'操作暂未完成',content:e.message,showCancel:false});this.refresh();}},
 retrySave(){try{const store=getApp().store;if(store.pending){const result=store.retry();if(result?.restored)this.setData({moodEffect:result});}else if(store.loadError)store.load();this.refresh();if(store.loadError)throw Error(store.loadError);wx.showToast({title:'已恢复',icon:'success'});}catch(e){wx.showToast({title:e.message,icon:'none'});}},
 retryArt(){void getApp().loadFinanceArt().then(()=>{this.setData({artError:false});this.refresh();}).catch(e=>wx.showToast({title:e.message,icon:'none'}));},
 nav(e){this.setData({screen:e.currentTarget.dataset.screen,selectedItem:''});wx.pageScrollTo({scrollTop:0,duration:200});this.refresh();},
 chooseWorld(e){this.setData({chapterIndex:0,bookIndex:0,typeIndex:0,practiceChapterIndex:0});this.act(p=>{p.game.world=e.currentTarget.dataset.id;});},
 chooseChapter(e){const index=Number(e.currentTarget.dataset.index);if(!this.data.chapters[index])return;this.setData({chapterIndex:index});this.refresh();},
 continueAdventure(){this.act(p=>G.start(p,G.nextStage(p.game)),()=>getApp().challenge());},
 resume(){getApp().challenge();},
 play(e){const sid=e.currentTarget.dataset.id;if(!G.canPlay(getApp().store.progress.game,sid)){wx.showToast({title:'先完成前一关；普通关80%、Boss90%通关',icon:'none'});return;}this.act(p=>G.start(p,sid),()=>getApp().challenge());},
 expedition(){this.act(p=>{const s=G.expedition(p);G.start(p,s.id);},()=>getApp().challenge());},
 bagTab(e){this.setData({bagTab:e.currentTarget.dataset.tab,selectedItem:''});this.refresh();},
 filterShop(e){this.setData({shopFilter:e.currentTarget.dataset.id});this.refresh();},
 openItem(e){this.setData({selectedItem:e.currentTarget.dataset.id});this.refresh();},
 closeItem(){this.setData({selectedItem:''});this.refresh();},
 noop(){},
 restartGame(){this.startNew610();},
 selectStarter(e){this.act(p=>G.claimStarter(p,e.currentTarget.dataset.id),()=>{if(this.showGuideAfterStarter){this.showGuideAfterStarter=false;this.openGuide();}});},
 runSave610(action,value){if(this.save610Busy)return;this.save610Busy=true;try{getApp().changeSave(action,value);this.setData({screen:'home',chapterIndex:0,selectedItem:'',save610Error:'',moodEffect:null});this.refresh();if(action==='choose'){if(getApp().store.progress.game.starter_claimed)this.openGuide();else this.showGuideAfterStarter=true;}}catch(e){this.setData({save610Error:e.message});this.refresh();wx.showToast({title:'操作尚未完成，原档已保留',icon:'none'});}finally{this.save610Busy=false;}},
 continue610(){this.runSave610('choose','continue');},
 startNew610(){this.confirm610({title:this.data.upgradeInfo.hasLocal?'重新开始新的冒险？':'开始新的冒险？',content:'会先备份并核验本机原档，再建立新的进度。新冒险仍会正常保存，旧进度可从“我的”恢复。',confirmText:'备份开始',cancelText:'取消',success:r=>{if(r.confirm)this.runSave610('choose','new');}});},
 retry610(){this.runSave610('retry');},
 cancel610(){try{getApp().cancelSaveChange();this.setData({save610Error:''});this.refresh();}catch(e){this.setData({save610Error:e.message});}},
 restore610(e){const key=e.currentTarget.dataset.key;this.confirm610({title:'恢复这份本机备份？',content:'会先备份并核验当前进度，再恢复所选存档。两份进度都会保留。',confirmText:'备份恢复',success:r=>{if(r.confirm)this.runSave610('restore',key);}});},
 openGuide(){this.setData({guideStep:0});},nextGuide(){if(this.data.guideStep>=2)this.closeGuide();else this.setData({guideStep:this.data.guideStep+1});},closeGuide(){this.setData({guideStep:-1});},
 openUpdate(){getApp().updates?.prompt(true);},
 confirm610(options){wx.showModal({...options,fail:()=>wx.showToast({title:'确认窗口暂无法打开，请重试',icon:'none'})});},
 async checkCloud610(){await getApp().cloudSave.probe();this.refresh();},
 async syncCloud610(){const cloud=getApp().cloudSave;if(this.data.cloud610?.busy)return;await cloud.probe();this.refresh();const view=cloud.view();if(!view.known){wx.showToast({title:view.text,icon:'none'});return;}if(view.phase==='synced'){wx.showToast({title:'云存档已是最新',icon:'success'});return;}const actions=view.hasCloud?['继续云端进度（先备份本机）','把本机进度另存至云端']:['备份本机进度至当前微信'];wx.showActionSheet({itemList:actions,success:r=>{if(view.hasCloud&&r.tapIndex===0)this.continueCloud610();else wx.showModal({title:'使用本机进度同步？',content:(view.phase==='account'?'本机进度关联另一微信账号。确认后将另存至当前账号。':'会把本机这份进度同步到当前微信。')+'云端原有进度也会保留。',confirmText:'确认同步',success:d=>{if(d.confirm)void cloud.upload({explicit:true}).then(()=>{this.refresh();return cloud.telemetry();}).catch(e=>{this.refresh();wx.showToast({title:e.message,icon:'none'});});}});}});},
 continueCloud610(){this.confirm610({title:'继续当前微信的云存档？',content:'会先下载并校验云档，再完整备份本机当前进度，成功后才恢复云端冒险。',confirmText:'备份继续',success:r=>{if(r.confirm)void getApp().cloudSave.download().then(()=>{this.setData({screen:'home',chapterIndex:0,save610Error:''});this.refresh();}).catch(e=>{this.setData({save610Error:e.message});this.refresh();wx.showToast({title:e.message,icon:'none'});});}});},
 async openAdmin610(){try{const r=await getApp().cloudSave.metrics();this.setData({metrics610:r.days});}catch(e){wx.showToast({title:e.message,icon:'none'});}},closeAdmin610(){this.setData({metrics610:null});},
 arenaCount610(e){this.setData({arenaCountIndex:Number(e.detail.value)});},arenaRate610(e){this.setData({arenaRateIndex:Number(e.detail.value)});},arenaWeak610(e){this.setData({arenaWeak:!!e.detail.value});},
 startArena610(e){const p=getApp().store.progress;if(p.practice&&!p.practice.settled){wx.showModal({title:'先继续未完成的练习',content:'已有一场练习或比武尚未完成，先接着完成，避免覆盖进度。',confirmText:'继续练习',success:r=>{if(r.confirm)getApp().challenge(true);}});return;}const mode=e.currentTarget.dataset.mode,count=[5,10,20][this.data.arenaCountIndex],rate=[60,80,90][this.data.arenaRateIndex],actual=Math.min(count,require('../../utils/arena610').pools[p.game.world].length),target=Math.floor(actual*rate/100);wx.showModal({title:mode==='arena'?'普通比武':'技能比武',content:'本场 '+actual+' 题，对手目标 '+target+' 题。高于目标为胜，相同为平。'+(mode==='arena'?'本场禁用辅助技能。':'本场可使用已装备技能。'),confirmText:'开始比武',success:r=>{if(r.confirm)this.act(p=>require('../../utils/arena610').start(p,{mode,count,rate,weak:this.data.arenaWeak}),()=>getApp().challenge(true));}});},resumeArena610(){getApp().challenge(true);},
 async openGroup610(){if(this.group610Busy)return;this.group610Busy=true;try{const cloud=getApp().cloudSave;try{await cloud?.probe?.();}catch{}const state=cloud?.view(),remote=state?.known?state.group:null,group=remote?{...remote,dateText:new Date(remote.expiresAt-1).toLocaleDateString()}:require('../../data/release610').group;if(!group||Date.now()>=(typeof group.expiresAt==='number'?group.expiresAt:Date.parse(group.expiresAt))){wx.showToast({title:'群二维码已到期，等待管理员更新',icon:'none'});return;}this.setData({group610:group});}finally{this.group610Busy=false;}},closeGroup610(){this.setData({group610:null});},
 learnSkill(id){if(this.purchaseBusy)return;const row=Growth.view(getApp().store.progress.game).skills.find(s=>s.id===id);if(!row||!row.canLearn)return;this.purchaseBusy=true;const operation='learn-'+id+'-'+Date.now()+'-'+Math.random().toString(36).slice(2);wx.showModal({title:(row.rank?'升级':'学习')+row.name,content:'花费 '+row.price+' 金币，永久掌握第 '+(row.rank+1)+' 阶。施法时消耗魔法值。',success:r=>{if(r.confirm)this.act(p=>Growth.learn(p,id,operation));},complete:()=>{this.purchaseBusy=false;}});},
 equipSkill(e){this.act(p=>Growth.equip(p,e.currentTarget.dataset.id));},
 itemAction(e){const id=e.currentTarget.dataset.id,skillId=id.startsWith('skill:')?id.slice(6):null,g=getApp().store.progress.game;if(skillId&&G.modern(g)){this.learnSkill(skillId);return;}if(!skillId&&g.inventory.includes(id)){this.act(p=>G.equip(p,id));return;}if(this.purchaseBusy)return;const item=skillId?Skills.DEFINITIONS[skillId]:G.CATALOG[id];if(!item)return;this.purchaseBusy=true;wx.showModal({title:'兑换'+item.name+(skillId?'卷轴':''),content:'花费 '+item.price+' 金币'+(skillId?'，补充一次使用机会。':'，物品加入背包。'),success:r=>{if(r.confirm)this.act(p=>skillId?Skills.refill(p,skillId):G.buy(p,id),()=>wx.showToast({title:skillId?'技能已补充':'已加入背包',icon:'success'}));},complete:()=>{this.purchaseBusy=false;}});},
 setWish(e){const id=e.currentTarget.dataset.id;if(G.CATALOG[id])this.act(p=>{p.game.wishlist=id;},()=>wx.showToast({title:'已设为攒钱目标',icon:'success'}));},
 queueSkill(e){this.act(p=>Skills.queue(p,e.currentTarget.dataset.id));},
 refillInk(e){this.act(p=>Skills.refill(p,e.currentTarget.dataset.id,true),()=>wx.showToast({title:'技能次数 +1',icon:'success'}));},
 openMood(){this.setData({screen:'bag',bagTab:'shop',shopFilter:'consumable',selectedItem:''});this.refresh();wx.pageScrollTo({scrollTop:0,duration:0});},
 useMood(e){this.act(p=>G.Adventure.use(p,e.currentTarget.dataset.id),result=>this.setData({moodEffect:result}));},
 closeMoodEffect(){this.setData({moodEffect:null});},
 restMood(){this.act(p=>G.Adventure.rest(p),r=>wx.showToast({title:r.ready===false?'休息已开始，10分钟后可领取':'心情恢复了',icon:'none'}));},
 openShop(){this.setData({screen:'bag',bagTab:'shop',selectedItem:''});this.refresh();wx.pageScrollTo({scrollTop:0,duration:150});},
 selectBook(e){this.setData({bookIndex:Number(e.detail.value)});},
 selectType(e){this.setData({typeIndex:Number(e.detail.value)});},
 selectPracticeChapter(e){this.setData({practiceChapterIndex:Number(e.detail.value)});},
 practice(e){const mode=e.currentTarget.dataset.mode,p=getApp().store.progress,book=this.data.books[this.data.bookIndex].id,type=this.data.types[this.data.typeIndex],chapter=this.data.practiceChapters[this.data.practiceChapterIndex];const ids=G.META.filter(q=>q.book_id.startsWith(this.data.world.prefix)&&(!book||q.book_id===book)&&(type==='全部题型'||type===q.type)&&(chapter==='全部章节'||chapter===q.chapter)&&(mode!=='wrong'||p.wrong_book.includes(q.id))&&(mode!=='favorites'||p.favorites.includes(q.id))).map(q=>q.id);this.act(p=>G.startPractice(p,ids,mode==='wrong'?'错题复习':mode==='favorites'?'收藏复习':'自由刷题',mode==='wrong'?'review':'basic'),()=>getApp().challenge(true));},
 resumePractice(){getApp().challenge(true);},
 openHunting(){if(getApp().store.pending||getApp().store.loadError){wx.showToast({title:'请先处理存档保存或读取',icon:'none'});return;}wx.navigateTo({url:'/pages/hunting/index'});},
 openTown(){this.setData({screen:'town',selectedItem:''});this.refresh();wx.pageScrollTo({scrollTop:0,duration:150});},
 openFormulas(){this.setData({screen:'formulas'});this.refresh();wx.pageScrollTo({scrollTop:0,duration:150});},
 seeFormulas(e){this.act(p=>F.seeFormulas(p,e.currentTarget.dataset.chapter));},
 viewStory(e){const id=e.currentTarget.dataset.id;this.act(p=>F.seeStory(p,id),()=>{const info=F.storyFor(getApp().store.progress.game,id);this.setData({townStory:{name:info.act.name,lines:[...info.story,...(info.completed?info.completion_story:[])]}});});},
 closeStory(){this.setData({townStory:null});},
 buildTown(e){this.act(p=>F.upgradeBuilding(p,e.currentTarget.dataset.id),()=>wx.showToast({title:'小镇建筑升级了！',icon:'success'}));},
 recruitSpirit(e){if(G.modern(getApp().store.progress.game)){this.openHunting();return;}this.act(p=>F.recruit(p,e.currentTarget.dataset.id));},
 equipSpirit(e){this.act(p=>G.modern(p.game)?G.Hunting.equipSpirit(p,e.currentTarget.dataset.id):F.equipCompanion(p,e.currentTarget.dataset.id));},
 commission(e){this.act(p=>G.startCommission(p,e.currentTarget.dataset.id),()=>getApp().challenge(true));},
 claimCommission(e){this.act(p=>F.claimCommission(p,e.currentTarget.dataset.id),()=>wx.showToast({title:'收到NPC明信片',icon:'success'}));},
 rescue(){if(!this.data.rescueCount){wx.showToast({title:'当前科目救援已完成！',icon:'success'});return;}this.act(p=>G.startRescue(p),()=>getApp().challenge(true));},
 utility(e){const utility=e.currentTarget.dataset.utility;if(utility==='town'){this.openTown();return;}if(utility==='formulas'){this.openFormulas();return;}if(utility==='review'){this.setData({screen:'study'});this.refresh();return;}this.setData({screen:'tools',tool:utility});this.refresh();},
 scratch(e){this.act(p=>{F.ensureExpansion(p.game).tools.scratch=e.detail.value;});},
 startFocus(){this.act(p=>{const t=F.ensureExpansion(p.game).tools;t.focus_started_at=Date.now()/1000;t.focus_seconds=1500;});},
 stopFocus(){this.act(p=>{F.ensureExpansion(p.game).tools.focus_started_at=null;});},
 refreshFocus(){if(!getApp().store||this.data.upgradePending)return;if(G.modern(getApp().store.progress.game)){const r=G.Adventure.restStatus(getApp().store.progress.game);this.setData({restStarted:r.started,restRemaining:r.remaining,restText:Math.floor(r.remaining/60)+':'+String(r.remaining%60).padStart(2,'0')});}const t=getApp().store.progress.game.finance_expansion?.tools;if(!t)return;const remaining=t.focus_started_at?Math.max(0,t.focus_seconds-Math.floor(Date.now()/1000-t.focus_started_at)):t.focus_seconds;this.setData({focusRemaining:remaining,focusText:String(Math.floor(remaining/60)).padStart(2,'0')+':'+String(remaining%60).padStart(2,'0'),focusStarted:!!t.focus_started_at});},
 toggleTheme(){this.act(p=>{p.theme=p.theme==='dark'?'light':'dark';});},
 exportBackup(){try{const text=getApp().store.export(),path=wx.env.USER_DATA_PATH+'/小圆冒险存档.json';wx.getFileSystemManager().writeFile({filePath:path,data:text,encoding:'utf8',success:()=>{if(wx.shareFileMessage)wx.shareFileMessage({filePath:path,fail:()=>wx.showToast({title:'备份已保存到小程序本地',icon:'none'})});else wx.setClipboardData({data:text});},fail:()=>wx.showToast({title:'备份保存失败',icon:'none'})});}catch(e){wx.showToast({title:e.message,icon:'none'});}},
 importBackup(){wx.chooseMessageFile({count:1,type:'file',extension:['json'],success:r=>wx.getFileSystemManager().readFile({filePath:r.tempFiles[0].path,encoding:'utf8',success:f=>wx.showModal({title:'恢复文件备份',content:'会先备份并核验当前进度，再恢复所选文件。当前备份仍可从“我的”恢复。',confirmText:'备份恢复',success:d=>{if(d.confirm){try{const value=JSON.parse(f.data);this.runSave610('import',value);}catch(e){wx.showToast({title:'备份文件格式无效',icon:'none'});}}}}),fail:()=>wx.showToast({title:'备份文件无法读取',icon:'none'})}),fail:()=>{}});}
});
