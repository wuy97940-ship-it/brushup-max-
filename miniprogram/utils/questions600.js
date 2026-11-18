// 与电脑learning_explanations同一优先级；已有展示修订和完整解析不得退回原始短文本。
const options=q=>q.display_options&&Object.keys(q.display_options).length?q.display_options:q.options&&Object.keys(q.options).length?q.options:{};
const explanation=q=>String(q.detailed_explanation||q.explanation||'').trim();
module.exports={options,explanation};
