import React, {useCallback,useState} from 'react';
import { Animated, Image, View } from 'react-native';
import { useFocusEffect } from 'expo-router';
import { useAdventure } from '../state/AdventureProvider';
import { characters, art, Finance } from '../services/rules';
import { imageAssets } from './imageAssets';

export function Actor({size=180,pose='idle',preview}:{size?:number;pose?:string;preview?:any}){
  const {p}=useAdventure();const g=p.game;
  const look=preview||{skin:g.skin,outfit:g.outfit,xp:g.equipment.xp,coins:g.equipment.coins,wonder:g.equipment.wonder};
  const ch=characters.characters[look.skin]||characters.characters.xiaoyuan;
  const src=ch.poses[pose]||ch.poses[ch.aliases[pose]]||ch.poses.idle;
  const costume=Finance.CONFIG.outfits.find((i:any)=>i.id===look.outfit);
  const back:string[]=[],front:string[]=[look.outfit,look.xp,look.coins].filter((id:string)=>id&&(id!==look.outfit||!costume||costume.fit_character===look.skin)).map((id:string)=>characters.overlays[id]||(Finance.CONFIG.outfits.find((i:any)=>i.id===id)?.asset?'/assets/'+Finance.CONFIG.outfits.find((i:any)=>i.id===id).asset:'')).filter(Boolean);
  const wonder=art.wonders[look.wonder];if(wonder)(wonder.position==='back'?back:front).push(wonder.layer);
  const [y]=useState(()=>new Animated.Value(0));
  useFocusEffect(useCallback(()=>{if(p.reduce_motion){y.setValue(0);return;}const motion=Animated.loop(Animated.sequence([Animated.timing(y,{toValue:pose==='attack'?-10:-5,duration:pose==='attack'?170:1100,useNativeDriver:true}),Animated.timing(y,{toValue:0,duration:pose==='attack'?180:1100,useNativeDriver:true})]));motion.start();return ()=>{motion.stop();y.setValue(0);};},[pose,p.reduce_motion,y]));
  const name=look.skin==='xiaoyuan'?'小圆':look.skin==='xiaobao'?'小宝':'小团';
  const friend=!preview&&Finance.CONFIG.companions.find((s:any)=>s.id===g.finance_expansion?.companion);
  return <Animated.View accessibilityLabel={name+'卡通形象'} accessibilityRole="image" style={{width:size,height:size,transform:[{translateY:y}]}}>
    {back.map(path=><Image key={path} source={imageAssets[path]} style={{position:'absolute',width:'100%',height:'100%'}} resizeMode="contain"/>)}
    <Image testID="actor-main" source={imageAssets[src]} style={{width:'100%',height:'100%'}} resizeMode="contain"/>
    {front.map(path=><Image key={path} source={imageAssets[path]} style={{position:'absolute',width:'100%',height:'100%'}} resizeMode="contain"/>)}
    {friend&&<Image accessibilityLabel={friend.name+'陪伴中'} source={imageAssets['/assets/'+friend.asset]} style={{position:'absolute',right:'-10%',bottom:0,width:'38%',height:'38%'}} resizeMode="contain"/>}
  </Animated.View>;
}
export function ItemImage({path,size=80}:{path?:string;size?:number}){return path&&imageAssets[path]?<Image source={imageAssets[path]} style={{width:size,height:size}} resizeMode="contain"/>:<View style={{width:size,height:size,alignItems:'center',justifyContent:'center'}}><Image source={imageAssets['/assets/shop/souvenir_stars.png']} style={{width:size*0.7,height:size*0.7}} resizeMode="contain"/></View>;}
