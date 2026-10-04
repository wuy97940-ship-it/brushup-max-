import React from 'react';
import {ScrollView, View} from 'react-native';
import {Txt,usePalette} from './ui';
import {blocks} from '../shared/utils/study_text.js';
type Block={kind:'text';text:string}|{kind:'table';columns:number;rows:string[][]};

export function StudyText({text,testID,small=false}:{text:string;testID?:string;small?:boolean}){
 const palette=usePalette(),parts=blocks(text) as Block[];
 return <View testID={testID} style={{gap:12}}>{parts.map((part,index)=>part.kind==='text'?<Txt key={index} selectable kind={small?'small':'body'}>{part.text}</Txt>:<View key={index} style={{gap:6}}>
  <Txt kind="small">左右滑动查看完整表格</Txt><ScrollView horizontal showsHorizontalScrollIndicator contentContainerStyle={{minWidth:'100%'}} style={{borderWidth:1,borderColor:palette.line,borderRadius:8}}>
   <View style={{minWidth:part.columns*120}}>{part.rows.map((row,r)=><View key={r} style={{flexDirection:'row',borderBottomWidth:r===part.rows.length-1?0:1,borderColor:palette.line,backgroundColor:r===0?palette.soft:palette.card}}>{row.map((cell,c)=><View key={c} style={{width:120,padding:10,borderRightWidth:c===row.length-1?0:1,borderColor:palette.line}}><Txt selectable style={{fontSize:14,lineHeight:23,fontWeight:r===0?'700':'400'}}>{cell}</Txt></View>)}</View>)}</View>
  </ScrollView>
 </View>)}</View>;
}
