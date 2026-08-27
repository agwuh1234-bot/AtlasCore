(()=>{'use strict';
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const VIEW='atlas_dashboard_view';
const TAB_LABEL={projects:'Проекты',files:'Файлы',plugins:'Интеграции',actions:'Шаблоны',auto:'Инструменты'};
let appObserver=null;
function labelOf(b){return b?.querySelector('span:last-child')?.textContent?.trim()||b?.textContent?.trim()||''}
function storedTab(){try{return localStorage.getItem('atlas_active_tab')||''}catch(_){return''}}
function storedView(){try{return localStorage.getItem(VIEW)==='chat'?'chat':'home'}catch(_){return'home'}}
function saveView(v){try{localStorage.setItem(VIEW,v)}catch(_){}}
function tabButton(name){return $$('[data-tab]').find(x=>String(x.dataset.tab||'').toLowerCase()===name)}
function tapTab(name){tabButton(name)?.click()}
function setActive(label){const nav=$('#atlasRefNav');if(!nav||!label)return;$$('.ref-nav-item',nav).forEach(b=>{const on=labelOf(b)===label;b.classList.toggle('active',on);if(on)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current')})}
function setFocusChat(on){document.body.classList.toggle('atlas-chat-focus',!!on);saveView(on?'chat':'home')}
function syncSidebarToggle(){const t=$('#atlasSidebarToggle');if(!t)return;const open=document.body.classList.contains('atlas-sidebar-open');t.setAttribute('aria-expanded',String(open));t.setAttribute('aria-label',open?'Скрыть меню':'Открыть меню')}
function collapseSidebar(){if(innerWidth>=980)return;document.body.classList.remove('atlas-sidebar-open');try{localStorage.setItem('atlas_sidebar_open','0')}catch(_){}syncSidebarToggle()}
function closeCenters(){window.AtlasTemplates?.close?.();window.AtlasToolsCenter?.close?.();window.AtlasIntegrations?.close?.();window.AtlasSettingsCenter?.close?.();const settingsCard=$('#settingsCard');if(settingsCard&&!settingsCard.classList.contains('hidden'))settingsCard.classList.add('hidden')}
function home(){collapseSidebar();closeCenters();setFocusChat(false);tapTab('chat');setActive('Главная');window.AtlasHomeSummary?.refresh?.();setTimeout(()=>$('#chatList')?.scrollTo?.({top:0,behavior:'smooth'}),30)}
function chat(){collapseSidebar();closeCenters();setFocusChat(true);tapTab('chat');setActive('Чат');setTimeout(()=>{const list=$('#chatList');if(list)list.scrollTop=list.scrollHeight;$('#messageInput')?.focus()},30)}
function projects(){collapseSidebar();closeCenters();setFocusChat(false);tapTab('projects');setActive('Проекты')}
function files(){collapseSidebar();closeCenters();setFocusChat(false);tapTab('files');setActive('Файлы')}
function tools(){collapseSidebar();closeCenters();setFocusChat(false);setActive('Инструменты');window.AtlasToolsCenter?.open?.()||tapTab('plugins')}
function templates(){collapseSidebar();closeCenters();setFocusChat(false);setActive('Шаблоны');window.AtlasTemplates?.open?.()||tapTab('actions')}
function integrations(){collapseSidebar();closeCenters();setFocusChat(false);setActive('Интеграции');window.AtlasIntegrations?.open?.()||tapTab('plugins')}
function settings(){collapseSidebar();closeCenters();setFocusChat(false);setActive('Настройки');window.AtlasSettingsCenter?.open?.()||$('#settingsBtn')?.click()}
const ACTIONS={'Главная':home,'Чат':chat,'Проекты':projects,'Инструменты':tools,'Файлы':files,'Шаблоны':templates,'Интеграции':integrations,'Настройки':settings};
function overlayLabel(){if($('.atlas-settings-overlay,.atlas-settings'))return'Настройки';if($('.atlas-tools-overlay,.atlas-tools-center'))return'Инструменты';if($('.atlas-templates-overlay,.atlas-templates'))return'Шаблоны';if($('.integrations-overlay,.integrations-modal'))return'Интеграции';const settingsCard=$('#settingsCard');if(settingsCard&&!settingsCard.classList.contains('hidden'))return'Настройки';if($('.code-live,.video-live,.shop-live,.automation-live,.studio-workspace'))return'Инструменты';return''}
function sync(){syncSidebarToggle();const overlay=overlayLabel();if(overlay){setActive(overlay);return}const tab=$('.app-shell')?.dataset.activeTab||storedTab()||'chat';if(tab==='chat'){const focus=storedView()==='chat';document.body.classList.toggle('atlas-chat-focus',focus);setActive(focus?'Чат':'Главная');return}document.body.classList.remove('atlas-chat-focus');setActive(TAB_LABEL[tab]||'Главная')}
function bindAppObserver(){const app=$('.app-shell');if(!app||app.dataset.navObserved)return;app.dataset.navObserved='1';appObserver=new MutationObserver(sync);appObserver.observe(app,{attributes:true,attributeFilter:['data-active-tab']})}
function bindSidebarObserver(){if(!document.body||document.body.dataset.sidebarNavObserved)return;document.body.dataset.sidebarNavObserved='1';new MutationObserver(syncSidebarToggle).observe(document.body,{attributes:true,attributeFilter:['class']});syncSidebarToggle()}
document.addEventListener('click',e=>{const ref=e.target.closest?.('.ref-nav-item');if(ref){const label=labelOf(ref),fn=ACTIONS[label];if(fn){e.preventDefault();e.stopImmediatePropagation();fn();return}}const tab=e.target.closest?.('[data-tab]');if(tab){const id=String(tab.dataset.tab||'').toLowerCase();if(id==='chat'){setFocusChat(false);setActive('Главная')}else if(TAB_LABEL[id])setActive(TAB_LABEL[id]);return}const tool=e.target.closest?.('.dash-tool-card');if(tool){setActive('Инструменты');return}if(e.target.closest?.('#settingsBtn,.ref-profile')){setActive('Настройки');return}if(e.target.closest?.('#closeSettingsBtn,.atlas-settings-close'))setTimeout(sync,0)},true);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&innerWidth<980&&document.body.classList.contains('atlas-sidebar-open'))collapseSidebar()});
new MutationObserver(()=>{bindAppObserver();bindSidebarObserver();const nav=$('#atlasRefNav');if(nav&&!nav.dataset.navState){nav.dataset.navState='1';sync()}else if(nav)sync()}).observe(document.documentElement,{childList:true,subtree:true});
window.addEventListener('pageshow',()=>{bindAppObserver();bindSidebarObserver();sync()});
document.readyState==='loading'?document.addEventListener('DOMContentLoaded',()=>{bindAppObserver();bindSidebarObserver();sync()},{once:true}):(bindAppObserver(),bindSidebarObserver(),sync());
window.AtlasNavState={setActive,sync,home,chat};
})();