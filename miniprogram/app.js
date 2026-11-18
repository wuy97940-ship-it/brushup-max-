const {createUpgrade610}=require('./utils/upgrade610');
const {createUpdates}=require('./utils/update610');
const {createCloud}=require('./utils/cloud610');
const {routes,stageRoutes}=require('./data/questions');
const G=require('./utils/game600');
const Art=require('./utils/assets');
App({
 onLaunch(){
  this.backgroundReady=false;this.foreground=false;this.cloudTimer=null;
  this.upgrade=createUpgrade610(wx);this.store=this.upgrade.openSession().store;
  this.updates=createUpdates(wx,{save:()=>this.saveForUpdate(),canPrompt:()=>!!this.store&&!this.upgrade.status().pending,changed:()=>this.notifyHome()});
  this.huntingMedia=require('./utils/hunting_media600').create();this.questionBanks=require('./data/bank_loaders600').create();this.financeArtReady=!Art.packages.length;this.loadingArts=null;this.outfit610Ready={};this.loadingOutfit610={};
  this.cloudSave=createCloud(wx,{getStore:()=>this.store,getUpgrade:()=>this.upgrade,adopt:value=>this.changeSave('cloud',value),changed:()=>this.notifyHome()});
 },
 onShow(){this.foreground=true;this.settleLogin();this.updates?.show();this.scheduleCloud();},
 onHide(){this.foreground=false;if(this.cloudTimer!==null)clearTimeout(this.cloudTimer);this.cloudTimer=null;this.updates?.hide();},
 // onReady确认首屏已经渲染，再让自动云探测/同步进入下一个任务；显式操作不延迟。
 pageReady(){if(this.backgroundReady)return;this.backgroundReady=true;this.scheduleCloud();},
 scheduleCloud(){if(!this.backgroundReady||!this.foreground||!this.cloudSave||this.cloudTimer!==null)return;this.cloudTimer=setTimeout(()=>{this.cloudTimer=null;if(!this.foreground)return;if(this.store)void this.cloudSave.upload().then(()=>this.cloudSave.telemetry()).catch(()=>{});else void this.cloudSave.probe();},0);},
 settleLogin(){const store=this.store;if(!store||store.pending||store.loadError||!G.modern(store.progress.game)||!store.progress.game.starter_claimed)return;const state=store.progress.game.growth600;if(state.last_seen_day>=G.Growth600.dayKey(Date.now())&&state.settled_through)return;try{store.commit(p=>{const result=G.Growth600.login(p.game);G.Hunting.failIfDead(p);return result;});}catch(e){wx.showToast({title:'离线状态尚未保存，请重试',icon:'none'});}},
 notifyHome(){const page=typeof getCurrentPages==='function'&&getCurrentPages().find(p=>p.route==='pages/home/index');if(page?.homeVisible)page.refresh();},
 changeSave(action,value){this.store=null;try{const result=action==='choose'?this.upgrade.choose(value):action==='restore'?this.upgrade.restore(value):action==='import'?this.upgrade.importSnapshot(value):action==='cloud'?this.upgrade.adoptCloud(value):this.upgrade.retry();this.store=result;this.settleLogin();this.updates?.notify();return result;}catch(e){const state=this.upgrade.status();if(!state.pending&&!state.loadError)this.store=this.upgrade.openStore();throw e;}},
 cancelSaveChange(){this.upgrade.cancel();const status=this.upgrade.status();if(!status.pending&&!status.loadError)this.store=this.upgrade.openStore();},
 saveForUpdate(){const store=this.store;if(!store||this.upgrade.status().pending)throw Error('请先完成存档选择。');if(store.pending)store.retry();if(store.loadError)throw Error(store.loadError);const page=getCurrentPages().slice(-1)[0];page?.flushForUpdate?.();if(store.pending||store.loadError)throw Error('存档尚未保存。');const before=store.snapshot();store.load();if(store.loadError||JSON.stringify(store.snapshot())!==JSON.stringify(before))throw Error('存档读回未通过，请先处理存档。');},
 // 静态跨包模块路径由微信分包异步化机制下载；加载完成后才开放图片路径。
 loadFinanceArt(){if(this.financeArtReady)return Promise.resolve();if(this.loadingArts)return this.loadingArts;if(typeof require.async!=='function')return Promise.reject(Error('请更新微信后加载冒险图片。'));this.loadingArts=Promise.all([require.async('./packages/financeArt/bank.js'),require.async('./packages/adventureArt/bank.js'),require.async('./packages/adventureSupply/bank.js')]).then(()=>{this.financeArtReady=true;this.loadingArts=null;}).catch(()=>{this.loadingArts=null;throw Error('冒险图片暂未加载，请保持联网后重试。');});return this.loadingArts;},
 loadOutfitArt610(name){
  const loaders={outfitArt610:()=>require.async('./packages/outfitArt610/bank.js'),outfitArtTuan610:()=>require.async('./packages/outfitArtTuan610/bank.js'),outfitHats610a:()=>require.async('./packages/outfitHats610a/bank.js'),outfitHats610b:()=>require.async('./packages/outfitHats610b/bank.js'),outfitHats610c:()=>require.async('./packages/outfitHats610c/bank.js')};
  if(!loaders[name])return Promise.reject(Error('装扮素材不存在。'));if(this.outfit610Ready[name])return Promise.resolve();if(this.loadingOutfit610[name])return this.loadingOutfit610[name];if(typeof require.async!=='function')return Promise.reject(Error('请更新微信后加载装扮。'));
  this.loadingOutfit610[name]=loaders[name]().then(()=>{this.outfit610Ready[name]=true;delete this.loadingOutfit610[name];}).catch(()=>{delete this.loadingOutfit610[name];throw Error('装扮图片暂未加载，请保持联网后重试。');});return this.loadingOutfit610[name];
 },
 returnHome(){
  const pages=getCurrentPages();
  if(pages.length>1&&pages[0].route==='pages/home/index')wx.navigateBack({delta:pages.length-1});
  else wx.redirectTo({url:'/pages/home/index'});
 },
 challenge(practice=false,redirect=false){
  if(!this.store){this.returnHome();return;}const p=this.store.progress,a=practice?p.practice:p.game.active;
  if(!a)return;
  const route=!practice&&stageRoutes?.[a.stage_id]||routes[a.qids[Math.min(a.index,a.qids.length-1)]];
  const url=route+'?practice='+(practice?'1':'0');
  wx[redirect?'redirectTo':'navigateTo']({url,fail:()=>wx.showToast({title:'题目加载失败，请重试',icon:'none'})});
 }
});
