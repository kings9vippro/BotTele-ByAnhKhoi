/* Dev Anh Khôi · v2.0 · Shared API, native scroll gestures, bounded SSE */
'use strict';
(() => {
 const $=id=>document.getElementById(id), reduced=matchMedia('(prefers-reduced-motion: reduce)');
 const launch=new URLSearchParams(location.hash.slice(1)).get('tgWebAppData')||'';
 const motionEnabled=()=>document.documentElement.dataset.motion==='on';
 const REQUEST_TIMEOUT_MS=18000,STREAM_BASE_DELAY_MS=1000,STREAM_MAX_DELAY_MS=30000,STREAM_JITTER=0.2,STREAM_STALE_MS=12000,SDK_BOOT_WAIT_MS=2000;
 const connectionLabels={CONNECTING:'Đang kết nối…',CONNECTED:'Đã đồng bộ',AUTHENTICATED:'Đã đăng nhập',PARTIAL:'Đã đăng nhập · đồng bộ một phần',RECONNECTING:'Đang kết nối lại…',DEGRADED:'Luồng gián đoạn · đang thử lại',DISCONNECTED:'Mất kết nối · dữ liệu cũ',AUTH_REQUIRED:'Cần đăng nhập',ACCESS_DENIED:'Không đủ quyền truy cập',SERVER_CONFIG:'Máy chủ cần cấu hình xác thực'};
 let tg, active='home', data={}, accounts=[], identities=[], eventRows=[], cursor=0, stream, refreshing, refreshController, toastTimer, streamGeneration=0, legacyTelemetry, reconnectTimer, reconnectAttempt=0, lastStreamAt=0, streamConnected=false, requestSequence=0, terminalAuth=false, retryAfterDelay=0, csrfToken='',sessionValidated=false,syncWarnings=[];
 const names={home:'Tổng quan',accounts:'Tài khoản',discord:'Discord',zalo:'Zalo',tasks:'Tác vụ',activity:'Nhật ký',settings:'Cài đặt'};
 const keys=Object.keys(names), pages=$('pages');
 const element=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 function hideStartupPanel(){$('startup-panel').hidden=true;}
 function showAuthGate(state,reason){
  const card=$('auth-gate');
  if(!card){
   const startup=$('startup-panel');
   if(startup)startup.hidden=false;
   setConnection(state);return;
  }
  hideStartupPanel();
  const variants={
   missing:'Chưa có phiên quản trị. Đăng nhập bằng mật khẩu web để tiếp tục. Nếu sử dụng Telegram Mini App, hãy mở từ bot đã cấp quyền.',
   expired:'Phiên Telegram đã hết hạn. Đóng Mini App và mở lại từ bot để lấy phiên mới.',
   forbidden:'Tài khoản Telegram này chưa được cấp quyền quản lý.',
   server:'Máy chủ chưa có cấu hình xác thực Telegram hợp lệ. Quản trị viên cần kiểm tra hosting.',
   invalid:'Phiên xác thực không hợp lệ. Đóng và mở lại Mini App từ bot.'
  };
  $('auth-message').textContent=variants[reason]||variants.invalid;
  $('auth-heading').textContent=reason==='forbidden'?'Không đủ quyền':reason==='server'?'Chưa thể xác thực':'Đăng nhập quản trị';
  card.hidden=false;document.body.classList.add('auth-locked');setConnection(state);
 }
 function hideAuthGate(){const card=$('auth-gate');if(card)card.hidden=true;document.body.classList.remove('auth-locked');hideStartupPanel();}
 function toast(text){
  const message=String(text||'');
  if($('sheet')?.open){
   let status=$('sheet-status');
   if(!status){status=element('p',undefined,'sheet-status');status.id='sheet-status';$('sheet-content').append(status);}
   status.textContent=message;
   return;
  }
  $('toasts').replaceChildren(element('div',message,'toast'));
  clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toasts').replaceChildren(),4500);
 }
 class MiniAppError extends Error{constructor(message,{kind='temporary',status=0,retryAfterMs=0}={}){super(message);this.name='MiniAppError';this.kind=kind;this.status=status;this.retryAfterMs=retryAfterMs;}}
 function initData(){return String(tg?.initData||launch||'').trim();}
 function setConnection(state){const n=$('connection');n.dataset.state=state;n.textContent=connectionLabels[state]||connectionLabels.DISCONNECTED;n.classList.toggle('live',state==='CONNECTED');}
 function failed(error,state='DEGRADED'){
  if(error?.name==='AbortError')return;
  const authenticationLost=error?.status===401 ||
   (error?.status===403&&error?.code==='unauthorized_account'&&!sessionValidated);
  if(authenticationLost){
   sessionValidated=false;terminalAuth=true;stream?.abort();clearTimeout(reconnectTimer);
   showAuthGate('AUTH_REQUIRED',error?.code==='expired_init_data'?'expired':error?.code==='missing_init_data'?'missing':'invalid');
  }else if(error?.code==='server_configuration'&&!sessionValidated){
   terminalAuth=true;showAuthGate('SERVER_CONFIG','server');
  }
  if(Number.isFinite(error?.retryAfterMs))retryAfterDelay=Math.max(retryAfterDelay,error.retryAfterMs);
  const startup=$('startup-panel');
  if(!sessionValidated&&!terminalAuth&&!startup.hidden){
   startup.querySelector('[role="status"]').textContent='Chưa kết nối được với API. Bạn có thể thử lại mà không cần đăng nhập lần nữa.';
  }
  $('error').hidden=terminalAuth;
  $('error').textContent=error?.message||'Một chức năng đang tạm gián đoạn.';
  if(!terminalAuth){
   if(!sessionValidated)setConnection(state);
   else if(!error?.status||error.status>=500||error.status===429)setConnection('PARTIAL');
  }
 }
 function requestId(prefix='miniapp'){requestSequence=(requestSequence+1)%1000000;const random=window.crypto?.randomUUID?.()||Math.random().toString(36).slice(2);return `${prefix}-${Date.now().toString(36)}-${requestSequence.toString(36)}-${random}`;}
 function requestSignal(parent,timeout=REQUEST_TIMEOUT_MS){const controller=new AbortController();let timedOut=false;const timer=setTimeout(()=>{timedOut=true;controller.abort();},timeout),abort=()=>controller.abort();if(parent?.aborted)abort();else parent?.addEventListener('abort',abort,{once:true});return {signal:controller.signal,isTimeout:()=>timedOut,cleanup:()=>{clearTimeout(timer);parent?.removeEventListener('abort',abort);}};}
 function retryAfterMs(response){const seconds=Number(response.headers.get('Retry-After'));return Number.isFinite(seconds)&&seconds>0?Math.min(60000,Math.round(seconds*1000)):0;}
 async function api(path,body,options={}){const h={'X-Telegram-Init-Data':tg?.initData||launch,'X-Request-ID':requestId()};if(body!==undefined){h['Content-Type']='application/json';if(csrfToken)h['X-CSRF-Token']=csrfToken;}const request=requestSignal(options.signal,options.timeout||REQUEST_TIMEOUT_MS);try{const r=await fetch('/api/miniapp/'+path,{method:options.method||(body===undefined?'GET':'POST'),headers:h,body:body===undefined?undefined:JSON.stringify(body),signal:request.signal,cache:'no-store'});let d;try{d=await r.json();}catch{throw Object.assign(new Error('API trả về dữ liệu không phải JSON hợp lệ.'),{status:r.status,code:'invalid_json'});}
  if(!r.ok||d.ok===false)throw Object.assign(new Error(d.error||d.message||'Yêu cầu thất bại'),{status:r.status,code:d.code||'http_error',retryAfterMs:retryAfterMs(r)});
  return d;
 }catch(e){if(e?.name==='AbortError'&&request.isTimeout())throw Object.assign(new Error('Yêu cầu vượt quá thời gian chờ.'),{code:'timeout'});throw e;}
 finally{request.cleanup();}}
 function dashboardFailureLabel(error){
  if(error?.code==='timeout')return 'quá thời gian chờ';
  const status=Number(error?.status);
  if(status>=400)return 'HTTP '+status;
  return 'mất kết nối';
 }
 function shouldRetryDashboard(error){
  const status=Number(error?.status);
  return error?.code==='timeout'||status===429||status>=500||(!status&&error?.name!=='AbortError');
 }
 async function loadDashboardJob(job,options){
  try{return await job.load();}
  catch(error){
   if(options.signal?.aborted||!shouldRetryDashboard(error))throw error;
   const pause=Math.min(2500,Math.max(350,Number(error?.retryAfterMs)||350));
   await new Promise(resolve=>setTimeout(resolve,pause));
   if(options.signal?.aborted)throw Object.assign(new Error('Đã hủy'),{name:'AbortError'});
   return job.load();
  }
 }
 async function uploadFile(form,options={}){const h={'X-Telegram-Init-Data':tg?.initData||launch,'X-Request-ID':requestId('upload')};if(csrfToken)h['X-CSRF-Token']=csrfToken;const request=requestSignal(options.signal,options.timeout||REQUEST_TIMEOUT_MS);try{const r=await fetch('/api/miniapp/upload_file',{method:'POST',headers:h,body:new FormData(form),signal:request.signal,cache:'no-store'});const d=await r.json();if(!r.ok||!d.ok)throw Error(d.error||'Tải tệp thất bại');return d;}finally{request.cleanup();}}
 function button(text,fn,cls){const b=element('button',text,cls);b.type='button';b.onclick=async()=>{if(b.disabled)return;b.disabled=true;b.setAttribute('aria-busy','true');try{await fn();}catch(e){failed(e);}finally{b.disabled=false;b.removeAttribute('aria-busy');}};return b;}
 function theme(){const mode=$('theme').value;document.documentElement.dataset.theme=mode==='system'?(tg?.colorScheme||(matchMedia('(prefers-color-scheme:light)').matches?'light':'dark')):mode;}
 function initTelegram(){const sdk=window.Telegram?.WebApp;if(!sdk||tg===sdk)return;tg=sdk;tg.ready();tg.expand();tg.onEvent?.('themeChanged',theme);tg.onEvent?.('viewportChanged',()=>{document.documentElement.style.setProperty('--safe',Math.max(tg.safeAreaInset?.bottom||0,tg.contentSafeAreaInset?.bottom||0)+'px');});tg.BackButton?.onClick(()=>{if($('sheet').open)$('sheet').close();else go('home');});theme();}
 initTelegram();$('telegram-sdk').addEventListener('load',initTelegram);$('theme').onchange=()=>{try{localStorage.setItem('glaze-theme',$('theme').value);}catch{}theme();};try{$('theme').value=localStorage.getItem('glaze-theme')||'dark';}catch{$('theme').value='dark';}theme();
 for(const [id,allowed,fallback] of [['text-size',['normal','large'],'normal'],['accent',['blue','rose','mint'],'blue']]){
  const input=$(id),key='glaze-'+id;
  try{const saved=localStorage.getItem(key);input.value=allowed.includes(saved)?saved:fallback;}catch{input.value=fallback;}
  const apply=()=>{document.documentElement.setAttribute('data-'+id,input.value);try{localStorage.setItem(key,input.value);}catch{}};
  input.addEventListener('change',apply);apply();
 }

 // Animation state is visual-only; authentication, APIs and QR retain their original contracts.
 let animationHooksReady=false;
 const motionInput=$('motion');
 function applyMotion(){
  const setting=motionInput.value;
  const enabled=setting==='on'||(setting==='system'&&!reduced.matches);
  document.documentElement.dataset.motion=enabled?'on':'off';
  $('motion-note').textContent=enabled
   ?'Đã bật: chữ bật lên theo từng ký tự, hoa bay, chuyển tab và các thẻ hiện dần khi cuộn.'
   :'Đã tắt chuyển động. Có thể bật lại bất kỳ lúc nào.';
  if(!enabled)document.querySelectorAll('.scroll-reveal').forEach(el=>el.classList.add('is-visible'));
  if(animationHooksReady&&enabled)requestAnimationFrame(()=>{
   replayKineticTitle(active);observeReveals();
  });
 }
 try{motionInput.value=localStorage.getItem('glaze-motion')||'off';}
 catch{motionInput.value='off';}
 if(!['system','on','off'].includes(motionInput.value))motionInput.value='system';
 motionInput.onchange=()=>{
  try{localStorage.setItem('glaze-motion',motionInput.value);}catch{}
  applyMotion();
 };
 reduced.addEventListener?.('change',()=>{
  if(motionInput.value==='system')applyMotion();
 });
 applyMotion();

 const primaryNav=new Set(['home','accounts','tasks']);
 let requestedPage=null;
 const moreMenu=$('more-menu');
 function closeMore(){
  if(!moreMenu)return;
  moreMenu.hidden=true;
  $('more-trigger')?.setAttribute('aria-expanded','false');
 }
 function toggleMore(){
  if(!moreMenu)return;
  const opening=moreMenu.hidden;
  moreMenu.hidden=!opening;
  $('more-trigger')?.setAttribute('aria-expanded',opening?'true':'false');
  if(opening)moreMenu.querySelector('button')?.focus({preventScroll:true});
  else $('more-trigger')?.focus({preventScroll:true});
 }
 function select(name){
  if(!keys.includes(name)||active===name&&$(name)?.getAttribute('aria-hidden')==='false')return;
  active=name;
  document.querySelectorAll('[data-bottom]').forEach(b=>{
   const current=b.dataset.bottom===name||(b.dataset.bottom==='more'&&!primaryNav.has(name));
   b.setAttribute('aria-current',current?'page':'false');
  });
  keys.forEach(key=>{
   const section=$(key);
   if(section){
    section.setAttribute('aria-hidden',key===name?'false':'true');
    section.setAttribute('aria-label',names[key]);
   }
  });
  closeMore();
  revealPage(name);
  replayKineticTitle(name);
  if(name==='zalo'&&!terminalAuth)refreshZaloWatches().catch(failed);
  if(name==='home')tg?.BackButton?.hide();else tg?.BackButton?.show();
 }
 function go(name){
  if(!keys.includes(name))return;
  requestedPage=name;
  select(name);
  pages.scrollTo({left:keys.indexOf(name)*pages.clientWidth,behavior:motionEnabled()?'smooth':'auto'});
  tg?.HapticFeedback?.selectionChanged();
  if(!terminalAuth&&['accounts','zalo','discord'].includes(name)&&Date.now()-lastFullSync>30000)refresh().catch(failed);
 }
 const navPaths={
  home:'M3 11.5 12 4l9 7.5V21h-6v-7H9v7H3z',
  accounts:'M16 19v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2h14z M9 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
  tasks:'M12 3v9l5 3 M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z',
  more:'M4 7h16 M4 12h16 M4 17h16'
 };
 const ns='http://www.w3.org/2000/svg';
 for(const key of ['home','accounts','tasks','more']){
  const label=key==='more'?'Thêm':names[key];
  const b=button('',()=>key==='more'?toggleMore():go(key));
  const svg=document.createElementNS(ns,'svg');
  svg.classList.add('bottom-icon');svg.setAttribute('viewBox','0 0 24 24');
  svg.setAttribute('width','24');svg.setAttribute('height','24');
  svg.setAttribute('fill','none');svg.setAttribute('stroke','currentColor');
  svg.setAttribute('stroke-width','1.8');svg.setAttribute('stroke-linejoin','round');
  svg.setAttribute('stroke-linecap','round');svg.setAttribute('aria-hidden','true');
  const path=document.createElementNS(ns,'path');path.setAttribute('d',navPaths[key]);svg.append(path);
  b.append(svg,element('span',label,'nav-caption'));b.dataset.bottom=key;b.classList.add('bottom-nav-button');
  b.setAttribute('aria-label',label);b.title=label;
  if(key==='more'){b.id='more-trigger';b.setAttribute('aria-expanded','false');b.setAttribute('aria-controls','more-menu');}
  $('bottom').append(b);
 }
 for(const key of ['discord','zalo','activity','settings']){
  const b=button(names[key],()=>go(key));
  b.dataset.more=key;b.classList.add('more-option');moreMenu.append(b);
 }
 document.addEventListener('pointerdown',e=>{
  if(!moreMenu.hidden&&!moreMenu.contains(e.target)&&!$('more-trigger').contains(e.target))closeMore();
 });
 document.addEventListener('keydown',e=>{
  if(e.key==='Escape'&&!moreMenu.hidden){closeMore();$('more-trigger').focus();}
 });
 for(const [id,page] of [['home-open-accounts','accounts'],['home-open-tasks','tasks'],['home-open-zalo','zalo'],['home-open-discord','discord'],['home-open-activity','activity'],['account-open-zalo','zalo'],['account-open-discord','discord'],['task-open-activity','activity'],['task-open-zalo','zalo']]){
  const target=$(id);if(target)target.addEventListener('click',()=>go(page));
 }
 $('startup-retry')?.addEventListener('click',()=>{terminalAuth=false;refresh();});
 $('auth-retry')?.addEventListener('click',()=>{
  initTelegram();
  // Web sessions authenticate using cookies; the server still enforces access.
  terminalAuth=false;hideAuthGate();setConnection('CONNECTING');
  refresh().finally(()=>{if(!terminalAuth)scheduleReconnect(streamGeneration,100);});
 });
 let scrollFrame;
 pages.onscroll=()=>{
  if(scrollFrame)return;
  scrollFrame=requestAnimationFrame(()=>{
   scrollFrame=null;
   if(requestedPage){
    const target=keys.indexOf(requestedPage)*pages.clientWidth;
    if(Math.abs(pages.scrollLeft-target)>3)return;
    requestedPage=null;
   }
   const next=keys[Math.round(pages.scrollLeft/pages.clientWidth)]||'home';
   if(next!==active)select(next);
  });
 };
 pages.addEventListener('pointerdown',()=>{requestedPage=null;},{passive:true});
 pages.addEventListener('scrollend',()=>{
  requestedPage=null;
  const next=keys[Math.round(pages.scrollLeft/pages.clientWidth)]||'home';
  if(next!==active)select(next);
 });
 window.addEventListener('resize',()=>{
  requestedPage=null;
  pages.scrollTo({left:keys.indexOf(active)*pages.clientWidth,behavior:'instant'});
 });
 let revealFrame=0;
 let revealObserver=null;
 function ensureRevealObserver(){
  if(!motionEnabled()||!('IntersectionObserver' in window))return null;
  if(!revealObserver)revealObserver=new IntersectionObserver(entries=>{
   for(const entry of entries)if(entry.isIntersecting){
    entry.target.classList.add('is-visible');
    revealObserver.unobserve(entry.target);
   }
  },{threshold:.08,rootMargin:'0px 0px 8px 0px'});
  return revealObserver;
 }
 function revealPage(name){
  if(!motionEnabled())return;
  const section=$(name);
  if(!section)return;
  section.classList.remove('page-enter');
  requestAnimationFrame(()=>{
   if(active!==name)return;
   section.classList.add('page-enter');
   observeReveals();
  });
 }
 function observeReveals(){
  if(active==='tasks')return;
  const observer=ensureRevealObserver();
  if(!observer)return;
  const section=$(active);
  section?.querySelectorAll('article,.card,.metric,.file-category').forEach(el=>{
   if(el.dataset.revealReady)return;
   el.dataset.revealReady='1';el.classList.add('scroll-reveal');observer.observe(el);
  });
 }

 // Words never split at narrow mobile widths; individual graphemes animate on every navigation.
 function kineticGraphemes(value){
  if(typeof Intl.Segmenter==='function')
   return Array.from(new Intl.Segmenter('vi',{granularity:'grapheme'}).segment(value),x=>x.segment);
  return Array.from(value);
 }
 function buildKineticTitle(heading,key){
  if(!heading||heading.dataset.kineticReady)return;
  const original=(heading.textContent||'').trim();
  if(!original)return;
  const pieces=original.match(/\S+|\s+/gu)||[original];
  const frag=document.createDocumentFragment();
  let letters=0,wordIndex=0;
  for(const piece of pieces){
   if(/^\s+$/u.test(piece)){frag.append(document.createTextNode(piece));continue;}
   const word=element('span',undefined,'glaze-kinetic-word');
   for(const part of kineticGraphemes(piece)){
    const char=element('span',part,'glaze-kinetic-letter');
    char.style.setProperty('--glaze-char-index',String(Math.min(letters++,40)));
    if(key==='home'&&wordIndex>=2)char.classList.add('glaze-kinetic-accent');
    word.append(char);
   }
   frag.append(word);wordIndex++;
  }
  heading.replaceChildren(frag);
  heading.setAttribute('aria-label',original);
  heading.dataset.kineticReady='1';
  heading.classList.add('glaze-kinetic-title');
 }
 function buildFlowerField(section){
  if(section.querySelector('.glaze-flower-field'))return;
  const garden=element('div',undefined,'glaze-flower-field');
  garden.setAttribute('aria-hidden','true');
  const shapes=['✿','✧','❀','✦','✿','✧','❁'];
  const left=[8,85,70,14,91,34,63],top=[70,135,275,420,580,755,980];
  for(let i=0;i<shapes.length;i++){
   const petal=element('span',shapes[i],'glaze-flower');
   petal.style.setProperty('--glaze-x',left[i]+'%');
   petal.style.setProperty('--glaze-y',top[i]+'px');
   petal.style.setProperty('--glaze-petal-index',String(i));
   petal.style.setProperty('--glaze-petal-size',(18+(i%4)*7)+'px');
   garden.append(petal);
  }
  section.prepend(garden);
 }
 function initKineticSections(){
  for(const key of keys){
   const section=$(key);
   if(!section)continue;
   buildKineticTitle(section.querySelector(':scope > h1, .overview-heading h1'),key);
   buildFlowerField(section);
  }
 }
 function replayKineticTitle(name){
  if(!motionEnabled())return;
  const section=$(name);
  if(!section)return;
  for(const node of [section.querySelector('.glaze-kinetic-title'),section.querySelector('.glaze-flower-field')]){
   if(!node)continue;
   const className=node.classList.contains('glaze-flower-field')?'glaze-flower-play':'glaze-kinetic-play';
   node.classList.remove(className);
   // Reflow only the two tiny decorative nodes to restart the effect on tab swipes.
   void node.offsetWidth;
   node.classList.add(className);
  }
 }

 const contentObserver='MutationObserver' in window?
  new MutationObserver(()=>{
   if(revealFrame)return;
   revealFrame=requestAnimationFrame(()=>{revealFrame=0;observeReveals();});
  }):null;
 contentObserver?.observe(pages,{childList:true,subtree:true});
 initKineticSections();
 animationHooksReady=true;
 select('home');
 // Small, noninteractive spark/flower burst at the selected tab; never touches QR or forms.
 const tapShapes=['✿','✧','❀','✦','✿'];
 function flowerTap(button){
  if(!motionEnabled()||!button||document.body.classList.contains('auth-locked'))return;
  const rect=button.getBoundingClientRect();
  if(rect.width<=0||rect.height<=0)return;
  const burst=element('span',undefined,'glaze-tap-garden');
  burst.setAttribute('aria-hidden','true');
  burst.style.setProperty('--tap-x',(rect.left+rect.width/2)+'px');
  burst.style.setProperty('--tap-y',(rect.top+Math.min(17,rect.height/3))+'px');
  for(let i=0;i<tapShapes.length;i++){
   const petal=element('span',tapShapes[i],'glaze-tap-petal');
   petal.style.setProperty('--tap-i',String(i));
   petal.style.setProperty('--tap-dx',(i-2)*23+'px');
   petal.style.setProperty('--tap-dy',(-19-Math.abs(i-2)*13)+'px');
   petal.style.setProperty('--tap-rotate',((i-2)*65)+'deg');
   burst.append(petal);
  }
  document.body.append(burst);
  setTimeout(()=>burst.remove(),1300);
 }
 for(const group of [$('bottom'),$('more-menu')]){
  group?.addEventListener('click',event=>{
   const button=event.target.closest('button');
   if(button&&group.contains(button))flowerTap(button);
  });
 }
 let sheetReturnFocus;
 function sheet(title,content,actions=[]){const dialog=$('sheet');if(dialog.open)dialog.close();$('toasts').replaceChildren();sheetReturnFocus=document.activeElement;$('sheet-title').textContent=title;$('sheet-content').replaceChildren(typeof content==='string'?element('p',content):content);$('sheet-actions').replaceChildren(...actions);dialog.showModal();$('sheet-close').focus();}
 function closeSheet(){if($('sheet').open)$('sheet').close();sheetReturnFocus?.focus?.();sheetReturnFocus=null;}
 $('sheet-close').onclick=closeSheet;$('sheet').addEventListener('close',()=>{sheetReturnFocus?.focus?.();sheetReturnFocus=null;});let dragY;
 $('sheet-handle').onpointerdown=e=>{dragY=e.clientY;e.target.setPointerCapture(e.pointerId);};$('sheet-handle').onpointermove=e=>{if(dragY!==undefined)$('sheet').style.transform=`translateY(${Math.max(0,e.clientY-dragY)}px)`;};$('sheet-handle').onpointerup=e=>{if(e.clientY-dragY>90)closeSheet();dragY=undefined;$('sheet').style.transform='';};$('sheet-handle').onpointercancel=()=>{dragY=undefined;$('sheet').style.transform='';};
 function confirmAction(title,fn){sheet(title,'Thao tác này áp dụng trên máy chủ.',[button('Xác nhận',async()=>{await fn();$('sheet').close();await refresh();},'danger')]);}
 function row(title,detail){const r=element('article',undefined,'card');r.append(element('strong',title),element('p',detail));return r;}
 async function downloadZaloSession(accountId){
  const receipt=await api('export_zalo_session',{account_id:accountId});
  const uri=URL.createObjectURL(new Blob([receipt.text],{type:'text/plain;charset=utf-8'}));
  const link=document.createElement('a');link.href=uri;link.download=receipt.filename;
  document.body.append(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(uri),1000);
 }
 let accountPage=1;
 function renderAccounts(){
  const target=$('account-list'), q=$('account-search').value.trim().toLowerCase();
  const live=accounts.filter(a=>a.enabled&&a.listener_health?.code==='running'&&a.listener_health?.session_hint!=='relogin_required').length;
  const reauth=accounts.filter(a=>a.listener_health?.session_hint==='relogin_required').length;
  const summary=$('account-health-summary');
  if(summary){
   const headline=element('strong',live+'/'+accounts.length+' ACC có listener đang chạy');
   const caption=element('p','Trạng thái luồng không chứng minh cookie đã đăng nhập; kiểm tra trực tiếp lệnh .menu ở từng ACC.');
   const details=element('small',reauth?reauth+' ACC cần cập nhật phiên.':'Mỗi ACC có mã riêng, không hiển thị cookie đăng nhập.');
   summary.replaceChildren(headline,caption,details,button('Kiểm tra ngay',refreshAccountHealth,'account-refresh'));
  }
  target.replaceChildren();let matched=0;
  for(const a of accounts){
   if(!(''+a.name+' '+a.id+' '+(a.uid||'')).toLowerCase().includes(q))continue;
   if(++matched>accountPage*30)continue;
   const health=a.listener_health||{},code=health.code||'not_started';
   const state=health.session_hint==='relogin_required'?'Cần đăng nhập lại':
     code==='running'?'Listener đang chạy':
     code==='duplicate_imei'?'Trùng thiết bị với ACC-'+health.conflicting_acc_id:
     code==='listener_start_failed'?'Không khởi chạy':
     code==='worker_unavailable'?'Luồng bị gián đoạn':
     code==='stopped'?'Đã dừng':'Chưa kết nối';
   const card=element('article',undefined,'card account-card');
   const head=element('div',undefined,'account-card-head');
   const title=element('strong','ACC-'+a.id+' · '+(a.name||'Zalo'));
   const badge=element('span',state,'account-status');
   badge.dataset.state=health.session_hint==='relogin_required'?'error':code;
   head.append(title,badge);
   card.append(head,element('p','Zalo · '+(a.enabled?'Đã bật':'Đã tắt')+' · '+(a.chat_cmd_enabled?'Có nhận lệnh':'Tạm tắt lệnh')));
   if(health.ws_state)card.append(element('small',health.ws_state,'account-connection'));
   if(health.last_event_at)card.append(element('small','Tin nhắn sự kiện gần nhất: '+new Date(health.last_event_at*1000).toLocaleString()));
   else card.append(element('small','Chưa ghi nhận sự kiện thực tế từ listener.'));
   const actions=element('div',undefined,'actions');
   actions.append(button('Xem task ACC',()=>{
    go('tasks');$('task-account-filter').value=String(a.id);
    $('task-account-filter').dispatchEvent(new Event('change'));
   },'primary'));
   actions.append(button('Tải Cookie + IMEI',()=>downloadZaloSession(a.id)));
   actions.append(button(a.chat_cmd_enabled?'Tắt lệnh':'Bật lệnh',async()=>{await api('toggle_acc_cmd',{acc_id:a.id});await refresh();}));
   actions.append(button('Xóa',()=>confirmAction('Xóa ACC-'+a.id+' · '+a.name,()=>api('delete_acc',{acc_id:a.id})),'danger'));
   card.append(actions);target.append(card);
  }
  for(const a of identities){
   if(!(''+a.name+' '+a.uid).toLowerCase().includes(q))continue;
   if(++matched>accountPage*30)continue;
   target.append(credentialCard(a));
  }
  if(!matched)target.append(element('p','Chưa có tài khoản phù hợp.'));
  else if(matched>accountPage*30)target.append(button('Xem thêm tài khoản · '+(matched-accountPage*30)+' còn lại',()=>{accountPage++;renderAccounts();}));
 }
 $('account-search').oninput=()=>{accountPage=1;renderAccounts();};
 let healthPending=null;
 async function refreshAccountHealth(){
  if(healthPending)return healthPending;
  healthPending=(async()=>{
   const result=await api('account_health',undefined,{timeout:8000});
   const latest=new Map((result.accounts||[]).map(a=>[String(a.id),a]));
   let changed=false;
   for(const account of accounts){
    const newer=latest.get(String(account.id));
    if(!newer)continue;
    if(JSON.stringify(account.listener_health)!==JSON.stringify(newer.listener_health)||
       account.chat_cmd_enabled!==newer.chat_cmd_enabled){
      account.listener_health=newer.listener_health;
      account.chat_cmd_enabled=newer.chat_cmd_enabled;
      changed=true;
    }
   }
   if(changed&&active==='accounts')renderAccounts();
   return result;
  })();
  try{return await healthPending;}finally{healthPending=null;}
 }

 let boxRequest=0,boxPage=1,boxPages=1,boxSelected=new Set(),boxOwner='';
 function renderLaunchAccounts(){
  const select=$('launch-account'),previous=select.value;
  select.replaceChildren(element('option','Chọn tài khoản'));select.firstChild.value='';
  for(const account of accounts.filter(a=>a.enabled)){
   const option=element('option',account.name+' · #'+account.id);
   option.value=String(account.id);select.append(option);
  }
  select.value=[...select.options].some(o=>o.value===previous)?previous:'';
  if(select.value!==previous){boxSelected.clear();boxOwner=select.value;boxPage=1;loadLaunchBoxes().catch(failed);}
 }
 async function loadLaunchBoxes(page=boxPage){
  const accountId=$('launch-account').value,field=$('launch-boxes'),requestId=++boxRequest;
  if(boxOwner!==accountId){boxSelected.clear();boxOwner=accountId;page=1;}
  field.replaceChildren(element('legend','Chọn tối đa 5 box · Xem theo trang'));
  if(!accountId){field.append(element('p','Chọn tài khoản Zalo để xem nhóm.'));return;}
  const suffix=page>1?'&page='+page:'';
  const result=await api('boxes?account_id='+encodeURIComponent(accountId)+suffix);
  if(requestId!==boxRequest)return;
  boxPage=page;boxPages=Math.max(1,Number(result.total_pages)||1);
  const boxes=result.boxes||[];
  for(const box of boxes){
   const label=element('label'),input=element('input');
   input.type='checkbox';input.value=box.id;input.checked=boxSelected.has(box.id);
   input.onchange=()=>{
    if(input.checked){
     if(boxSelected.size>=5){input.checked=false;toast('Tối đa 5 box mỗi lần.');return;}
     boxSelected.add(box.id);
    }else boxSelected.delete(box.id);
    const count=$('box-selection-count');if(count)count.textContent='Đã chọn '+boxSelected.size+'/5';
   };
   label.classList.add('zalo-group-row');
   label.append(input,document.createTextNode(box.name+' · '+box.id));field.append(label);
  }
  if(!boxes.length)field.append(element('p',result.total?'Trang này không có nhóm.':'Chưa có box. Bấm Quét nhóm từ Cookie Zalo.'));
  const status=element('p','Trang '+boxPage+'/'+boxPages+' · '+(result.total===undefined?boxes.length:result.total)+' box','zalo-page-info');
  const count=element('strong','Đã chọn '+boxSelected.size+'/5');count.id='box-selection-count';
  status.append(document.createTextNode(' · '),count);
  const nav=element('div',undefined,'zalo-box-pagination');
  const prev=button('‹ Trước',()=>loadLaunchBoxes(boxPage-1).catch(failed));
  const next=button('Tiếp ›',()=>loadLaunchBoxes(boxPage+1).catch(failed));
  prev.disabled=boxPage<=1;next.disabled=boxPage>=boxPages;
  nav.append(prev,next);field.append(status,nav);
 }
 $('launch-account').onchange=()=>{boxSelected.clear();boxOwner=$('launch-account').value;boxPage=1;loadLaunchBoxes(1).catch(failed);renderWatchedBoxes();};
 $('refresh-boxes').onclick=async()=>{
  const account_id=$('launch-account').value;
  if(!account_id){toast('Chọn tài khoản Zalo trước.');return;}
  const b=$('refresh-boxes');b.disabled=true;
  try{const result=await api('scan_boxes',{account_id},{timeout:60000});toast(result.message||'Đã quét nhóm');boxPage=1;await loadLaunchBoxes(1);}
  catch(error){failed(error);}finally{b.disabled=false;}
 };
 let watchedBoxes=[],watchRefreshing=null,watchLastFetched=0,watchError='';
 function renderWatchedBoxes(){
  const target=$('zalo-watch-status');
  if(!target)return;
  const selected=String($('launch-account').value||'');
  target.replaceChildren();
  if(!selected){target.append(element('p','Chọn cookie Zalo để xem các box đang canh.'));return;}
  if(watchError){
   target.append(element('p','Không đồng bộ được trạng thái: '+watchError+'. Đang hiển thị ảnh chụp gần nhất.'));
  }
  const items=watchedBoxes.filter(w=>String(w.acc_id)===selected);
  if(!items.length){target.append(element('p','Cookie này chưa bật canh treo trong tiến trình hiện tại.'));return;}
  const now=Date.now()/1000;
  const snapshotAge=(Date.now()-watchLastFetched)/1000;
  if(snapshotAge>12)target.append(element('p','Dữ liệu canh box đã cũ; kết nối có thể đang gián đoạn.'));
  for(const item of items){
   const threshold=Number(item.timeout_sec)||90;
   const last=Number(item.last_message_at);
   const hasLast=Number.isFinite(last)&&last>0;
   const elapsed=hasLast?Math.max(0,Math.floor(now-last)):null;
   const status=!hasLast?'Chờ tin nhắn đầu tiên':
     elapsed>=threshold?'Đã im lặng '+elapsed+'s':'Đang canh · '+elapsed+'s/'+threshold+'s';
   const timestamp=item.inactive_since_label?'Ngừng nhắn từ: '+item.inactive_since_label:
     'Tin cuối: '+(item.last_message_at_label||'Chưa có');
   const sync=item.last_sync_at===null||item.last_sync_at===undefined?'Chưa đồng bộ API Zalo':
     item.last_sync_ok===false?'API Zalo lỗi · dữ liệu cũ':
     (Number(item.last_sync_age_seconds)>60?'Lịch sử Zalo chưa cập nhật gần đây':
     'API Zalo đã kiểm tra');
   const card=row(item.box_name||item.box_id,status+' · '+timestamp);
   card.append(element('small','ACC #'+selected+' · '+sync));
   target.append(card);
  }
 }
 async function refreshZaloWatches(){
  if(watchRefreshing)return watchRefreshing;
  watchRefreshing=(async()=>{
   try{
    const result=await api('zalo_watch');
    watchedBoxes=Array.isArray(result.watches)?result.watches:[];
    watchLastFetched=Date.now();watchError='';
   }catch(error){
    watchError=error?.message||'Kết nối tạm gián đoạn';
    throw error;
   }finally{renderWatchedBoxes();}
  })().finally(()=>{watchRefreshing=null;});
  return watchRefreshing;
 }
 async function toggleSelectedWatches(action){
  const account_id=$('launch-account').value;
  if(!account_id||!boxSelected.size){toast('Chọn tài khoản và ít nhất một box.');return;}
  const errors=[];
  for(const box_id of boxSelected)try{
   await api('zalo_watch',{action,account_id,box_id,timeout_sec:90});
  }catch(error){errors.push(box_id+': '+error.message);}
  await refreshZaloWatches();
  if(errors.length)toast(errors.join(' · '));
  else toast(action==='start'?'Đã bật canh treo 1p30s':'Đã dừng canh treo');
 }
 $('watch-start').onclick=()=>toggleSelectedWatches('start').catch(failed);
 $('watch-stop').onclick=()=>toggleSelectedWatches('stop').catch(failed);
 setInterval(()=>{if(active==='zalo'&&!document.hidden&&!terminalAuth)
  refreshZaloWatches().catch(()=>{});},5000);
 setInterval(()=>{if(active==='zalo'&&!document.hidden)renderWatchedBoxes();},1000);
 $('launch-form').onsubmit=async e=>{
  e.preventDefault();const form=e.currentTarget,submit=form.querySelector('button[type=submit],button.primary');
  const boxIds=[...boxSelected];
  if(!boxIds.length||boxIds.length>5){toast('Chọn từ 1 đến 5 box.');return;}
  submit.disabled=true;
  try{
   const body={...Object.fromEntries(new FormData(form)),box_ids:boxIds};
   const launched=await api('launch',body);
   toast(launched.message||'Đã tạo task');$('task-account-filter').value=String(body.account_id);await refreshRegistry();await refresh();go('tasks');
  }catch(error){failed(error);}finally{submit.disabled=false;}
 };
 let tasksSignature='',registryGeneration=0,registryVersion=0,registryTasks=[],registryState='loading',taskAccountInitialized=false,taskPage=1;
 function renderTaskAccounts(){
  const target=$('task-account-filter'),before=target.value,available=new Set(['discord']);
  target.replaceChildren(element('option','Thông báo Discord'),element('option','Task chưa xác định cookie'));
  target.children[0].value='discord';target.children[1].value='unassigned';
  available.add('unassigned');
  for(const account of accounts){
   const id=String(account.id),option=element('option',account.name+' · Cookie #'+id);
   option.value=id;target.append(option);available.add(id);
  }
  const preferred=accounts.find(a=>a.enabled);
  target.value=taskAccountInitialized&&available.has(before)?before:(preferred?String(preferred.id):'discord');
  taskAccountInitialized=true;
 }
 $('task-account-filter').onchange=()=>{
  taskPage=1;
  registryGeneration++;registryPending=null;registryFetchedAt=0;registryNextRetryAt=0;registryErrorCount=0;
  registryTasks=[];registryVersion++;registryState='loading';renderTasks();
  refreshRegistry().catch(failed);
 };
 let registryPending=null,registryFetchedAt=0,registryNextRetryAt=0,registryErrorCount=0;
 async function refreshRegistry(options={}){
  const account=$('task-account-filter').value||'discord';
  if(registryPending?.account===account)return registryPending.promise;
  const generation=++registryGeneration;
  const operation=(async()=>{
   try{
    const path=['discord','unassigned'].includes(account)?'task_registry':'task_registry?account_id='+encodeURIComponent(account);
    const result=await api(path,undefined,options);
    if(generation!==registryGeneration||account!==$('task-account-filter').value)return;
    registryTasks=(Array.isArray(result.tasks)?result.tasks:[]).filter(task=>
      account==='discord'?task.execution_source==='durable_notifications':
      account==='unassigned'?task.execution_source==='legacy_process'&&!(task.account_ids||[]).length:
       (task.account_ids||[]).map(String).includes(account));
    registryVersion++;
    registryFetchedAt=Date.now();registryErrorCount=0;registryNextRetryAt=0;
    registryState='ready';
   }catch(error){
    if(generation===registryGeneration&&account===$('task-account-filter').value){
     registryState=error?.status===403?'forbidden':error?.status===401?'unauthorized':'unavailable';
     registryErrorCount=Math.min(5,registryErrorCount+1);
     registryNextRetryAt=Date.now()+Math.min(30000,4000*Math.pow(2,registryErrorCount-1));
    }
    throw error;
   }finally{if(generation===registryGeneration)renderTasks();}
  })();
  registryPending={account,promise:operation};
  try{return await operation;}finally{if(registryPending?.promise===operation)registryPending=null;}
 }
 function renderTasks(){
  const f=$('task-filter').value,target=$('task-list'),acc=$('task-account-filter').value;
  const query=$('task-search').value.trim().toLocaleLowerCase('vi');
  const signature=JSON.stringify([f,acc,query,taskPage,registryVersion,registryState]);
  const scope=acc==='discord'?'Discord':acc==='unassigned'?'Task chưa gắn tài khoản':
    'Zalo #'+acc+' · '+(accounts.find(a=>String(a.id)===acc)?.name||'');
  const age=registryFetchedAt?Math.floor((Date.now()-registryFetchedAt)/1000):null;
  $('task-account-status').textContent=scope+' · '+(age===null?'Chưa đồng bộ':
    registryState!=='ready'?'Không có dữ liệu mới; ảnh chụp cũ từ '+age+'s trước':
    'Cập nhật '+age+'s trước');
  if(signature===tasksSignature)return;
  const activeCount=registryTasks.filter(task=>['QUEUED','RUNNING','RETRYING','PAUSED','CANCELLING'].includes(task.status)).length;
  const errorCount=registryTasks.filter(task=>['FAILED','UNKNOWN','INTERRUPTED'].includes(task.status)).length;
  $('stop-all').hidden=acc!=='discord'||activeCount===0;
  $('stop-all-zalo').hidden=acc==='discord'||!accounts.length||activeCount===0;
  if($('task-summary'))$('task-summary').hidden=registryTasks.length===0;
  const filters=$('tasks').querySelector('.task-filters');if(filters)filters.hidden=registryTasks.length===0;
  $('task-summary')?.replaceChildren(...[['Đang xử lý',activeCount],['Cần xem',errorCount],['Tổng task',registryTasks.length]].map(([label,value])=>{
   const metric=element('div',undefined,'task-summary-item');metric.append(element('strong',value),element('span',label));return metric;
  }));

  const focused=document.activeElement?.dataset?.taskAction;
  tasksSignature=signature;target.replaceChildren();
  if(registryState!=='ready'){
   const notice=registryState==='loading'?'Đang tải tác vụ…':
     registryState==='forbidden'?'Tài khoản chưa được cấp quyền xem tác vụ.':
     registryState==='unauthorized'?'Phiên Telegram không hợp lệ. Hãy mở lại từ bot.':
     'Không tải được trạng thái mới. Dữ liệu bên dưới có thể đã cũ.';
   target.append(element('p',notice));
   if(registryState==='unavailable')target.append(button('Thử tải lại',()=>refreshRegistry()));
  }
  let visible=0;
  for(const task of registryTasks){
   const searchable=[task.id,task.task_type,task.target,...(task.account_names||[])].join(' ').toLocaleLowerCase('vi');
   if(query&&!searchable.includes(query))continue;
   if(f==='active'&&!['QUEUED','RUNNING','RETRYING','PAUSED','CANCELLING'].includes(task.status)||
     !['all','active'].includes(f)&&task.status!==f)continue;
   visible++;
   if(visible>(taskPage*25))continue;
   const timestamp=task.started||task.created;
   const timeText=timestamp?new Date(timestamp*1000).toLocaleString():'Chưa bắt đầu';
   const label=task.platform==='discord'?'Discord':'Zalo';
   const statusNames={QUEUED:'Đang chờ',RUNNING:'Đang chạy',RETRYING:'Đang thử lại',PAUSED:'Tạm dừng',CANCELLING:'Đang dừng',STOPPED:'Đã dừng',INTERRUPTED:'Gián đoạn',COMPLETED:'Hoàn tất',CANCELLED:'Đã hủy',FAILED:'Thất bại',UNKNOWN:'Chưa rõ'};
   const card=element('article',undefined,'card task-card');
   const head=element('div',undefined,'task-card-head');
   const badge=element('span',statusNames[task.status]||task.status,'task-state');badge.dataset.state=task.status;
   head.append(element('strong',label+' · '+(task.task_type||'Tác vụ')),badge);
   card.append(head,element('p',task.target||'Chưa có đích','task-target'));
   if(task.account_names?.length)card.append(element('small',task.account_names.join(', '),'task-account-names'));
   card.append(element('small',timeText,'task-time'));
   if(task.shared_execution)card.append(element('small','Tác vụ nhiều tài khoản; dừng sẽ ảnh hưởng tất cả.','task-warning'));
   if(task.error)card.append(element('p',task.error,'task-error'));
   const actions=element('div',undefined,'actions');
   for(const action of task.actions||[]){
    const labels={stop:'Dừng',pause:'Tạm dừng',resume:'Tiếp tục',retry:'Thử lại'};
    const b=button(labels[action]||action,async()=>{
     if(task.execution_source==='durable_notifications')
      await api('notification_control',{id:task.source_id,action});
     else if(task.execution_source==='legacy_process'&&action==='stop')
      await api('stop_task',{task_id:task.source_id});
     else throw Error('Hành động không được hỗ trợ bởi tác vụ này');
     await refreshRegistry();await refreshControl();
    });
    b.dataset.taskAction=task.id+':'+action;actions.append(b);
   }
   if(['STOPPED','INTERRUPTED','COMPLETED','CANCELLED','FAILED','UNKNOWN'].includes(task.status)){
    actions.append(button('Xóa',()=>confirmAction('Xóa tác vụ đã kết thúc?',async()=>{
     if(task.execution_source==='durable_notifications')
      await api('delete_finished_notification',{id:task.source_id});
     else await api('delete_finished_task',{task_ref:task.id});
    }),'danger'));
   }
   const technical=element('details',undefined,'task-technical');
   technical.append(element('summary','Thông tin task'),element('small','ID '+task.id+' · Chủ '+task.owner),
    element('small',task.persistence==='process_local'?'Lưu trong tiến trình':'Lưu trong SQLite'));
   card.append(actions,technical);target.append(card);
  }
  if(visible>taskPage*25)target.append(button('Xem thêm '+Math.min(25,visible-taskPage*25)+' tác vụ',()=>{
   taskPage++;renderTasks();
  }));
  if(registryState==='ready'&&!target.children.length)
   target.append(element('p','Không có tác vụ trong bộ lọc này.'));
  if(focused)for(const b of target.querySelectorAll('button[data-task-action]'))
   if(b.dataset.taskAction===focused){b.focus({preventScroll:true});break;}
 }
 $('task-filter').onchange=()=>{taskPage=1;renderTasks();};
 $('task-filter').append(new Option('Đã dừng','STOPPED'));
 $('task-search').oninput=()=>{taskPage=1;renderTasks();};
 function paintMetrics(){if(!legacyTelemetry)return;const t=legacyTelemetry,discord=identities.filter(x=>x.platform==='discord').length,facebook=identities.filter(x=>x.platform==='facebook').length;const values=[['Tài khoản',accounts.length+identities.length],['Discord',discord],['Facebook',facebook],['Zalo',accounts.length],['Đang chạy',(data.counts?.RUNNING||0)+t.running_tasks],['Đang chờ',(data.counts?.QUEUED||0)+(data.counts?.RETRYING||0)],['Hoàn tất',data.counts?.COMPLETED||0],['Thất bại',data.counts?.FAILED||0],['Worker',data.workers||0],['Kênh',data.channels?.length||0],['Thông lượng',data.completed_last_minute===undefined?'—':data.completed_last_minute+'/phút'],['API',data.api_latency_seconds==null?'Chưa đo':data.api_latency_seconds.toFixed(2)+'s'],['RAM',t.ram_mb+' MB']];$('metrics').replaceChildren(...values.map(([label,value])=>{const r=element('div',undefined,'metric');r.append(element('span',label),element('strong',value));return r;}));$('metrics').setAttribute('aria-busy','false');}
 async function refreshCredentialLinks(){
  identities=(await api('credential_links')).links;
  renderCredentialLinks();renderAccounts();paintMetrics();
 }
 function credentialCard(item){
  const provider=item.platform==='facebook'?'Facebook':'Discord';
  const labels={verified:'Phiên đã kiểm tra',invalid:'Phiên hết hạn',unknown:'Chưa xác nhận'};
  const state=labels[item.status]||labels.unknown;
  const card=row(item.name||provider,provider+' · ID '+item.uid);
  card.classList.add('credential-card');
  const badge=element('span',state,'credential-state');badge.dataset.state=item.status||'unknown';
  card.append(badge,element('small','Kiểm tra '+(item.checked_at?new Date(item.checked_at*1000).toLocaleString():'chưa có')+(item.kind==='bot'?' · Bot':'')));
  if(item.last_error)card.append(element('small',item.last_error,'credential-error'));
  const actions=element('div',undefined,'actions');
  actions.append(button('Kiểm tra lại',async()=>{
   const result=await api('credential_links/check',{id:item.id},{timeout:15000});
   await refreshCredentialLinks();
   toast(result.result.status==='verified'?'Phiên còn hoạt động':result.result.error);
  }));
  actions.append(button('Gỡ',()=>confirmAction('Gỡ tài khoản này?',()=>api('credential_links',{id:item.id},{method:'DELETE'})),'danger'));
  card.append(actions);return card;
 }
 function renderCredentialLinks(){
  for(const platform of ['discord','facebook']){
   const target=$(platform+'-links');if(!target)continue;
   const linked=identities.filter(item=>item.platform===platform);
   target.replaceChildren(...(linked.length?linked.map(credentialCard):[element('p','Chưa có tài khoản đã kiểm tra.')]))
  }
  const chooser=$('discord-send-account');
  if(chooser){
   const previous=chooser.value;
   chooser.replaceChildren(...identities.filter(item=>item.platform==='discord'&&item.kind==='bot'&&item.status==='verified').map(item=>{
    const option=element('option',item.name+' · Bot đã xác minh');
    option.value=String(item.id);return option;
   }));
   if([...chooser.options].some(option=>option.value===previous))chooser.value=previous;
   $('discord-send-form').hidden=!chooser.options.length;
   $('discord-send-empty').hidden=!!chooser.options.length;
  }
 }
 let channelSignature='';function renderControl(next){data=next;cursor=next.cursor||cursor;paintMetrics();if(next.reset)eventRows=[];for(const e of next.events||[])if(!eventRows.some(r=>r.seq===e.seq))eventRows.push(e);eventRows=eventRows.slice(-200);renderTasks();$('health').textContent=`${next.workers} worker · ${next.channels.length} kênh · API trung bình ${next.api_latency_seconds===null?'Chưa đo':next.api_latency_seconds.toFixed(3)+'s'}`;$('event-list').replaceChildren(...eventRows.slice().reverse().map(e=>row(e.status,`${e.task} · ${new Date(e.at*1000).toLocaleTimeString()}`)));$('commands').replaceChildren(...next.commands.map(c=>{const r=element('div',undefined,'row');r.append(element('strong','/'+c.name),element('small',c.description));return r;}));const signature=JSON.stringify(next.channels);if(signature!==channelSignature){channelSignature=signature;const chosen=new Set([...$('channel-options').querySelectorAll(':checked')].map(x=>x.value));$('channels').replaceChildren(...next.channels.map(c=>row(c.name,c.id)));$('channel-options').replaceChildren(element('legend','Chọn tối đa 5 kênh'));for(const c of next.channels){const label=element('label');const box=element('input');box.type='checkbox';box.value=c.id;box.checked=chosen.has(c.id);label.append(box,document.createTextNode(c.name));$('channel-options').append(label);}}
 const bins=Array(10).fill(0),now=Date.now()/1000;for(const e of eventRows){const i=9-Math.floor((now-e.at)/60);if(i>=0&&i<10)bins[i]++;}const max=Math.max(1,...bins);$('chart').replaceChildren();bins.forEach((n,i)=>{const rect=document.createElementNS('http://www.w3.org/2000/svg','rect');for(const[k,v]of Object.entries({x:i*60+5,y:100-n/max*90,width:48,height:n/max*90,rx:5,fill:'currentColor'}))rect.setAttribute(k,v);$('chart').append(rect);});$('chart-summary').textContent=`${bins.reduce((a,b)=>a+b,0)} sự kiện trong 10 phút (tối đa 200 sự kiện đã tải).`;
 }
 async function refreshControl(options={}){renderControl(await api('control?cursor='+cursor,undefined,options));}
 let lastFullSync=0;
 async function refresh(){
  if(terminalAuth)return;
  if(refreshing)return refreshing;
  const controller=new AbortController();
  refreshController=controller;
  const options={signal:controller.signal};
  const operation=(async()=>{
   // Authentication is independent of optional telemetry, storage and task endpoints.
   const viewer=await api('session',undefined,options);
   sessionValidated=true;
   csrfToken=viewer.csrf_token||'';
   hideAuthGate();
   setConnection('AUTHENTICATED');
   if(!legacyTelemetry)legacyTelemetry={running_tasks:0,ram_mb:'—',tasks:[]};
   paintMetrics();
   $('updated').textContent='Đã xác thực · đang cập nhật dữ liệu…';
   const warnings=[];
   const jobs=[];
   if(viewer.role==='admin'){
    jobs.push({
     name:'Liên kết tài khoản',load:()=>api('credential_links',undefined,options),
     use:r=>{identities=Array.isArray(r.links)?r.links:[];renderCredentialLinks();}
    });
    jobs.push({
     name:'Trạng thái xử lý',load:()=>api('telemetry',undefined,options),
     use:r=>{
      legacyTelemetry=r;
      $('storage').textContent='Kho: '+(r.storage_id||'Chưa có dữ liệu');
      $('legacy-tasks').replaceChildren(...(r.tasks||[]).map(task=>{
       const card=row(task.name,(task.status||'')+' · '+(task.target_label||''));
       if(task.can_stop)card.append(button('Dừng',async()=>{
        await api('stop_task',{task_id:task.id});await refresh();
       }));
       return card;
      }));
     }
    });
    jobs.push({
     name:'Tài khoản',load:()=>api('accounts',undefined,options),
     use:r=>{
      accounts=Array.isArray(r.accounts)?r.accounts:[];
      renderLaunchAccounts();renderTaskAccounts();renderAccounts();
     }
    });
    jobs.push({
     name:'Kho tệp',load:()=>api('files',undefined,options),
     use:r=>{
      $('selected-files').textContent='Nhây: '+(r.selected_nhay||'—')+' · Ngôn: '+(r.selected_ngon||'—');
      $('file-list').replaceChildren(...['nhay','ngon'].map(target=>{
       const title=target==='nhay'?'KHO NHÂY · từng dòng (.n)':'KHO NGÔN · nguyên đoạn (.g)';
       const box=element('article',undefined,'file-category');
       box.append(element('h2',title));
       const subset=(r.files||[]).filter(file=>file.file_type===target);
       if(!subset.length)box.append(element('p','Chưa có file thuộc loại này.'));
       for(const file of subset){
        const card=row(file.filename,(file.lines||0)+' dòng · '+(file.size_kb||0)+' KB');
        if(file.filename===(target==='nhay'?r.selected_nhay:r.selected_ngon))card.append(element('small','✓ Đang chọn'));
        else card.append(button('Dùng cho '+(target==='nhay'?'Nhây':'Ngôn'),async()=>{
         await api('select_file',{filename:file.filename,target});await refresh();
        },'primary'));
        box.append(card);
       }
       return box;
      }));
     }
    });
    jobs.push({
     name:'Danh sách lệnh',load:()=>api('commands',undefined,options),
     use:r=>{
      $('zalo-commands').replaceChildren(...(r.commands||[]).filter(x=>(x.platforms||[]).includes('zalo')).map(x=>row(x.usage,x.description)));
     }
    });
   }else{
    identities=[];renderCredentialLinks();accounts=[];renderTaskAccounts();
    if(!$('member-notice')){
     const notice=element('article','Tài khoản Zalo và tệp hiện do quản trị viên chính điều khiển. Discord và task chỉ hiển thị dữ liệu của bạn.');
     notice.id='member-notice';$('zalo').replaceChildren(notice);
     $('discord-credential-form').hidden=true;$('facebook-credential-form').hidden=true;$('stop-all').hidden=true;
    }
   }
   jobs.push({name:'Tổng quan',load:()=>refreshControl(options),use:()=>{}});
   // Every independent service settles without blocking authenticated UI.
   const results=await Promise.allSettled(jobs.map(job=>loadDashboardJob(job,options)));
   for(let i=0;i<jobs.length;i++){
    const result=results[i];
    if(result.status==='rejected'&&result.reason?.status===401)throw result.reason;
    if(result.status==='fulfilled'){
     try{jobs[i].use(result.value);}
     catch(error){warnings.push(jobs[i].name+' (lỗi hiển thị)');console.warn('GLAZE render issue:',jobs[i].name,error?.name||'Error');}
    }else warnings.push(jobs[i].name+' ('+dashboardFailureLabel(result.reason)+')');
   }
   try{await refreshRegistry(options);}
   catch(error){
    if(error?.status===401)throw error;
    warnings.push('Tác vụ ('+dashboardFailureLabel(error)+')');
   }
   renderAccounts();paintMetrics();
   syncWarnings=warnings;
   lastFullSync=Date.now();
   $('updated').textContent='Đã xác thực · cập nhật '+new Date().toLocaleTimeString();
   if(warnings.length){
    $('error').hidden=false;
    $('error').textContent='Tạm chưa tải được: '+warnings.join(', ')+'. Các phần khác vẫn có thể sử dụng. Bấm làm mới để thử lại.';
    setConnection('PARTIAL');
   }else{
    $('error').hidden=true;
    $('error').textContent='';
    setConnection('CONNECTED');
   }
  })();
  refreshing=operation.catch(error=>{
   if(error?.name!=='AbortError'){
    controller.abort();
    failed(error,sessionValidated?'PARTIAL':'DISCONNECTED');
   }
  }).finally(()=>{
   if(refreshController===controller)refreshController=null;
   refreshing=null;
  });
  return refreshing;
 }
 function inlineFeedback(id,message){
  const target=$(id);if(!target)return;
  target.hidden=false;target.textContent=message;
 }
 function form(id,path,extra={},after,onSaved){$(id).onsubmit=async e=>{
  e.preventDefault();const form=e.currentTarget,submit=form.querySelector('button');
  if(submit.disabled)return;submit.disabled=true;submit.setAttribute('aria-busy','true');
  const isLink=path==='credential_links',feedbackId=extra.platform+'-link-feedback';
  if(isLink)inlineFeedback(feedbackId,extra.platform==='discord'
   ?'Đang xác minh Bot token với Discord (không gửi tin nhắn thử)...'
   :'Đang kiểm tra phiên trên máy chủ...');
  try{
   const body={...Object.fromEntries(new FormData(form)),...extra};
   const result=await api(path,body,{timeout:isLink&&extra.platform==='discord'?15000:isLink?25000:REQUEST_TIMEOUT_MS});
   after?.(result);
   if(isLink)inlineFeedback(feedbackId,'Đã xác minh và lưu: '+(result.link?.name||'tài khoản'));
   toast('Đã lưu trên máy chủ');
   if(onSaved)onSaved(result);else await refresh();
  }catch(error){
   if(isLink){
    const timedOut=error?.code==='timeout'||error?.code==='discord_timeout';
    const message=timedOut
     ?'Xác minh quá thời gian chờ. Không gửi lại liên tục. Bấm “Kiểm tra đường kết nối Discord” để kiểm tra máy chủ.'
     :(error?.message||'Lỗi máy chủ');
    inlineFeedback(feedbackId,'Không kết nối được: '+message);
   }
   if(!isLink||error?.status===401)failed(error);
  }finally{submit.disabled=false;submit.removeAttribute('aria-busy');}
 };}
 form('channel-form','channels',{},()=>$('channel-form').reset());form('zalo-form','add_cookie',{},()=>$('zalo-form').reset());form('file-form','add_file');
 for(const platform of ['discord','facebook'])form(platform+'-credential-form','credential_links',{platform},()=>$(platform+'-credential-form').reset(),result=>{
  if(!result.link?.id)return;
  identities=[result.link,...identities.filter(item=>item.id!==result.link.id&&
   !(item.platform===result.link.platform&&item.uid===result.link.uid))];
  renderCredentialLinks();renderAccounts();paintMetrics();
 });
 if($('discord-send-form'))$('discord-send-form').onsubmit=async e=>{
  e.preventDefault();const submit=e.currentTarget.querySelector('button[type=submit]');
  if(submit.disabled)return;submit.disabled=true;
  try{
   const fields=e.currentTarget.elements;
   const result=await api('credential_links/send_discord',{
    id:Number(fields.account_id.value),channel_id:fields.channel_id.value.trim(),content:fields.content.value
   },{timeout:15000});
   toast('Discord đã nhận tin · ID '+result.message_id);
   inlineFeedback('discord-send-feedback','Đã gửi thành công · ID '+result.message_id);
   fields.content.value='';
  }catch(error){
   inlineFeedback('discord-send-feedback','Không gửi được tin: '+(error?.message||'Lỗi kết nối'));
   if(error?.status===401)failed(error);
  }finally{submit.disabled=false;}
 };
 for(const provider of ['discord','zalo']){
  const testButton=$(provider+'-connectivity');
  if(!testButton)continue;
  testButton.onclick=async()=>{
   if(testButton.disabled)return;testButton.disabled=true;
   const feedbackId=provider+'-network-status';
   inlineFeedback(feedbackId,'Đang kiểm tra kết nối từ máy chủ...');
   try{
    const status=await api('provider_health/'+provider,undefined,{timeout:12000});
    inlineFeedback(feedbackId,status.message+(status.http_status?' (HTTP '+status.http_status+')':'')
     +(status.reachable?' · đường truyền hoạt động':' · chưa thể kết nối'));
   }catch(error){
    inlineFeedback(feedbackId,'Không kiểm tra được đường truyền: '+(error?.message||'Lỗi API'));
    failed(error);
   }finally{testButton.disabled=false;}
  };
 }
 $('zalo-form').closest('details').open=true;
 $('upload-form').onsubmit=async e=>{e.preventDefault();const b=e.currentTarget.querySelector('button');if(b.disabled)return;b.disabled=true;try{await uploadFile(e.currentTarget);toast('Đã tải tệp lên');await refresh();}catch(error){failed(error);}finally{b.disabled=false;}};
 $('send-form').onsubmit=async e=>{e.preventDefault();const b=e.currentTarget.querySelector('button');b.disabled=true;try{await api('notifications',{channels:[...$('channel-options').querySelectorAll(':checked')].map(x=>x.value),content:e.currentTarget.elements.content.value});toast('Đã đưa vào hàng chờ');await refreshControl();}catch(e){failed(e);}finally{b.disabled=false;}};
 function renderQrReceipt(status){
  let holder=$('qr-receipt');
  if(!holder){holder=element('div',undefined,'qr-receipt');holder.id='qr-receipt';$('qr-status').after(holder);}
  holder.replaceChildren();
  if(status.status!=='success'||!status.imei)return;
  const fields=[
   'Tài khoản: '+(status.account_name||'Zalo'),
   'Mã ACC: '+(status.account_handle||'Chưa lưu'),
   'IMEI đầy đủ: '+status.imei,
   'UID: '+(status.uid||'Chưa nhận diện'),
  ];
  holder.append(element('pre',fields.join('\\n')));
  if(!status.account_id){holder.append(element('p','Chưa tìm thấy phiên đã lưu. Hãy kiểm tra tài khoản trước khi tải.'));return;}
  holder.append(button('Tải Cookie + IMEI .txt',()=>downloadZaloSession(status.account_id),'primary'));
  if(!$('sheet').open)sheet('Phiên Zalo đã sẵn sàng','Cookie và IMEI đã được lưu cho ACC-'+status.account_id+'. Chạm nút bên dưới để tải tệp .txt về thiết bị.',[
   button('Tải tệp .txt',async()=>{await downloadZaloSession(status.account_id);closeSheet();},'primary')
  ]);
 }
 $('qr').onclick=async()=>{
  const trigger=$('qr'),image=$('qr-image');
  let receiptRetries=0,transientFailures=0;
  trigger.disabled=true;
  image.hidden=true;
  image.removeAttribute('src');
  $('qr-receipt')?.replaceChildren();
  $('qr-status').textContent='Đang tạo mã QR…';
  const finish=()=>{
   trigger.disabled=false;
   image.hidden=true;
   image.removeAttribute('src');
  };
  try{
   const result=await api('start_qr',{});
   const poll=async()=>{
    try{
     const status=await api('qr_status/'+encodeURIComponent(result.session_id));
     transientFailures=0;
     $('qr-status').textContent=status.message||status.status;
     if(status.status==='success'&&!status.account_id&&receiptRetries++<5){
      setTimeout(poll,1000);
      return;
     }
     if(['success','expired','failed','cancelled','error','declined'].includes(status.status)){
      finish();
      if(status.status==='success')renderQrReceipt(status);
      await refresh();
      return;
     }
     if(status.qr_base64){
      const source=status.qr_base64.startsWith('data:')?status.qr_base64:'data:image/png;base64,'+status.qr_base64;
      if(image.getAttribute('src')!==source)image.src=source;
      image.hidden=false;
     }
     setTimeout(poll,document.hidden?8000:2000);
    }catch(error){
     if((error?.code==='timeout'||!error?.status||error.status>=500)&&transientFailures<2){
      transientFailures++;
      $('qr-status').textContent='Kết nối chậm; đang kiểm tra lại phiên QR…';
      setTimeout(poll,2500*transientFailures);
      return;
     }
     finish();$('qr-status').textContent='Lỗi kiểm tra QR: '+(error?.message||'Mất kết nối');failed(error);
    }
   };
   await poll();
  }catch(error){finish();$('qr-status').textContent='Không tạo được QR: '+(error?.message||'Mất kết nối');failed(error);}
 };
 $('stop-all').onclick=()=>confirmAction('Dừng thông báo Discord của tôi?',()=>api('notifications/stop_all',{}));
 $('stop-all-zalo').onclick=()=>confirmAction('Dừng tác vụ trên mọi tài khoản Zalo?',()=>api('quick_action',{action:'stop_all'}));
 $('refresh').onclick=refresh;
 function reconnectDelay(){const exponential=Math.min(STREAM_MAX_DELAY_MS,STREAM_BASE_DELAY_MS*2**Math.min(reconnectAttempt,6));reconnectAttempt=Math.min(reconnectAttempt+1,10);return Math.round(exponential*(1-STREAM_JITTER+Math.random()*STREAM_JITTER*2));}
 function scheduleReconnect(generation,delay){if(terminalAuth||document.hidden||navigator.onLine===false||generation!==streamGeneration)return;clearTimeout(reconnectTimer);const wait=delay===undefined?Math.max(reconnectDelay(),retryAfterDelay):delay;retryAfterDelay=0;if(!sessionValidated)setConnection('RECONNECTING');reconnectTimer=setTimeout(connect,wait);}
 async function connect(){
  if(terminalAuth||document.hidden||navigator.onLine===false)return;
  clearTimeout(reconnectTimer);const generation=++streamGeneration;stream?.abort();stream=new AbortController();streamConnected=false;if(!sessionValidated)setConnection(reconnectAttempt?'RECONNECTING':'CONNECTING');
  let received=false,retryError,handshakeTimedOut=false,handshakeTimer;
  try{
   const r=await fetch('/api/miniapp/events?cursor='+cursor,{headers:{'X-Telegram-Init-Data':tg?.initData||launch,'X-Request-ID':requestId('sse')},signal:stream.signal,cache:'no-store'});
   if(!r.ok){
     let details={};try{details=await r.json();}catch{}
     throw Object.assign(new Error(details.error||'Luồng cập nhật tạm gián đoạn'),{status:r.status,code:details.code||'http_error'});
   }
   if(!r.body)throw Error('Trình duyệt không hỗ trợ luồng cập nhật');
   const reader=r.body.getReader(),decoder=new TextDecoder();let buffer='';lastStreamAt=Date.now();
   while(generation===streamGeneration){
    const{done,value}=await reader.read();
    if(done)break;
    if(generation!==streamGeneration)break;
    lastStreamAt=Date.now();buffer+=decoder.decode(value,{stream:true});let at;
    while((at=buffer.indexOf('\n\n'))>=0){
     const msg=buffer.slice(0,at);buffer=buffer.slice(at+2);const line=msg.split('\n').find(x=>x.startsWith('data: '));
     if(line){const snapshot=JSON.parse(line.slice(6));renderControl(snapshot);received=true;streamConnected=true;reconnectAttempt=0;if(!syncWarnings.length){$('error').hidden=true;setConnection('CONNECTED');}else setConnection('PARTIAL');}
    }
   }
   if(generation===streamGeneration){streamConnected=false;if(!received)setConnection(sessionValidated?'PARTIAL':'DEGRADED');}
  }catch(e){if(e.name!=='AbortError'&&generation===streamGeneration){streamConnected=false;failed(e,'DEGRADED');}}
  finally{if(!terminalAuth&&!document.hidden&&navigator.onLine!==false&&generation===streamGeneration){if(!received)streamConnected=false;scheduleReconnect(generation);}}
 }
 function checkStreamHealth(){if(document.hidden||navigator.onLine===false||!stream||stream.signal.aborted||!lastStreamAt)return;if(Date.now()-lastStreamAt>STREAM_STALE_MS){streamConnected=false;setConnection(sessionValidated?'PARTIAL':'DEGRADED');stream.abort();}}
 document.addEventListener('visibilitychange',()=>{clearTimeout(reconnectTimer);streamGeneration++;stream?.abort();refreshController?.abort();if(document.hidden){streamConnected=false;return;}reconnectAttempt=0;lastStreamAt=0;setConnection(sessionValidated?'PARTIAL':'CONNECTING');if(!terminalAuth)refresh().finally(()=>scheduleReconnect(streamGeneration,100));});
 window.addEventListener('offline',()=>{clearTimeout(reconnectTimer);streamGeneration++;stream?.abort();refreshController?.abort();streamConnected=false;setConnection('DISCONNECTED');});
 window.addEventListener('online',()=>{if(document.hidden)return;reconnectAttempt=0;setConnection('CONNECTING');refresh().finally(()=>scheduleReconnect(streamGeneration,100));});
 setInterval(()=>{if(!terminalAuth&&!document.hidden&&navigator.onLine!==false&&Date.now()-lastFullSync>=60000)refresh();},15000);
 setInterval(()=>{if(active==='tasks'&&!terminalAuth&&!document.hidden&&navigator.onLine!==false
   &&Date.now()>=registryNextRetryAt)refreshRegistry().catch(()=>{});},4000);
 setInterval(()=>{if(active==='tasks'&&!document.hidden&&registryFetchedAt){
   const status=$('task-account-status');if(status&&registryState==='ready')
    status.textContent=status.textContent.replace(/Cập nhật \d+s trước/,
      'Cập nhật '+Math.floor((Date.now()-registryFetchedAt)/1000)+'s trước');
 }},1000);
 setInterval(()=>{if(!terminalAuth&&!document.hidden&&navigator.onLine!==false
    &&accounts.length&&['accounts','tasks','zalo'].includes(active))refreshAccountHealth().catch(()=>{});},7000);
 setInterval(checkStreamHealth,5000);
 async function bootstrap(){
   // A normal web browser can check its server session immediately. Only wait
   // for the Telegram bridge when the page is actually inside Telegram.
   const telegramContainer=/Telegram/i.test(navigator.userAgent)||!!window.TelegramWebviewProxy||
    !!window.webkit?.messageHandlers?.TelegramWebviewProxy;
   if(!tg?.initData&&!launch&&telegramContainer&&$('telegram-sdk')){
     await new Promise(resolve=>{
       const script=$('telegram-sdk');let settled=false;
       const done=()=>{if(settled)return;settled=true;clearTimeout(timer);resolve();};
       const timer=setTimeout(done,SDK_BOOT_WAIT_MS);
       script.addEventListener('load',done,{once:true});
       script.addEventListener('error',done,{once:true});
       if(window.Telegram?.WebApp)done();
     });
     initTelegram();
   }
   await refresh();
   if(!terminalAuth){
    if(location.hash==='#accounts')go('accounts');
    scheduleReconnect(streamGeneration,100);
   }
 }
 bootstrap();
})();
