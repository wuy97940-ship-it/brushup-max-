const Chunks=require('./storage_chunks600'),Config=require('../data/release610');
const JOURNAL='xiaoyuan-adventure:cloud610:pending',PART=48000;
const copy=v=>JSON.parse(JSON.stringify(v));
function payload(store){const value=store.snapshot();return {schema_version:value.schema_version,progress:value.progress,metadata:{release610:{version:'6.1.0',accepted:true,runId:value.metadata.release610.runId}}};}
const fingerprint=store=>Chunks.checksum(JSON.stringify(payload(store)));
function split(text){const parts=[];for(let i=0;i<text.length;){let end=Math.min(text.length,i+PART);if(end<text.length&&text.charCodeAt(end-1)>=0xD800&&text.charCodeAt(end-1)<=0xDBFF)end--;parts.push(text.slice(i,end));i=end;}return parts;}
function createCloud(api,{getStore,getUpgrade,adopt,changed=()=>{},makeId=()=>('sync-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2)+'-'+Math.random().toString(36).slice(2))}){
 let known=false,account=null,head=null,admin=false,group=null,error='',busy=false,probing=null,inited=false;
 async function request(action,data={}){
  if(!api.cloud?.init||!api.cloud?.callFunction)throw Error('请更新微信后使用云存档。');
  if(!inited){api.cloud.init({env:Config.cloudEnvironment,traceUser:false});inited=true;}
  const response=await api.cloud.callFunction({name:Config.cloudFunction,data:action==='hello'?{action,...data}:{action,account,...data},config:{env:Config.cloudEnvironment}}),body=response?.result;
  if(body?.ok!==true)throw Error(body?.message||'云存档暂不可用，本机学习进度仍会保存。');return body.result;
 }
 function view(){
  const store=getStore();let phase='unknown',text=error||'正在检查当前微信的云存档。';
  if(known){if(!store){phase=head?'available':'empty';text=head?'当前微信有云存档，可以继续云端冒险。':'当前微信还没有云存档。';}
   else if(store.pending||store.loadError){phase='save-error';text='请先处理本机存档保存或读取。';}
   else {const binding=store.metadata.cloud610,fp=fingerprint(store),runId=store.metadata.release610.runId;
    if(binding&&binding.account!==account){phase='account';text='本机进度关联另一微信账号，请确认要使用的存档。';}
    else if(!binding){phase=head?'available':'empty';text=head?'云端有一份进度，选择使用本机或云端。':'可将本机进度备份至当前微信。';}
    else if((head?.revision||0)!==binding.baseRevision||(head?.runId||null)!==binding.baseRunId){phase=fp===binding.checksum&&runId===binding.baseRunId?'remote':'conflict';text=phase==='remote'?'云端有更新的进度，点此选择继续。':'两份进度有变化，均已保留，请选择继续哪一份。';}
    else {phase=fp===binding.checksum&&runId===binding.baseRunId?'synced':'local';text=phase==='synced'?'已同步至当前微信。':'新学习进度已保存在本机，等待同步。';}
   }}
  return {phase,text,known,hasCloud:!!head,admin,busy,group,updatedAt:head?.updatedAt||null};
 }
 const publish=()=>changed(view());
 async function probe(){if(probing)return probing;probing=(async()=>{try{const r=await request('hello');if(!/^[a-f0-9]{40}$/.test(r.account))throw Error('云存档身份核验失败。');account=r.account;head=r.head;admin=r.admin===true;group=r.group||null;known=true;error='';}catch(e){known=false;error='暂时无法连接云存档，本机进度已保留。';}finally{probing=null;publish();}return view();})();return probing;}
 function readPending(){const v=Chunks.read(api,JOURNAL);if(!v)return null;const op=v.progress?.operation;if(!op||typeof op.account!=='string'||!op.value||Chunks.checksum(JSON.stringify(op.value))!==op.checksum)throw Error('待同步存档读回失败，请保留本机数据。');return op;}
 function clearPending(){const pointer=api.getStorageSync(JOURNAL);api.removeStorageSync(JOURNAL);if(pointer?.parts?.prefix?.startsWith(JOURNAL+':part:'))for(let i=0;i<pointer.parts.count;i++){try{api.removeStorageSync(pointer.parts.prefix+':'+i);}catch{}}}
 function archivePending(){const op=readPending();if(!op)return;getUpgrade().saveExternalBackup(op.value,'cloud-unsent');clearPending();}
 async function upload({explicit=false}={}){
  if(busy)return view();busy=true;publish();try{
   await probe();if(!known)throw Error(error);const store=getStore();if(!store)throw Error('请先完成存档选择。');if(store.pending||store.loadError)throw Error('请先处理本机存档。');
   let op=readPending();
   if(op&&op.account!==account){if(!explicit)throw Error('当前微信已切换，请先选择存档。');archivePending();op=null;}
   if(explicit&&op&&(op.baseRevision!==(head?.revision||0)||op.baseRunId!==(head?.runId||null))&&head?.operationId!==op.operationId){archivePending();op=null;}
   if(!op){
    if(!explicit&&!['local'].includes(view().phase))return view();
    const value=payload(store),text=JSON.stringify(value);op={account,value,checksum:Chunks.checksum(text),operationId:makeId(),runId:value.metadata.release610.runId,baseRevision:head?.revision||0,baseRunId:head?.runId||null};
    if(Chunks.bytes(text)>6*1024*1024)throw Error('存档较大，请先导出本机备份；本次未改云档。');
    const envelope={schema_version:6,seq:1,progress:{operation:op}};Chunks.write(api,JOURNAL,envelope,{},api.getStorageSync(JOURNAL));if(JSON.stringify(readPending())!==JSON.stringify(op))throw Error('待同步备份读回未完成。');
   }
   const text=JSON.stringify(op.value),parts=split(text);let response=await request('begin',{account:op.account,operationId:op.operationId,runId:op.runId,baseRevision:op.baseRevision,baseRunId:op.baseRunId,count:parts.length,length:text.length,checksum:op.checksum});
   if(response.conflict){head=response.head;return view();}
   if(!response.committed){for(let i=0;i<parts.length;i++)await request('putChunk',{account:op.account,operationId:op.operationId,index:i,text:parts[i]});response=await request('commit',{account:op.account,operationId:op.operationId});}
   if(response.conflict){head=response.head;return view();}if(!response.committed)throw Error('云端尚未完成同步。');
   head=response.head;const revision=head?.operationId===op.operationId?head.revision:response.committedRevision;
   if(!Number.isSafeInteger(revision)||revision<1)throw Error('同步版本未读回，请重试。');
   const current=getStore();if(current!==store||current.metadata.release610.runId!==op.runId||account!==op.account)throw Error('本机已切换账号或冒险；已保留本次同步，请重新选择。');
   current.setMetadata({...current.metadata,cloud610:{account:op.account,baseRevision:revision,baseRunId:op.runId,checksum:op.checksum,snapshotId:op.operationId}});
   const binding=current.metadata.cloud610;current.load();if(current.loadError||JSON.stringify(current.metadata.cloud610)!==JSON.stringify(binding))throw Error('本机同步记录读回失败，请重试。');clearPending();error='';return view();
  }catch(e){known=false;error=e.message;throw e;}finally{busy=false;publish();}
 }
 async function download(){
  if(busy)throw Error('正在同步，请稍等。');busy=true;publish();try{
   await probe();if(!known)throw Error(error);if(!head)throw Error('当前微信还没有云存档。');
   const selected=copy(head),selectedAccount=account,store=getStore(),before=store?fingerprint(store):null,r=await request('manifest',{account:selectedAccount,snapshotId:selected.snapshotId}),parts=[];
   if(r.runId!==selected.runId||r.revision!==selected.revision||r.checksum!==selected.checksum||!Number.isInteger(r.count)||r.count<1||r.count>128)throw Error('云存档版本校验失败。');
   for(let i=0;i<r.count;i++){const part=await request('getChunk',{account:selectedAccount,snapshotId:selected.snapshotId,index:i});if(part.index!==i||typeof part.text!=='string')throw Error('云存档分段未读全。');parts.push(part.text);}
   const text=parts.join('');if(text.length!==r.length||Chunks.checksum(text)!==r.checksum)throw Error('云存档完整性校验失败。');const value=JSON.parse(text);
   if(account!==selectedAccount||getStore()!==store||(store&&fingerprint(store)!==before))throw Error('下载期间账号或本机进度已变化，请重新确认。');
   archivePending();adopt({value,binding:{account:selectedAccount,baseRevision:r.revision,baseRunId:r.runId,checksum:r.checksum,snapshotId:selected.snapshotId}});error='';return view();
  }catch(e){known=false;error=e.message;throw e;}finally{busy=false;publish();}
 }
 async function telemetry(){try{const store=getStore();if(!store||!known||store.metadata.cloud610?.account!==account)return;const G=require('./game600');await request('visit',{learnedToday:G.Growth600.dailyView(store.progress.game).count,cleared:G.stats(store.progress.game).cleared});}catch{}}
 return {view,probe,upload,download,telemetry,async metrics(){return request('metrics');}};
}
module.exports={JOURNAL,createCloud,payload,fingerprint,split};
