// 题包只做无损离线编码，解码后保持原题字段和题号；不联网、不执行题目文本。
const pako=require('./vendor/pako_inflate.min');
const alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
function fromBase64(text){
 if(typeof text!=='string'||text.length%4||text.length>12*1024*1024||!/^[A-Za-z0-9+/]*={0,2}$/.test(text))throw Error('题包编码不完整，请重新载入。');
 const padding=text.endsWith('==')?2:text.endsWith('=')?1:0,bytes=new Uint8Array(text.length/4*3-padding);
 let position=0;
 for(let i=0;i<text.length;i+=4){
  const value=(alphabet.indexOf(text[i])<<18)|(alphabet.indexOf(text[i+1])<<12)|((text[i+2]==='='?0:alphabet.indexOf(text[i+2]))<<6)|(text[i+3]==='='?0:alphabet.indexOf(text[i+3]));
  bytes[position++]=(value>>>16)&255;
  if(position<bytes.length)bytes[position++]=(value>>>8)&255;
  if(position<bytes.length)bytes[position++]=value&255;
 }
 return bytes;
}
function decodeBank(encoded){
 try{const value=JSON.parse(pako.ungzip(fromBase64(encoded),{to:'string'}));if(!value||typeof value!=='object'||Array.isArray(value))throw Error('题库结构无效');return value;}
 catch{throw Error('离线题包解码失败，请重新打开本关。');}
}
module.exports={decodeBank};
