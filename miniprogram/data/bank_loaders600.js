// 由 tools/prepare_github_public_610.py 按最终app.json分包生成；并发复用，失败可重试。
const {routes}=require('./questions');
const loaders={"/packages/accounting1/pages/quiz/index":()=>require.async("../packages/accounting1/bank.js"),"/packages/law1/pages/quiz/index":()=>require.async("../packages/law1/bank.js"),"/packages/finance1/pages/quiz/index":()=>require.async("../packages/finance1/bank.js")};
function create(transport=route=>loaders[route]()){
 const loaded=new Map();
 function bank(route){if(!Object.hasOwn(loaders,route))return Promise.reject(Error('题目分包未登记'));if(!loaded.has(route)){const promise=Promise.resolve().then(()=>transport(route)).catch(e=>{loaded.delete(route);throw e;});loaded.set(route,promise);}
  return loaded.get(route);}
 async function load(ids){const unique=[...new Set(ids)];if(!unique.length||unique.some(id=>!routes[id]))throw Error('题号不属于本题库');const banks=await Promise.all([...new Set(unique.map(id=>routes[id]))].map(bank)),questions=Object.assign({},...banks),result={};for(const id of unique){if(!questions[id])throw Error('题目资源不完整，请重试');result[id]=questions[id];}return result;}
 return {load};
}
module.exports={create};
