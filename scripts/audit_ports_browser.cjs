const { chromium } = require('playwright');
const http = require('http');
const urls = [
  'http://127.0.0.1:8504/',
  'http://127.0.0.1:8506/',
  'http://127.0.0.1:8504/src/main.jsx',
  'http://127.0.0.1:8504/api/overview',
  'http://127.0.0.1:8504/visual-editor/index.html',
  'http://127.0.0.1:8504/echarts-studio.html',
  'http://127.0.0.1:8505/visual-editor/index.html',
  'http://127.0.0.1:8510/'
];
function request(url){return new Promise(resolve=>http.get(url,res=>{let body='';res.on('data',b=>{if(body.length<300)body+=b.toString()});res.on('end',()=>resolve({url,status:res.statusCode,contentType:res.headers['content-type'],sample:body.slice(0,120)}))}).on('error',e=>resolve({url,error:e.message})))}
(async()=>{
 let failures=0;
 for(const url of urls){const r=await request(url);console.log('HTTP',JSON.stringify(r));if(r.status!==200)failures++}
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 for(const port of [8504,8506]){
  const page=await browser.newPage();
  const errors=[];
  page.on('pageerror',e=>errors.push('JS '+e.message));
  page.on('console',msg=>{if(msg.type()==='error')errors.push('CONSOLE '+msg.text())});
  await page.goto('http://127.0.0.1:'+port+'/',{waitUntil:'domcontentloaded',timeout:30000});
  await page.waitForTimeout(3500);
  console.log('BROWSER',JSON.stringify({port,title:await page.title(),root:await page.locator('#root').innerText().then(s=>s.slice(0,180)),errors}));
  if(errors.some(e=>e.includes('SyntaxError')||e.includes('Invalid or unexpected token')))failures++;
  if(!(await page.locator('#root').innerText()).trim())failures++;
  for(const path of ['/visual-editor/index.html','/echarts-studio.html']){
    const p=await browser.newPage();
    const e=[];
    p.on('pageerror',err=>e.push(err.message));
    await p.goto('http://127.0.0.1:'+port+path,{waitUntil:'domcontentloaded',timeout:30000});
    await p.waitForTimeout(1800);
    console.log('BROWSER',JSON.stringify({port,path,title:await p.title(),errors:e}));
    if(e.some(x=>x.includes('SyntaxError')||x.includes('Invalid or unexpected token')))failures++;
    await p.close();
  }
  await page.close();
 }
 await browser.close();
 console.log('AUDIT_FAILURES',failures);
 process.exitCode=failures?1:0;
})().catch(e=>{console.error(e);process.exitCode=1});
