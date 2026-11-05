/* Dev Anh Khôi · v2.0 · Shared API, native scroll gestures, bounded SSE */
'use strict';
(() => {
 const $=id=>document.getElementById(id), reduced=matchMedia('(prefers-reduced-motion: reduce)');
 const launch=new URLSearchParams(location.hash.slice(1)).get('tgWebAppData')||'';
 let tg, active='home', data={}, accounts=[], identities=[], eventRows=[], cursor=0, stream, refreshing, toastTimer, streamGeneration=0, legacyTelemetry;
 const names={home:'Tổng quan',accounts:'Tài khoản',discord:'Discord',zalo:'Zalo',tasks:'Task',activity:'Nhật ký',music:'Âm nhạc',settings:'Cài đặt'};
 const keys=Object.keys(names), pages=$('pages');
 const element=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 function toast(text){$('toasts').replaceChildren(element('div',text,'toast'));clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toasts').replaceChildren(),4500);}
 function failed(error){$('error').hidden=false;$('error').textContent=error.message;$('connection').textContent='Mất kết nối · dữ liệu cũ';$('connection').classList.remove('live');}
 async function api(path,body){const h={'X-Telegram-Init-Data':tg?.initData||launch};if(body!==undefined)h['Content-Type']='application/json';const r=await fetch('/api/miniapp/'+path,{method:body===undefined?'GET':'POST',headers:h,body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(18000),cache:'no-store'});const d=await r.json();if(!r.ok||d.ok===false)throw Error(d.error||d.message||'Yêu cầu thất bại');return d;}
 async function uploadFile(form){const h={'X-Telegram-Init-Data':tg?.initData||launch};const r=await fetch('/api/miniapp/upload_file',{method:'POST',headers:h,body:new FormData(form),signal:AbortSignal.timeout(18000)});const d=await r.json();if(!r.ok||!d.ok)throw Error(d.error||'Tải tệp thất bại');return d;}
 function button(text,fn,cls){const b=element('button',text,cls);b.type='button';b.onclick=async()=>{if(b.disabled)return;b.disabled=true;b.setAttribute('aria-busy','true');try{await fn();}catch(e){failed(e);toast(e.message);}finally{b.disabled=false;b.removeAttribute('aria-busy');}};return b;}
 function theme(){const mode=$('theme').value;document.documentElement.dataset.theme=mode==='system'?(tg?.colorScheme||(matchMedia('(prefers-color-scheme:light)').matches?'light':'dark')):mode;}
 function initTelegram(){tg=window.Telegram?.WebApp;if(!tg)return;tg.ready();tg.expand();tg.onEvent?.('themeChanged',theme);tg.onEvent?.('viewportChanged',()=>{document.documentElement.style.setProperty('--safe',Math.max(tg.safeAreaInset?.bottom||0,tg.contentSafeAreaInset?.bottom||0)+'px');});tg.BackButton?.onClick(()=>{if($('sheet').open)$('sheet').close();else go('home');});theme();}
 initTelegram();$('telegram-sdk').addEventListener('load',initTelegram);$('theme').onchange=()=>{try{localStorage.setItem('glaze-theme',$('theme').value);}catch{}theme();};try{$('theme').value=localStorage.getItem('glaze-theme')||'system';}catch{}theme();
 for(const [id,allowed,fallback] of [['text-size',['normal','large'],'normal'],['accent',['blue','rose','mint'],'blue']]){
  const input=$(id),key='glaze-'+id;
  try{const saved=localStorage.getItem(key);input.value=allowed.includes(saved)?saved:fallback;}catch{input.value=fallback;}
  const apply=()=>{document.documentElement.setAttribute('data-'+id,input.value);try{localStorage.setItem(key,input.value);}catch{}};
  input.addEventListener('change',apply);apply();
 }
 function select(name){active=name;document.querySelectorAll('[data-tab]').forEach(b=>{const on=b.dataset.tab===name;b.setAttribute('aria-selected',on);b.setAttribute('aria-current',on?'page':'false');b.tabIndex=on?0:-1;});document.querySelectorAll('[data-bottom]').forEach(b=>b.setAttribute('aria-current',b.dataset.bottom===name?'page':'false'));keys.forEach(key=>$(key)?.setAttribute('aria-hidden',key===name?'false':'true'));$('tab-'+name)?.scrollIntoView({block:'nearest',inline:'nearest',behavior:reduced.matches?'auto':'smooth'});if(name==='music')loadMusic();if(name==='home')tg?.BackButton?.hide();else tg?.BackButton?.show();}
 function go(name){select(name);pages.scrollTo({left:keys.indexOf(name)*pages.clientWidth,behavior:reduced.matches?'auto':'smooth'});tg?.HapticFeedback?.selectionChanged();}
 keys.forEach((key,i)=>{const b=button(names[key],()=>go(key));b.id='tab-'+key;b.dataset.tab=key;b.role='tab';b.setAttribute('aria-controls',key);$(key).setAttribute('aria-labelledby',b.id);$(key).tabIndex=0;b.onkeydown=e=>{const d=e.key==='ArrowRight'||e.key==='ArrowDown'?1:e.key==='ArrowLeft'||e.key==='ArrowUp'?-1:0;if(d||e.key==='Home'||e.key==='End'){e.preventDefault();const next=e.key==='Home'?keys[0]:e.key==='End'?keys[keys.length-1]:keys[(i+d+keys.length)%keys.length];go(next);$('tab-'+next).focus();}};$('tabs').append(b);});
 for(const [key,icon]of [['home','⌂'],['accounts','◎'],['tasks','◷'],['activity','≋'],['music','♫'],['settings','⚙']]){const b=button('',()=>go(key)),iconNode=element('span',icon,'bottom-icon');iconNode.setAttribute('aria-hidden','true');b.append(iconNode);b.dataset.bottom=key;b.classList.add('bottom-nav-button');b.setAttribute('aria-label',names[key]);b.title=names[key];$('bottom').append(b);}
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
 function renderAccounts(){const target=$('account-list'),q=$('account-search').value.toLowerCase();target.replaceChildren();for(const a of [...accounts.map(a=>({...a,kind:'Zalo',label:a.name,state:a.listener_started?'Luồng đã khởi chạy':'Đã lưu'})),...identities.map(a=>({...a,kind:'Discord',label:a.display_name,state:a.status}))]){if(!`${a.label} ${a.id} ${a.uid||a.provider_uid}`.toLowerCase().includes(q))continue;const r=row(a.label,`${a.kind} · #${a.id} · ${a.state}`);if(a.kind==='Zalo')r.append(button(a.chat_cmd_enabled?'Tắt lệnh':'Bật lệnh',async()=>{await api('toggle_acc_cmd',{acc_id:a.id});await refresh();}));r.append(button(a.kind==='Discord'?'Ngắt liên kết':'Xóa',()=>confirmAction('Xác nhận '+a.label,()=>api(a.kind==='Discord'?'oauth/disconnect':'delete_acc',a.kind==='Discord'?{id:a.id}:{acc_id:a.id})),'danger'));target.append(r);}if(!target.children.length)target.append(element('p','Chưa có tài khoản phù hợp.'));}
 $('account-search').oninput=renderAccounts;
 let boxRequest=0;
 function renderLaunchAccounts(){
  const select=$('launch-account'),previous=select.value;
  select.replaceChildren(element('option','Chọn tài khoản'));
  select.firstChild.value='';
  for(const account of accounts.filter(a=>a.enabled)){
   const option=element('option',`${account.name} · #${account.id}`);
   option.value=String(account.id);select.append(option);
  }
  select.value=[...select.options].some(o=>o.value===previous)?previous:'';
  if(select.value!==previous)loadLaunchBoxes();
 }
 async function loadLaunchBoxes(){
  const accountId=$('launch-account').value,field=$('launch-boxes'),requestId=++boxRequest;
  field.replaceChildren(element('legend','Chọn tối đa 5 box'));
  if(!accountId){field.append(element('p','Chọn tài khoản để tải tên box.'));return;}
  const result=await api('boxes?account_id='+encodeURIComponent(accountId));
  if(requestId!==boxRequest)return;
  const boxes=result.boxes||[];
  for(const box of boxes){
   const label=element('label');const input=element('input');input.type='checkbox';input.value=box.id;
   label.append(input,document.createTextNode(`${box.name} · ${box.id}`));field.append(label);
  }
  if(!boxes.length)field.append(element('p','Chưa có tên box trong bộ nhớ. Mở nhóm trên tài khoản Zalo rồi làm mới.'));
 }
 $('launch-account').onchange=()=>loadLaunchBoxes().catch(failed);
 $('refresh-boxes').onclick=()=>loadLaunchBoxes().catch(failed);
 $('launch-form').onsubmit=async e=>{
  e.preventDefault();const form=e.currentTarget,submit=form.querySelector('button[type=submit],button.primary');
  const boxIds=[...$('launch-boxes').querySelectorAll('input:checked')].map(input=>input.value);
  if(!boxIds.length||boxIds.length>5){toast('Chọn từ 1 đến 5 box.');return;}
  submit.disabled=true;
  try{
   const body={...Object.fromEntries(new FormData(form)),box_ids:boxIds};
   const launched=await api('launch',body);
   toast(launched.message||'Đã tạo task');await refresh();go('tasks');
  }catch(error){failed(error);toast(error.message);}finally{submit.disabled=false;}
 };
 let tasksSignature='';
 function renderTasks(){
  const f=$('task-filter').value,target=$('task-list');
  const signature=JSON.stringify([f,data.tasks]);
  if(signature===tasksSignature)return;
  const focused=document.activeElement?.dataset?.taskAction;
  tasksSignature=signature;target.replaceChildren();
  for(const t of data.tasks||[]){
   if(f==='active'&&!['QUEUED','RUNNING','RETRYING','PAUSED','CANCELLING'].includes(t.status)||!['all','active'].includes(f)&&t.status!==f)continue;
   const r=row(`Discord · ${t.channel}`,`${t.status} · ${new Date(t.created*1000).toLocaleString()} · ${t.attempts} lần thử`);
   r.append(element('small',`Task ${t.id} · Chủ ${t.owner} · Bắt đầu ${t.started?new Date(t.started*1000).toLocaleTimeString():'chưa'} · Cập nhật ${new Date(t.updated*1000).toLocaleTimeString()}`));
   if(t.latency>0)r.append(element('small',`API ${t.latency.toFixed(2)} giây`));
   if(t.error)r.append(element('p',t.error));
   const actions=element('div',undefined,'actions');
   for(const [name,label,states]of [['pause','Tạm dừng',['QUEUED','RETRYING']],['resume','Tiếp tục',['PAUSED']],['stop','Dừng',['QUEUED','RETRYING','RUNNING','PAUSED']],['retry','Thử lại',['FAILED']]])if(states.includes(t.status)){
    const b=button(label,async()=>{await api('notification_control',{id:t.id,action:name});await refreshControl();});
    b.dataset.taskAction=`${t.id}:${name}`;actions.append(b);
   }
   const detail=()=>sheet('Chi tiết tác vụ',JSON.stringify(t,null,2));
   const info=button('Chi tiết / Logs',detail);info.dataset.taskAction=`${t.id}:detail`;actions.append(info);
   let press;r.onpointerdown=()=>{press=setTimeout(detail,650);};r.onpointerup=r.onpointercancel=r.onpointerleave=()=>clearTimeout(press);
   r.append(actions);target.append(r);
  }
  if(!target.children.length)target.append(element('p','Không có tác vụ trong bộ lọc này.'));
  if(focused)for(const b of target.querySelectorAll('button[data-task-action]'))if(b.dataset.taskAction===focused){b.focus({preventScroll:true});break;}
 }
 $('task-filter').onchange=renderTasks;
 function paintMetrics(){if(!legacyTelemetry)return;const t=legacyTelemetry;const values=[['Tài khoản',accounts.length+identities.length],['Discord',identities.length],['Zalo',accounts.length],['Đang chạy',(data.counts?.RUNNING||0)+t.running_tasks],['Đang chờ',(data.counts?.QUEUED||0)+(data.counts?.RETRYING||0)],['Hoàn tất',data.counts?.COMPLETED||0],['Thất bại',data.counts?.FAILED||0],['Worker',data.workers||0],['Kênh',data.channels?.length||0],['Thông lượng',data.completed_last_minute===undefined?'—':data.completed_last_minute+'/phút'],['API',data.api_latency_seconds==null?'Chưa đo':data.api_latency_seconds.toFixed(2)+'s'],['RAM',t.ram_mb+' MB']];$('metrics').replaceChildren(...values.map(([label,value])=>{const r=element('div',undefined,'metric');r.append(element('span',label),element('strong',value));return r;}));$('metrics').setAttribute('aria-busy','false');}
 let channelSignature='';function renderControl(next){data=next;cursor=next.cursor||cursor;paintMetrics();if(next.reset)eventRows=[];for(const e of next.events||[])if(!eventRows.some(r=>r.seq===e.seq))eventRows.push(e);eventRows=eventRows.slice(-200);renderTasks();$('health').textContent=`${next.workers} worker · ${next.channels.length} kênh · API trung bình ${next.api_latency_seconds===null?'Chưa đo':next.api_latency_seconds.toFixed(3)+'s'}`;$('event-list').replaceChildren(...eventRows.slice().reverse().map(e=>row(e.status,`${e.task} · ${new Date(e.at*1000).toLocaleTimeString()}`)));$('commands').replaceChildren(...next.commands.map(c=>{const r=element('div',undefined,'row');r.append(element('strong','/'+c.name),element('small',c.description));return r;}));const signature=JSON.stringify(next.channels);if(signature!==channelSignature){channelSignature=signature;const chosen=new Set([...$('channel-options').querySelectorAll(':checked')].map(x=>x.value));$('channels').replaceChildren(...next.channels.map(c=>row(c.name,c.id)));$('channel-options').replaceChildren(element('legend','Chọn tối đa 5 kênh'));for(const c of next.channels){const label=element('label');const box=element('input');box.type='checkbox';box.value=c.id;box.checked=chosen.has(c.id);label.append(box,document.createTextNode(c.name));$('channel-options').append(label);}}
 const bins=Array(10).fill(0),now=Date.now()/1000;for(const e of eventRows){const i=9-Math.floor((now-e.at)/60);if(i>=0&&i<10)bins[i]++;}const max=Math.max(1,...bins);$('chart').replaceChildren();bins.forEach((n,i)=>{const rect=document.createElementNS('http://www.w3.org/2000/svg','rect');for(const[k,v]of Object.entries({x:i*60+5,y:100-n/max*90,width:48,height:n/max*90,rx:5,fill:'currentColor'}))rect.setAttribute(k,v);$('chart').append(rect);});$('chart-summary').textContent=`${bins.reduce((a,b)=>a+b,0)} sự kiện trong 10 phút (tối đa 200 sự kiện đã tải).`;
 }
 async function refreshControl(){renderControl(await api('control?cursor='+cursor));}
 async function refresh(){
  if(refreshing)return refreshing;
  refreshing=(async()=>{
   const viewer=await api('session');
   const [o,p]=await Promise.all([api('oauth/connections'),api('oauth/providers')]);
   identities=o.connections;
   if(viewer.role==='admin'){
    const [t,a,f,c]=await Promise.all([api('telemetry'),api('accounts'),api('files'),api('commands')]);
    accounts=a.accounts;legacyTelemetry=t;renderLaunchAccounts();
    $('storage').textContent='Kho: '+t.storage_id;
    $('selected-files').textContent=`Nhây: ${f.selected_nhay||'—'} · Ngôn: ${f.selected_ngon||'—'}`;
    $('file-list').replaceChildren(...f.files.map(file=>{const r=element('div',undefined,'row');r.append(element('strong',file.filename));for(const target of ['nhay','ngon'])r.append(button(target,async()=>{await api('select_file',{filename:file.filename,target});await refresh();}));return r;}));
    $('zalo-commands').replaceChildren(...c.commands.filter(x=>x.platforms.includes('zalo')).map(x=>row(x.usage,x.description)));
    $('legacy-tasks').replaceChildren(...t.tasks.map(task=>{const r=row(task.name,`${task.status} · ${task.target_label}`);if(task.can_stop)r.append(button('Dừng',async()=>{await api('stop_task',{task_id:task.id});await refresh();}));return r;}));
   }else{
    accounts=[];legacyTelemetry={running_tasks:0,ram_mb:'—'};
    if(!$('member-notice')){const notice=element('article','Tài khoản Zalo và tệp hiện do quản trị viên chính điều khiển. Discord và task trong trang này chỉ hiển thị dữ liệu của bạn.');notice.id='member-notice';$('zalo').replaceChildren(notice);$('oauth-form').closest('article').hidden=true;$('stop-all').hidden=true;}
   }
   await refreshControl();renderAccounts();paintMetrics();
   $('oauth-status').textContent=p.providers[0]?.configured?'OAuth đã cấu hình':'Cần quản trị viên cấu hình ứng dụng Discord';
   $('updated').textContent='Đồng bộ: '+new Date().toLocaleTimeString();
   $('error').hidden=true;$('connection').textContent='Đã đồng bộ';$('connection').classList.add('live');
  })().catch(failed).finally(()=>refreshing=null);
  return refreshing;
 }
 function form(id,path,extra={},after){$(id).onsubmit=async e=>{e.preventDefault();const form=e.currentTarget,submit=form.querySelector('button');if(submit.disabled)return;submit.disabled=true;submit.setAttribute('aria-busy','true');try{const body={...Object.fromEntries(new FormData(form)),...extra};const result=await api(path,body);after?.(result);toast('Đã lưu trên máy chủ');await refresh();}catch(e){failed(e);}finally{submit.disabled=false;submit.removeAttribute('aria-busy');}};}
 form('channel-form','channels',{},()=>$('channel-form').reset());form('zalo-form','add_cookie',{},()=>$('zalo-form').reset());form('file-form','add_file');form('oauth-form','oauth/configure',{provider:'discord'},r=>{$('oauth-config-result').textContent='Đăng ký Redirect URI: '+r.redirect_uri;$('oauth-form').elements.client_secret.value='';});
 $('upload-form').onsubmit=async e=>{e.preventDefault();const b=e.currentTarget.querySelector('button');if(b.disabled)return;b.disabled=true;try{await uploadFile(e.currentTarget);toast('Đã tải tệp lên');await refresh();}catch(error){failed(error);}finally{b.disabled=false;}};
 $('send-form').onsubmit=async e=>{e.preventDefault();const b=e.currentTarget.querySelector('button');b.disabled=true;try{await api('notifications',{channels:[...$('channel-options').querySelectorAll(':checked')].map(x=>x.value),content:e.currentTarget.elements.content.value});toast('Đã đưa vào hàng chờ');await refreshControl();}catch(e){failed(e);}finally{b.disabled=false;}};
 $('discord-login').onclick=async()=>{try{const r=await api('oauth/start',{provider:'discord'});$('oauth-link').href=r.url;$('oauth-link').hidden=false;if(tg?.openLink)tg.openLink(r.url);}catch(e){failed(e);}};
 let qrTimer;$('qr').onclick=async()=>{clearTimeout(qrTimer);try{const r=await api('start_qr',{});const poll=async()=>{try{const s=await api('qr_status/'+encodeURIComponent(r.session_id));$('qr-status').textContent=s.message||s.status;if(s.qr_base64){$('qr-image').src=s.qr_base64.startsWith('data:')?s.qr_base64:'data:image/png;base64,'+s.qr_base64;$('qr-image').hidden=false;}if(['success','expired','failed','cancelled','error','declined'].includes(s.status)){await refresh();return;}qrTimer=setTimeout(poll,document.hidden?8000:2000);}catch(e){failed(e);}};await poll();}catch(e){failed(e);}};
 $('stop-all').onclick=()=>confirmAction('Dừng tất cả tác vụ?',async()=>{await api('notifications/stop_all',{});await api('quick_action',{action:'stop_all'});});$('refresh').onclick=refresh;
 let reconnectTimer;async function connect(){if(document.hidden)return;const generation=++streamGeneration;stream?.abort();stream=new AbortController();try{const r=await fetch('/api/miniapp/events?cursor='+cursor,{headers:{'X-Telegram-Init-Data':tg?.initData||launch},signal:stream.signal});if(!r.ok)throw Error('Luồng cập nhật tạm gián đoạn');const reader=r.body.getReader(),decoder=new TextDecoder();let buffer='';while(generation===streamGeneration){const{done,value}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});let at;while((at=buffer.indexOf('\n\n'))>=0){const msg=buffer.slice(0,at);buffer=buffer.slice(at+2);const line=msg.split('\n').find(x=>x.startsWith('data: '));if(line){renderControl(JSON.parse(line.slice(6)));$('connection').textContent='Đang cập nhật';$('connection').classList.add('live');}}}}catch(e){if(e.name!=='AbortError'&&generation===streamGeneration)failed(e);}finally{if(!document.hidden&&generation===streamGeneration)reconnectTimer=setTimeout(connect,3000);}}
 document.addEventListener('visibilitychange',()=>{clearTimeout(reconnectTimer);streamGeneration++;stream?.abort();if(!document.hidden){refresh();reconnectTimer=setTimeout(connect,100);}});window.addEventListener('offline',()=>failed(Error('Thiết bị đang ngoại tuyến')));setInterval(()=>{if(!document.hidden)refresh();},15000);refresh().then(connect);
})();
