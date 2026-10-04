// 官方ES6编译把BigInt指数改成Math.pow，误拒有效数值；无BigInt VM另测兼容性。
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const file=path.join(root,'miniprogram/utils/finance.js');
const context=vm.createContext({BigInt:undefined});
const factory=vm.runInContext('(function(require,module,exports){'+fs.readFileSync(file,'utf8')+'\n})',context,{filename:file});
const moduleFixture={exports:{}};
factory(spec=>require(path.resolve(path.dirname(file),spec)),moduleFixture,moduleFixture.exports);
const F=moduleFixture.exports;
const spec=(value,extras={})=>({key:'value',label:'关键数值',value,unit:'元',decimals:2,exact:false,...extras});

// 独立使用 Node 的整数比值作为测试预言机；产品模块的 VM 完全没有此能力。
function oracle(expected,input,places,exact,shift){
 const ratio=value=>{const [whole,fraction='']=value.split('.');return {n:BigInt(whole+fraction),d:10n**BigInt(fraction.length)};};
 const w=ratio(expected),a=ratio(input);
 if(shift>=0)a.n*=10n**BigInt(shift);else a.d*=10n**BigInt(-shift);
 const signed=a.n*w.d-w.n*a.d,delta=signed<0n?-signed:signed;
 return exact?delta===0n:delta*2n*10n**BigInt(places)<=a.d*w.d;
}
test('无BigInt的环境可核对有效数值和百分比，并完成真实结构提交',()=>{
 assert.equal(vm.runInContext('typeof BigInt',context),'undefined');
 assert(F.numericCheck(spec('12.00',{unit:'%'}),'0.12','小数').correct);
 const q={id:'case',subquestions:[{id:'1',prompt:'收益率',reference:'12%',checks:['value']}],numeric_checks:[spec('12.00',{unit:'%'})]};
 const a={qids:['case'],answers:{},references:[],settled:false};
 F.saveDraft(a,q,'process','1','根据现金流及投资额计算收益率');
 F.saveDraft(a,q,'values','value','0.12');F.saveDraft(a,q,'units','value','小数');
 assert(F.prepareSubmission(a,q).checks[0].correct);F.setProcess(a,q,'1',true);
 assert(F.grade(a,q).record.correct);
});
test('100位整数保持精确，正负数、零和进退位不经浮点转换',()=>{
 const huge='9'.repeat(100);
 assert(F.numericCheck(spec(huge,{exact:true}),huge).correct);
 assert(!F.numericCheck(spec(huge,{exact:true}),huge.slice(0,-1)+'8').correct);
 assert(F.numericCheck(spec('0',{exact:true}),'-0.000').correct);
 assert(F.numericCheck(spec('-0.00'),'0.005').correct);
 assert(F.numericCheck(spec('-1.00'),'-0.995').correct);
 assert(!F.numericCheck(spec('-1.00'),'-0.9949999999999999').correct);
 assert(F.numericCheck(spec('1000.00'),'999.995').correct);
 assert(F.numericCheck(spec('999.99'),'999.995').correct);
});
test('30位精度的半单位、单位换算和边界外一位正确判定',()=>{
 const expected='0.'+'0'.repeat(29)+'1';
 assert(F.numericCheck(spec(expected,{decimals:30}),'0.'+'0'.repeat(29)+'15').correct);
 assert(!F.numericCheck(spec(expected,{decimals:30}),'0.'+'0'.repeat(29)+'1500001').correct);
 assert(F.numericCheck(spec('12.00',{unit:'%'}),'0.12005','小数').correct);
 assert(!F.numericCheck(spec('12.00',{unit:'%'}),'0.1200500001','小数').correct);
 assert(F.numericCheck(spec('123.45'),'0.0123445','万元').correct);
 assert(!F.numericCheck(spec('123.45'),'0.01234449999','万元').correct);
});
test('非数值、101位输入及不兼容单位仍拒绝',()=>{
 for(const input of ['', 'NaN','Infinity','1e9','1+2','123abc','9'.repeat(101)])assert(!F.numericCheck(spec('1'),input).correct,input);
 assert(!F.numericCheck(spec('1'),'1','%').correct);
 assert(F.numericCheck(spec('1234.50'),'1,234.50元').correct);
});
test('十进制字符串判定与独立整数比值比对4000种正负和单位组合',()=>{
 let seed=39017;const next=()=>seed=(Math.imul(seed,1664525)+1013904223)>>>0;
 for(let i=0;i<4000;i++){
  const make=()=>{const sign=next()%2?'-':'';const fraction=(next()%100000000).toString().padStart(8,'0');return sign+(next()%10000000)+'.'+fraction;};
  const expected=make(),input=i%4===0?expected:make(),places=next()%9,exact=!!(i%7===0),shift=[0,4,-4][next()%3];
  const expectedUnit=shift<0?'万元':'元',inputUnit=shift>0?'万元':'元';
  assert.equal(F.numericCheck(spec(expected,{unit:expectedUnit,decimals:places,exact}),input,inputUnit).correct,oracle(expected,input,places,exact,shift),String(i));
 }
});
test('公开财管40道案例的168个参考值在无BigInt环境都可核对',()=>{
 const data=JSON.parse(fs.readFileSync(path.join(root,'data/questions.json'),'utf8'));
 const questions=data.questions.filter(q=>q.book_id==='cg_original_v02'&&(q.numeric_checks||[]).length);
 const checks=questions.flatMap(q=>q.numeric_checks);
 assert.equal(questions.length,40);
 assert.equal(checks.length,168);
 for(const check of checks)assert(F.numericCheck(check,check.value,check.unit).correct,check.key+':'+check.value);
});
