// 完整穿戴成品角色；各入口共用同一套动作图。
const {sheets}=require('./outfit_frames610');
const outfits={
 outfit_finance_xiaoyuan_sailing:{sheet:'xiaoyuan-sailing',skin:'xiaoyuan'},
 outfit_finance_xiaoyuan_workshop:{sheet:'xiaoyuan-workshop',skin:'xiaoyuan'},
 outfit_finance_orange_adventurer_sailing:{sheet:'orange-sailing',skin:'orange_adventurer'},
 outfit_finance_orange_adventurer_workshop:{sheet:'orange-workshop',skin:'orange_adventurer'}
};
const hats={outfit_forest:'hat-forest',outfit_island:'hat-island',outfit_snow:'hat-snow',outfit_ruins:'hat-ruins',outfit_sky:'hat-sky',outfit_stars:'hat-stars'};
const percent=n=>(Math.round(n*10000)/10000)+'%';
function look(id,skin,pose='idle'){
 const definition=outfits[id];if(definition&&definition.skin!==skin)return null;
 const sheet=sheets[definition?.sheet||hats[id]],frames=sheet?.actors[skin];if(!frames)return null;
 const frame=frames[pose]||frames.idle;if(!frame)return null;
 const scale=94/Math.max(frame.width,frame.height),w=frame.width*scale,h=frame.height*scale;
 return {package:sheet.package,src:sheet.src,pose:frames[pose]?pose:'idle',frameStyle:'left:'+percent((100-w)/2)+';top:'+percent(98-h)+';width:'+percent(w)+';height:'+percent(h)+';',imageStyle:'left:'+percent(-frame.x*100/frame.width)+';top:'+percent(-frame.y*100/frame.height)+';width:'+percent(sheet.width*100/frame.width)+';height:'+percent(sheet.height*100/frame.height)+';'};
}
module.exports={outfits,hats,look};
