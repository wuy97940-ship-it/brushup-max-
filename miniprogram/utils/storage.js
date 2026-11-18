// 整个存档以一次同步写入提交，成功后才更新内存和播放动画。
const G=require('./game');
const Migration=require('./migration');
const Chunks=require('./storage_chunks600');
const KEY='xiaoyuan-original-public-v02';
const KEY600='xiaoyuan-adventure-6.0.0';
const valid=p=>Migration.validProgress(p,G);
function createStore(api,{fresh600=false,readOnly=false}={}){
 const storageKey=fresh600?KEY600:KEY,fresh=()=>fresh600?require('./game600').defaultProgress600():G.defaultProgress();
 function freeze(o){if(o&&typeof o==='object'&&!Object.isFrozen(o)){Object.freeze(o);Object.values(o).forEach(freeze);}return o;}
 const campaign=fresh600?freeze(G.copy(G.CAMPAIGN)):null;
 function bind(p){if(fresh600)p.game.campaign=campaign;return p;}
 function portable(p){if(!fresh600)return p;const game={...p.game};delete game.campaign;game.campaign_ref=campaign.bank_fingerprint;return {...p,game};}
 function hydrate(p){if(!fresh600)return p;const result=G.copy(p);if(result?.game?.campaign_ref){if(result.game.campaign_ref!==campaign.bank_fingerprint||result.game.campaign)throw Error('题库指纹不匹配');result.game.campaign=campaign;delete result.game.campaign_ref;}return result;}
 function cloneProgress(p){if(!fresh600)return G.copy(p);const data=portable(p),result=G.copy(data);delete result.game.campaign_ref;return bind(result);}
 function envelope(p,n,meta=metadata){const value={schema_version:fresh600?6:1,seq:n,progress:portable(p)};if(Object.keys(meta).length)value.metadata=G.copy(meta);return value;}
 const accepted=p=>valid(p)&&(!fresh600||p.game.ruleset==='6.0.0');
 // 已有有效档直接读取；仅空档或首次读取失败才建立隔离的默认进度。
 let progress=null,pending=null,seq=0,loadError='',persistedPointer=null,metadata={};
 function writable(){if(readOnly)throw Error('请先确认升级存档选择，当前只读保护原存档。');}
 function checkedMetadata(value){if(value==null)return {};if(typeof value!=='object'||Array.isArray(value))throw Error('存档附加信息无效');return G.copy(value);}
 function read(){try{const value=fresh600?Chunks.read(api,storageKey,v=>{persistedPointer=v;}):api.getStorageSync(storageKey);if(value){const normalized=Migration.normalizeProgress(hydrate(value.progress),G);if(!normalized||!accepted(normalized))throw Error('存档内容损坏或题库不匹配');let nextSeq=value.seq||0;if(!Number.isSafeInteger(nextSeq)||nextSeq<0)throw Error('存档序列无效');const nextMetadata=checkedMetadata(value.metadata);const changed=fresh600?JSON.stringify(portable(normalized))!==JSON.stringify(value.progress):normalized!==value.progress;if(changed&&!readOnly){if(fresh600)persistedPointer=Chunks.write(api,storageKey,envelope(normalized,nextSeq+1,nextMetadata),{},persistedPointer);else api.setStorageSync(storageKey,envelope(normalized,nextSeq+1,nextMetadata));nextSeq++;}progress=bind(normalized);seq=nextSeq;metadata=nextMetadata;}else {progress=bind(Migration.normalizeProgress(fresh(),G));seq=0;metadata={};}loadError='';}catch(e){if(!progress)progress=bind(Migration.normalizeProgress(fresh(),G));loadError='已有存档无法读取，已保留原数据。请重试读取或导入备份。';}}
 read();
 return {
  get progress(){return progress;},get pending(){return !!pending;},get loadError(){return loadError;},get readOnly(){return readOnly;},get metadata(){return G.copy(metadata);},
  load(){if(pending)throw Error('请先重试保存。');read();return progress;},
  commit(change){writable();if(loadError)throw Error(loadError);if(pending)throw Error('上次保存未成功，请先重试保存。');const candidate=cloneProgress(progress);const result=change(candidate);pending={envelope:envelope(candidate,seq+1),memory:candidate,result};return this.retry();},
  retry(){writable();if(!pending)return null;try{if(fresh600)persistedPointer=Chunks.write(api,storageKey,pending.envelope,pending,persistedPointer);else api.setStorageSync(storageKey,pending.envelope);}catch(e){throw Error('保存失败，请释放手机存储空间后重试；奖励尚未领取。');}progress=pending.memory;seq=pending.envelope.seq;metadata=checkedMetadata(pending.envelope.metadata);const result=pending.result;pending=null;loadError='';return result;},
  snapshot(){if(pending||loadError)throw Error('请先处理保存或读取失败。');return G.copy(envelope(progress,seq));},
  setMetadata(value){writable();if(pending||loadError)throw Error('请先处理保存或读取失败。');const meta=checkedMetadata(value),candidate=cloneProgress(progress);pending={envelope:envelope(candidate,seq+1,meta),memory:candidate,result:true};return this.retry();},
  export(){if(pending||loadError)throw Error('请先处理保存或读取失败。');const value={schema_version:fresh600?6:1,bank_family:Migration.BASELINE.family,progress:portable(progress)};if(Object.keys(metadata).length)value.metadata=G.copy(metadata);return JSON.stringify(value);},
  // 6.1备份/云档精确恢复，不把恢复当新成绩或再次领取成长奖励。
  replaceSnapshot(value){writable();if(pending)throw Error('请先重试保存。');if(!value||value.schema_version!==(fresh600?6:1))throw Error('备份版本不匹配。');const p=Migration.normalizeProgress(hydrate(value.progress),G);if(!accepted(p))throw Error('备份与本题库或6.0新局不匹配，请使用同版本备份。');const meta=checkedMetadata(value.metadata);pending={envelope:envelope(p,seq+1,meta),memory:bind(p),result:true};return this.retry();},
  import(text){writable();let p=JSON.parse(text);p=Migration.normalizeProgress(hydrate(p.progress||p),G);if(!accepted(p))throw Error('备份与本题库或6.0新局不匹配，请使用同版本备份。');if(pending)throw Error('请先重试保存。');G.claimGrowth(p);p=bind(p);pending={envelope:envelope(p,seq+1),memory:p,result:true};const result=this.retry();loadError='';return result;}
 };
}
module.exports={KEY,KEY600,createStore,valid};
