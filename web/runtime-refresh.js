(()=>{'use strict';
const BUILD='atlas-pwa-v21-20260827';
const RELOAD_KEY='atlas_runtime_reload_'+BUILD;
let reloading=false;
const safeSession={get(k){try{return sessionStorage.getItem(k)}catch{return null}},set(k,v){try{sessionStorage.setItem(k,v)}catch{}}};
function paint(online){const s=document.getElementById('serviceStatus');if(s)s.textContent=online?'online':'offline';const dot=document.querySelector('.topbar .dot');if(dot){dot.classList.toggle('online',online);dot.classList.toggle('offline',!online)}window.dispatchEvent(new CustomEvent('atlas-brand-health',{detail:{online,source:'runtime-refresh'}}))}
async function health(){try{const r=await fetch('/health?atlas_refresh='+Date.now(),{cache:'no-store',credentials:'same-origin',headers:{'Cache-Control':'no-cache'}});paint(r.ok);return r.ok}catch{paint(false);return false}}
function reloadOnce(){if(reloading||safeSession.get(RELOAD_KEY)==='1')return;reloading=true;safeSession.set(RELOAD_KEY,'1');location.reload()}
async function removeLegacyAppScope(rootRegistration){try{const regs=await navigator.serviceWorker.getRegistrations();await Promise.allSettled(regs.map(async reg=>{if(reg===rootRegistration)return;let scopePath='';try{scopePath=new URL(reg.scope).pathname}catch{}if(scopePath==='/app/'&&String(reg.active?.scriptURL||reg.installing?.scriptURL||reg.waiting?.scriptURL||'').includes('/app/sw.js'))await reg.unregister()}))}catch{}}
async function installWorker(){if(!('serviceWorker'in navigator))return null;navigator.serviceWorker.addEventListener('controllerchange',reloadOnce);navigator.serviceWorker.addEventListener('message',e=>{if(e.data?.type==='ATLAS_SW_UPDATED')reloadOnce()});try{const reg=await navigator.serviceWorker.register('/app/sw.js',{scope:'/',updateViaCache:'none'});await removeLegacyAppScope(reg);try{await reg.update()}catch{}if(reg.waiting)reg.waiting.postMessage({type:'SKIP_WAITING'});setTimeout(()=>removeLegacyAppScope(reg),1200);return reg}catch(e){console.warn('Atlas service worker update failed',e);return null}}
function boot(){void health();void installWorker();setInterval(()=>void health(),10000);window.addEventListener('online',()=>void health());window.addEventListener('offline',()=>paint(false));window.addEventListener('pageshow',()=>void health());document.addEventListener('visibilitychange',()=>{if(!document.hidden)void health()})}
document.readyState==='loading'?document.addEventListener('DOMContentLoaded',boot,{once:true}):boot();
window.AtlasRuntimeRefresh={health,installWorker,build:BUILD};
})();
