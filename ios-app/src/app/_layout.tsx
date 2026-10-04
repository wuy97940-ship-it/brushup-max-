import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AdventureProvider, useAdventure } from '../state/AdventureProvider';
function Navigation(){const {p}=useAdventure();return <><StatusBar style={p.theme==='dark'?'light':'dark'}/><Stack screenOptions={{headerShown:false}}><Stack.Screen name="(tabs)"/><Stack.Screen name="quiz"/><Stack.Screen name="settings" options={{presentation:'modal'}}/></Stack></>;}
export default function Layout(){return <SafeAreaProvider><AdventureProvider><Navigation/></AdventureProvider></SafeAreaProvider>;}
