const {createStore}=require('./utils/storage');
const {routes}=require('./data/questions');
const G=require('./utils/game');
const Art=require('./utils/assets');
App({
 onLaunch(){this.store=createStore(wx);this.financeArtReady=!Art.packages.length;this.loadingArts=null;if(!this.store.loadError&&G.needsGrowth(this.store.progress)){try{this.store.commit(p=>G.claimGrowth(p));}catch(e){/* 首页显示待重试存档，候选奖励不会重算。 */}}void this.loadFinanceArt().catch(()=>{});},
 // 静态跨包模块路径由微信分包异步化机制下载；加载完成后才开放图片路径。
 loadFinanceArt(){if(this.financeArtReady)return Promise.resolve();if(this.loadingArts)return this.loadingArts;if(typeof require.async!=='function')return Promise.reject(Error('请更新微信后加载小镇图片。'));this.loadingArts=require.async('./packages/financeArt/bank.js').then(()=>{this.financeArtReady=true;this.loadingArts=null;}).catch(()=>{this.loadingArts=null;throw Error('小镇图片暂未加载，请保持联网后重试。');});return this.loadingArts;},
 returnHome(){
  const pages=getCurrentPages();
  if(pages.length>1&&pages[0].route==='pages/home/index')wx.navigateBack({delta:pages.length-1});
  else wx.redirectTo({url:'/pages/home/index'});
 },
 challenge(practice=false,redirect=false){
  const p=this.store.progress,a=practice?p.practice:p.game.active;
  if(!a)return;
  const route=routes[a.qids[Math.min(a.index,a.qids.length-1)]];
  const url=route+'?practice='+(practice?'1':'0');
  wx[redirect?'redirectTo':'navigateTo']({url,fail:()=>wx.showToast({title:'题目加载失败，请重试',icon:'none'})});
 }
});
