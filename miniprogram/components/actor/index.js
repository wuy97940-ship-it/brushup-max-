const resources=require('../../data/characters');
const art=require('../../data/shop_art');
const finance=require('../../data/finance_config');
const Art=require('../../utils/assets');
const Hunting=require('../../data/hunting600');
const Outfits610=require('../../data/outfits610');
Component({
 properties:{skin:{type:String,value:'xiaoyuan'},pose:{type:String,value:'idle'},outfit:{type:String,value:''},xp:{type:String,value:''},coins:{type:String,value:''},wonder:{type:String,value:''},companion:{type:String,value:''},companions:{type:Array,value:[]}},
 data:{image:'',layers:[],backLayers:[],costume:null,costumeVisible:false,outfitError:false,loadedImages:[],failedImages:[]},
 observers:{'skin,pose,outfit,xp,coins,wonder,companion,companions':function(){this.refreshActor();}},
 lifetimes:{attached(){this.alive=true;this.artReady=!!getApp().financeArtReady;this.friendLoads=new Set();this.outfitLoads=new Set();this.outfitFailures=new Set();this.refreshActor();},detached(){this.alive=false;}},
 methods:{
  refreshActor(){
   const {skin,pose,outfit,xp,coins,wonder,companion}=this.data,app=getApp();
   this.artReady=!!app.financeArtReady;
   const c=resources.characters[skin]||resources.characters.xiaoyuan,actualPose=c.poses[pose]?pose:c.aliases[pose]||'idle',image=c.poses[actualPose]||c.poses.idle,catalogOutfit=finance.outfits.find(x=>x.id===outfit),look=Outfits610.look(outfit,skin,actualPose);
   const layers=[look?'':outfit,xp,coins].filter(id=>id&&(id!==outfit||!catalogOutfit||catalogOutfit.fit_character===skin)).map(id=>resources.overlays[id]||(finance.outfits.find(x=>x.id===id)?.asset?'/assets/'+finance.outfits.find(x=>x.id===id).asset:'')).filter(Boolean),backLayers=[],needed=[image,...layers];
   const extra=art.wonders[wonder];if(extra){(extra.position==='back'?backLayers:layers).push(extra.layer);needed.push(extra.layer);}
   const ids=(this.data.companions.length?this.data.companions:[companion].filter(Boolean)).slice(0,2),media=app.huntingMedia;
   const friendImages=ids.map(id=>{const ref=Hunting.art[id];if(ref&&media){if(media.isReady(ref.package))return ref.path;if(this.alive&&!this.friendLoads.has(ref.package)){this.friendLoads.add(ref.package);void media.load(ref.package).then(()=>{if(this.alive)this.refreshActor();}).catch(()=>{this.friendLoads.delete(ref.package);});}return '';}const friend=finance.companions.find(c=>c.id===id);if(!friend)return '';const path='/assets/'+friend.asset;needed.push(path);return Art.readyImage(path,this.artReady);}).filter(Boolean);
   this.currentLook610=look;
   const costume=look&&app.outfit610Ready?.[look.package]?look:null,outfitError=!!look&&(this.outfitFailures?.has(look.package)||this.data.failedImages.includes(look.src));
   this.setData({image:Art.readyImage(image,this.artReady),layers:layers.map(p=>Art.readyImage(p,this.artReady)).filter(Boolean),backLayers:backLayers.map(p=>Art.readyImage(p,this.artReady)).filter(Boolean),friendImages,costume,costumeVisible:!!costume&&this.data.loadedImages.includes(costume.src)&&!outfitError,outfitError});
   // 初始主角在主包内；只有实际穿戴/同行需要跨包图片时才下载。
   if(this.alive&&!this.artReady&&!this.artLoading&&needed.some(p=>Art.routes[p])){this.artLoading=true;void app.loadFinanceArt().then(()=>{this.artLoading=false;if(this.alive)this.refreshActor();}).catch(()=>{this.artLoading=false;});}
   if(this.alive&&look&&!app.outfit610Ready?.[look.package]&&!this.outfitLoads.has(look.package)&&!this.outfitFailures.has(look.package)){
    this.outfitLoads.add(look.package);void app.loadOutfitArt610(look.package).then(()=>{this.outfitLoads.delete(look.package);if(this.alive)this.refreshActor();}).catch(()=>{this.outfitLoads.delete(look.package);this.outfitFailures.add(look.package);if(this.alive)this.refreshActor();});
   }
  },
  retryOutfit610(){const look=this.currentLook610;if(!look)return;this.outfitFailures.delete(look.package);this.setData({outfitError:false,costume:null,costumeVisible:false,loadedImages:this.data.loadedImages.filter(s=>s!==look.src),failedImages:this.data.failedImages.filter(s=>s!==look.src)},()=>{if(this.alive)this.refreshActor();});},
  imageLoaded(e){if(!this.alive)return;const src=e.currentTarget.dataset.src;if(!src)return;this.setData({loadedImages:[...new Set([...this.data.loadedImages,src])],failedImages:this.data.failedImages.filter(s=>s!==src)});this.refreshActor();},
  imageFailed(e){if(!this.alive)return;const src=e.currentTarget.dataset.src;if(!src)return;this.setData({failedImages:[...new Set([...this.data.failedImages,src])]});this.refreshActor();}
 }
});
