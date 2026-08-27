(()=>{'use strict';
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const VIEW='atlas_dashboard_view';
const TAB_LABEL={projects:'Проекты',files:'Файлы',plugins:'Интеграции',actions:'Шаблоны',auto:'Инструменты'};
let appObserver=null;
function labelOf(b){return b?.querySelector('span:last-child')?.textContent?.trim()||b?.textContent?.trim()||''}
function storedTab(){try{return localStorage.getItem('atlas_active_tab')||''}catch{return''}}
function storedView(){try{return localStorage.getItem(VIEW)==='chat'?'chat':'home'}catch{return'home'}}
function saveView(v){try{localStorage.setItem(VIEW,v)}catch{}}
function tabButton(name){return $$('[data-tab]').find(x=>String(x.dataset.tab||'').toLowerCase()===name)}
function tapTab(name){tabButton(name)?.click()}
function setActive(label){const nav=$('#atlasRefNav');if(!nav||!label)return;$$('.ref-nav-item',nav).forEach(b=>{const on=labelOf(b)===label;b.classList.toggle('active',on);if(on)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current')})}
function setFocusChat(on){document.body.classList.toggle('atlas-chat-focus',!!on);saveView(on?'chat':'home')}
function closeCenters(){window.AtlasTemplates?.close?.();window.AtlasToolsCenter?.close?.();window.AtlasIntegrations?.close?.();const settings=$('#settingsCard');if(settings&&!settings.classList.contains('hidden'))settings.classList.add('hidden')}
function home(){closeCenters();setFocusChat(false);tapTab('chat');setActive('Главная');window.AtlasHomeSummary?.refresh?.();setTimeout(()=>$('#chatList')?.scrollTo?.({top:0,behavior:'smooth'}),30)}
function chat(){closeCenters();setFocusChat(true);tapTab('chat');setActive('Чат');setTimeout(()=>{const list=$('#chatList');if(list)list.scrollTop=list.scrollHeight;$('#messageInput')?.focus()},30)}
function projects(){closeCenters();setFocusChat(false);tapTab('projects');setActive('Проекты')}
function files(){closeCenters();setFocusChat(false);tapTab('files');setActive('Файлы')}
function tools(){closeCenters();setFocusChat(false);setActive('Инструменты');window.AtlasToolsCenter?.open?.()||tapTab('plugins')}
function templates(){closeCenters();setFocusChat(false);setActive('Шаблоны');window.AtlasTemplates?.open?.()||tapTab('actions')}
function integrations(){closeCenters();setFocusChat(false);setActive('Интеграции');window.AtlasIntegrations?.open?.()||tapTab('plugins')}
function settings(){closeCenters();setFocusChat(false);setActive('Настройки');$('#settingsBtn')?.click()}
const ACTIONS={'Главная':home,'Чат':chat,'Проекты':projects,'Инструменты':tools,'Файлы':files,'Шаблоны':templates,'Интеграции':integrations,'Настройки':settings};
function overlayLabel(){if($('.atlas-tools-overlay,.atlas-tools-center'))return'Инструменты';if($('.atlas-templates-overlay,.atlas-templates'))return'Шаблоны';if($('.integrations-overlay,.integrations-modal'))return'Интеграции';const settingsCard=$('#settingsCard');if(settingsCard&&!settingsCard.classList.contains('hidden'))return'Настройки';if($('.code-live,.video-live,.shop-live,.automation-live,.studio-workspace'))return'Инструменты';return''}
function sync(){const overlay=overlayLabel();if(overlay){setActive(overlay);return}const tab=$('.app-shell')?.dataset.activeTab||storedTab()||'chat';if(tab==='chat'){const focus=storedView()==='chat';document.body.classList.toggle('atlas-chat-focus',focus);setActive(focus?'Чат':'Главная');return}document.body.classList.remove('atlas-chat-focus');setActive(TAB_LABEL[tab]||'Главная')}
function bindAppObserver(){const app=$('.app-shell');if(!app||app.dataset.navObserved)return;app.dataset.navObserved='1';appObserver=new MutationObserver(sync);appObserver.observe(app,{attributes:true,attributeFilter:['data-active-tab']})}
document.addEventListener('click',e=>{const ref=e.target.closest?.('.ref-nav-item');if(ref){const label=labelOf(ref),fn=ACTIONS[label];if(fn){e.preventDefault();e.stopImmediatePropagation();fn();return}}const tab=e.target.closest?.('[data-tab]');if(tab){const id=String(tab.dataset.tab||'').toLowerCase();if(id==='chat'){setFocusChat(false);setActive('Главная')}else if(TAB_LABEL[id])setActive(TAB_LABEL[id]);return}const tool=e.target.closest?.('.dash-tool-card');if(tool){setActive('Инструменты');return}if(e.target.closest?.('#settingsBtn,.ref-profile')){setActive('Настройки');return}if(e.target.closest?.('#closeSettingsBtn'))setTimeout(sync,0)},true);
new MutationObserver(()=>{bindAppObserver();const nav=$('#atlasRefNav');if(nav&&!nav.dataset.navState){nav.dataset.navState='1';sync()}else if(nav)sync()}).observe(document.documentElement,{childList:true,subtree:true});
window.addEventListener('pageshow',()=>{bindAppObserver();sync()});
document.readyState==='loading'?document.addEventListener('DOMContentLoaded',()=>{bindAppObserver();sync()},{once:true}):(bindAppObserver(),sync());
window.AtlasNavState={setActive,sync,home,chat};
})();