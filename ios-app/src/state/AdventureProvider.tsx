import React, { createContext, useContext, useEffect, useRef, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { ActivityIndicator, Modal, Text, View, Pressable, StyleSheet } from 'react-native';
import { createStore } from '../services/transactionStore';
import { G } from '../services/rules';

type ContextValue = { p:any; busy:boolean; pending:boolean; loadError:string; run:<T>(change:(p:any)=>T)=>Promise<T>; act:(work:()=>Promise<unknown>)=>Promise<void>; retry:()=>Promise<void>; importBackup:(text:string)=>Promise<void>; exportBackup:()=>string; report:(s:string)=>void };
const Context = createContext<ContextValue|null>(null);
export function AdventureProvider({children}:{children:React.ReactNode}) {
  const [store] = useState(()=>createStore(AsyncStorage));
  const [p,setP] = useState<any>(store.progress);
  const [loaded,setLoaded] = useState(false), [busy,setBusy] = useState(false), [,setRevision] = useState(0), [message,setMessage] = useState('');
  const mounted = useRef(true);
  const sync = () => {if(mounted.current){setP(store.progress);setRevision(v=>v+1);setBusy(store.writing);}};
  useEffect(()=>{
    mounted.current=true;
    store.load().then(async()=>{if(!store.loadError&&G.needsGrowth(store.progress))await store.commit((v:any)=>G.claimGrowth(v));})
      .catch(e=>{if(mounted.current)setMessage(e.message);})
      .finally(()=>{if(mounted.current){setP(store.progress);setLoaded(true);setRevision(v=>v+1);}});
    return ()=>{mounted.current=false;};
  },[store]);
  async function run<T>(change:(v:any)=>T):Promise<T> {setBusy(true);try{return await store.commit(change) as T;}finally{sync();}}
  async function act(work:()=>Promise<unknown>){try{await work();}catch(e){if(mounted.current)setMessage(e instanceof Error?e.message:'操作未完成，请重试。');}finally{sync();}}
  async function retry(){await act(async()=>{setBusy(true);if(store.pending)await store.retry();else if(store.loadError)await store.load();setMessage('');});}
  const value:ContextValue={p,busy,pending:store.pending,loadError:store.loadError,run,act,retry,
    importBackup:async text=>{setBusy(true);try{await store.import(text);}finally{sync();}},exportBackup:()=>store.export(),report:setMessage};
  if(!loaded)return <View style={styles.loading}><ActivityIndicator size="large" color="#2269dd"/><Text style={styles.body}>正在打开冒险存档…</Text></View>;
  return <Context.Provider value={value}>{children}
    <Modal transparent visible={!!message} animationType="fade" onRequestClose={()=>setMessage('')}>
      <View style={styles.veil}><View style={styles.dialog} accessibilityViewIsModal><Text style={styles.title}>冒险提示</Text><Text style={styles.body}>{message}</Text>
        <Pressable accessibilityRole="button" accessibilityLabel="知道了" onPress={()=>setMessage('')} style={styles.button}><Text style={styles.buttonText}>知道了</Text></Pressable>
      </View></View>
    </Modal>
  </Context.Provider>;
}
export function useAdventure(){const value=useContext(Context);if(!value)throw Error('冒险状态尚未初始化');return value;}
const styles=StyleSheet.create({loading:{flex:1,alignItems:'center',justifyContent:'center',gap:18,backgroundColor:'#eff5ff'},veil:{flex:1,alignItems:'center',justifyContent:'center',backgroundColor:'#10264388',padding:24},dialog:{maxWidth:480,width:'100%',borderRadius:24,padding:26,backgroundColor:'#fff',gap:18},title:{fontSize:22,fontWeight:'800',color:'#173453'},body:{fontSize:16,lineHeight:26,color:'#314e70'},button:{backgroundColor:'#2269dd',padding:15,borderRadius:14,alignItems:'center'},buttonText:{color:'#fff',fontWeight:'700',fontSize:17}});
