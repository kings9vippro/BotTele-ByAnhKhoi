const {chromium}=require('playwright');
const crypto=require('crypto'),assert=require('assert/strict');
(async()=>{
 const values={auth_date:String(Math.floor(Date.now()/1000)),user:JSON.stringify({id:123})};
 const check=Object.keys(values).sort().map(k=>`${k}=${values[k]}`).join('\n');
 values.hash=crypto.createHmac('sha256',crypto.createHmac('sha256','WebAppData').update('test-token').digest()).update(check).digest('hex');
 const auth=new URLSearchParams(values).toString();
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
 try{
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
 await page.goto('http://127.0.0.1:5873/miniapp#tgWebAppData='+encodeURIComponent(auth),{waitUntil:'domcontentloaded'});
 assert.equal(await page.locator('html').getAttribute('data-theme'),'dark','new Mini App should default to the compact dark theme');
 await page.waitForFunction(()=>document.querySelector('#metrics').getAttribute('aria-busy')==='false');
 assert.equal(await page.locator('#tabs button').count(),8);
 assert.equal(await page.locator('#bottom .bottom-nav-button').count(),5);
 assert.deepEqual(await page.locator('#bottom .bottom-nav-button').evaluateAll(buttons=>buttons.map(button=>({label:button.getAttribute('aria-label'),visibleText:button.innerText.trim(),icon:button.querySelector('.bottom-icon')?.textContent,iconHidden:button.querySelector('.bottom-icon')?.getAttribute('aria-hidden')}))),[
  {label:'Tổng quan',visibleText:'⌂',icon:'⌂',iconHidden:'true'},
  {label:'Tài khoản',visibleText:'◎',icon:'◎',iconHidden:'true'},
  {label:'Task',visibleText:'◷',icon:'◷',iconHidden:'true'},
  {label:'Âm nhạc',visibleText:'♫',icon:'♫',iconHidden:'true'},
  {label:'Cài đặt',visibleText:'⚙',icon:'⚙',iconHidden:'true'}
 ]);
 await page.locator('#bottom button[aria-label="Âm nhạc"]').click();
 await page.waitForFunction(()=>document.querySelector('#music-tracks').getAttribute('aria-busy')==='false');
 assert.equal(await page.locator('#music-tracks article').count(),10);
 assert.match(await page.locator('#music-playlist').getAttribute('href'),/^https:\/\/open\.spotify\.com\/playlist\//);
 await page.route('https://open.spotify.com/**',r=>r.abort());
 await page.getByRole('button',{name:'Mở trình phát Spotify'}).click();
 assert.match(await page.locator('#music-player iframe').getAttribute('src'),/^https:\/\/open\.spotify\.com\/embed\/playlist\//);
 await page.locator('#bottom button[aria-label="Cài đặt"]').click();
 await page.waitForFunction(()=>document.querySelector('#settings').getAttribute('aria-hidden')==='false');
 await page.waitForTimeout(350);
 await page.getByLabel('Application ID',{exact:true}).fill('12345');
 await page.locator('#theme').selectOption('light');
 assert.equal(await page.locator('html').getAttribute('data-theme'),'light');
 await page.locator('#text-size').selectOption('large');
 await page.locator('#accent').selectOption('mint');
 assert.equal(await page.locator('html').getAttribute('data-text-size'),'large');
 assert.equal(await page.locator('html').getAttribute('data-accent'),'mint');
 await page.locator('#bottom button[aria-label="Tổng quan"]').click();
 await page.locator('#bottom button[aria-label="Cài đặt"]').click();
 assert.equal(await page.getByLabel('Application ID',{exact:true}).inputValue(),'12345');
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
 await page.locator('#bottom button[aria-label="Task"]').click();
 await page.getByRole('button',{name:'Dừng toàn bộ task Zalo (tất cả cookie)',exact:true}).click();
 assert.equal(await page.locator('dialog').evaluate(x=>x.open),true);
 await page.keyboard.press('Escape');
 assert.equal(await page.locator('dialog').evaluate(x=>x.open),false);
 // Browser-native horizontal paging keeps vertical panel scroll independent.
 await page.evaluate(()=>document.querySelector('#pages').scrollTo({left:0,behavior:'instant'}));
 await page.waitForFunction(()=>document.querySelector('#tab-home').getAttribute('aria-selected')==='true');
 const input=await page.context().newCDPSession(page);
 await input.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:330,y:470}]});
 for(let x=320;x>=40;x-=20)await input.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x,y:470}]});
 await input.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
 await page.waitForFunction(()=>document.querySelector('#tab-accounts').getAttribute('aria-selected')==='true');
 await input.send('Input.synthesizeScrollGesture',{x:220,y:470,xDistance:0,yDistance:-250,gestureSourceType:'touch'});
 assert.equal(await page.locator('#tab-accounts').getAttribute('aria-selected'),'true');
 for(const width of [320,390,768,1280]){await page.setViewportSize({width,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));}
 await page.setViewportSize({width:390,height:844});
 let launchBody;
 await page.route('**/api/miniapp/accounts',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({ok:true,accounts:[{id:2,name:'Second',uid:'uid-second',platform:'zalo',enabled:true,chat_cmd_enabled:true}]})}));
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
 await page.waitForFunction(()=>document.querySelector('#tab-tasks').getAttribute('aria-selected')==='true');
 assert.equal(launchBody.account_id,'2');
 assert.deepEqual(launchBody.box_ids,['box-two','box-three']);
 assert.equal(await page.locator('#task-account-filter').inputValue(),'2');
 await page.getByText('ID legacy:task2', {exact:false}).waitFor();
 assert.doesNotMatch(await page.locator('#task-list').innerText(),/legacy:otheracc/);

 await page.screenshot({path:'/tmp/glaze-v4.png'});
 const denied=await page.request.get('http://127.0.0.1:5873/api/miniapp/control');assert.equal(denied.status(),401);
 for(const path of ['/api/discord/reg_login','/api/messenger/login','/integrations/facebook'])assert.equal((await page.request.post('http://127.0.0.1:5873'+path)).status(),410);
 assert.deepEqual(errors,[]);
 console.log('V4 browser: 8 tabs, Spotify catalog/embed shell, account/box selection, theme, gestures, auth and retired routes passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});