(()=>{'use strict';
const SELECTOR='link[data-atlas-deferred-style]';
let started=false;
function enable(){if(started)return;started=true;const links=[...document.querySelectorAll(SELECTOR)];for(const link of links){if(link.hasAttribute('data-atlas-lazy-style'))continue;link.media='all';link.removeAttribute('data-atlas-deferred-style')}}
function afterFirstPaint(){if('requestAnimationFrame'in window){requestAnimationFrame(()=>requestAnimationFrame(enable));return}setTimeout(enable,0)}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',afterFirstPaint,{once:true});else afterFirstPaint();
window.AtlasStyleLoader={enable};
})();