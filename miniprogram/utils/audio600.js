// 每页仅复用一个BGM和一个短音效上下文；不在逐题渲染中重新创建或重播背景音乐。
const media=require('../data/hunting600');
function create(api,load,{onError=()=>{}}={}){
 let music=null,effect=null,disposed=false,generation=0,track='',settings={music:true,sound:true};
 const pending=new Map();
 function resource(ref){if(!ref)return Promise.reject(Error('未配置音频资源'));if(!pending.has(ref.package)){const promise=Promise.resolve().then(()=>load(ref.package)).catch(e=>{pending.delete(ref.package);throw e;});pending.set(ref.package,promise);}return pending.get(ref.package);}
 function context(short){if(disposed)throw Error('音频页面已关闭');if(typeof api.createInnerAudioContext!=='function')throw Error('当前微信暂不支持音频播放');const c=api.createInnerAudioContext({useWebAudioImplement:short});c.loop=!short;c.volume=short?.75:.32;c.obeyMuteSwitch=true;if(typeof c.onError==='function')c.onError(()=>{if(!disposed){if(!short){track='';generation++;}onError('声音暂未播放，请检查静音设置或重试');}});return c;}
 async function background(id='default'){
  if(disposed||!settings.music)return false;
  if(track===id&&music)return true;
  track=id;const token=++generation,ref=media.bgm[id]||media.bgm.default;
  try{await resource(ref);if(disposed||token!==generation||!settings.music)return false;if(!music)music=context(false);else music.stop();music.src=ref.path;music.play();return true;}catch{if(!disposed&&token===generation){track='';onError('音乐暂未加载，请重试');}return false;}
 }
 let effectGeneration=0;
 async function sound(name){if(disposed||!settings.sound)return false;const token=++effectGeneration,ref=media.audio[name];try{await resource(ref);if(disposed||token!==effectGeneration||!settings.sound)return false;if(!effect)effect=context(true);else effect.stop();effect.src=ref.path;effect.play();return true;}catch{if(!disposed&&token===effectGeneration)onError('音效暂未加载，请重试');return false;}}
 function configure(value){settings={...settings,...value};if(!settings.music){generation++;track='';music?.stop();}if(!settings.sound){effectGeneration++;effect?.stop();}}
 function destroy(){if(disposed)return;disposed=true;generation++;effectGeneration++;for(const c of [music,effect])if(c){try{c.stop();}finally{c.destroy();}}music=effect=null;pending.clear();}
 return {background,sound,configure,destroy};
}
module.exports={create};
