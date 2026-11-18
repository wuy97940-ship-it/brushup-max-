// 官方更新事件只描述下载状态；当前题先存好，用户确认后才重启。
function createUpdates(api,{save,canPrompt=()=>true,changed=()=>{}}){
 let status='checking',foreground=false,prompted=false,dialog=false,manager=null;
 const view=()=>({status,ready:status==='ready',text:status==='ready'?'新版本已准备好':status==='failed'?'新版下载失败，可稍后重试':status==='available'?'正在下载新版本':status==='unsupported'?'请在微信中检查更新':'当前版本 '+require('../data/release610').version});
 function publish(){changed(view());}
 function prompt(manual=false){
  if(status!=='ready'){if(manual)api.showToast({title:view().text,icon:'none'});return;}
  if(dialog||!foreground||(!manual&&prompted)||!canPrompt())return;
  prompted=true;dialog=true;
  api.showModal({title:'新版本已准备好',content:'更新会保留学习存档。立即更新前会先保存当前题，重启后即可使用新版。',cancelText:'稍后',confirmText:'立即更新',
   success:r=>{dialog=false;if(!r.confirm)return;try{save();manager.applyUpdate();}catch(e){api.showModal({title:'当前学习还未保存',content:'请先重试保存，再从“我的”打开更新。'+(e.message||''),showCancel:false});}},fail:()=>{dialog=false;}});
 }
 if(typeof api.getUpdateManager==='function'){
  manager=api.getUpdateManager();
  manager.onCheckForUpdate(r=>{if(status==='ready')return;status=r.hasUpdate?'available':'current';publish();});
  manager.onUpdateReady(()=>{status='ready';publish();prompt();});
  manager.onUpdateFailed(()=>{status='failed';publish();});
 }else status='unsupported';
 return {view,prompt,show(){if(!foreground)prompted=false;foreground=true;prompt();},hide(){foreground=false;},notify(){publish();prompt();}};
}
module.exports={createUpdates};
