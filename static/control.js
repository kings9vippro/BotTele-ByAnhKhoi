/* Dev Anh Khôi · v2.0 · Shared API, native scroll gestures, bounded SSE */
'use strict';
(() => {
 const $=id=>document.getElementById(id), reduced=matchMedia('(prefers-reduced-motion: reduce)');
 const launch=new URLSearchParams(location.hash.slice(1)).get('tgWebAppData')||'';
 const REQUEST_TIMEOUT_MS=18000,STREAM_BASE_DELAY_MS=1000,STREAM_MAX_DELAY_MS=30000,STREAM_JITTER=0.2,STREAM_STALE_MS=12000;
 const connectionLabels={CONNECTING:'Đang kết nối…',CONNECTED:'Đã đồng bộ',RECONNECTING:'Đang kết nối lại…',DEGRADED:'Luồng gián đoạn · đang thử lại',DISCONNECTED:'Mất kết nối · dữ liệu cũ',AUTH_REQUIRED:'Cần đăng nhập Telegram',ACCESS_DENIED:'Không đủ quyền truy cập',SERVER_ERROR:'Máy chủ chưa sẵn sàng'};
 let tg, active='home', data={}, accounts=[], identities=[], eventRows=[], cursor=0, stream, refreshing, refreshController, toastTimer, streamGeneration=0, legacyTelemetry, reconnectTimer, reconnectAttempt=0, lastStreamAt=0, streamConnected=false, requestSequence=0, terminalAuth=false;
 const names={home:'Tổng quan',accounts:'Tài khoản',discord:'Discord',zalo:'Zalo',tasks:'Task',activity:'Nhật ký',music:'Âm nhạc',settings:'Cài đặt'};
 const keys=Object.keys(names), pages=$('pages');
 const element=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 function showAuthGate(state,reason){
  const card=$('auth-gate');if(!card)return;
  const variants={
   missing:'Thiếu dữ liệu xác thực Telegram. Hãy mở Mini App từ nút của bot trong Telegram, không qua Safari.',
   expired:'Phiên Telegram đã hết hạn. Đóng Mini App và mở lại từ bot để lấy phiên mới.',
   forbidden:'Tài khoản Telegram này chưa được cấp quyền quản lý.',
   server:'Máy chủ chưa có cấu hình xác thực Telegram hợp lệ. Quản trị viên cần kiểm tra hosting.',
   invalid:'Phiên xác thực không hợp lệ. Đóng và mở lại Mini App từ bot.'
  };
  $('auth-message').textContent=variants[reason]||variants.invalid;
  $('auth-heading').textContent=reason==='forbidden'?'Không đủ quyền':reason==='server'?'Chưa thể xác thực':'Mở trong Telegram';
  card.hidden=false;document.body.classList.add('auth-locked');setConnection(state);
 }
 function hideAuthGate(){$('auth-gate').hidden=true;document.body.classList.remove('auth-locked');}
 function toast(text){$('toasts').replaceChildren(element('div',text,'toast'));clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toasts').replaceChildren(),4500);}
 function setConnection(state){const n=$('connection');n.dataset.state=state;n.textContent=connectionLabels[state]||connectionLabels.DISCONNECTED;n.classList.toggle('live',state==='CONNECTED');}
 function failed(error,state='DISCONNECTED'){
  if(error?.name==='AbortError')return;
  if(error?.status===401){terminalAuth=true;state='AUTH_REQUIRED';stream?.abort();clearTimeout(reconnectTimer);showAuthGate(state,error?.code==='expired_init_data'?'expired':'invalid');}
  else if(error?.status===403){terminalAuth=true;state='ACCESS_DENIED';showAuthGate(state,'forbidden');}
  else if(error?.code==='server_configuration'||error?.status===503){terminalAuth=true;state='SERVER_ERROR';showAuthGate(state,'server');}
  $('error').hidden=false;
  $('error').textContent=error?.message||'Không thể đồng bộ dữ liệu.';
  setConnection(state);
 }
 function requestId(prefix='miniapp'){requestSequence=(requestSequence+1)%1000000;const random=window.crypto?.randomUUID?.()||Math.random().toString(36).slice(2);return `${prefix}-${Date.now().toString(36)}-${requestSequence.toString(36)}-${random}`;}
 function requestSignal(parent,timeout=REQUEST_TIMEOUT_MS){const controller=new AbortController();let timedOut=false;const timer=setTimeout(()=>{timedOut=true;controller.abort();},timeout),abort=()=>controller.abort();if(parent?.aborted)abort();else parent?.addEventListener('abort',abort,{once:true});return {signal:controller.signal,isTimeout:()=>timedOut,cleanup:()=>{clearTimeout(timer);parent?.removeEventListener('abort',abort);}};}
 async function api(path,body,options={}){const h={'X-Telegram-Init-Data':tg?.initData||launch,'X-Request-ID':requestId()};if(body!==undefined)h['Content-Type']='application/json';const request=requestSignal(options.signal,options.timeout||REQUEST_TIMEOUT_MS);try{const r=await fetch('/api/miniapp/'+path,{method:body===undefined?'GET':'POST',headers:h,body:body===undefined?undefined:JSON.stringify(body),signal:request.signal,cache:'no-store'});let d;try{d=await r.json();}catch{throw Object.assign(new Error('API trả về dữ liệu không phải JSON hợp lệ.'),{status:r.status,code:'invalid_json'});}
  if(!r.ok||d.ok===false)throw Object.assign(new Error(d.error||d.message||'Yêu cầu thất bại'),{status:r.status,code:d.code||'http_error'});
  return d;
 }catch(e){if(e?.name==='AbortError'&&request.isTimeout())throw Object.assign(new Error('Yêu cầu vượt quá thời gian chờ.'),{code:'timeout'});throw e;}
 finally{request.cleanup();}}
 async function uploadFile(form,options={}){const h={'X-Telegram-Init-Data':tg?.initData||launch,'X-Request-ID':requestId('upload')};const request=requestSignal(options.signal,options.timeout||REQUEST_TIMEOUT_MS);try{const r=await fetch('/api/miniapp/upload_file',{method:'POST',headers:h,body:new FormData(form),signal:request.signal,cache:'no-store'});const d=await r.json();if(!r.ok||!d.ok)throw Error(d.error||'Tải tệp thất bại');return d;}finally{request.cleanup();}}
 function button(text,fn,cls){const b=element('button',text,cls);b.type='button';b.onclick=async()=>{if(b.disabled)return;b.disabled=true;b.setAttribute('aria-busy','true');try{await fn();}catch(e){failed(e);toast(e.message);}finally{b.disabled=false;b.removeAttribute('aria-busy');}};return b;}
 function theme(){const mode=$('theme').value;document.documentElement.dataset.theme=mode==='system'?(tg?.colorScheme||(matchMedia('(prefers-color-scheme:light)').matches?'light':'dark')):mode;}
 function initTelegram(){const sdk=window.Telegram?.WebApp;if(!sdk||tg===sdk)return;tg=sdk;tg.ready();tg.expand();tg.onEvent?.('themeChanged',theme);tg.onEvent?.('viewportChanged',()=>{document.documentElement.style.setProperty('--safe',Math.max(tg.safeAreaInset?.bottom||0,tg.contentSafeAreaInset?.bottom||0)+'px');});tg.BackButton?.onClick(()=>{if($('sheet').open)$('sheet').close();else go('home');});theme();}
 initTelegram();$('telegram-sdk').addEventListener('load',initTelegram);$('theme').onchange=()=>{try{localStorage.setItem('glaze-theme',$('theme').value);}catch{}theme();};try{$('theme').value=localStorage.getItem('glaze-theme')||'dark';}catch{$('theme').value='dark';}theme();
 for(const [id,allowed,fallback] of [['text-size',['normal','large'],'normal'],['accent',['blue','rose','mint'],'blue']]){
  const input=$(id),key='glaze-'+id;
  try{const saved=localStorage.getItem(key);input.value=allowed.includes(saved)?saved:fallback;}catch{input.value=fallback;}
  const apply=()=>{document.documentElement.setAttribute('data-'+id,input.value);try{localStorage.setItem(key,input.value);}catch{}};
  input.addEventListener('change',apply);apply();
 }
 function select(name){active=name;document.querySelectorAll('[data-tab]').forEach(b=>{const on=b.dataset.tab===name;b.setAttribute('aria-selected',on);b.setAttribute('aria-current',on?'page':'false');b.tabIndex=on?0:-1;});document.querySelectorAll('[data-bottom]').forEach(b=>b.setAttribute('aria-current',b.dataset.bottom===name?'page':'false'));keys.forEach(key=>$(key)?.setAttribute('aria-hidden',key===name?'false':'true'));$('tab-'+name)?.scrollIntoView({block:'nearest',inline:'nearest',behavior:reduced.matches?'auto':'smooth'});if(name==='music')loadMusic();if(name==='zalo'&&!terminalAuth)refreshZaloWatches().catch(failed);if(name==='home')tg?.BackButton?.hide();else tg?.BackButton?.show();}
 function go(name){select(name);pages.scrollTo({left:keys.indexOf(name)*pages.clientWidth,behavior:reduced.matches?'auto':'smooth'});tg?.HapticFeedback?.selectionChanged();if(!terminalAuth&&['accounts','zalo','discord'].includes(name)&&Date.now()-lastFullSync>30000)refresh().catch(failed);}
 keys.forEach((key,i)=>{const b=button(names[key],()=>go(key));b.id='tab-'+key;b.dataset.tab=key;b.role='tab';b.setAttribute('aria-controls',key);$(key).setAttribute('aria-labelledby',b.id);$(key).tabIndex=0;b.onkeydown=e=>{const d=e.key==='ArrowRight'||e.key==='ArrowDown'?1:e.key==='ArrowLeft'||e.key==='ArrowUp'?-1:0;if(d||e.key==='Home'||e.key==='End'){e.preventDefault();const next=e.key==='Home'?keys[0]:e.key==='End'?keys[keys.length-1]:keys[(i+d+keys.length)%keys.length];go(next);$('tab-'+next).focus();}};$('tabs').append(b);});
 // Consistent 24×24 outline SVG icons prevent iOS font glyph misalignment.
 const navPaths={
  home:'M3 11.5 12 4l9 7.5V21h-6v-7H9v7H3z',
  accounts:'M16 19v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2h14z M9 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M18 10a3 3 0 0 1 0 6 M18 4a3 3 0 0 1 0 6',
  tasks:'M12 3v9l5 3 M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z',
  music:'M9 18V5l12-2v13 M9 8l12-2 M9 18a3 2 0 1 1-6 0 3 2 0 0 1 6 0z M21 16a3 2 0 1 1-6 0 3 2 0 0 1 6 0z',
  settings:'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z M12 2v3 M12 19v3 M4.9 4.9 7 7 M17 17l2.1 2.1 M2 12h3 M19 12h3 M4.9 19.1 7 17 M17 7l2.1-2.1'
 };
 const ns='http://www.w3.org/2000/svg';
 for(const key of ['home','accounts','tasks','music','settings']){
  const b=button('',()=>go(key));
  const svg=document.createElementNS(ns,'svg');
  svg.classList.add('bottom-icon');svg.setAttribute('viewBox','0 0 24 24');
  svg.setAttribute('width','24');svg.setAttribute('height','24');
  svg.setAttribute('fill','none');svg.setAttribute('stroke','currentColor');
  svg.setAttribute('stroke-width','1.8');svg.setAttribute('stroke-linejoin','round');
  svg.setAttribute('stroke-linecap','round');svg.setAttribute('aria-hidden','true');
  const path=document.createElementNS(ns,'path');path.setAttribute('d',navPaths[key]);svg.append(path);
  b.append(svg);b.dataset.bottom=key;b.classList.add('bottom-nav-button');
  b.setAttribute('aria-label',names[key]);b.title=names[key];$('bottom').append(b);
 }
 for(const [id,page] of [['home-open-accounts','accounts'],['home-open-tasks','tasks'],['home-open-zalo','zalo'],['account-open-zalo','zalo'],['account-open-discord','discord'],['task-open-activity','activity'],['task-open-zalo','zalo']]){
  const target=$(id);if(target)target.addEventListener('click',()=>go(page));
 }
 $('auth-retry')?.addEventListener('click',()=>{
  initTelegram();if(!(tg?.initData||launch)){showAuthGate('AUTH_REQUIRED','missing');return;}
  terminalAuth=false;hideAuthGate();setConnection('CONNECTING');
  refresh().finally(()=>{if(!terminalAuth)scheduleReconnect(streamGeneration,100);});
 });
 let musicData,musicLoading;
 async function loadMusic(){
  if(musicData||musicLoading)return musicLoading;
  musicLoading=(async()=>{
   const response=await fetch('/static/viet_hits.json',{cache:'force-cache'});
   if(!response.ok)throw Error('Không tải được danh sách nhạc.');
   const payload=await response.json();
   if(!/^[A-Za-z0-9]{22}$/.test(payload.playlist_id)||!Array.isArray(payload.tracks))throw Error('Danh sách nhạc không hợp lệ.');
   musicData=payload;
   $('music-source').textContent=`${payload.source} · kiểm tra ${payload.checked_at}. Danh sách có thể thay đổi trên Spotify.`;
   const playlist=new URL(payload.playlist_url);
   if(playlist.origin==='https://open.spotify.com'){$('music-playlist').href=playlist.href;$('music-playlist').hidden=false;}
   $('music-tracks').replaceChildren(...payload.tracks.slice(0,10).map((track,index)=>{
    const card=element('article',undefined,'card');const link=element('a',`${index+1}. ${track.name}`);
    const url=new URL(track.url);
    if(url.origin==='https://open.spotify.com'&&url.pathname.startsWith('/track/')){link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';}
    card.append(link,element('p',track.artist));return card;
   }));
   $('music-tracks').setAttribute('aria-busy','false');
  })().catch(error=>{$('music-tracks').replaceChildren(element('p',error.message));$('music-tracks').setAttribute('aria-busy','false');}).finally(()=>musicLoading=null);
  return musicLoading;
 }
 $('music-play').onclick=async()=>{
  await loadMusic();if(!musicData)return;
  const frame=element('iframe');frame.title='Spotify · Hot Hits Vietnam';frame.loading='lazy';
  frame.src='https://open.spotify.com/embed/playlist/'+musicData.playlist_id+'?utm_source=generator';
  frame.allow='autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture';
  frame.referrerPolicy='strict-origin-when-cross-origin';
  $('music-player').replaceChildren(frame);$('music-play').hidden=true;
 };
 let scrollFrame;pages.onscroll=()=>{if(scrollFrame)return;scrollFrame=requestAnimationFrame(()=>{scrollFrame=null;select(keys[Math.round(pages.scrollLeft/pages.clientWidth)]||'home');});};window.addEventListener('resize',()=>pages.scrollTo({left:keys.indexOf(active)*pages.clientWidth}));select('home');
 let sheetReturnFocus;
 function sheet(title,content,actions=[]){sheetReturnFocus=document.activeElement;$('sheet-title').textContent=title;$('sheet-content').replaceChildren(typeof content==='string'?element('p',content):content);$('sheet-actions').replaceChildren(...actions);$('sheet').showModal();$('sheet-close').focus();}
 function closeSheet(){if($('sheet').open)$('sheet').close();sheetReturnFocus?.focus?.();sheetReturnFocus=null;}
 $('sheet-close').onclick=closeSheet;$('sheet').addEventListener('close',()=>{sheetReturnFocus?.focus?.();sheetReturnFocus=null;});let dragY;
 $('sheet-handle').onpointerdown=e=>{dragY=e.clientY;e.target.setPointerCapture(e.pointerId);};$('sheet-handle').onpointermove=e=>{if(dragY!==undefined)$('sheet').style.transform=`translateY(${Math.max(0,e.clientY-dragY)}px)`;};$('sheet-handle').onpointerup=e=>{if(e.clientY-dragY>90)closeSheet();dragY=undefined;$('sheet').style.transform='';};$('sheet-handle').onpointercancel=()=>{dragY=undefined;$('sheet').style.transform='';};
 function confirmAction(title,fn){sheet(title,'Thao tác này áp dụng trên máy chủ.',[button('Xác nhận',async()=>{await fn();$('sheet').close();await refresh();},'danger')]);}
 function row(title,detail){const r=element('article',undefined,'card');r.append(element('strong',title),element('p',detail));return r;}
 function renderAccounts(){const target=$('account-list'),q=$('account-search').value.toLowerCase();target.replaceChildren();for(const a of [...accounts.map(a=>({...a,kind:'Zalo',label:a.name,state:a.listener_health?.code==='running'?'Đang nhận lệnh':
   a.listener_health?.code==='duplicate_imei'?'Trùng phiên với ACC #'+a.listener_health.conflicting_acc_id:
   a.listener_health?.code==='listener_start_failed'?'Lỗi khởi chạy (xem Logs)':
   a.listener_health?.code==='worker_unavailable'?'Luồng gián đoạn':
   !a.chat_cmd_enabled?'Đang tắt lệnh':'Chưa nhận lệnh'})),...identities.map(a=>({...a,kind:'Discord',label:a.display_name,state:a.status}))]){if(!`${a.label} ${a.id} ${a.uid||a.provider_uid}`.toLowerCase().includes(q))continue;const r=row(a.label,`${a.kind} · #${a.id} · ${a.state}`);if(a.kind==='Zalo')r.append(button(a.chat_cmd_enabled?'Tắt lệnh':'Bật lệnh',async()=>{await api('toggle_acc_cmd',{acc_id:a.id});await refresh();}));r.append(button(a.kind==='Discord'?'Ngắt liên kết':'Xóa',()=>confirmAction('Xác nhận '+a.label,()=>api(a.kind==='Discord'?'oauth/disconnect':'delete_acc',a.kind==='Discord'?{id:a.id}:{acc_id:a.id})),'danger'));target.append(r);}if(!target.children.length)target.append(element('p','Chưa có tài khoản phù hợp.'));}
 $('account-search').oninput=renderAccounts;
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
  catch(error){failed(error);toast(error.message);}finally{b.disabled=false;}
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
  }catch(error){failed(error);toast(error.message);}finally{submit.disabled=false;}
 };
 let tasksSignature='',registryTasks=[],registryState='loading',taskAccountInitialized=false;
 function renderTaskAccounts(){
  const target=$('task-account-filter'),before=target.value,available=new Set(['discord']);
  target.replaceChildren(element('option','Thông báo Discord'),element('option','Task chưa xác định cookie'));
  target.children[0].value='discord';target.children[1].value='unassigned';
  available.add('unassigned');
  for(const account of accounts.filter(a=>a.enabled)){
   const id=String(account.id),option=element('option',account.name+' · Cookie #'+id);
   option.value=id;target.append(option);available.add(id);
  }
  const preferred=accounts.find(a=>a.enabled);
  target.value=taskAccountInitialized&&available.has(before)?before:(preferred?String(preferred.id):'discord');
  taskAccountInitialized=true;
 }
 $('task-account-filter').onchange=()=>{
  registryTasks=[];registryState='loading';tasksSignature='';renderTasks();
  refreshRegistry().catch(failed);
 };
 let registryPending=null,registryFetchedAt=0,registryNextRetryAt=0,registryErrorCount=0;
 async function refreshRegistry(options={}){
  const account=$('task-account-filter').value||'discord';
  if(registryPending?.account===account)return registryPending.promise;
  const operation=(async()=>{
   try{
    const path=['discord','unassigned'].includes(account)?'task_registry':'task_registry?account_id='+encodeURIComponent(account);
    const result=await api(path,undefined,options);
    if(account!==$('task-account-filter').value)return;
    registryTasks=(Array.isArray(result.tasks)?result.tasks:[]).filter(task=>
      account==='discord'?task.execution_source==='durable_notifications':
      account==='unassigned'?task.execution_source==='legacy_process'&&!(task.account_ids||[]).length:
       (task.account_ids||[]).map(String).includes(account));
    registryFetchedAt=Date.now();registryErrorCount=0;registryNextRetryAt=0;
    registryState='ready';
   }catch(error){
    if(account===$('task-account-filter').value){
     registryState=error?.status===403?'forbidden':error?.status===401?'unauthorized':'unavailable';
     registryErrorCount=Math.min(5,registryErrorCount+1);
     registryNextRetryAt=Date.now()+Math.min(30000,4000*Math.pow(2,registryErrorCount-1));
    }
    throw error;
   }finally{tasksSignature='';renderTasks();}
  })();
  registryPending={account,promise:operation};
  try{return await operation;}finally{if(registryPending?.promise===operation)registryPending=null;}
 }
 function renderTasks(){
  const f=$('task-filter').value,target=$('task-list'),acc=$('task-account-filter').value;
  const signature=JSON.stringify([f,acc,registryTasks,registryState]);
  const scope=acc==='discord'?'Chỉ hiển thị tác vụ thông báo Discord.':acc==='unassigned'?
    'Task cũ chưa lưu ID cookie.':
    'Cookie Zalo #'+acc+' · '+(accounts.find(a=>String(a.id)===acc)?.name||'')+' · Tác vụ đa cookie không thể dừng riêng.';
  const age=registryFetchedAt?Math.floor((Date.now()-registryFetchedAt)/1000):null;
  $('task-account-status').textContent=scope+' · '+(age===null?'Chưa đồng bộ':
    registryState!=='ready'?'Không có dữ liệu mới; ảnh chụp cũ từ '+age+'s trước':
    'Cập nhật '+age+'s trước');
  $('stop-all').hidden=acc!=='discord';

  if(signature===tasksSignature)return;
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
  for(const task of registryTasks){
   if(f==='active'&&!['QUEUED','RUNNING','RETRYING','PAUSED','CANCELLING'].includes(task.status)||
     !['all','active'].includes(f)&&task.status!==f)continue;
   const timestamp=task.started||task.created;
   const timeText=timestamp?new Date(timestamp*1000).toLocaleString():'Chưa bắt đầu';
   const label=task.platform==='discord'?'Discord':'Zalo';
   const card=row(label+' · '+(task.task_type||'Tác vụ'),task.status+' · '+timeText);
   if(task.shared_execution)card.append(element('small','Tác vụ nhiều cookie · dừng sẽ ảnh hưởng các cookie khác.'));
   card.append(element('small','ID '+task.id+' · Chủ '+task.owner+' · '+(task.target||'Không có đích')));
   card.append(element('small',task.persistence==='process_local'?
     'Chỉ tồn tại trong tiến trình · có thể mất khi khởi động lại':
     'Lưu trong SQLite · độ bền phụ thuộc ổ đĩa máy chủ'));
   if(task.error)card.append(element('p',task.error));
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
   const details=()=>sheet('Chi tiết tác vụ',JSON.stringify(task,null,2));
   const info=button('Chi tiết',details);info.dataset.taskAction=task.id+':detail';actions.append(info);
   card.append(actions);target.append(card);
  }
  if(registryState==='ready'&&!target.children.length)
   target.append(element('p','Không có tác vụ trong bộ lọc này.'));
  if(focused)for(const b of target.querySelectorAll('button[data-task-action]'))
   if(b.dataset.taskAction===focused){b.focus({preventScroll:true});break;}
 }
 $('task-filter').onchange=renderTasks;
 function paintMetrics(){if(!legacyTelemetry)return;const t=legacyTelemetry;const values=[['Tài khoản',accounts.length+identities.length],['Discord',identities.length],['Zalo',accounts.length],['Đang chạy',(data.counts?.RUNNING||0)+t.running_tasks],['Đang chờ',(data.counts?.QUEUED||0)+(data.counts?.RETRYING||0)],['Hoàn tất',data.counts?.COMPLETED||0],['Thất bại',data.counts?.FAILED||0],['Worker',data.workers||0],['Kênh',data.channels?.length||0],['Thông lượng',data.completed_last_minute===undefined?'—':data.completed_last_minute+'/phút'],['API',data.api_latency_seconds==null?'Chưa đo':data.api_latency_seconds.toFixed(2)+'s'],['RAM',t.ram_mb+' MB']];$('metrics').replaceChildren(...values.map(([label,value])=>{const r=element('div',undefined,'metric');r.append(element('span',label),element('strong',value));return r;}));$('metrics').setAttribute('aria-busy','false');}
 let channelSignature='';function renderControl(next){data=next;cursor=next.cursor||cursor;paintMetrics();if(next.reset)eventRows=[];for(const e of next.events||[])if(!eventRows.some(r=>r.seq===e.seq))eventRows.push(e);eventRows=eventRows.slice(-200);renderTasks();$('health').textContent=`${next.workers} worker · ${next.channels.length} kênh · API trung bình ${next.api_latency_seconds===null?'Chưa đo':next.api_latency_seconds.toFixed(3)+'s'}`;$('event-list').replaceChildren(...eventRows.slice().reverse().map(e=>row(e.status,`${e.task} · ${new Date(e.at*1000).toLocaleTimeString()}`)));$('commands').replaceChildren(...next.commands.map(c=>{const r=element('div',undefined,'row');r.append(element('strong','/'+c.name),element('small',c.description));return r;}));const signature=JSON.stringify(next.channels);if(signature!==channelSignature){channelSignature=signature;const chosen=new Set([...$('channel-options').querySelectorAll(':checked')].map(x=>x.value));$('channels').replaceChildren(...next.channels.map(c=>row(c.name,c.id)));$('channel-options').replaceChildren(element('legend','Chọn tối đa 5 kênh'));for(const c of next.channels){const label=element('label');const box=element('input');box.type='checkbox';box.value=c.id;box.checked=chosen.has(c.id);label.append(box,document.createTextNode(c.name));$('channel-options').append(label);}}
 const bins=Array(10).fill(0),now=Date.now()/1000;for(const e of eventRows){const i=9-Math.floor((now-e.at)/60);if(i>=0&&i<10)bins[i]++;}const max=Math.max(1,...bins);$('chart').replaceChildren();bins.forEach((n,i)=>{const rect=document.createElementNS('http://www.w3.org/2000/svg','rect');for(const[k,v]of Object.entries({x:i*60+5,y:100-n/max*90,width:48,height:n/max*90,rx:5,fill:'currentColor'}))rect.setAttribute(k,v);$('chart').append(rect);});$('chart-summary').textContent=`${bins.reduce((a,b)=>a+b,0)} sự kiện trong 10 phút (tối đa 200 sự kiện đã tải).`;
 }
 async function refreshControl(options={}){renderControl(await api('control?cursor='+cursor,undefined,options));}
 let lastFullSync=0;
 async function refresh(){
  if(terminalAuth)return;
  if(refreshing)return refreshing;
  const controller=new AbortController();refreshController=controller;const options={signal:controller.signal};
  const operation=(async()=>{
   const viewer=await api('session',undefined,options);
   const [o,p]=await Promise.all([api('oauth/connections',undefined,options),api('oauth/providers',undefined,options)]);
   identities=o.connections;
   if(viewer.role==='admin'){
    const [t,a,f,c]=await Promise.all([api('telemetry',undefined,options),api('accounts',undefined,options),api('files',undefined,options),api('commands',undefined,options)]);
    accounts=a.accounts;legacyTelemetry=t;renderLaunchAccounts();renderTaskAccounts();
    $('storage').textContent='Kho: '+t.storage_id;
    $('selected-files').textContent=`Nhây: ${f.selected_nhay||'—'} · Ngôn: ${f.selected_ngon||'—'}`;
    $('file-list').replaceChildren(...['nhay','ngon'].map(target=>{
      const title=target==='nhay'?'KHO NHÂY · từng dòng (.n)':'KHO NGÔN · nguyên đoạn (.g)';
      const box=element('article',undefined,'file-category');
      box.append(element('h2',title));
      const subset=f.files.filter(file=>file.file_type===target);
      if(!subset.length)box.append(element('p','Chưa có file thuộc loại này.'));
      for(const file of subset){
       const card=row(file.filename,(file.lines||0)+' dòng · '+(file.size_kb||0)+' KB');
       if(file.filename===(target==='nhay'?f.selected_nhay:f.selected_ngon))
        card.append(element('small','✓ Đang chọn'));
       else card.append(button('Dùng cho '+(target==='nhay'?'Nhây':'Ngôn'),async()=>{
        await api('select_file',{filename:file.filename,target});await refresh();
       },'primary'));
       box.append(card);
      }
      return box;
    }));
    $('zalo-commands').replaceChildren(...c.commands.filter(x=>x.platforms.includes('zalo')).map(x=>row(x.usage,x.description)));
    $('legacy-tasks').replaceChildren(...t.tasks.map(task=>{const r=row(task.name,`${task.status} · ${task.target_label}`);if(task.can_stop)r.append(button('Dừng',async()=>{await api('stop_task',{task_id:task.id});await refresh();}));return r;}));
   }else{
    accounts=[];legacyTelemetry={running_tasks:0,ram_mb:'—'};renderTaskAccounts();
    if(!$('member-notice')){const notice=element('article','Tài khoản Zalo và tệp hiện do quản trị viên chính điều khiển. Discord và task trong trang này chỉ hiển thị dữ liệu của bạn.');notice.id='member-notice';$('zalo').replaceChildren(notice);$('oauth-form').closest('article').hidden=true;$('stop-all').hidden=true;}
   }
   await Promise.all([refreshControl(options),refreshRegistry(options)]);renderAccounts();paintMetrics();hideAuthGate();lastFullSync=Date.now();
   $('oauth-status').textContent=p.providers[0]?.configured?'OAuth đã cấu hình':'Cần quản trị viên cấu hình ứng dụng Discord';
   $('updated').textContent='Đồng bộ: '+new Date().toLocaleTimeString();
   $('error').hidden=true;if(streamConnected)setConnection('CONNECTED');
  })();
  refreshing=operation.catch(error=>{if(error?.name!=='AbortError')failed(error);}).finally(()=>{if(refreshController===controller)refreshController=null;refreshing=null;});
  return refreshing;
 }
 function form(id,path,extra={},after){$(id).onsubmit=async e=>{e.preventDefault();const form=e.currentTarget,submit=form.querySelector('button');if(submit.disabled)return;submit.disabled=true;submit.setAttribute('aria-busy','true');try{const body={...Object.fromEntries(new FormData(form)),...extra};const result=await api(path,body);after?.(result);toast('Đã lưu trên máy chủ');await refresh();}catch(e){failed(e);}finally{submit.disabled=false;submit.removeAttribute('aria-busy');}};}
 form('channel-form','channels',{},()=>$('channel-form').reset());form('zalo-form','add_cookie',{},()=>$('zalo-form').reset());form('file-form','add_file');form('oauth-form','oauth/configure',{provider:'discord'},r=>{$('oauth-config-result').textContent='Đăng ký Redirect URI: '+r.redirect_uri;$('oauth-form').elements.client_secret.value='';});
 $('upload-form').onsubmit=async e=>{e.preventDefault();const b=e.currentTarget.querySelector('button');if(b.disabled)return;b.disabled=true;try{await uploadFile(e.currentTarget);toast('Đã tải tệp lên');await refresh();}catch(error){failed(error);}finally{b.disabled=false;}};
 $('send-form').onsubmit=async e=>{e.preventDefault();const b=e.currentTarget.querySelector('button');b.disabled=true;try{await api('notifications',{channels:[...$('channel-options').querySelectorAll(':checked')].map(x=>x.value),content:e.currentTarget.elements.content.value});toast('Đã đưa vào hàng chờ');await refreshControl();}catch(e){failed(e);}finally{b.disabled=false;}};
 $('discord-login').onclick=async()=>{try{const r=await api('oauth/start',{provider:'discord'});$('oauth-link').href=r.url;$('oauth-link').hidden=false;if(tg?.openLink)tg.openLink(r.url);}catch(e){failed(e);}};
 let qrTimer;$('qr').onclick=async()=>{clearTimeout(qrTimer);try{const r=await api('start_qr',{});const poll=async()=>{try{const s=await api('qr_status/'+encodeURIComponent(r.session_id));$('qr-status').textContent=s.message||s.status;if(s.qr_base64){$('qr-image').src=s.qr_base64.startsWith('data:')?s.qr_base64:'data:image/png;base64,'+s.qr_base64;$('qr-image').hidden=false;}if(['success','expired','failed','cancelled','error','declined'].includes(s.status)){await refresh();return;}qrTimer=setTimeout(poll,document.hidden?8000:2000);}catch(e){failed(e);}};await poll();}catch(e){failed(e);}};
 $('stop-all').onclick=()=>confirmAction('Dừng tất cả tác vụ?',async()=>{await api('notifications/stop_all',{});await api('quick_action',{action:'stop_all'});});$('refresh').onclick=refresh;
 function reconnectDelay(){const exponential=Math.min(STREAM_MAX_DELAY_MS,STREAM_BASE_DELAY_MS*2**Math.min(reconnectAttempt,6));reconnectAttempt=Math.min(reconnectAttempt+1,10);return Math.round(exponential*(1-STREAM_JITTER+Math.random()*STREAM_JITTER*2));}
 function scheduleReconnect(generation,delay){if(terminalAuth||document.hidden||navigator.onLine===false||generation!==streamGeneration)return;clearTimeout(reconnectTimer);const wait=delay===undefined?reconnectDelay():delay;setConnection('RECONNECTING');reconnectTimer=setTimeout(connect,wait);}
 async function connect(){
  if(terminalAuth||document.hidden||navigator.onLine===false)return;
  clearTimeout(reconnectTimer);const generation=++streamGeneration;stream?.abort();stream=new AbortController();streamConnected=false;setConnection(reconnectAttempt?'RECONNECTING':'CONNECTING');
  let received=false;
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
     if(line){const snapshot=JSON.parse(line.slice(6));renderControl(snapshot);received=true;streamConnected=true;reconnectAttempt=0;$('error').hidden=true;setConnection('CONNECTED');}
    }
   }
   if(generation===streamGeneration){streamConnected=false;setConnection('DEGRADED');}
  }catch(e){if(e.name!=='AbortError'&&generation===streamGeneration){streamConnected=false;failed(e,'DEGRADED');}}
  finally{if(!terminalAuth&&!document.hidden&&navigator.onLine!==false&&generation===streamGeneration){if(!received)streamConnected=false;scheduleReconnect(generation);}}
 }
 function checkStreamHealth(){if(document.hidden||navigator.onLine===false||!stream||stream.signal.aborted||!lastStreamAt)return;if(Date.now()-lastStreamAt>STREAM_STALE_MS){streamConnected=false;setConnection('DEGRADED');stream.abort();}}
 document.addEventListener('visibilitychange',()=>{clearTimeout(reconnectTimer);streamGeneration++;stream?.abort();refreshController?.abort();if(document.hidden){streamConnected=false;return;}reconnectAttempt=0;lastStreamAt=0;setConnection('CONNECTING');if(!terminalAuth)refresh().finally(()=>scheduleReconnect(streamGeneration,100));});
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
 setInterval(checkStreamHealth,5000);
 async function bootstrap(){
   // Telegram's SDK loads asynchronously; defer the first authorized API request.
   if(!tg?.initData&&!launch&&$('telegram-sdk')){
     await new Promise(resolve=>{
       const script=$('telegram-sdk');let settled=false;
       const done=()=>{if(settled)return;settled=true;clearTimeout(timer);resolve();};
       const timer=setTimeout(done,2000);
       script.addEventListener('load',done,{once:true});
       script.addEventListener('error',done,{once:true});
       if(window.Telegram?.WebApp)done();
     });
     initTelegram();
   }
   if(!(tg?.initData||launch)){terminalAuth=true;showAuthGate('AUTH_REQUIRED','missing');return;}
   await refresh();
   if(!terminalAuth)scheduleReconnect(streamGeneration,100);
 }
 bootstrap();
})();