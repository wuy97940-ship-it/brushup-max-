import { Platform } from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import * as Sharing from 'expo-sharing';
import { File, Paths } from 'expo-file-system';

export async function shareBackup(text:string) {
  const name = '小圆原创版存档-'+new Date().toISOString().slice(0,10)+'.json';
  if (Platform.OS === 'web') {
    const url = URL.createObjectURL(new Blob([text], {type:'application/json'}));
    const a = document.createElement('a'); a.href=url; a.download=name; a.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000); return;
  }
  const file = new File(Paths.cache, name); file.write(text);
  if (!await Sharing.isAvailableAsync()) throw Error('此设备暂不支持文件分享，请在可用设备上导出备份。');
  await Sharing.shareAsync(file.uri,{mimeType:'application/json',UTI:'public.json',dialogTitle:'保存小圆冒险存档'});
}
export async function pickBackup():Promise<string|null> {
  const result = await DocumentPicker.getDocumentAsync({type:['application/json','text/plain'],multiple:false,copyToCacheDirectory:true});
  if (result.canceled) return null;
  const asset = result.assets[0];
  if ((asset.size||0) > 5_000_000) throw Error('备份文件过大，请选择本应用导出的JSON存档。');
  if (Platform.OS === 'web' && asset.file) return asset.file.text();
  return new File(asset.uri).text();
}
