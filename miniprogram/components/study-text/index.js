const {blocks}=require('../../utils/study_text');
Component({properties:{content:{type:String,value:'',observer(value){this.setData({blocks:blocks(value)});}},theme:{type:String,value:'light'}},data:{blocks:[]}});
