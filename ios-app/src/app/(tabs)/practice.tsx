import {useState} from 'react';
import {router} from 'expo-router';
import {Button, Card, Row, Screen, Txt} from '../../components/ui';
import {G, questions} from '../../services/rules';
import {useAdventure} from '../../state/AdventureProvider';
export default function Practice(){const {p,run,act}=useAdventure();const [world,setWorld]=useState('accounting'),[chapter,setChapter]=useState(0),[filter,setFilter]=useState('all');
 const w=p.game.campaign.worlds.find((v:any)=>v.id===world),prefix=world==='accounting'?'acc':world==='finance'?'cg_original_':'law';
 const ids=Object.values(questions).filter(q=>q.book_id.startsWith(prefix)&&(chapter===0||q.chapter_no===chapter)&&(filter==='all'||filter==='wrong'&&p.wrong_book.includes(q.id)||filter==='favorites'&&p.favorites.includes(q.id)||filter==='subjective'&&G.subjective(q))).map(q=>q.id);
 const records=Object.values(p.answered) as any[],correct=records.filter(r=>r.correct).length;
 return <Screen title="学习小屋" sub="慢慢复盘，把薄弱处练成拿手题。">
  <Card><Txt kind="h2">学习足迹</Txt><Txt>已作答 {records.length} / {Object.keys(questions).length} 题 · 最近作答正确 {correct} 题</Txt><Txt kind="small">当前错题 {p.wrong_book.length} · 收藏 {p.favorites.length}。统计采用每题最近一次作答，冒险星级单独保存。</Txt></Card>
  <Row>{p.game.campaign.worlds.map((w:any)=><Button key={w.id} label={w.name} secondary={world!==w.id} onPress={()=>{setWorld(w.id);setChapter(0);}}/>)}</Row>
  <Row>{[['all','全部'],['wrong','当前错题'],['favorites','收藏'],['subjective','案例题']].map(([id,label])=><Button key={id} label={label} secondary={filter!==id} onPress={()=>setFilter(id)}/>)}</Row>
  <Card><Txt kind="h2">选择章节</Txt><Row><Button label="全部章节" secondary={chapter!==0} onPress={()=>setChapter(0)}/>{w.chapters.map((ch:any)=><Button key={ch.id} label={ch.number+'. '+ch.title} secondary={chapter!==ch.number} onPress={()=>setChapter(ch.number)}/>)}</Row></Card>
  <Card><Txt kind="h2">找到 {ids.length} 道题</Txt><Txt kind="small">自由刷题不发金币或经验，答题继续更新错题与学习记录。技能仍可按次数使用。</Txt><Button label="开始这组复习" disabled={!ids.length} onPress={()=>{void act(async()=>{await run((v:any)=>G.startPractice(v,ids,'原创题复习'));router.push({pathname:'/quiz',params:{practice:'1'}});});}}/>
    {p.practice&&!p.practice.settled&&<Button label="恢复未完成复习" secondary onPress={()=>router.push({pathname:'/quiz',params:{practice:'1'}})}/>}
  </Card>
 </Screen>;
}
