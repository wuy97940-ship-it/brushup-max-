// 仅为显示拆分连续的竖线表格；不改写题干、数字、符号或原始题库。
function blocks(value){
 const lines=String(value||'').split('\n'),result=[];let text=[];
 const flush=()=>{if(text.length){result.push({kind:'text',text:text.join('\n')});text=[];}};
 const cells=line=>line.trim().replace(/^\|/,'').replace(/\|$/,'').split('|').map(x=>x.trim());
 for(let i=0;i<lines.length;){
  if(!lines[i].includes('|')){text.push(lines[i++]);continue;}
  let j=i;while(j<lines.length&&lines[j].includes('|'))j++;
  const rows=lines.slice(i,j).map(cells).filter(row=>!row.every(cell=>/^:?-{3,}:?$/.test(cell)));
  if(rows.length>=2&&rows.every(row=>row.length>=2)){
   flush();const columns=Math.max(...rows.map(row=>row.length));
   result.push({kind:'table',columns,width:columns*240,rows:rows.map(row=>Array.from({length:columns},(_,k)=>row[k]||''))});i=j;
  }else{text.push(...lines.slice(i,j));i=j;}
 }
 flush();return result;
}
module.exports={blocks};
