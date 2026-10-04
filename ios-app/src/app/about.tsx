import {useState} from 'react';
import {router} from 'expo-router';
import {Button,Card,Row,Screen,Txt} from '../components/ui';
import support from '../release/support.json';
import notices from '../release/third-party-notices.json';

export default function About(){
 const [tab,setTab]=useState<'privacy'|'help'|'licenses'>('privacy');
 return <Screen title="隐私与使用帮助" header={false} sub="这些说明也可以离线阅读。">
  <Button label="返回设置" secondary onPress={()=>router.canGoBack()?router.back():router.replace('/settings')}/>
  <Row>{([['privacy','隐私说明'],['help','使用帮助'],['licenses','软件许可']] as const).map(([id,label])=><Button key={id} label={label} secondary={tab!==id} onPress={()=>setTab(id)}/>)}</Row>
  {tab==='privacy'&&<>
   <Card><Txt kind="h2">你的学习数据</Txt><Txt>作答记录、错题、收藏、关卡、金币、经验、技能、装备和设置保存在当前设备。本应用不向开发者上传这些学习数据。</Txt><Txt>本版没有广告、充值、付费金币、第三方统计或学习账号登录功能。</Txt></Card>
   <Card><Txt kind="h2">文件、备份与删除</Txt><Txt>只有你选择导入或导出时，应用才通过系统文件选择器或分享面板处理备份。备份包含学习进度，请自行保管，并留意你选择的分享目的地。</Txt><Txt>各设备的学习进度独立保存。卸载或清除应用数据可能丢失进度，建议先导出备份。网页版可在浏览器的网站数据设置中删除本地数据；原生版可通过系统管理应用数据。</Txt></Card>
   <Card><Txt kind="h2">设备权限与网络</Txt><Txt>刷题不使用相机、照片库、联系人、麦克风或定位。题目、解析和角色随应用提供。</Txt><Txt>浏览器版首次加载和检查更新需要访问托管服务，服务商会处理传输所需的网络请求信息；学习存档保留在设备。Expo Go开发体验的宿主网络与诊断行为由Expo Go提供。</Txt></Card>
   <Card><Txt kind="h2">联系与版本</Txt><Txt selectable>反馈渠道：{support.support_email}</Txt><Txt>反馈可通过项目仓库的Issues提交题号、复现步骤和修改建议。请避免发送个人存档或身份资料。</Txt><Txt kind="small">说明更新：{support.policy_version}。如果数据处理方式改变，我们会同步更新这些说明。</Txt></Card>
  </>}
  {tab==='help'&&<>
   <Card><Txt kind="h2">怎样闯关？</Txt><Txt>完成本轮全部题目，70%正确率解锁下一关，90%获得高质量通关，100%点亮三星。失败可以立即重试，本轮只计第一次提交。</Txt><Txt>案例Boss先填写自己的推理，再查看参考答案并自评。核心结论和关键理由均正确，才选择“掌握了”。</Txt></Card>
   <Card><Txt kind="h2">金币、装备与技能</Txt><Txt>金币来自学习奖励，可以兑换角色、换装和装备。试穿不扣金币；兑换前会展示价格与通关门槛。每500经验升一级，成长页可查看下一项技能。</Txt><Txt>“瞒天过海”只适用于普通关和远征差一题时继续前进，真实正确率和错题仍会保留。Boss需要按正常通关线完成。</Txt></Card>
   <Card><Txt kind="h2">恢复进度与反馈问题</Txt><Txt>退出后可恢复已保存的挑战。保存失败时先重试保存，再继续操作。设置页可以导出JSON备份，再在同题库版本中导入；导入前请备份当前进度。</Txt><Txt>反馈题目问题时，请提供科目、章节、题号、题干中的问题与建议。遇到页面问题可说明设备型号和操作步骤。</Txt><Txt selectable>联系：{support.support_email}</Txt></Card>
  </>}
  {tab==='licenses'&&<>
   <Card><Txt kind="h2">第三方软件许可</Txt><Txt>感谢以下开源项目。本页保留相关项目的版本、许可与声明。</Txt></Card>
   {notices.packages.map(item=><Card key={item.name}><Txt kind="h2">{item.name} {item.version}</Txt><Txt kind="small">{item.license}</Txt><Txt selectable kind="small">{item.text}</Txt></Card>)}
  </>}
 </Screen>;
}
