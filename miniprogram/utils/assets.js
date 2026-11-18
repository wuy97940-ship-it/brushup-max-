// 公共财管美术分包只存图片；题目仍按关卡进入各自题包。
const base=require('../data/asset_routes');
const Mood=require('./adventure600');
const routes={...base.routes};
for(const id of Object.keys(Mood.ITEMS))routes['/assets/mood/'+id+'.png']=Mood.C.art[id];
const packages=[...new Set([...base.packages,'adventureArt','adventureSupply'])];
const image=path=>routes[path]||path;
const readyImage=(path,ready)=>routes[path]&&!ready?'':image(path);
module.exports={routes,packages,image,readyImage};
