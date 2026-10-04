// 共用模块从微信1.1.0源导出；bank/campaign使用独立原创版。
export const G: any = require('../shared/utils/game');
export const Finance: any = require('../shared/utils/finance');
// 这是存档规则函数；命名避开 React Hook 的 use 前缀。
export const mercyClear: (p:any)=>any = G.useMercy;
export const Skills: any = require('../shared/utils/skills');
export const Shop: any = require('../shared/utils/shop');
export const characters: any = require('../shared/data/characters');
export const art: any = require('../shared/data/shop_art');
export const bank: any = require('../content/original-bank.json');
export const questions: Record<string, Question> = bank.questions;
export type NumericCheck = {key:string;label:string;value:string;unit:string;decimals:number|null;exact:boolean};
export type Subquestion = {id:string;prompt:string;reference:string;checks:string[];process_checklist:string[]};
export type Analysis = {position:string;principle:string;formulas:string[];steps:string[];option_analysis:Record<string,string>;units:string;pitfalls:string[];memory:string};
export type Question = { id:string; book_id:string; chapter_no:number; chapter:string; type:string; stem:string; options:Record<string,string>; answer:string; explanation:string; difficulty:number; source_id:string;source_ref?:any;analysis?:Analysis;subquestions?:Subquestion[];numeric_checks?:NumericCheck[];stem_images?:string[];reference_images?:string[];stem_images_primary?:boolean;reference_images_primary?:boolean;original_explanation?:string };
export const normalize = (s:string) => s.replace(/[,，、\s]/g,'').split('').sort().join('');
export const answerCorrect = (q:Question, answer:string) => q.type === '判断题' ? q.answer === answer : normalize(q.answer) === normalize(answer);
