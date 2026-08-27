(function(){
'use strict';
var ARM_MS=5000;
var armedUntil=0;
var timer=0;

function button(){return document.getElementById('developerBtn')}
function notice(text){
  var el=document.getElementById('notice');
  if(!el)return;
  el.textContent=text||'';
  el.className='notice'+(text?' show':'');
}
function clearArm(){
  armedUntil=0;
  if(timer){clearTimeout(timer);timer=0}
  var btn=button();
  if(btn){btn.removeAttribute('data-write-armed');btn.removeAttribute('aria-describedby')}
}
function arm(btn){
  armedUntil=Date.now()+ARM_MS;
  btn.setAttribute('data-write-armed','true');
  btn.setAttribute('aria-describedby','writeGuardHint');
  notice('Нажмите Developer Mode ещё раз в течение 5 секунд, чтобы разрешить записи.');
  if(timer)clearTimeout(timer);
  timer=setTimeout(clearArm,ARM_MS);
}
function ensureHint(){
  if(document.getElementById('writeGuardHint'))return;
  var hint=document.createElement('span');
  hint.id='writeGuardHint';
  hint.hidden=true;
  hint.textContent='Для включения режима записи требуется повторное подтверждение.';
  document.body.appendChild(hint);
}
function onClick(event){
  var btn=button();
  if(!btn||event.target!==btn&&!btn.contains(event.target))return;
  var label=btn.querySelector('b');
  var alreadyOn=label&&label.textContent.trim()==='вкл';
  if(alreadyOn){clearArm();return}
  if(Date.now()<=armedUntil){clearArm();return}
  event.preventDefault();
  event.stopImmediatePropagation();
  arm(btn);
}

ensureHint();
document.addEventListener('click',onClick,true);
window.addEventListener('pagehide',clearArm,{once:false});
document.addEventListener('visibilitychange',function(){if(document.hidden)clearArm()});
})();
