import React, {useEffect,useRef} from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextStyle, View, ViewStyle, useWindowDimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { useAdventure } from '../state/AdventureProvider';
import { G, Shop } from '../services/rules';
import { Actor } from './Actor';

export function usePalette(){const {p}=useAdventure();return p.theme==='dark'?{bg:'#13213b',card:'#1d3050',text:'#edf4ff',muted:'#a3b7d3',soft:'#263e65',line:'#3c567c',blue:'#6eb1ff',accent:'#ebbd61',good:'#72d6b7',bad:'#ff97a2'}:{bg:'#eff5ff',card:'#fff',text:'#173453',muted:'#6b819d',soft:'#e4efff',line:'#d4e3f6',blue:'#2269dd',accent:'#ae7d21',good:'#21876e',bad:'#cc5264'};}
export function Txt({children,kind='body',style,...props}:{children?:React.ReactNode;kind?:'title'|'h2'|'body'|'small'|'label';style?:TextStyle}&React.ComponentProps<typeof Text>){const c=usePalette();return <Text {...props} style={[textStyles[kind],{color:kind==='small'?c.muted:c.text},style]}>{children}</Text>;}
export function Card({children,style}:{children:React.ReactNode;style?:ViewStyle}){const c=usePalette();return <View style={[{backgroundColor:c.card,borderRadius:22,padding:20,gap:12},style]}>{children}</View>;}
export function Button({label,onPress,secondary=false,disabled=false,testID,style}:{label:string;onPress:()=>void;secondary?:boolean;disabled?:boolean;testID?:string;style?:ViewStyle}){const c=usePalette(),{busy}=useAdventure();return <Pressable testID={testID} accessibilityRole="button" accessibilityLabel={label} accessibilityState={{disabled:disabled||busy}} disabled={disabled||busy} onPress={onPress} style={({pressed})=>[{minHeight:48,paddingHorizontal:18,paddingVertical:14,borderRadius:15,alignItems:'center',justifyContent:'center',backgroundColor:secondary?c.soft:'#2269dd',opacity:disabled||busy?0.45:pressed?0.8:1},style]}><Text style={{fontSize:16,fontWeight:'700',color:secondary?c.blue:'#fff',textAlign:'center'}}>{label}</Text></Pressable>;}
export function Row({children,style}:{children:React.ReactNode;style?:ViewStyle}){return <View style={[{flexDirection:'row',alignItems:'center',gap:12,flexWrap:'wrap'},style]}>{children}</View>;}
export function Columns({children}:{children:React.ReactNode}){const {width}=useWindowDimensions();return <View style={{flexDirection:'row',flexWrap:'wrap',gap:16}}>{React.Children.map(children,child=><View style={{width:width>=780?'48.5%':'100%'}}>{child}</View>)}</View>;}
export function Bar({value,color}:{value:number;color?:string}){const c=usePalette();return <View accessibilityRole="progressbar" accessibilityValue={{min:0,max:100,now:Math.round(value)}} style={{height:8,borderRadius:8,overflow:'hidden',backgroundColor:c.soft}}><View style={{height:8,width:`${Math.min(100,Math.max(0,value))}%`,backgroundColor:color||c.blue,borderRadius:8}}/></View>;}
export function Screen({children,title,sub,header=true,scrollKey}:{children:React.ReactNode;title:string;sub?:string;header?:boolean;scrollKey?:string}){
  const {p,pending,loadError,retry,busy}=useAdventure();const c=usePalette();const g=p.game,shop=Shop.view(g);
  const scroll=useRef<ScrollView>(null);
  useEffect(()=>{scroll.current?.scrollTo({y:0,animated:false});},[scrollKey]);
  return <SafeAreaView edges={['top','left','right']} style={{flex:1,backgroundColor:c.bg}}><ScrollView ref={scroll} keyboardShouldPersistTaps="handled" contentContainerStyle={{padding:20,paddingBottom:36,alignItems:'center'}}><View style={{width:'100%',maxWidth:1100,gap:20}}>
    <Row style={{justifyContent:'space-between'}}><View style={{flex:1}}><Txt kind="small" style={{letterSpacing:2,color:c.blue}}>XIAOYUAN · ADVENTURE</Txt><Txt kind="title">{title}</Txt>{sub&&<Txt kind="small">{sub}</Txt>}</View><Button label="设置" secondary onPress={()=>router.push('/settings')}/></Row>
    {(pending||loadError)&&<Card style={{borderWidth:1,borderColor:c.bad}}><Txt style={{color:c.bad}}>{loadError||'本次操作还未保存。请重试后继续；不会重复抽奖或扣费。'}</Txt><Button label="重试保存或读取" onPress={()=>{void retry();}}/></Card>}
    {header&&<Row style={{justifyContent:'space-between'}}><Row style={{flex:1}}><Actor size={68}/><View style={{flex:1,gap:6}}><Txt kind="h2">Lv.{G.stats(g).level} {G.CATALOG[g.title]?.name||'知识冒险者'}</Txt><Bar value={shop.xpInLevel/5}/><Txt kind="small">{shop.xpInLevel} / 500 经验</Txt></View></Row><View style={{alignItems:'flex-end'}}><Txt kind="h2" style={{color:c.accent}}>✦ {g.coins}</Txt><Txt kind="small">金币</Txt></View></Row>}
    {busy&&<Txt kind="small">正在保存…</Txt>}{children}
  </View></ScrollView></SafeAreaView>;
}
const textStyles=StyleSheet.create({title:{fontSize:28,fontWeight:'800',lineHeight:40},h2:{fontSize:20,fontWeight:'700',lineHeight:28},body:{fontSize:16,lineHeight:26},small:{fontSize:13,lineHeight:21},label:{fontSize:15,fontWeight:'700',lineHeight:24}});
