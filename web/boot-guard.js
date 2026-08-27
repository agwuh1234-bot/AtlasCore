(()=>{'use strict';
const $=id=>document.getElementById(id);
let authenticated=false,armed=true;
async function session(){try{const r=await fetch('/app-session?boot_guard='+Date.now(),{cache:'no-store',credentials:'same-origin',headers:{'Cache-Control':'no-cache'}});if(!r.ok)return false;const j=await r.json();authenticated=j?.authenticated===true;return authenticated}catch{return false}}
function revealCore(reason=''){if(!authenticated||!armed)return;const login=$('loginCard'),chat=$('chatCard'),composer=$('composerWrap');login?.classList.add('hidden');chat?.classList.remove('hidden');composer?.classList.remove('hidden');document.body.classList.add('atlas-core-ready');const status=$('serviceStatus');if(status&&status.textContent==='offline')status.textContent='online';try{window.dispatchEvent(new CustomEvent('atlas-boot-fallback',{detail:{reason}}))}catch{}}
function appReady(){const chat=$('chatCard'),composer=$('composerWrap'),login=$('loginCard');return !!(chat&&!chat.classList.contains('hidden')&&composer&&!composer.classList.contains('hidden')&&login?.classList.contains('hidden'))}
async function boot(){await session();setTimeout(()=>{if(!appReady())revealCore('core-timeout')},1400);setTimeout(()=>{if(!appReady())revealCore('extended-timeout')},3500);window.addEventListener('atlas-app-ready',()=>{armed=false},{once:true})}
document.readyState==='loading'?document.addEventListener('DOMContentLoaded',()=>void boot(),{once:true}):void boot();
window.AtlasBootGuard={session,revealCore,appReady};
})();