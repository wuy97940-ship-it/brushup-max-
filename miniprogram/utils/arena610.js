const pools=require('../data/arena610');
function start(p,{world=p.game.world,mode='arena',count=10,rate=80,weak=true,ids=null,target=null}={}){
 const G=require('./game600');if(!G.modern(p.game))throw Error('此存档保留旧规则；比武场仅供6.0规则冒险使用。');
 if(!['arena','arena_skills'].includes(mode)||![5,10,20].includes(count)||![60,80,90].includes(rate)||!pools[world])throw Error('比武设置无效。');
 if(mode==='arena_skills'&&G.Adventure.level(p.game)<10)throw Error('技能比武在10级开放。');
 const rows=pools[world],eligible=new Set(rows.map(r=>r[0]));
 let qids=ids;if(!qids){const verified=new Set(rows.filter(r=>r[1]).map(r=>r[0]));qids=G.shuffle(rows.map(r=>r[0]),Math.random);qids.sort((a,b)=>Number(!verified.has(a))-Number(!verified.has(b))||(weak?Number(!p.wrong_book.includes(a))-Number(!p.wrong_book.includes(b)):0));qids=qids.slice(0,count);}
 if(qids.length<5||qids.length!==new Set(qids).size||qids.some(id=>!eligible.has(id)))throw Error('本场至少需要5道本学科经核验的重难点客观题。');
 const name=G.CAMPAIGN.worlds.find(w=>w.id===world).name+' · '+(mode==='arena'?'普通比武':'技能比武');
 const a=G.startPractice(p,qids,name,mode);a.arena610={world,count,rate,weak};a.target=target??Math.floor(qids.length*rate/100);a.chapter_key='arena550:'+world;
 if(!Number.isInteger(a.target)||a.target<0||a.target>qids.length)throw Error('比武目标无效。');return a;
}
function finish(p){
 const G=require('./game600'),a=p.practice;if(!a?.arena610)throw Error('当前没有比武。');if(a.settled)return a.result;
 G.requireAction(p.game);if(a.qids.some(id=>!a.answers[id]))throw Error('请完成本场全部题目。');
 const records=a.qids.map(id=>a.answers[id]),correct=records.filter(r=>r.correct).length;
 const independent=records.filter(r=>r.correct&&!r.assisted&&!r.self_assessed).length;
 const score=a.product_mode==='arena_skills'?records.filter(r=>r.game_correct??r.correct).length:independent;
 const outcome=score>a.target?'胜':score===a.target?'平':'败',day=G.Growth600.day(p.game).key;
 const s=p.game.product600,best=s.arena_best||(s.arena_best={}),key=day+':'+a.chapter_key,proposed=G.Adventure.C.rewards.arena_xp[outcome];
 const earned=Math.floor(Math.max(0,proposed-(best[key]||0))*(100+(a.bonuses.xp||0))/100);best[key]=Math.max(best[key]||0,proposed);p.game.xp+=earned;
 const totals=G.Growth600.state(p.game).arena_records||(G.Growth600.state(p.game).arena_records={});const row=totals[a.product_mode]||(totals[a.product_mode]={'胜':0,'平':0,'败':0});row[outcome]++;
 const result={mode:a.product_mode,name:a.name,outcome,target:a.target,correct,game_correct:score,independent_correct:independent,total:a.qids.length,passed:outcome!=='败',stars:0,quality:'比武'+outcome,xp:a.xp_earned+earned,answer_xp:a.xp_earned,settlement_xp:earned,coins:0,wrong_qids:a.qids.filter(id=>!a.answers[id].correct),level_before:a.challenge_rules.level,level_after:G.Adventure.level(p.game)};
 a.result=result;a.settled=true;G.Adventure.ensure(p.game);return result;
}
module.exports={start,finish,pools};
