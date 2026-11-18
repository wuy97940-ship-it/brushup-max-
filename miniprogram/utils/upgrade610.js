// 版本选择前只读；完整操作意图、原档备份核验后，最后才提交当前档指针。
const {createStore,KEY,KEY600}=require('./storage');
const Chunks=require('./storage_chunks600');
const RELEASE='6.1.0',JOURNAL='xiaoyuan-adventure:upgrade610:pending';
const BACKUPS='xiaoyuan-adventure:backups610',ARCHIVE='xiaoyuan-adventure:backup610:',ACTIVE='xiaoyuan-adventure:active610';
const copy=value=>JSON.parse(JSON.stringify(value));
const fingerprint=value=>Chunks.checksum(JSON.stringify(value));
const isObject=value=>value&&typeof value==='object'&&!Array.isArray(value);

function createUpgrade610(api,{makeId=()=>Date.now().toString(36)+'-'+Math.random().toString(36).slice(2)+'-'+Math.random().toString(36).slice(2)}={}){
 let pending=null;
 const raw=key=>(key===KEY600?Chunks.read(api,key):api.getStorageSync(key))||null;
 function normalized(value,key){
  const store=createStore({getStorageSync:k=>k===key?copy(value):''},{fresh600:key===KEY600,readOnly:true});
  if(store.loadError)throw Error(store.loadError);
  return store.snapshot();
 }
 function current(){
  const selected=api.getStorageSync(ACTIVE);
  if(selected){if(!isObject(selected)||![KEY,KEY600].includes(selected.key))throw Error('当前存档引用损坏，请保留原数据。');const value=raw(selected.key);if(!value)throw Error('当前存档引用缺失，请恢复备份。');return {key:selected.key,raw:value,snapshot:normalized(value,selected.key)};}
  const six=raw(KEY600),legacy=six?null:raw(KEY),key=six?KEY600:legacy?KEY:KEY600,value=six||legacy;
  return {key,raw:value,snapshot:normalized(value,key)};
 }
 function accepted(value){const a=value?.metadata?.release610;return a?.version===RELEASE&&a.accepted===true&&typeof a.runId==='string'&&!!a.runId;}
 function registry(){const value=api.getStorageSync(BACKUPS);if(!value)return [];if(!Array.isArray(value)||value.some(r=>!isObject(r)||typeof r.key!=='string'||!r.key.startsWith(ARCHIVE)))throw Error('备份目录损坏，请保留原数据。');return copy(value);}
 function operation(){
  if(pending)return pending;
  const value=Chunks.read(api,JOURNAL);if(!value)return null;
  const op=value.progress?.operation;
  if(!isObject(op)||op.version!==RELEASE||!['continue','new','restore','import','cloud'].includes(op.choice)||![KEY,KEY600].includes(op.sourceKey)||![KEY,KEY600].includes(op.targetKey)||typeof op.id!=='string'||!op.id||op.backupKey!==ARCHIVE+op.id)throw Error('升级恢复记录损坏，请保留原存档。');
  normalized(op.target,op.targetKey);
  pending={op,journalPointer:api.getStorageSync(JOURNAL)};
  return pending;
 }
 function archiveValue(key,expectedChecksum){
  const value=Chunks.read(api,key),payload=value?.progress?.archive;
  if(!isObject(payload)||![KEY,KEY600].includes(payload.sourceKey)||fingerprint(payload.original)!==payload.checksum||(expectedChecksum&&payload.checksum!==expectedChecksum))throw Error('备份读回校验失败，原存档已保留。');
  return payload;
 }
 function clearJournal(){
  const pointer=api.getStorageSync(JOURNAL);
  // 已提交后清理失败不撤销新档；下次凭操作标识识别已完成事务。
  try{api.removeStorageSync(JOURNAL);}catch{return;}
  if(pointer?.parts?.prefix?.startsWith(JOURNAL+':part:'))for(let i=0;i<pointer.parts.count;i++){try{api.removeStorageSync(pointer.parts.prefix+':'+i);}catch{}}
  pending=null;
 }
 function openCheckedStore(state){
  if(!accepted(state.snapshot))throw Error('请先选择继续原存档或备份后重新开始。');
  return createStore(api,{fresh600:state.key===KEY600});
 }
 function openStore(){return openCheckedStore(current());}
 function inspect(){
  const state=current(),work=operation(),unfinished=!!work&&(state.key!==work.op.targetKey||state.raw?.metadata?.release610?.operationId!==work.op.id);
  return {state,status:{pending:!accepted(state.snapshot)||unfinished,hasLocal:!!state.raw,legacy:state.key===KEY,waitingChoice:work?.op.choice||null,loadError:'',backups:registry().map(({key,createdAt,reason})=>({key,createdAt,reason}))}};
 }
 const failedStatus=e=>({pending:true,hasLocal:true,loadError:e.message,backups:[]});
 function apply(){
  const work=operation();if(!work)throw Error('没有待重试的存档操作。');const op=work.op;
  const actual=raw(op.targetKey);
  if(actual?.metadata?.release610?.operationId===op.id){
   if(current().key!==op.targetKey){
    if(op.sourceKey!==op.targetKey&&fingerprint(raw(op.sourceKey))!==op.sourceChecksum)throw Error('当前档已变化，请保留两份进度并重新核对。');
    api.setStorageSync(ACTIVE,{key:op.targetKey,operationId:op.id});
   }
   clearJournal();return openStore();
  }
  if(fingerprint(raw(op.sourceKey))!==op.sourceChecksum||fingerprint(actual)!==op.targetBeforeChecksum)throw Error('本机进度已经变化，请保留当前档并重新核对。');
  const journal={schema_version:6,seq:1,progress:{operation:op}};
  work.journalPointer=Chunks.write(api,JOURNAL,journal,work.journalPlan||(work.journalPlan={}),work.journalPointer);
  const persisted=Chunks.read(api,JOURNAL);
  if(fingerprint(persisted)!==fingerprint(journal))throw Error('操作记录读回失败，尚未建立新局。');
  if(op.sourceRaw){
   const archive={schema_version:6,seq:1,progress:{archive:{sourceKey:op.sourceKey,original:op.sourceRaw,checksum:op.sourceChecksum,createdAt:op.createdAt}}};
   Chunks.write(api,op.backupKey,archive,work.backupPlan||(work.backupPlan={}),api.getStorageSync(op.backupKey));
   archiveValue(op.backupKey,op.sourceChecksum);
   const items=registry();
   if(!items.some(row=>row.key===op.backupKey)){
    items.push({key:op.backupKey,sourceKey:op.sourceKey,checksum:op.sourceChecksum,createdAt:op.createdAt,reason:op.choice});
    api.setStorageSync(BACKUPS,items);
    if(fingerprint(registry())!==fingerprint(items))throw Error('备份目录读回失败，尚未建立新局。');
   }
  }
  // 跨命名空间恢复时，目标位置原有的非当前档也保留一份，避免覆盖它。
  if(op.targetKey!==op.sourceKey&&op.targetRawBefore){
   const key=op.backupKey+'-target',checksum=fingerprint(op.targetRawBefore);
   const archive={schema_version:6,seq:1,progress:{archive:{sourceKey:op.targetKey,original:op.targetRawBefore,checksum,createdAt:op.createdAt}}};
   Chunks.write(api,key,archive,work.targetBackupPlan||(work.targetBackupPlan={}),api.getStorageSync(key));archiveValue(key,checksum);
   const items=registry();if(!items.some(row=>row.key===key)){items.push({key,sourceKey:op.targetKey,checksum,createdAt:op.createdAt,reason:'restore-inactive'});api.setStorageSync(BACKUPS,items);if(fingerprint(registry())!==fingerprint(items))throw Error('备份目录读回失败。');}
  }
  if(op.targetKey===KEY600)Chunks.write(api,op.targetKey,op.target,work.targetPlan||(work.targetPlan={}),api.getStorageSync(op.targetKey));
  else api.setStorageSync(op.targetKey,op.target);
  if(fingerprint(raw(op.targetKey))!==fingerprint(op.target))throw Error('存档读回未完成，请重试同一操作。');
  if(current().key!==op.targetKey)api.setStorageSync(ACTIVE,{key:op.targetKey,operationId:op.id});
  if(current().key!==op.targetKey)throw Error('当前存档切换尚未完成，请重试。');
  clearJournal();return openStore();
 }
 function start(choice,backupKey,external){
  const existing=operation();
  if(existing){if(existing.op.choice!==choice||existing.op.restoreFrom!==(backupKey||null))throw Error('请先重试或取消上一次存档操作。');return apply();}
  const before=current();if(choice==='continue'&&accepted(before.snapshot))return openStore();
  if(choice==='continue'&&!before.raw)throw Error('本机没有原存档，请选择开始新的冒险。');
  let targetKey=before.key,target=copy(before.snapshot);
  if(choice==='new'){targetKey=KEY600;target=normalized(null,KEY600);}
  if(choice==='restore'){
   const row=registry().find(r=>r.key===backupKey);if(!row)throw Error('请选择已有的本机备份。');
   const backup=archiveValue(row.key,row.checksum);targetKey=backup.sourceKey;target=normalized(backup.original,targetKey);
  }
  if(choice==='import'){
   if(!isObject(external)||![1,6].includes(external.schema_version)||!isObject(external.progress))throw Error('请使用本小程序导出的完整备份文件。');
   if(external.bank_family&&external.bank_family!==require('./migration').BASELINE.family)throw Error('备份题库不匹配。');
   targetKey=external.schema_version===6?KEY600:KEY;target=normalized(external,targetKey);
  }
  if(choice==='cloud'){
   const value=external?.value,binding=external?.binding;
   if(!isObject(value)||![1,6].includes(value.schema_version)||!isObject(value.progress)||!isObject(binding)||typeof binding.account!=='string'||!/^[a-f0-9]{40}$/.test(binding.account)||!Number.isSafeInteger(binding.baseRevision)||binding.baseRevision<1||binding.baseRunId!==value.metadata?.release610?.runId)throw Error('云存档身份或版本不匹配。');
   targetKey=value.schema_version===6?KEY600:KEY;target=normalized(value,targetKey);
  }
  const id=makeId();if(!/^[A-Za-z0-9_-]{4,160}$/.test(id))throw Error('存档操作编号无效。');
  target.metadata=target.metadata||{};
  if(choice!=='continue'){delete target.metadata.cloud610;delete target.metadata.sync610;}
  target.metadata.release610={version:RELEASE,accepted:true,choice,operationId:id,
   runId:choice==='cloud'?external.binding.baseRunId:choice==='continue'&&before.snapshot.metadata?.release610?.runId||'run-'+id};
  if(choice==='cloud')target.metadata.cloud610=copy(external.binding);
  target.seq=(raw(targetKey)?.seq||0)+1;
  const op={version:RELEASE,id,choice,restoreFrom:backupKey||null,sourceKey:before.key,sourceRaw:before.raw,
   sourceChecksum:fingerprint(before.raw),targetKey,targetRawBefore:raw(targetKey),targetBeforeChecksum:fingerprint(raw(targetKey)),target,
   backupKey:ARCHIVE+id,createdAt:Date.now()};
  pending={op,journalPointer:api.getStorageSync(JOURNAL)};return apply();
 }
 return {
  // 同一次启动复用刚完成的只读检查；可写store仍重新读取和完整验证，不缓存跨操作状态。
  openSession(){try{const {state,status}=inspect();return {status,store:status.pending?null:openCheckedStore(state)};}catch(e){return {status:failedStatus(e),store:null};}},
  status(){try{return inspect().status;}catch(e){return failedStatus(e);}},
  listBackups(){return registry().map(({key,createdAt,reason})=>({key,createdAt,reason}));},
  choose(choice){if(!['continue','new'].includes(choice))throw Error('存档选择无效。');return start(choice);},
  restore(key){return start('restore',key);},importSnapshot(value){return start('import',null,value);},adoptCloud(value){return start('cloud',null,value);},retry:apply,openStore,
  saveExternalBackup(value,reason='cloud-unsent'){
   if(!value||![1,6].includes(value.schema_version))throw Error('待保存备份无效。');const sourceKey=value.schema_version===6?KEY600:KEY;normalized(value,sourceKey);
   const key=ARCHIVE+makeId(),checksum=fingerprint(value),createdAt=Date.now();const archive={schema_version:6,seq:1,progress:{archive:{sourceKey,original:copy(value),checksum,createdAt}}};
   Chunks.write(api,key,archive,{},api.getStorageSync(key));archiveValue(key,checksum);const items=registry();items.push({key,sourceKey,checksum,createdAt,reason});api.setStorageSync(BACKUPS,items);if(fingerprint(registry())!==fingerprint(items))throw Error('备份目录读回失败。');return key;
  },
  readBackup(key){const row=registry().find(r=>r.key===key);if(!row)throw Error('备份不存在。');return copy(archiveValue(key,row.checksum).original);},
  cancel(){const work=operation();if(!work)return;const op=work.op;
   if(raw(op.targetKey)?.metadata?.release610?.operationId===op.id){clearJournal();return;}
   if(fingerprint(raw(op.sourceKey))!==op.sourceChecksum||fingerprint(raw(op.targetKey))!==op.targetBeforeChecksum)throw Error('当前档已变化，请先重试核对。');
   clearJournal();},
 };
}
module.exports={RELEASE,JOURNAL,BACKUPS,ACTIVE,createUpgrade610};
