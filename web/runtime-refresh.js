(()=>{'use strict';
const BUILD='atlas-pwa-v22-20260827';
const RELOAD_KEY='atlas_runtime_reload_'+BUILD;
let reloading=false;
const safeSession={get(k){try{return sessionStorage.getItem(k)}catch{return null}},set(k,v){try{sessionStorage.setItem(k,v)}catch{}}};
function paint(online){const s=document.getElementById('serviceStatus');if(s)s.textContent=online?'online':'offline';const dot=document.querySelector('.topbar .dot');if(dot){dot.classList.toggle('online',online);dot.classList.toggle('offline',!online)}window.dispatchEvent(new CustomEvent('atlas-brand-health',{detail:{online,source:'runtime-refresh'}}))}
async function health(){try{const r=await fetch('/health?atlas_refresh='+Date.now(),{cache:'no-store',credentials:'same-origin',headers:{'Cache-Control':'no-cache'}});paint(r.ok);return r.ok}catch{paint(false);return false}}
function reloadOnce(){if(reloading||safeSession.get(RELOAD_KEY)==='1')return;reloading=true;safeSession.set(RELOAD_KEY,'1');location.reload()}
function installLoginGuard(){
  if(!document.getElementById('atlas-login-guard-style')){
    const style=document.createElement('style');
    style.id='atlas-login-guard-style';
    style.textContent='body.atlas-login-open{overflow:hidden!important}body.atlas-login-open #loginCard{position:fixed!important;inset:0!important;display:grid!important;place-items:center!important;z-index:2147483646!important;pointer-events:auto!important;touch-action:auto!important}body.atlas-login-open #loginCard .modal{position:relative!important;z-index:2!important;pointer-events:auto!important}body.atlas-login-open #loginCard input{pointer-events:auto!important;touch-action:auto!important;-webkit-user-select:text!important;user-select:text!important;-webkit-appearance:none!important}body.atlas-login-open #loginCard button{pointer-events:auto!important;touch-action:manipulation!important}body.atlas-login-open .app-shell> :not(#loginCard){pointer-events:none!important}body.atlas-login-open>.atlas-right-backdrop,body.atlas-login-open>.atlas-dialog-overlay,body.atlas-login-open>.atlas-action-overlay,body.atlas-login-open>.atlas-share-overlay,body.atlas-login-open>.atlas-settings-overlay,body.atlas-login-open>.atlas-tools-overlay,body.atlas-login-open>.atlas-templates-overlay,body.atlas-login-open>.integrations-overlay{pointer-events:none!important}';
    document.head.appendChild(style);
  }
  const card=document.getElementById('loginCard');
  if(!card)return;
  const input=document.getElementById('passwordInput');
  const sync=()=>{
    const open=!card.classList.contains('hidden');
    document.body.classList.toggle('atlas-login-open',open);
    if(open){
      ['atlas-right-open','atlas-dialog-open','atlas-settings-open','atlas-tools-open','atlas-templates-open','atlas-share-open','integrations-open'].forEach(c=>document.body.classList.remove(c));
      document.querySelectorAll('.atlas-right-backdrop,.atlas-dialog-overlay,.atlas-action-overlay,.atlas-share-overlay,.atlas-settings-overlay,.atlas-tools-overlay,.atlas-templates-overlay,.integrations-overlay').forEach(el=>{if(!card.contains(el))el.style.pointerEvents='none'});
    }
  };
  new MutationObserver(sync).observe(card,{attributes:true,attributeFilter:['class']});
  if(input){
    const refocus=()=>setTimeout(()=>{try{input.focus({preventScroll:false})}catch{try{input.focus()}catch{}}},0);
    input.addEventListener('touchend',refocus,{passive:true});
    input.addEventListener('pointerup',refocus,{passive:true});
  }
  sync();
}
async function removeLegacyAppScope(rootRegistration){try{const regs=await navigator.serviceWorker.getRegistrations();await Promise.allSettled(regs.map(async reg=>{if(reg===rootRegistration)return;let scopePath='';try{scopePath=new URL(reg.scope).pathname}catch{}if(scopePath==='/app/'&&String(reg.active?.scriptURL||reg.installing?.scriptURL||reg.waiting?.scriptURL||'').includes('/app/sw.js'))await reg.unregister()}))}catch{}}
async function installWorker(){if(!('serviceWorker'in navigator))return null;navigator.serviceWorker.addEventListener('controllerchange',reloadOnce);navigator.serviceWorker.addEventListener('message',e=>{if(e.data?.type==='ATLAS_SW_UPDATED')reloadOnce()});try{const reg=await navigator.serviceWorker.register('/app/sw.js',{scope:'/',updateViaCache:'none'});await removeLegacyAppScope(reg);try{await reg.update()}catch{}if(reg.waiting)reg.waiting.postMessage({type:'SKIP_WAITING'});setTimeout(()=>removeLegacyAppScope(reg),1200);return reg}catch(e){console.warn('Atlas service worker update failed',e);return null}}
function boot(){installLoginGuard();void health();void installWorker();setInterval(()=>void health(),10000);window.addEventListener('online',()=>void health());window.addEventListener('offline',()=>paint(false));window.addEventListener('pageshow',()=>{installLoginGuard();void health()});document.addEventListener('visibilitychange',()=>{if(!document.hidden){installLoginGuard();void health()}})}
document.readyState==='loading'?document.addEventListener('DOMContentLoaded',boot,{once:true}):boot();
window.AtlasRuntimeRefresh={health,installWorker,installLoginGuard,build:BUILD};
})();
