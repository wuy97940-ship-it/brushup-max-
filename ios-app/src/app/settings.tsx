import {useState} from 'react';
import {Modal, ScrollView, Switch, View} from 'react-native';
import {SafeAreaView} from 'react-native-safe-area-context';
import {router} from 'expo-router';
import {Button,Card,Row,Screen,Txt} from '../components/ui';
import {pickBackup,shareBackup} from '../services/backup';
import {bank} from '../services/rules';
import {useAdventure} from '../state/AdventureProvider';
export default function Settings(){const {p,run,act,exportBackup,importBackup}=useAdventure();const [incoming,setIncoming]=useState<string|null>(null);
 return <Screen title="我的设置" header={false} sub="让冒险舒适一点，也让存档安全一点。">
  <Button label="返回冒险" secondary onPress={()=>router.canGoBack()?router.back():router.replace('/')}/>
  <Card><Row style={{justifyContent:'space-between'}}><Txt kind="label">深色主题</Txt><Switch accessibilityLabel="深色主题" value={p.theme==='dark'} onValueChange={value=>{void act(async()=>{await run((v:any)=>{v.theme=value?'dark':'light';});});}}/></Row><Row style={{justifyContent:'space-between'}}><Txt kind="label">减少动画</Txt><Switch accessibilityLabel="减少动画" value={!!p.reduce_motion} onValueChange={value=>{void act(async()=>{await run((v:any)=>{v.reduce_motion=value;});});}}/></Row></Card>
  <Card><Txt kind="h2">存档备份</Txt><Txt>存档保存在当前设备。可导出JSON，再在另一台设备手动导入同题库的备份。</Txt><Txt kind="small">iPhone、iPad、电脑版和微信分别保存学习进度。原创版和私人教材版使用各自的备份。</Txt>
    <Button label="导出当前存档" onPress={()=>{void act(async()=>shareBackup(exportBackup()));}}/>
    <Button label="选择备份文件" secondary onPress={()=>{void act(async()=>{const text=await pickBackup();if(text)setIncoming(text);});}}/>
  </Card>
  <Card><Txt kind="h2">关于与隐私</Txt><Txt>小圆冒险世界 0.2.0 · 原创候选版</Txt><Txt kind="small">题库：{Object.keys(bank.questions).length}题 · 会计、经济法与财务成本管理。角色图、解析和规则随应用提供，可离线刷题。</Txt><Txt kind="small">本版不要求学习账号，不含广告、充值、购买金币或第三方统计。答案、金币、等级、收藏与装扮仅保存到当前设备；导出备份时由你选择系统文件或分享目的地。</Txt><Txt kind="small">相册、相机、麦克风、联系人和定位均不用于刷题。导入/导出通过系统文件选择与分享完成。Expo Go体验环境的网络与诊断行为由其宿主应用提供；这不等于独立App已上线。</Txt><Txt kind="small">公开版题目为本项目编写的候选学习内容。正式上架前还需完成内容复核、真机验收及苹果审核。</Txt></Card>
  <Button label="隐私说明、使用帮助与软件许可" secondary onPress={()=>router.push('/about')}/>
  <Modal visible={!!incoming} transparent animationType="fade" onRequestClose={()=>setIncoming(null)}><SafeAreaView style={{flex:1,backgroundColor:'#102643aa',justifyContent:'center',padding:24}}><ScrollView contentContainerStyle={{flexGrow:1,justifyContent:'center',alignItems:'center'}}><View style={{maxWidth:500,width:'100%'}}><Card><Txt kind="h2">导入备份</Txt><Txt>确认后将替换当前设备的原创版存档。请先导出当前存档留作回退。题库不匹配的文件会被拒绝。</Txt><Button label="先导出当前存档" secondary onPress={()=>{void act(async()=>shareBackup(exportBackup()));}}/><Button label="确认导入并替换" onPress={()=>{void act(async()=>{await importBackup(incoming!);setIncoming(null);});}}/><Button label="取消导入" secondary onPress={()=>setIncoming(null)}/></Card></View></ScrollView></SafeAreaView></Modal>
 </Screen>;
}
