const {chromium}=require('playwright');
const crypto=require('crypto'),assert=require('assert/strict');
(async()=>{
 const values={auth_date:String(Math.floor(Date.now()/1000)),user:JSON.stringify({id:123})};
 const check=Object.keys(values).sort().map(k=>`${k}=${values[k]}`).join('\n');
 values.hash=crypto.createHmac('sha256',crypto.createHmac('sha256','WebAppData').update('test-token').digest()).update(check).digest('hex');
 const auth=new URLSearchParams(values).toString();
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined,args:['--no-sandbox']});
 try{
 const webAdmin=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
 await webAdmin.route('https://telegram.org/**',route=>route.abort());
 await webAdmin.goto('http://127.0.0.1:5873/login',{waitUntil:'domcontentloaded'});
 assert.equal(await webAdmin.locator('.login-flora span').count(),5);
 assert.equal(await webAdmin.locator('.login-letter').count(),13);
 const toggle=webAdmin.locator('#login-motion-toggle');
 if(await webAdmin.locator('html').getAttribute('data-motion')!=='on')await toggle.click();
 assert.equal(await webAdmin.locator('html').getAttribute('data-motion'),'on');
 assert.match(await webAdmin.locator('.login-letter').first().evaluate(el=>getComputedStyle(el).animationName),/glaze-login-letter/);
 assert.match(await webAdmin.locator('.login-flora span').first().evaluate(el=>getComputedStyle(el).animationName),/glaze-login-flower/);
 await toggle.click();
 assert.equal(await webAdmin.locator('html').getAttribute('data-motion'),'off');
 await toggle.click();
 assert.equal(await webAdmin.locator('html').getAttribute('data-motion'),'on');
 await webAdmin.locator('#login-password').fill('ci-browser-only-password');
 await Promise.all([
  webAdmin.waitForURL('http://127.0.0.1:5873/'),
  webAdmin.locator('button[type="submit"]').click()
 ]);
 await webAdmin.waitForFunction(()=>['AUTHENTICATED','CONNECTED','PARTIAL'].includes(document.querySelector('#connection')?.dataset.state));
 assert.equal(await webAdmin.locator('#auth-gate').isVisible(),false,'web admin cookie session must unlock the dashboard');
 const liveSession=await webAdmin.request.get('http://127.0.0.1:5873/api/miniapp/session');
 assert.equal(liveSession.status(),200);
 assert.equal((await liveSession.json()).auth_mode,'web_session');
 await webAdmin.locator('#bottom button[aria-label="Tác vụ"]').click();
 await webAdmin.waitForFunction(()=>document.querySelector('#tasks')?.getAttribute('aria-hidden')==='false');
 assert.equal(await webAdmin.locator('.glaze-tap-garden .glaze-tap-petal').count(),5,'tab click should produce animated flowers');
 assert.equal(await webAdmin.locator('#bottom .bottom-nav-button').count(),4);
 await webAdmin.close();
 const external=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
 await external.route('https://telegram.org/**',r=>r.abort());
 await external.goto('http://127.0.0.1:5873/miniapp',{waitUntil:'domcontentloaded'});
 await external.waitForFunction(()=>document.body.classList.contains('auth-locked'));
 assert.equal(await external.locator('#auth-gate').isVisible(),true);
 assert.equal(await external.locator('#pages').isVisible(),false);
 assert.match(await external.locator('#auth-message').innerText(),/Telegram/);
 await external.close();
 const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('https://telegram.org/**',r=>r.abort());
 const linkedAt=Date.now()/1000;
 await page.route('**/api/miniapp/credential_links',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({ok:true,links:[
  {id:8,platform:'discord',uid:'1234',name:'Discord fixture',status:'verified',kind:'bot',updated:linkedAt,checked_at:linkedAt,last_error:''},
  {id:9,platform:'facebook',uid:'5678',name:'Facebook fixture',status:'invalid',kind:'cookie',updated:linkedAt,checked_at:linkedAt,last_error:'Phiên hết hạn'}
 ]})}));
 await page.route('**/api/miniapp/credential_links/check',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({ok:true,result:{id:8,status:'verified',name:'Discord fixture'}})}));
 await page.goto('http://127.0.0.1:5873/miniapp#tgWebAppData='+encodeURIComponent(auth),{waitUntil:'domcontentloaded'});
 assert.equal(await page.locator('html').getAttribute('data-theme'),'dark','new Mini App should default to the Yanbi Aurora dark theme');
 await page.waitForFunction(()=>document.querySelector('#metrics').getAttribute('aria-busy')==='false');
 assert.equal(await page.locator('#tabs').count(),0);
 assert.equal(await page.locator('#bottom .bottom-nav-button').count(),4);
 const nav=await page.locator('#bottom .bottom-nav-button').evaluateAll(buttons=>buttons.map(button=>{
   const svg=button.querySelector('svg.bottom-icon');
   const rect=svg?.getBoundingClientRect(),buttonRect=button.getBoundingClientRect();
   return {label:button.getAttribute('aria-label'),width:rect?.width,height:rect?.height,
    centered:!!rect&&Math.abs(rect.x+rect.width/2-(buttonRect.x+buttonRect.width/2))<2,
    aria:svg?.getAttribute('aria-hidden')};
 }));
 assert.deepEqual(nav.map(i=>i.label),['Tổng quan','Tài khoản','Tác vụ','Thêm']);
 assert(nav.every(i=>i.width===24&&i.height===24&&i.centered&&i.aria==='true'),
        'all four mobile icons should be identically sized and centered');
 const viaMore=async id=>{
  await page.locator('#bottom button[aria-label="Thêm"]').click();
  await page.locator('#more-menu button[data-more="'+id+'"]').click();
 };
 await viaMore('discord');
 await page.waitForFunction(()=>document.querySelector('#discord').getAttribute('aria-hidden')==='false');
 assert.equal(await page.locator('#discord-links .credential-state').innerText(),'Phiên đã kiểm tra');
 await page.locator('#discord-links').getByRole('button',{name:'Kiểm tra lại'}).click();
 await page.locator('#bottom button[aria-label="Tài khoản"]').click();
 assert.equal(await page.locator('#facebook-links .credential-state').innerText(),'Phiên hết hạn');
 assert.equal(await page.locator('#music').count(),0);
 assert.equal(await page.locator('#home-open-music').count(),0);
 await viaMore('zalo');
 await page.waitForFunction(()=>document.querySelector('#zalo').getAttribute('aria-hidden')==='false');
 // Restore-and-protect the previously working QR contract (provider is mocked).
 const qrId='123e4567-e89b-12d3-a456-426614174000';
 const qrImage='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLQzQAAAABJRU5ErkJggg==';
 let qrStatusCalls=0;
 await page.route('**/api/miniapp/start_qr',r=>r.fulfill({status:200,contentType:'application/json',
  body:JSON.stringify({ok:true,session_id:qrId,status:'waiting_scan'})}));
 await page.route(url=>url.pathname==='/api/miniapp/qr_status/'+qrId,r=>{
  qrStatusCalls++;
  return r.fulfill({status:200,contentType:'application/json',
   body:JSON.stringify({ok:true,status:qrStatusCalls===1?'waiting_scan':'expired',
    message:qrStatusCalls===1?'Đã tạo QR':'Mã QR hết hạn',
    qr_base64:qrStatusCalls===1?'data:image/png;base64,'+qrImage:''})});
 });
 await page.locator('#qr').click();
 await page.waitForFunction(()=>{const el=document.querySelector('#qr-image');return !el.hidden&&el.naturalWidth>0;});
 await page.waitForFunction(()=>document.querySelector('#qr').disabled===false,{timeout:8000});
 assert.equal(await page.locator('#qr-image').isVisible(),false);
 assert.equal(qrStatusCalls>=2,true);
 await page.unroute('**/api/miniapp/start_qr');
 await page.unroute(url=>url.pathname==='/api/miniapp/qr_status/'+qrId);
 await viaMore('settings');
 await page.waitForFunction(()=>document.querySelector('#settings').getAttribute('aria-hidden')==='false');
 await page.waitForTimeout(350);
 assert.equal(await page.locator('#oauth-form').count(),0);
 assert.equal(await page.locator('#facebook-credential-form').count(),1);
 assert.equal(await page.locator('#discord-credential-form').count(),1);
 await page.locator('#motion').selectOption('on');
 assert.equal(await page.locator('html').getAttribute('data-motion'),'on');
 await page.locator('#bottom button[aria-label="Tài khoản"]').click();
 await page.waitForFunction(()=>document.querySelector('#accounts').getAttribute('aria-hidden')==='false');
 const animated=await page.locator('#accounts').evaluate(section=>{
  const title=section.querySelector('.glaze-kinetic-title');
  const flower=section.querySelector('.glaze-flower');
  const character=section.querySelector('.glaze-kinetic-letter');
  return {letters:title?.querySelectorAll('.glaze-kinetic-letter').length||0,
   flowers:section.querySelectorAll('.glaze-flower').length,
   titleAnimation:character?getComputedStyle(character).animationName:'',
   flowerAnimation:flower?getComputedStyle(flower).animationName:'',
   headingLabel:title?.getAttribute('aria-label')||'',
   pointerEvents:flower?getComputedStyle(flower.parentElement).pointerEvents:''};
 });
 assert(animated.letters>=5,'headings must be built from animated letters');
 assert.equal(animated.flowers,7,'seven decorative flowers should exist on each page');
 assert.match(animated.titleAnimation,/glaze-character-pop/);
 assert.match(animated.flowerAnimation,/glaze-petal-float/);
 assert.equal(animated.pointerEvents,'none');
 assert.match(animated.headingLabel,/Kết nối/);
 await viaMore('settings');
 await page.locator('#motion').selectOption('off');
 assert.equal(await page.locator('html').getAttribute('data-motion'),'off');
 await page.locator('#motion').selectOption('on');
 await page.locator('#theme').selectOption('light');
 assert.equal(await page.locator('html').getAttribute('data-theme'),'light');
 await page.locator('#text-size').selectOption('large');
 await page.locator('#accent').selectOption('mint');
 assert.equal(await page.locator('html').getAttribute('data-text-size'),'large');
 assert.equal(await page.locator('html').getAttribute('data-accent'),'mint');
 await page.locator('#bottom button[aria-label="Tổng quan"]').click();
 await viaMore('settings');
 assert.equal(await page.locator('#oauth-form').count(),0);
 await page.route('**/api/miniapp/telemetry',route=>route.fulfill({
  status:503,contentType:'application/json',
  body:JSON.stringify({ok:false,error:'simulated fixture-only telemetry failure'})
 }));
 await page.reload({waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>document.querySelector('#error').textContent.includes('Trạng thái xử lý'));
 assert.equal(await page.locator('#auth-gate').isVisible(),false);
 assert.equal(await page.locator('#pages').isVisible(),true);
 await page.unroute('**/api/miniapp/telemetry');
 await page.locator('#refresh').click();
 await page.waitForFunction(()=>document.querySelector('#error').hidden===true);
 await page.locator('#bottom button[aria-label="Tài khoản"]').click();
 await page.locator('#account-open-zalo').click();
 await page.getByText('Thêm hoặc cập nhật tệp',{exact:true}).click();
 await page.getByLabel('Tên tệp',{exact:true}).fill('v4-browser.txt');
 await page.locator('#file-form textarea').fill('Persistent browser content');
 await page.getByRole('button',{name:'Lưu và chọn tệp',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#selected-files').textContent.includes('v4-browser.txt'));
 assert.equal(await page.locator('#file-list .file-category').count(),2);
 assert.match(await page.locator('#file-list .file-category').first().innerText(),/KHO NHÂY/);
 assert.match(await page.locator('#file-list .file-category').last().innerText(),/KHO NGÔN/);
 assert.equal(await page.locator('#launch-form select[name=mode] option').count(),6);
 await page.locator('#bottom button[aria-label="Tác vụ"]').click();
 await page.getByRole('button',{name:'Dừng thông báo Discord của tôi',exact:true}).click();
 assert.equal(await page.locator('dialog').evaluate(x=>x.open),true);
 await page.keyboard.press('Escape');
 assert.equal(await page.locator('dialog').evaluate(x=>x.open),false);
 // Browser-native horizontal paging keeps vertical panel scroll independent.
 await page.evaluate(()=>document.querySelector('#pages').scrollTo({left:0,behavior:'instant'}));
 await page.waitForFunction(()=>document.querySelector('#home').getAttribute('aria-hidden')==='false');
 const input=await page.context().newCDPSession(page);
 await input.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:330,y:470}]});
 for(let x=320;x>=40;x-=20)await input.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x,y:470}]});
 await input.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
 await page.waitForFunction(()=>document.querySelector('#accounts').getAttribute('aria-hidden')==='false');
 await input.send('Input.synthesizeScrollGesture',{x:220,y:470,xDistance:0,yDistance:-250,gestureSourceType:'touch'});
 assert.equal(await page.locator('#accounts').getAttribute('aria-hidden'),'false');
 for(const width of [320,390,768,1280]){await page.setViewportSize({width,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));}
 await page.setViewportSize({width:390,height:844});
 let launchBody;
 await page.route('**/api/miniapp/accounts',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({ok:true,accounts:[{id:2,name:'Second',uid:'uid-second',platform:'zalo',enabled:true,chat_cmd_enabled:true,listener_health:{code:'running'}},{id:3,name:'Third',uid:'uid-third',platform:'zalo',enabled:true,chat_cmd_enabled:true,listener_health:{code:'listener_start_failed'}}]})}));
 await page.route('**/api/miniapp/boxes?account_id=2',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({ok:true,page:1,total:2,total_pages:2,boxes:[{id:'box-two',name:'Box Two',account_id:2,platform:'zalo'}]})}));
 await page.route('**/api/miniapp/boxes?account_id=2&page=2',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({ok:true,page:2,total:2,total_pages:2,boxes:[{id:'box-three',name:'Box Three',account_id:2,platform:'zalo'}]})}));
 await page.route('**/api/miniapp/launch',async r=>{launchBody=r.request().postDataJSON();await r.fulfill({contentType:'application/json',body:JSON.stringify({ok:true,task_id:'task-fixture',message:'Đã chạy'})});});
 await page.route('**/api/miniapp/zalo_watch',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({
  ok:true,refreshed_at:Date.now()/1000,persistence:'process_local',
  watches:[
   {box_id:'box-two',acc_id:2,box_name:'Watcher account two',timeout_sec:90,
    last_message_at:Math.floor(Date.now()/1000)-95,last_message_at_label:'09:00 GMT+7',
    inactive_since_label:'09:01 GMT+7',last_sync_at:Date.now()/1000-12,last_sync_ok:false,
    status:'silent',silence_seconds:95},
   {box_id:'box-other',acc_id:999,box_name:'Confidential account other',
    timeout_sec:90,last_message_at:Date.now()/1000-5,last_sync_at:Date.now()/1000,
    last_sync_ok:true,status:'monitoring',silence_seconds:5}
  ]
 })}));
 const v8Task={id:'legacy:task2',source_id:'task2',platform:'zalo',owner:'123',
  task_type:'treo_ngon',status:'RUNNING',started:1000,created:1000,
  account_ids:['2'],actions:[],persistence:'process_local',target:'box-two',
  execution_source:'legacy_process'};
 await page.route('**/api/miniapp/task_registry?account_id=2',r=>r.fulfill({
  contentType:'application/json',body:JSON.stringify({ok:true,account_id:'2',tasks:[v8Task]})}));

 await page.reload({waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>document.querySelector('#metrics').getAttribute('aria-busy')==='false');
 await page.locator('#bottom button[aria-label="Tài khoản"]').click();
 await page.locator('#account-open-zalo').click();
 await page.locator('#launch-account').selectOption('2');
 assert.equal(await page.locator('#launch-account option[value="2"]').count(),1);
 assert.equal(await page.locator('#launch-account option[value="3"]').count(),1);
 assert.equal(await page.locator('#task-account-filter option[value="3"]').count(),1);
 await page.getByText('Box Two · box-two').waitFor();
 await page.getByText('Watcher account two').waitFor();
 assert.match(await page.locator('#zalo-watch-status').innerText(),/API Zalo lỗi/);
 assert.doesNotMatch(await page.locator('#zalo-watch-status').innerText(),/Confidential account other/);
 const firstWatchText=await page.locator('#zalo-watch-status').innerText();
 await page.waitForTimeout(2800);
 const secondWatchText=await page.locator('#zalo-watch-status').innerText();
 assert.notEqual(firstWatchText,secondWatchText, 'watch elapsed timer should update locally');
 await page.locator('#launch-boxes input[value="box-two"]').check();
 await page.getByRole('button',{name:'Tiếp ›'}).click();
 await page.locator('#launch-boxes input[value="box-three"]').check();
 await page.getByRole('button',{name:'‹ Trước'}).click();
 assert.equal(await page.locator('#launch-boxes input[value="box-two"]').isChecked(),true);
 assert.match(await page.locator('#box-selection-count').innerText(),/2\/5/);
 await page.locator('#launch-form textarea').fill('Hello from fixture');
 await page.getByRole('button',{name:'Chạy trên box đã chọn'}).click();
 await page.waitForFunction(()=>document.querySelector('#tasks').getAttribute('aria-hidden')==='false');
 assert.equal(launchBody.account_id,'2');
 assert.deepEqual(launchBody.box_ids,['box-two','box-three']);
 assert.equal(await page.locator('#task-account-filter').inputValue(),'2');
 await page.locator('#task-list .task-card-head').getByText('Zalo · treo_ngon').waitFor();
 await page.locator('#task-list .task-technical summary').click();
 await page.getByText('ID legacy:task2', {exact:false}).waitFor();
 assert.doesNotMatch(await page.locator('#task-list').innerText(),/legacy:otheracc/);
 assert.equal(await page.locator('#stop-all').isVisible(),false);
 assert.equal(await page.locator('#stop-all-zalo').isVisible(),true);
 await page.locator('#task-search').fill('nonexistent');
 assert.match(await page.locator('#task-list').innerText(),/Không có tác vụ/);
 await page.locator('#task-search').fill('box-two');
 await page.locator('#task-list .task-technical summary').click();
 assert.match(await page.locator('#task-list').innerText(),/legacy:task2/);

 await page.screenshot({path:'/tmp/glaze-v4.png'});
 const denied=await page.request.get('http://127.0.0.1:5873/api/miniapp/control');assert.equal(denied.status(),401);
 for(const path of ['/api/discord/reg_login','/api/messenger/login','/integrations/facebook'])assert.equal((await page.request.post('http://127.0.0.1:5873'+path)).status(),410);
 assert.deepEqual(errors,[]);
 console.log('Browser: authenticated GLAZE single navigation dock, More menu, mobile scroll, account/box selection, gestures, and task UI passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
