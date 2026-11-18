// 小档沿用单次写入；大档先写完整分段，最后提交一个小指针。原指针成功前不变。
const LIMIT=750000,PART=160000,MAX_PARTS=80;
function bytes(s){let n=0;for(let i=0;i<s.length;i++){const c=s.charCodeAt(i);if(c<128)n++;else if(c<2048)n+=2;else if(c>=0xD800&&c<=0xDBFF&&i+1<s.length&&s.charCodeAt(i+1)>=0xDC00&&s.charCodeAt(i+1)<=0xDFFF){n+=4;i++;}else n+=3;}return n;}
function checksum(s){let a=2166136261,b=0;for(let i=0;i<s.length;i++){a=Math.imul(a^s.charCodeAt(i),16777619)>>>0;b=(b+s.charCodeAt(i)*(i%65521+1))>>>0;}return a.toString(16)+':'+b.toString(16);}
function descriptor(v){return !!v&&v.schema_version===6&&v.chunked===1;}
function valid(v,key){const p=v?.parts;return descriptor(v)&&Number.isSafeInteger(v.seq)&&v.seq>=0&&p&&typeof p.prefix==='string'&&p.prefix.startsWith(key+':part:')&&p.prefix.length<160&&Number.isSafeInteger(p.count)&&p.count>0&&p.count<=MAX_PARTS&&Number.isSafeInteger(p.length)&&p.length>0&&p.length<=MAX_PARTS*PART&&typeof p.checksum==='string';}
function read(api,key,observe=()=>{}){const v=api.getStorageSync(key);observe(v);if(!descriptor(v))return v;if(!valid(v,key))throw Error('存档分段索引无效');const parts=[];for(let i=0;i<v.parts.count;i++){const part=api.getStorageSync(v.parts.prefix+':'+i);if(typeof part!=='string'||part.length>PART)throw Error('存档分段缺失或损坏');parts.push(part);}const text=parts.join('');if(text.length!==v.parts.length||checksum(text)!==v.parts.checksum)throw Error('存档分段校验失败');const value=JSON.parse(text);if(value.schema_version!==6||value.seq!==v.seq||!value.progress)throw Error('存档分段序列不匹配');return value;}
function plan(key,envelope,old){const text=JSON.stringify(envelope);if(bytes(text)<=LIMIT)return {pointer:envelope,parts:[],old};const prefix=key+':part:'+envelope.seq+':'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2),parts=[];for(let i=0;i<text.length;){let end=Math.min(text.length,i+PART);if(end<text.length&&text.charCodeAt(end-1)>=0xD800&&text.charCodeAt(end-1)<=0xDBFF)end--;parts.push(text.slice(i,end));i=end;}if(parts.length>MAX_PARTS)throw Error('存档超出可恢复的分段数量，请保留原档。');return {old,parts,pointer:{schema_version:6,seq:envelope.seq,chunked:1,parts:{prefix,count:parts.length,length:text.length,checksum:checksum(text)}}};}
function write(api,key,envelope,pending,old){const p=pending.chunkPlan||(pending.chunkPlan=plan(key,envelope,old));for(let i=0;i<p.parts.length;i++)api.setStorageSync(p.pointer.parts.prefix+':'+i,p.parts[i]);api.setStorageSync(key,p.pointer);
 // 清理失败不撤销已经成功提交的存档，也不触及非本命名空间的键。
 if(typeof api.removeStorageSync==='function'&&valid(p.old,key)&&(!p.pointer.parts||p.old.parts.prefix!==p.pointer.parts.prefix))for(let i=0;i<p.old.parts.count;i++){try{api.removeStorageSync(p.old.parts.prefix+':'+i);}catch{}}
 return p.pointer;
}
module.exports={bytes,checksum,read,write};
