// 静态跨包入口供微信编译器识别；只加载本次精灵及动作需要的媒体包。
const M=require('../data/hunting600');
const loaders={
 financeArt:()=>require.async('../packages/financeArt/bank.js'),
 spiritMedia1:()=>require.async('../packages/spiritMedia1/bank.js'),
 spiritMedia2:()=>require.async('../packages/spiritMedia2/bank.js'),
 spiritMedia3:()=>require.async('../packages/spiritMedia3/bank.js'),
 spiritMedia4:()=>require.async('../packages/spiritMedia4/bank.js'),
 spiritMedia5:()=>require.async('../packages/spiritMedia5/bank.js'),
 spiritMedia6:()=>require.async('../packages/spiritMedia6/bank.js')
};
function create(transport=name=>loaders[name]()){
 const loaded=new Map(),ready=new Set();
 function load(name){if(!Object.hasOwn(loaders,name))return Promise.reject(Error('未知媒体分包'));if(!loaded.has(name)){const promise=Promise.resolve().then(()=>transport(name)).then(result=>{ready.add(name);return result;}).catch(e=>{loaded.delete(name);ready.delete(name);throw e;});loaded.set(name,promise);}return loaded.get(name);}
 async function prepare(id,{music=true,sound=true}={}){const refs=[M.art[id],M.art.yuanbao_ball];if(music)refs.push(M.bgm[id]||M.bgm.default);if(sound)refs.push(...Object.values(M.audio));await Promise.all([...new Set(refs.filter(Boolean).map(r=>r.package))].map(load));return {image:M.art[id]?.path||'',ball:M.art.yuanbao_ball.path};}
 return {load,prepare,isReady:name=>ready.has(name)};
}
module.exports={create};
