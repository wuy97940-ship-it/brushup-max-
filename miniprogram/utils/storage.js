// 整个存档以一次同步写入提交，成功后才更新内存和播放动画。
const G=require('./game');
const Migration=require('./migration');
const KEY='xiaoyuan-original-public-v02';
const valid=p=>Migration.validProgress(p,G);
function createStore(api){
 let progress=Migration.normalizeProgress(G.defaultProgress(),G),pending=null,seq=0,loadError='';
 function read(){try{const value=api.getStorageSync(KEY);if(value){const normalized=Migration.normalizeProgress(value.progress,G);if(!normalized||!valid(normalized))throw Error('存档内容损坏或题库不匹配');let nextSeq=value.seq||0;if(normalized!==value.progress){api.setStorageSync(KEY,{schema_version:1,seq:nextSeq+1,progress:normalized});nextSeq++;}progress=normalized;seq=nextSeq;}else {progress=Migration.normalizeProgress(G.defaultProgress(),G);seq=0;}loadError='';}catch(e){loadError='已有存档无法读取，已保留原数据。请重试读取或导入备份。';}}
 read();
 return {
  get progress(){return progress;},get pending(){return !!pending;},get loadError(){return loadError;},
  load(){if(pending)throw Error('请先重试保存。');read();return progress;},
  commit(change){if(loadError)throw Error(loadError);if(pending)throw Error('上次保存未成功，请先重试保存。');const candidate=G.copy(progress);const result=change(candidate);const envelope={schema_version:1,seq:seq+1,progress:candidate};pending={envelope,result};return this.retry();},
  retry(){if(!pending)return null;try{api.setStorageSync(KEY,pending.envelope);}catch(e){throw Error('保存失败，请释放手机存储空间后重试；奖励尚未领取。');}progress=pending.envelope.progress;seq=pending.envelope.seq;const result=pending.result;pending=null;loadError='';return result;},
  export(){if(pending||loadError)throw Error('请先处理保存或读取失败。');return JSON.stringify({schema_version:1,bank_family:Migration.BASELINE.family,progress});},
  import(text){let p=JSON.parse(text);p=Migration.normalizeProgress(p.progress||p,G);if(!valid(p))throw Error('备份与本题库不匹配，私人教材版和公开原创版使用各自备份。');if(pending)throw Error('请先重试保存。');G.claimGrowth(p);pending={envelope:{schema_version:1,seq:seq+1,progress:p},result:true};const result=this.retry();loadError='';return result;}
 };
}
module.exports={KEY,createStore,valid};
