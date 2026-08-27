(()=>{'use strict';
const form=document.getElementById('loginForm');
const input=document.getElementById('key');
const button=document.getElementById('submit');
const error=document.getElementById('error');
if(!form||!input||!button||!error)return;

function focusInput(){
  try{input.focus({preventScroll:true})}catch{try{input.focus()}catch{}}
}
function openAtlas(){
  window.location.replace('/?stable=2&login='+Date.now());
}

input.addEventListener('pointerdown',()=>setTimeout(focusInput,0),{passive:true});
input.addEventListener('touchend',()=>setTimeout(focusInput,0),{passive:true});

async function verifySession(){
  try{
    const r=await fetch('/app-session?login_check='+Date.now(),{
      credentials:'same-origin',
      cache:'no-store',
      headers:{'Cache-Control':'no-cache'}
    });
    if(!r.ok)return false;
    const data=await r.json();
    return data?.authenticated===true;
  }catch{return false}
}

form.addEventListener('submit',async e=>{
  e.preventDefault();
  const key=input.value.trim();
  if(!key){error.textContent='Введите ключ';focusInput();return}
  button.disabled=true;
  button.textContent='Входим…';
  error.textContent='';
  try{
    const r=await fetch('/app-login',{
      method:'POST',
      credentials:'same-origin',
      cache:'no-store',
      headers:{'Content-Type':'application/json','Cache-Control':'no-cache'},
      body:JSON.stringify({key})
    });
    if(r.status===401){error.textContent='Неверный ключ';input.select();return}
    if(!r.ok){error.textContent='Ошибка входа: '+r.status;return}
    const authenticated=await verifySession();
    if(!authenticated){
      error.textContent='Вход принят, но браузер не сохранил сессию. Откройте эту страницу в Safari.';
      return;
    }
    openAtlas();
  }catch{
    error.textContent='Нет соединения с Atlas';
  }finally{
    button.disabled=false;
    button.textContent='Войти';
  }
});

window.addEventListener('pageshow',()=>{
  void verifySession().then(ok=>{if(ok)openAtlas()});
});
})();