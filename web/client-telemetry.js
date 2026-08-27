(function(){
  'use strict';
  var sent={};
  function text(value,limit){
    var s='';
    try{s=value==null?'':String(value)}catch(e){s='unprintable'}
    return s.slice(0,limit||500);
  }
  function report(payload){
    var key=text(payload.kind,40)+'|'+text(payload.message,180)+'|'+text(payload.source,180)+'|'+text(payload.line,20);
    if(sent[key])return;
    sent[key]=1;
    payload.path=text(location.pathname+location.search,300);
    payload.ua=text(navigator.userAgent,400);
    payload.ready=text(document.readyState,40);
    try{
      fetch('/app-client-error',{
        method:'POST',
        credentials:'same-origin',
        cache:'no-store',
        keepalive:true,
        headers:{'Content-Type':'application/json','Cache-Control':'no-cache'},
        body:JSON.stringify(payload)
      }).catch(function(){});
    }catch(e){}
  }
  window.addEventListener('error',function(event){
    var err=event&&event.error;
    report({
      kind:'window.error',
      message:text(event&&event.message||err&&err.message||'Unknown error',500),
      source:text(event&&event.filename||'',300),
      line:text(event&&event.lineno||'',20),
      column:text(event&&event.colno||'',20),
      stack:text(err&&err.stack||'',1200)
    });
  },true);
  window.addEventListener('unhandledrejection',function(event){
    var reason=event&&event.reason;
    report({
      kind:'unhandledrejection',
      message:text(reason&&reason.message||reason||'Unhandled rejection',500),
      source:'promise',
      line:'',
      column:'',
      stack:text(reason&&reason.stack||'',1200)
    });
  });
  window.setTimeout(function(){
    try{
      var login=document.getElementById('loginCard');
      var chat=document.getElementById('chatCard');
      var composer=document.getElementById('composerWrap');
      fetch('/app-session?telemetry='+Date.now(),{credentials:'same-origin',cache:'no-store'})
        .then(function(r){return r.ok?r.json():null})
        .then(function(data){
          if(!data||data.authenticated!==true)return;
          var loginOpen=login&&!login.classList.contains('hidden');
          var chatHidden=!chat||chat.classList.contains('hidden');
          var composerHidden=!composer||composer.classList.contains('hidden');
          if(loginOpen||chatHidden||composerHidden){
            report({kind:'boot.stalled',message:'Authenticated Atlas core remained hidden',source:'bootstrap',line:'',column:'',stack:''});
          }
        }).catch(function(){});
    }catch(e){}
  },6500);
  window.AtlasClientTelemetry={report:report};
})();
