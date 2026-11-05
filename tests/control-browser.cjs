const {chromium}=require('playwright');
const crypto=require('crypto'),assert=require('assert/strict');
(async()=>{
 const values={auth_date:String(Math.floor(Date.now()/1000)),user:JSON.stringify({id:123})};
 const check=Object.keys(values).sort().map(k=>`${k}=${values[k]}`).join('\n');
 values.hash=crypto.createHmac('sha256',crypto.createHmac('sha256','WebAppData').update('test-token').digest()).update(check).digest('hex');
 const auth=new URLSearchParams(values).toString();
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
 try{
 const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('https://telegram.org/**',r=>r.abort());
 await page.goto('http://127.0.0.1:5873/miniapp#tgWebAppData='+encodeURIComponent(auth));
 await page.waitForFunction(()=>document.querySelector('#metrics').getAttribute('aria-busy')==='false');
 assert.equal(await page.getByRole('tab').count(),8);
 assert.equal(await page.locator('#bottom .bottom-nav-button').count(),6);
 assert.deepEqual(await page.locator('#bottom .bottom-nav-button').evaluateAll(buttons=>buttons.map(button=>({label:button.getAttribute('aria-label'),visibleText:button.innerText.trim(),iconHidden:button.querySelector('.bottom-icon')?.getAttribute('aria-hidden')}))),[
  {label:'Tổng quan',visibleText:'',iconHidden:'true'},
  {label:'Tài khoản',visibleText:'',iconHidden:'true'},
  {label:'Task',visibleText:'',iconHidden:'true'},
  {label:'Nhật ký',visibleText:'',iconHidden:'true'},
  {label:'Âm nhạc',visibleText:'',iconHidden:'true'},
  {label:'Cài đặt',visibleText:'',iconHidden:'true'}
 ]);
 await page.getByRole('tab',{name:'Âm nhạc',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#music-tracks').getAttribute('aria-busy')==='false');
 assert.equal(await page.locator('#music-tracks article').count(),10);
 assert.match(await page.locator('#music-playlist').getAttribute('href'),/^https:\/\/open\.spotify\.com\/playlist\//);
 await page.route('https://open.spotify.com/**',r=>r.abort());
 await page.getByRole('button',{name:'Mở trình phát Spotify'}).click();
 assert.match(await page.locator('#music-player iframe').getAttribute('src'),/^https:\/\/open\.spotify\.com\/embed\/playlist\//);
 await page.getByRole('tab',{name:'Cài đặt',exact:true}).click();
 await page.getByLabel('Application ID',{exact:true}).fill('12345');
 await page.locator('#theme').selectOption('light');
 assert.equal(await page.locator('html').getAttribute('data-theme'),'light');
 await page.locator('#text-size').selectOption('large');
 await page.locator('#accent').selectOption('mint');
 assert.equal(await page.locator('html').getAttribute('data-text-size'),'large');
 assert.equal(await page.locator('html').getAttribute('data-accent'),'mint');
 await page.getByRole('tab',{name:'Tổng quan',exact:true}).click();
 await page.getByRole('tab',{name:'Cài đặt',exact:true}).click();
 assert.equal(await page.getByLabel('Application ID',{exact:true}).inputValue(),'12345');
 await page.getByRole('tab',{name:'Zalo',exact:true}).click();
 await page.getByText('Thêm hoặc cập nhật tệp',{exact:true}).click();
 await page.getByLabel('Tên tệp',{exact:true}).fill('v4-browser.txt');
 await page.locator('#file-form textarea').fill('Persistent browser content');
 await page.getByRole('button',{name:'Lưu và chọn tệp',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#selected-files').textContent.includes('v4-browser.txt'));
 await page.getByRole('tab',{name:'Task',exact:true}).click();
 await page.getByRole('button',{name:'Dừng tất cả tác vụ',exact:true}).click();
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
 assert.equal(await page.getByRole('tab',{name:'Tài khoản',exact:true}).getAttribute('aria-selected'),'true');
 for(const width of [320,390,768,1280]){await page.setViewportSize({width,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));}
 await page.setViewportSize({width:390,height:844});
 let launchBody;
 await page.route('**/api/miniapp/accounts',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({ok:true,accounts:[{id:2,name:'Second',uid:'uid-second',platform:'zalo',enabled:true,chat_cmd_enabled:true}]})}));
 await page.route('**/api/miniapp/boxes?account_id=2',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({ok:true,boxes:[{id:'box-two',name:'Box Two',account_id:2,platform:'zalo'}]})}));
 await page.route('**/api/miniapp/launch',async r=>{launchBody=r.request().postDataJSON();await r.fulfill({contentType:'application/json',body:JSON.stringify({ok:true,task_id:'task-fixture',message:'Đã chạy'})});});
 await page.reload();
 await page.waitForFunction(()=>document.querySelector('#metrics').getAttribute('aria-busy')==='false');
 await page.getByRole('tab',{name:'Zalo',exact:true}).click();
 await page.locator('#launch-account').selectOption('2');
 await page.getByText('Box Two · box-two').waitFor();
 await page.locator('#launch-boxes input[value="box-two"]').check();
 await page.locator('#launch-form textarea').fill('Hello from fixture');
 await page.getByRole('button',{name:'Chạy trên box đã chọn'}).click();
 await page.waitForFunction(()=>document.querySelector('#tab-tasks').getAttribute('aria-selected')==='true');
 assert.equal(launchBody.account_id,'2');
 assert.deepEqual(launchBody.box_ids,['box-two']);
 await page.screenshot({path:'/tmp/glaze-v4.png'});
 const denied=await page.request.get('http://127.0.0.1:5873/api/miniapp/control');assert.equal(denied.status(),401);
 for(const path of ['/api/discord/reg_login','/api/messenger/login','/integrations/facebook'])assert.equal((await page.request.post('http://127.0.0.1:5873'+path)).status(),410);
 assert.deepEqual(errors,[]);
 console.log('V4 browser: 8 tabs, Spotify catalog/embed shell, account/box selection, theme, gestures, auth and retired routes passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
