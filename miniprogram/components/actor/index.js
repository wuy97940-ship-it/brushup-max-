const resources=require('../../data/characters');
const art=require('../../data/shop_art');
const finance=require('../../data/finance_config');
const Art=require('../../utils/assets');
Component({
 properties:{skin:{type:String,value:'xiaoyuan'},pose:{type:String,value:'idle'},outfit:{type:String,value:''},xp:{type:String,value:''},coins:{type:String,value:''},wonder:{type:String,value:''},companion:{type:String,value:''}},
 data:{image:'',layers:[],backLayers:[],loadedImages:[],failedImages:[]},
 observers:{'skin,pose,outfit,xp,coins,wonder,companion':function(){this.refreshActor();}},
 lifetimes:{attached(){this.artReady=!!getApp().financeArtReady;this.refreshActor();void getApp().loadFinanceArt().then(()=>{this.artReady=true;this.refreshActor();}).catch(()=>{});}},
 methods:{
  refreshActor(){const {skin,pose,outfit,xp,coins,wonder,companion}=this.data;const c=resources.characters[skin]||resources.characters.xiaoyuan;const image=c.poses[pose]||c.poses[c.aliases[pose]]||c.poses.idle;const costume=finance.outfits.find(x=>x.id===outfit);let layers=[outfit,xp,coins].filter(id=>id&&(id!==outfit||!costume||costume.fit_character===skin)).map(id=>resources.overlays[id]||(finance.outfits.find(x=>x.id===id)?.asset?'/assets/'+finance.outfits.find(x=>x.id===id).asset:'')).filter(Boolean);const extra=art.wonders[wonder],backLayers=[];if(extra)(extra.position==='back'?backLayers:layers).push(extra.layer);layers=layers.map(path=>Art.readyImage(path,this.artReady)).filter(Boolean);const friend=finance.companions.find(c=>c.id===companion);this.setData({image:Art.image(image),layers,backLayers:backLayers.map(Art.image),friendImage:friend?Art.readyImage('/assets/'+friend.asset,this.artReady):''});},
  imageLoaded(e){const src=e.currentTarget.dataset.src;this.setData({loadedImages:[...new Set([...this.data.loadedImages,src])],failedImages:this.data.failedImages.filter(s=>s!==src)});},
  imageFailed(e){const src=e.currentTarget.dataset.src;this.setData({failedImages:[...new Set([...this.data.failedImages,src])]});}
 }
});
