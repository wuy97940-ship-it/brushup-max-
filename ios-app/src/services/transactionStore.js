// 一次完整JSON写入是提交边界，重试不重复抽奖、建造或领取。
const G=require('../shared/utils/game');
const Migration=require('../shared/utils/migration');
const KEY='xiaoyuan-ios-original-v01';
const fingerprint=G.CAMPAIGN.bank_fingerprint;
const normalizeProgress=p=>Migration.normalizeProgress(p,G);
const valid=p=>Migration.validProgress(p,G);
function createStore(api){
 let progress=normalizeProgress(G.defaultProgress()),seq=0,pending=null,loadError='',writing=false;
 return {
  get progress(){return progress;},get pending(){return !!pending;},get loadError(){return loadError;},get writing(){return writing;},
  async load(){
   if(writing||pending)throw Error('请先处理正在进行的保存。');
   try{const raw=await api.getItem(KEY);if(raw){const value=JSON.parse(raw),normalized=normalizeProgress(value.progress);if(!valid(normalized))throw Error('存档损坏或题库不匹配');let nextSeq=value.seq||0;if(normalized!==value.progress){nextSeq++;await api.setItem(KEY,JSON.stringify({schema_version:1,bank_fingerprint:fingerprint,seq:nextSeq,progress:normalized}));}progress=normalized;seq=nextSeq;}else{progress=normalizeProgress(G.defaultProgress());seq=0;}loadError='';}
   catch{loadError='已有存档无法读取，原数据仍保留。请重试读取或导入本题库的备份。';}return progress;
  },
  async commit(change){
   if(loadError)throw Error(loadError);if(writing)throw Error('正在保存，请稍候。');if(pending)throw Error('上次保存未成功，请先重试保存。');
   const candidate=G.copy(progress),result=change(candidate);
   pending={envelope:{schema_version:1,bank_fingerprint:fingerprint,seq:seq+1,progress:candidate},result};return this.retry();
  },
  async retry(){
   if(writing)throw Error('正在保存，请稍候。');if(!pending)return null;writing=true;
   try{await api.setItem(KEY,JSON.stringify(pending.envelope));}
   catch{throw Error('保存失败。请释放设备存储空间后重试；已保留本次操作，重试不会重复抽奖或领取。');}
   finally{writing=false;}
   progress=pending.envelope.progress;seq=pending.envelope.seq;const result=pending.result;pending=null;loadError='';return result;
  },
  export(){if(pending||writing||loadError)throw Error('请先处理保存或读取失败。');return JSON.stringify({schema_version:1,bank_family:Migration.BASELINE.family,bank_fingerprint:fingerprint,seq,progress},null,2);},
  async import(text){
   if(pending||writing)throw Error('请先处理本次保存。');let value;try{value=JSON.parse(text);}catch{throw Error('备份不是有效的JSON文件。');}
   const p=normalizeProgress(value.progress||value);if(!valid(p))throw Error('备份损坏或属于另一题库。公开原创版与私人教材版不能互导进度。');
   G.claimGrowth(p);pending={envelope:{schema_version:1,bank_fingerprint:fingerprint,seq:seq+1,progress:G.copy(p)},result:true};return this.retry();
  }
 };
}
module.exports={KEY,createStore,valid,normalizeProgress};
