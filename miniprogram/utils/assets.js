// 公共财管美术分包只存图片；题目仍按关卡进入各自题包。
const {routes,packages}=require('../data/asset_routes');
const image=path=>routes[path]||path;
const readyImage=(path,ready)=>routes[path]&&!ready?'':image(path);
module.exports={routes,packages,image,readyImage};
