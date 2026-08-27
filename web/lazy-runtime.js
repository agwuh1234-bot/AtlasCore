(()=>{'use strict';
const loaded=new Map();
const pending=new Map();
const groups={
  tools:['/app/tools-center.js'],
  templates:['/app/templates-center.js'],
  integrations:['/app/integrations-center.js'],
  settings:['/app/settings-center.js'],
  search:['/app/project-search.js'],
  share:['/app/share-center.js'],
  files:['/app/files.js','/app/studio-panels.js','/app/studio-viewers.js','/app/studio-results.js','/app/file-studio-live.js'],
  code:['/app/studio-panels.js','/app/studio-viewers.js','/app/studio-results.js','/app/code-studio-live.js'],
  video:['/app/studio-panels.js','/app/studio-viewers.js','/app/studio-results.js','/app/video-studio-live.js'],
  shopify:['/app/studio-panels.js','/app/studio-viewers.js','/app/studio-results.js','/app/shopify-studio-live.js'],
  automation:['/app/schedules.js','/app/studio-panels.js','/app/studio-viewers.js','/app/studio-results.js','/app/automation-studio-live.js','/app/automation-executions.js'],
  workspace:['/app/workspace-control.js'],
  support:['/app/recovery.js','/app/push.js','/app/control_center.js']
};
function existing(src){return [...document.scripts].some(s=>s.src&&new URL(s.src,location.href).pathname===src&&s.type!=='application/atlas-lazy')}
function loadScript(src){if(existing(src))return Promise.resolve();if(loaded.get(src))return loaded.get(src);const p=new Promise((resolve,reject)=>{const s=document.createElement('script');s.src=src+'?lazy=20260827b';s.defer=true;s.dataset.atlasLoaded='1';s.onload=()=>resolve();s.onerror=()=>reject(new Error('Не удалось загрузить '+src));document.head.appendChild(s)});loaded.set(src,p);return p}
async function loadGroup(name){if(pending.has(name))return pending.get(name);const p=(async()=>{for(const src of groups[name]||[])await loadScript(src);return true})();pending.set(name,p);try{return await p}finally{pending.delete(name)}}
function labelOf(target){const nav=target.closest?.('.ref-nav-item');if(nav)return nav.textContent.trim();const card=target.closest?.('.dash-tool-card,.atlas-tool-live-card,.atlas-template-card,.atlas-action-card');if(card)return card.textContent.trim();return target.textContent?.trim?.()||''}
function groupFromLabel(text){const t=String(text||'').toLowerCase();if(t.includes('code studio')||t.includes('code review')||t.includes('bug fix'))return'code';if(t.includes('video studio')||t.includes('ugc')||t.includes('reels')||t.includes('tiktok'))return'video';if(t.includes('shopify studio')||t.includes('product page')||t.includes('cro'))return'shopify';if(t.includes('file studio')||t==='файлы'||t.includes('анализ файла'))return'files';if(t.includes('automation studio')||t.includes('n8n'))return'automation';return''}
function openCenter(name){const api={tools:'AtlasToolsCenter',templates:'AtlasTemplatesCenter',integrations:'AtlasIntegrationsCenter',settings:'AtlasSettingsCenter',search:'AtlasProjectSearch',share:'AtlasShareCenter'}[name];const obj=api&&window[api];if(obj?.open){obj.open();return true}return false}
async function handleFeatureClick(e){if(e.__atlasLazyReplay)return;const target=e.target;const text=labelOf(target);let center='';if(text==='Инструменты'||target.closest?.('.dash-tool-card.add'))center='tools';else if(text==='Шаблоны')center='templates';else if(text==='Интеграции')center='integrations';else if(text==='Настройки'||target.closest?.('#settingsBtn'))center='settings';else if(/^поделиться$/i.test(text)||target.closest?.('[data-action="share"]'))center='share';
if(center){e.preventDefault();e.stopImmediatePropagation();try{await loadGroup(center);openCenter(center)}catch(err){console.error(err);window.AtlasNotice?.error?.('Не удалось открыть раздел')||void 0}return}
const feature=groupFromLabel(text);if(feature){const card=target.closest?.('.dash-tool-card,.atlas-tool-live-card,.atlas-template-card,.atlas-action-card,.ref-nav-item')||target;e.preventDefault();e.stopImmediatePropagation();try{await loadGroup(feature);const replay=new MouseEvent('click',{bubbles:true,cancelable:true,view:window});Object.defineProperty(replay,'__atlasLazyReplay',{value:true});card.dispatchEvent(replay)}catch(err){console.error(err);window.AtlasNotice?.error?.('Не удалось загрузить Studio')||void 0}}
}
window.addEventListener('click',e=>{void handleFeatureClick(e)},true);
window.addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&String(e.key).toLowerCase()==='k'){if(window.AtlasProjectSearch?.open)return;e.preventDefault();void loadGroup('search').then(()=>window.AtlasProjectSearch?.open?.())}},true);
setTimeout(()=>{void loadGroup('support')},6000);
window.AtlasLazy={loadGroup,loadScript,groups};
})();