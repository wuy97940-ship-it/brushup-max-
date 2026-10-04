import { Tabs } from 'expo-router';
import { Text } from 'react-native';
import { usePalette } from '../../components/ui';
export default function TabsLayout(){const c=usePalette();return <Tabs screenOptions={{headerShown:false,tabBarActiveTintColor:c.blue,tabBarInactiveTintColor:c.muted,tabBarStyle:{backgroundColor:c.card,borderTopColor:c.line,minHeight:66},tabBarLabelStyle:{fontSize:12,fontWeight:'600'}}}>
  {([['index','冒险','⌂'],['map','地图','♧'],['bag','背包','◇'],['growth','成长','✧'],['practice','复习','▤']] as const).map(([name,title,icon])=><Tabs.Screen key={name} name={name} options={{title,tabBarIcon:({color})=><Text style={{fontSize:23,color}}>{icon}</Text>}}/>)}
  </Tabs>;}
