// 在微信真实无损解码模块和原子存储模块上检查原创候选。
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const bank=require('../content/original-bank.json');
const G=require('../miniprogram/utils/game');
const F=G.Finance;
const Store=require('../miniprogram/utils/storage');
const Q=require('../miniprogram/data/questions');

test('微信三个科目包由产品解码器恢复704题完整字段',()=>{
 const recovered={};
 for(const world of G.CAMPAIGN.worlds)Object.assign(recovered,require(`../miniprogram/packages/${world.id}1/bank.js`));
 assert.deepEqual(recovered,bank.questions);
 assert.equal(Q.meta.length,704);
 assert.equal(Object.keys(Q.routes).length,704);
 assert.equal(Object.keys(G.CAMPAIGN.levels).length,128);
 for(const route of Object.values(Q.routes))assert(fs.existsSync(path.join(root,'miniprogram',route.slice(1)+'.js')));
});

test('所有原创计算的参考数值均通过实际数值判定器',()=>{
 let checks=0;
 for(const q of Object.values(bank.questions))for(const check of q.numeric_checks||[]){
  assert(F.numericCheck(check,check.value,check.unit).correct,q.id+':'+check.key);checks++;
 }
 assert.equal(checks,168);
});

test('微信原子保存失败保持旧材料，重试不重复升级，公开备份拒绝私人家族',()=>{
 let saved=null,fail=false;
 const api={getStorageSync:()=>saved,setStorageSync:(key,value)=>{assert.equal(key,Store.KEY);if(fail)throw Error('空间不足');saved=JSON.parse(JSON.stringify(value));}};
 const store=Store.createStore(api);
 store.commit(p=>{F.state(p.game).materials=3;});
 const id=F.CONFIG.buildings[0].id;
 fail=true;
 assert.throws(()=>store.commit(p=>F.upgradeBuilding(p,id)),/保存失败/);
 assert.equal(F.state(store.progress.game).materials,3);
 fail=false;store.retry();assert.equal(F.state(store.progress.game).materials,2);
 assert.equal(F.state(store.progress.game).buildings[id],1);assert.equal(store.retry(),null);
 const forged=JSON.parse(store.export());forged.progress.bank_family='private-cpa';
 assert.throws(()=>store.import(JSON.stringify(forged)),/本题库/);
 assert.equal(F.state(store.progress.game).buildings[id],1);
});

test('公开微信与Expo共享运行代码和原创地图，具备三主角及六经营区域',()=>{
 for(const file of ['utils/game.js','utils/finance.js','utils/migration.js','utils/shop.js'])assert.deepEqual(fs.readFileSync(path.join(root,'miniprogram',file)),fs.readFileSync(path.join(root,'ios-app/src/shared',file)));
 assert.deepEqual(G.CAMPAIGN,require('../content/campaign.json'));
 assert(G.CATALOG.xiaobao);assert.equal(F.CONFIG.acts.length,6);assert.equal(F.CONFIG.buildings.length,6);
 assert.equal(F.CONFIG.outfits.length,12);assert.equal(F.CONFIG.companions.length,4);
});
