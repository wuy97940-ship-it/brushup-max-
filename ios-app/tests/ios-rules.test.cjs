const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const G = require('../src/shared/utils/game');
const S = require('../src/shared/utils/skills');
const Shop = require('../src/shared/utils/shop');
const bank = require('../src/content/original-bank.json');
const {createStore,valid,KEY} = require('../src/services/transactionStore');
const first = 'accounting:01:normal:01', boss = 'accounting:01:boss:01';
function fill(p, n, sid=first) {
  G.start(p,sid,true,()=>0.5);
  p.game.active.qids.forEach((id,i)=>{
    const q=bank.questions[id],a=p.game.active;
    if(G.subjective(q)){a.drafts[id]='我的计算与理由';a.references.push(id);}
    G.submit(p,q,G.subjective(q)?'我的计算与理由':q.answer,i<n);
  });
  return G.settle(p,()=>0.99,()=>0.99);
}
function memory(){let value=null,fail=false,writes=0;return {get value(){return value;},get writes(){return writes;},set fail(v){fail=v;},set raw(v){value=v;},async getItem(k){assert.equal(k,KEY);return value;},async setItem(k,v){assert.equal(k,KEY);writes++;if(fail)throw Error('disk full');value=v;}};}
test('已知案例措辞升级保留进度；写入失败不覆盖旧存档，篡改旧地图不能借迁移导入',async()=>{
 const legacy=G.defaultProgress();fill(legacy,9);legacy.game.coins=987;
 legacy.game.campaign=G.copy(require('../src/migration/baseline.json').campaign);legacy.game.campaign.bank_fingerprint='119b1f1b864d3f1f43552768c19d46098639f206988f0c2fa19349b3f3dd5c34';
 const api=memory();api.raw=JSON.stringify({schema_version:1,seq:3,progress:legacy});const original=api.value;
 const store=createStore(api);api.fail=true;await store.load();assert.ok(store.loadError);assert.equal(api.value,original);
 api.fail=false;await store.load();assert.equal(store.loadError,'');assert.equal(store.progress.game.coins,987);assert.equal(store.progress.game.active.result.correct,9);assert.equal(store.progress.game.campaign.bank_fingerprint,bank.fingerprint);
 const forged=G.copy(legacy);forged.game.campaign.levels[first].qids=['orig-acc-01-01'];
 await assert.rejects(store.import(JSON.stringify({progress:forged})),/另一题库/);
});
test('264原创题全部且只安排一次；48关、24案例、六地图、40关目标可达',()=>{
 const levels=Object.values(G.CAMPAIGN.levels).filter(l=>l.world_id!=='finance'),all=levels.flatMap(l=>l.qids);
 assert.equal(all.length,264);assert.equal(new Set(all).size,264);assert.deepEqual(new Set(all),new Set(Object.values(bank.questions).filter(q=>q.book_id!=='cg_original_v02').map(q=>q.id)));
 assert.equal(levels.length,48);assert.equal(levels.filter(l=>l.kind==='normal').length,24);assert.equal(levels.filter(l=>l.kind==='boss').length,24);
 assert.deepEqual(new Set(levels.map(l=>l.biome)),new Set(G.C.biomes.map(b=>b.id)));
 assert.ok(levels.length>=40);
 levels.forEach(l=>assert.equal(l.qids.length,l.kind==='normal'?10:1));
 for(const q of Object.values(bank.questions).filter(q=>q.book_id!=='cg_original_v02')) {
  assert.ok(q.id.startsWith('orig-'));assert.equal(q.authorship.kind,'project_original');assert.ok(q.stem.length>10);assert.ok(q.explanation.length>10);
  if(!G.subjective(q)){assert.equal(Object.keys(q.options).length,4);assert.ok(q.answer.split('').every(k=>q.options[k]));assert.equal(q.answer.length,q.type==='多选题'?2:1);}
  else assert.ok(q.answer.includes('\n'));
 }
});
test('会计96道数值题的答案按独立公式核验',()=>{
 for(let c=1;c<=12;c++)for(let n=1;n<=8;n++){
  const q=bank.questions[`orig-acc-${String(c).padStart(2,'0')}-${String(n).padStart(2,'0')}`],v=1000+n*100;
  const expected={1:String(4*v),2:'0元',3:`借存货${v}，贷应付账款${v}`,4:String(v),5:String((10+n)*(20+n)+100+n*10),6:String(v),7:String(2*v),8:String(4*v),9:String(5*v/20),10:String(5*v),11:'投资活动',12:'2'}[c];
  assert.equal(q.options[q.answer],expected,q.id);
 }
});
test('13份共有代码及当前透明素材与手机版逐字节相同；未复制私人题库或个人数据',()=>{
 const root=path.resolve(__dirname,'../..'),manifest=require('../shared-provenance.json');
 assert.ok(manifest.art_png_count>=106);assert.equal(manifest.shared_code_files,13);assert.ok(!fs.existsSync(path.join(root,'ios-app/assets/finance/source')));
 assert.equal(manifest.old_question_bank_included,false);
 for(const pair of manifest.shared_pairs){const a=fs.readFileSync(path.join(root,pair.source)),b=fs.readFileSync(path.join(root,pair.target));assert.deepEqual(a,b,pair.target);assert.equal(crypto.createHash('sha256').update(b).digest('hex'),pair.sha256);}
 const app=path.resolve(__dirname,'..');
 assert.ok(!fs.existsSync(path.join(app,'progress.json')));assert.ok(!fs.existsSync(path.join(app,'project.config.json')));
});
test('70/90/100、短关与无答题分母边界',()=>{
 assert.equal(G.stars(6,10),0);assert.equal(G.stars(7,10),1);assert.equal(G.stars(9,10),2);assert.equal(G.stars(10,10),3);
 assert.equal(G.stars(0,1),0);assert.equal(G.stars(1,1),3);assert.equal(G.stars(0,0),0);assert.equal(G.stars(7,9),1);assert.equal(G.stars(8,9),1);
});
test('失败可以立即整轮重试；两科第1章开放、章内Boss先解锁',()=>{
 const p=G.defaultProgress();assert.ok(G.canPlay(p.game,first));assert.ok(G.canPlay(p.game,'law:01:normal:01'));assert.ok(!G.canPlay(p.game,boss));
 assert.equal(fill(p,6).passed,false);assert.ok(!G.canPlay(p.game,boss));
 assert.equal(fill(p,7).passed,true);assert.ok(G.canPlay(p.game,boss));assert.ok(!G.canPlay(p.game,'accounting:02:normal:01'));
 fill(p,1,boss);assert.ok(G.canPlay(p.game,'accounting:02:normal:01'));
});
test('本轮首次提交计分；主观必须先草稿与参考，再自评',()=>{
 const p=G.defaultProgress();G.start(p,first);const q=bank.questions[p.game.active.qids[0]];
 assert.equal(G.submit(p,q,q.answer,false),true);assert.equal(G.submit(p,q,q.answer,true),false);assert.equal(p.game.active.answers[q.id].correct,false);
 fill(p,10);G.start(p,boss);const sq=bank.questions[p.game.active.qids[0]];
 assert.throws(()=>G.submit(p,sq,'自己作答',true),/参考/);p.game.active.drafts[sq.id]='自己作答';p.game.active.references.push(sq.id);
 G.submit(p,sq,'自己作答',true);assert.equal(G.settle(p,()=>0.99,()=>0.99).stars,3);
});
test('Lv3瞒天过海只多错一题；不改写真实正确率、不用于Boss',()=>{
 const p=G.defaultProgress();p.game.xp=1000;fill(p,6);assert.ok(S.mercyStatus(p.game,p.game.active,G.levelFor(p.game,first)).eligible);
 const r=G.useMercy(p);assert.ok(r.passed&&r.assisted);assert.equal(r.correct,6);assert.equal(r.stars,1);assert.equal(S.available(p.game,'mercy'),0);
 fill(p,0,boss);assert.ok(!S.mercyStatus(p.game,p.game.active,G.levelFor(p.game,boss)).eligible);
});
test('灵光一现排除真实错项，重按不扣，整场只用一次',()=>{
 const p=G.defaultProgress();p.game.xp=500;G.start(p,first);const q=bank.questions[p.game.active.qids[0]];
 const v=S.hint(p,q);assert.ok(!q.answer.includes(v[0]));assert.equal(S.available(p.game,'insight'),0);assert.deepEqual(S.hint(p,q),v);
 assert.throws(()=>S.hint(p,bank.questions[p.game.active.qids[1]]),/最多/);
});
test('妙笔生花在草稿参考后整理原文；重复不扣且自由复习可用',()=>{
 const p=G.defaultProgress();p.game.xp=4500;const q=bank.questions['orig-law-07-boss'];G.startPractice(p,[q.id],'定金复习');
 assert.throws(()=>S.outline(p,q,true),/填写/);p.practice.drafts[q.id]='200元限额，双倍400，超额另退';p.practice.references.push(q.id);
 assert.deepEqual(S.outline(p,q,true),q.answer.split('\n'));assert.deepEqual(S.outline(p,q,true),q.answer.split('\n'));assert.equal(S.available(p.game,'outline'),0);
});
test('Boss15%分界、五类掉落与稀有度、重复兑换',()=>{
 function rng(values){let i=0;return ()=>values[i++%values.length];}
 const p=G.defaultProgress();assert.equal(G.loot(p.game,()=>0.15).kind,'none');assert.equal(G.loot(p.game,rng([0.14,0])).kind,'coins');
 for(const [kind,v]of [['coins',0.05],['xp',0.25],['skin',0.45],['equipment',0.65],['collection',0.85]])assert.equal(G.loot(G.defaultProgress().game,rng([0,v,0,0])).kind,kind);
 const g=G.defaultProgress().game,d1=G.loot(g,rng([0,0.85,0,0])),d2=G.loot(g,rng([0,0.85,0,0]));
 assert.ok(!d1.duplicate&&d2.duplicate);assert.equal(d2.coins,30);
 const legend=G.loot(G.defaultProgress().game,rng([0,0.65,0.999,0]));assert.equal(legend.rarity,'legendary');
});
test('主线惊喜10%、奇物总机会2.5%，远征不赠主线惊喜',()=>{
 const g=G.defaultProgress().game;assert.deepEqual(G.surprise(g,()=>0.1),[]);
 const values=[0,0.8,0,0];let i=0;const result=G.surprise(g,()=>values[i++]);assert.equal(result[0].kind,'item');
 assert.equal(G.ECONOMY.surprise_percent*G.ECONOMY.surprise_kind_weights.item/100,2.5);
});
test('金币购买门槛、三槽装备、技能补充及排队不提前扣次数',()=>{
 const p=G.defaultProgress();p.game.coins=10000;p.game.xp=4500;
 assert.throws(()=>G.buy(p,'wonder_broom'),/通关/);p.game.results[first]={cleared:true,best_stars:3};G.buy(p,'wonder_lantern');G.equip(p,'wonder_lantern');assert.equal(G.bonuses(p.game).xp,5);
 assert.throws(()=>G.buy(p,'wonder_lantern'),/拥有/);
 S.queue(p,'gold');assert.equal(S.available(p.game,'gold'),1);G.start(p,boss);assert.equal(S.available(p.game,'gold'),0);assert.equal(p.game.active.bonuses.coins,50);
 const coins=p.game.coins;S.refill(p,'gold');assert.equal(p.game.coins,coins-15);S.state(p.game).ink=1;S.refill(p,'gold',true);assert.equal(S.state(p.game).ink,0);
});
test('装备/技能收益按开场快照并向下取整',()=>{
 const p=G.defaultProgress();p.game.inventory.push('equipment_xp_common');p.game.equipment.xp='equipment_xp_common';G.start(p,first);p.game.equipment.xp=null;
 p.game.active.qids.forEach(id=>G.submit(p,bank.questions[id],bank.questions[id].answer,true));const r=G.settle(p,()=>0.99,()=>0.99);
 assert.equal(r.xp,84);assert.equal(r.coins,20);
});
test('两科主线全通才能远征，每轮不重复且错题优先6道',()=>{
 const p=G.defaultProgress();assert.throws(()=>G.expedition(p),/三科/);
 for(const id of Object.keys(G.CAMPAIGN.levels))p.game.results[id]={cleared:true,best_stars:3};p.wrong_book=G.META.slice(0,8).map(q=>q.id);
 const e=G.expedition(p,()=>0.5);assert.equal(e.qids.length,10);assert.equal(new Set(e.qids).size,10);assert.equal(e.qids.filter(id=>p.wrong_book.includes(id)).length,6);
});
test('保存失败保持同一随机结果；重试/重启/重打均不重复领奖',async()=>{
 const api=memory(),store=createStore(api);await store.load();await store.commit(p=>fill(p,10));
 await store.commit(p=>G.start(p,boss));await store.commit(p=>{const q=bank.questions[p.game.active.qids[0]];p.game.active.references.push(q.id);G.submit(p,q,'草稿',true);});
 const before=G.copy(store.progress),rngs=[0,0.05];let n=0;api.fail=true;
 await assert.rejects(store.commit(p=>G.settle(p,()=>rngs[n++],()=>0.99)),/保存失败/);assert.deepEqual(store.progress,before);assert.equal(n,2);assert.ok(store.pending);
 await assert.rejects(store.commit(p=>G.settle(p)),/重试/);api.fail=false;const r=await store.retry();assert.equal(r.loot.kind,'coins');assert.equal(n,2);const xp=store.progress.game.xp,coins=store.progress.game.coins;
 assert.equal(await store.retry(),null);await store.commit(p=>G.settle(p));assert.equal(store.progress.game.coins,coins);
 const reloaded=createStore(api);await reloaded.load();assert.ok(!reloaded.loadError);assert.equal(reloaded.progress.game.xp,xp);await reloaded.commit(p=>fill(p,1,boss));assert.equal(reloaded.progress.game.coins,coins);assert.equal(reloaded.progress.game.xp,xp);
});
test('异步重复点击只执行一次交易',async()=>{
 const api=memory(),store=createStore(api);await store.load();await store.commit(p=>{p.game.results[first]={cleared:true,best_stars:3};p.game.coins=100;});
 const transaction=store.commit(p=>G.buy(p,'wonder_lantern'));await assert.rejects(store.commit(p=>G.buy(p,'wonder_lantern')),/保存/);await transaction;assert.equal(store.progress.game.coins,20);assert.equal(store.progress.game.inventory.filter(id=>id==='wonder_lantern').length,1);
});
test('损坏存档不覆盖；导入旧题库拒绝；同题库备份可恢复',async()=>{
 const api=memory();api.raw='{broken';const store=createStore(api);await store.load();assert.ok(store.loadError);assert.equal(api.value,'{broken');await assert.rejects(store.commit(p=>{p.game.coins=5;}),/保留/);
 const p=G.defaultProgress();p.game.campaign.bank_fingerprint='old-1026';await assert.rejects(store.import(JSON.stringify({progress:p})),/另一题库/);
 const fresh=G.defaultProgress();assert.ok(valid(fresh));await store.import(JSON.stringify({progress:fresh}));assert.ok(!store.loadError);assert.ok(valid(JSON.parse(store.export()).progress));
});
test('当前题序、草稿、参考、暂停挑战保存后恢复',async()=>{
 const api=memory(),store=createStore(api);await store.load();await store.commit(p=>{fill(p,10);G.start(p,boss);p.game.active.drafts['orig-acc-01-boss']='17000=6000+11000';p.game.active.references.push('orig-acc-01-boss');G.start(p,'law:01:normal:01');p.game.active.index=2;});
 const store2=createStore(api);await store2.load();assert.ok(!store2.loadError);await store2.commit(p=>G.start(p,boss));assert.equal(store2.progress.game.active.drafts['orig-acc-01-boss'],'17000=6000+11000');assert.ok(store2.progress.game.active.references.includes('orig-acc-01-boss'));
});
test('商店34项、五技能、完整六套收藏',()=>{
 const view=Shop.view(G.defaultProgress().game);assert.equal(view.shopItems.filter(i=>!i.id.startsWith('outfit_finance_')&&!i.id.startsWith('finance_')&&!i.id.startsWith('spirit_')).length,34);assert.equal(view.shopItems.length,34+G.Finance.CONFIG.outfits.length+G.Finance.CONFIG.props.length+G.Finance.CONFIG.companions.length);assert.equal(view.skills.length,5);assert.equal(view.themeSets.length,6);assert.equal(view.goal.id,'wonder_broom');
});
