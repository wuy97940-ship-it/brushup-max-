import {useEffect,useState} from 'react';
import {Button,Card,Txt} from './ui';
import {useAdventure} from '../state/AdventureProvider';

declare global {
 interface Window {xiaoyuanOffline?:string;xiaoyuanApplyUpdate?:()=>void;}
}
export function WebInstall(){
 const {run,act,pending,loadError}=useAdventure();
 const [offline,setOffline]=useState(typeof window==='undefined'?'preparing':window.xiaoyuanOffline||'preparing');
 const [help,setHelp]=useState(false);
 useEffect(()=>{const listener=()=>setOffline(window.xiaoyuanOffline||'preparing');window.addEventListener('xiaoyuan-offline',listener);listener();return ()=>window.removeEventListener('xiaoyuan-offline',listener);},[]);
 const messages:Record<string,string>={preparing:'正在准备离线包，请保持联网片刻。',ready:'离线包已就绪，断网也能继续刷题。',update:'发现新版本，保存进度后即可更新。',error:'离线包还未准备好，请联网重新打开。',unsupported:'当前浏览器暂不支持离线安装，请使用Safari打开正式网址。'};
 return <Card><Txt kind="h2">免费主屏幕版</Txt><Txt kind="small">当前为免费试玩版，原创基础题目持续校核中。</Txt><Txt kind="small">{messages[offline]||messages.preparing}</Txt>
  <Button label="如何添加到主屏幕" secondary onPress={()=>setHelp(!help)}/>
  {help&&<Txt>在iPhone或iPad的Safari中打开本网址，轻点“分享”，选择“添加到主屏幕”。以后点击小圆图标就可以打开。浏览器与主屏幕版可能独立保存进度，可通过设置里的JSON备份手动迁移。</Txt>}
  {offline==='update'&&<Button label="保存进度并更新" disabled={pending||!!loadError} onPress={()=>{void act(async()=>{await run(()=>{});window.xiaoyuanApplyUpdate?.();});}}/>}
 </Card>;
}
