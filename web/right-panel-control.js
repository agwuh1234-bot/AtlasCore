(()=>{'use strict';
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
let previousFocus=null,backdrop=null;
function panel(){return $('.atlas-dashboard-right')}
function triggers(){return $$('#atlasRightToggle,.atlas-dash-head .dash-head-btn[aria-label="Показать панель проекта"]')}
function sync(expanded){triggers().forEach(b=>{b.setAttribute('aria-expanded',String(expanded));b.setAttribute('aria-controls','atlasDashboardRight')});const p=panel();if(p){p.id='atlasDashboardRight';p.setAttribute('aria-hidden',innerWidth<=1100?String(!expanded):'false')}}
function ensureBackdrop(){if(backdrop&&document.contains(backdrop))return backdrop;backdrop=document.createElement('div');backdrop.className='atlas-right-backdrop';backdrop.onclick=close;document.body.append(backdrop);return backdrop}
function open(){const p=panel();if(!p)return;previousFocus=document.activeElement;document.body.classList.add('ref-right-open','dash-right-open','atlas-right-open');ensureBackdrop();sync(true);requestAnimationFrame(()=>$('.dash-right-close',p)?.focus()||$('button',p)?.focus())}
function close(){document.body.classList.remove('ref-right-open','dash-right-open','atlas-right-open');sync(false);const f=previousFocus;previousFocus=null;try{f?.focus?.({preventScroll:true})}catch{}}
function toggle(){document.body.classList.contains('atlas-right-open')?close():open()}
function trap(e){if(!document.body.classList.contains('atlas-right-open'))return;if(e.key==='Escape'){e.preventDefault();close();return}if(e.key!=='Tab'||innerWidth>1100)return;const p=panel();if(!p)return;const list=$$('button,[href],[tabindex]:not([tabindex="-1"])',p).filter(x=>!x.disabled);if(!list.length)return;const first=list[0],last=list[list.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}}
document.addEventListener('click',e=>{const trigger=e.target.closest?.('#atlasRightToggle,.atlas-dash-head .dash-head-btn[aria-label="Показать панель проекта"]');if(trigger){e.preventDefault();e.stopImmediatePropagation();toggle();return}const x=e.target.closest?.('.dash-right-close');if(x){e.preventDefault();e.stopImmediatePropagation();close()}},true);
document.addEventListener('keydown',trap,true);
addEventListener('resize',()=>{if(innerWidth>1100){document.body.classList.remove('ref-right-open','dash-right-open','atlas-right-open');sync(false)}else sync(document.body.classList.contains('atlas-right-open'))});
function install(){const p=panel();if(!p)return;ensureBackdrop();sync(document.body.classList.contains('atlas-right-open'))}
new MutationObserver(install).observe(document.documentElement,{childList:true,subtree:true});
document.readyState==='loading'?document.addEventListener('DOMContentLoaded',install,{once:true}):install();
window.AtlasRightPanel={open,close,toggle};
})();