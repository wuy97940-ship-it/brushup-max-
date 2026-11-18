// 局部Canvas仅在短动作期间绘制，等待答题时不运行动画循环；精灵图解码一次复用。
Component({
 properties:{targetId:{type:String,value:''},image:{type:String,value:''},ball:{type:String,value:''},heroImage:{type:String,value:''},biome:{type:String,value:'forest'},action:{type:Object,value:null},reducedMotion:{type:Boolean,value:false}},
 observers:{'image,ball,heroImage':function(){this.loadImages();},action:function(){this.animate();}},
 lifetimes:{attached(){this.alive=true;this.hidden=false;this.createSelectorQuery().select('#hunt-scene').fields({node:true,size:true}).exec(rows=>{const r=rows[0];if(!this.alive||!r?.node)return;this.canvas=r.node;this.width=r.width;this.height=r.height;const d=Math.min(2,(wx.getWindowInfo?wx.getWindowInfo():wx.getSystemInfoSync()).pixelRatio||1);this.canvas.width=Math.round(r.width*d);this.canvas.height=Math.round(r.height*d);this.ctx=this.canvas.getContext('2d');this.ctx.scale(d,d);this.loadImages();});},detached(){this.alive=false;this.cancel();this.targetImage=null;this.ballImage=null;this.heroImage=null;this.ctx=null;this.canvas=null;}},
 pageLifetimes:{hide(){this.hidden=true;this.cancel();},show(){this.hidden=false;this.draw();}},
 methods:{
  cancel(){if(this.frameId!=null&&this.canvas)this.canvas.cancelAnimationFrame(this.frameId);this.frameId=null;},
  loadImages(){if(!this.canvas||!this.alive)return;const key=this.data.image+'|'+this.data.ball+'|'+this.data.heroImage;if(this.imageKey===key)return;this.imageKey=key;this.cancel();this.targetImage=null;this.ballImage=null;this.heroImage=null;const sources=[[this.data.image,'targetImage'],[this.data.ball,'ballImage'],[this.data.heroImage,'heroImage']].filter(([src])=>!!src);let waiting=sources.length,error=false;const done=()=>{if(waiting||!this.alive||this.imageKey!==key)return;this.draw();this.triggerEvent('ready',{id:this.data.targetId,ready:!error&&!!this.targetImage,error:error?'猎场图片未加载，请重试':''});};
   for(const [src,field]of sources){const image=this.canvas.createImage();image.onload=()=>{if(!this.alive||this.imageKey!==key)return;this[field]=image;waiting--;done();};image.onerror=()=>{if(!this.alive||this.imageKey!==key)return;error=true;waiting--;done();};image.src=src;}done();
  },
  animate(){if(!this.ctx||!this.alive||this.hidden)return;this.cancel();const a=this.data.action;if(!a||this.data.reducedMotion){this.draw();return;}const started=Date.now(),duration=a.kind==='throw'||a.kind==='capture'?800:600;let previous=-Infinity;const frame=()=>{if(!this.alive||this.hidden)return;const elapsed=Date.now()-started;if(elapsed-previous>=30||elapsed>=duration){previous=elapsed;this.draw(a,Math.min(1,elapsed/duration));}if(elapsed<duration)this.frameId=this.canvas.requestAnimationFrame(frame);else {this.frameId=null;this.draw();}};frame();
  },
  draw(a=null,t=0){const c=this.ctx;if(!c||!this.alive||this.hidden)return;const w=this.width,h=this.height,colors=this.data.biome==='stars'?['#28264F','#53477C']:this.data.biome==='island'?['#D7F3FF','#A9DDE3']:['#DBF1DE','#AED5B5'];c.clearRect(0,0,w,h);c.fillStyle=colors[0];c.fillRect(0,0,w,h);c.fillStyle=colors[1];c.fillRect(0,h*.72,w,h*.28);
   const radius=h*.31,x=w*.73,y=h*.46,pulse=a?.kind==='correct'?1+Math.sin(t*Math.PI)*.06:1;c.save();c.globalAlpha=a?.kind==='capture'&&t>.6?Math.max(.1,1-(t-.6)*2):1;if(this.targetImage)c.drawImage(this.targetImage,x-radius*pulse,y-radius*pulse,radius*2*pulse,radius*2*pulse);c.restore();
   if(this.heroImage)c.drawImage(this.heroImage,w*.04,h*.22,h*.54,h*.54);
   if(!a)return;
   const reverse=a.kind==='ultimate',progress=Math.min(1,t/.8),sx=reverse?x:w*.19,ex=reverse?w*.19:x,bx=sx+(ex-sx)*progress,by=h*.48-Math.sin(progress*Math.PI)*h*.26;
   if(a.kind==='throw'||a.kind==='capture'){const size=h*.2;if(this.ballImage)c.drawImage(this.ballImage,bx-size/2,by-size/2,size,size);else {c.fillStyle='#3B82F6';c.beginPath();c.arc(bx,by,size/3,0,Math.PI*2);c.fill();}}
   else {c.fillStyle=a.color||'#3B82F6';c.beginPath();c.arc(bx,by,8,0,Math.PI*2);c.fill();for(let i=0;i<8;i++){const angle=i*Math.PI/4,spread=t*h*.2;c.beginPath();c.arc(bx+Math.cos(angle)*spread,by+Math.sin(angle)*spread,2.5,0,Math.PI*2);c.fill();}}
  }
 }
});
