const {draw}=require('../../utils/diagrams600');
const diagrams=require('../../data/question_diagrams600');
Component({
 properties:{diagramId:{type:String,value:''}},data:{error:''},
 observers:{diagramId(){if(this.ready)this.renderDiagram();}},
 lifetimes:{attached(){this.ready=true;this.renderDiagram();},detached(){this.ready=false;if(this.canvas&&this.frame)this.canvas.cancelAnimationFrame(this.frame);this.canvas=null;}},
 methods:{
  renderDiagram(){const id=this.data.diagramId;if(!id)return;const kind=diagrams[id]?.kind;if(!kind){this.failed(id,'这道题的重绘图尚未准备好，请先返回地图。');return;}
   this.createSelectorQuery().select('#curve600').fields({node:true,size:true}).exec(rows=>{if(!this.ready||this.data.diagramId!==id)return;const item=rows?.[0];if(!item?.node||!item.width||!item.height){this.failed(id,'图表未能显示，请更新微信后重试。');return;}
    try{const canvas=item.node,ratio=(wx.getWindowInfo?wx.getWindowInfo():wx.getSystemInfoSync()).pixelRatio||1;canvas.width=Math.round(item.width*ratio);canvas.height=Math.round(item.height*ratio);const ctx=canvas.getContext('2d');ctx.scale(ratio,ratio);draw(ctx,item.width,item.height,kind);this.canvas=canvas;this.setData({error:''});this.frame=canvas.requestAnimationFrame(()=>{if(this.ready&&this.data.diagramId===id)this.triggerEvent('diagramstatus',{id,ready:true});});}
    catch(e){this.failed(id,'图表绘制失败，请返回地图后重试。');}
   });
  },
  failed(id,error){this.setData({error});this.triggerEvent('diagramstatus',{id,ready:false,error});}
 }
});
