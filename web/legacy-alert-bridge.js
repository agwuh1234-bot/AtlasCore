(()=>{'use strict';
const nativeAlert=typeof window.alert==='function'?window.alert.bind(window):null;
function classify(text){const v=String(text||'');if(/ошиб|не удалось|недоступ|failed|error|invalid|отказ/i.test(v))return'error';if(/вниман|проверь|предуп|warning/i.test(v))return'warn';if(/сохран|готов|успеш|добавлен|удалён|success|done/i.test(v))return'success';return'info'}
window.alert=function atlasAlert(message){const text=String(message??'');if(window.AtlasNotice?.show){window.AtlasNotice.show(text||'Atlas',{type:classify(text)});return}nativeAlert?.(text)};
window.AtlasLegacyUI={nativeAlert};
})();