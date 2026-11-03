const fs=require('node:fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
async function audit(page){return page.evaluate(()=>{
 const canvas=document.createElement('canvas');canvas.width=canvas.height=1;const context=canvas.getContext('2d'),cache=new Map();
 const rgba=value=>{if(cache.has(value))return cache.get(value);context.clearRect(0,0,1,1);context.fillStyle=value;context.fillRect(0,0,1,1);const pixels=context.getImageData(0,0,1,1).data;const result=[pixels[0],pixels[1],pixels[2],pixels[3]/255];cache.set(value,result);return result;};
 const blend=(top,bottom)=>top.slice(0,3).map((v,i)=>v*top[3]+bottom[i]*(1-top[3]));
 const lum=color=>color.map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
 const ratio=(a,b)=>{const x=lum(a),y=lum(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);};
 const failures=[];let checked=0;
 for(const el of document.querySelectorAll('body *')){
  if(!el.getClientRects().length||getComputedStyle(el).visibility==='hidden'||['SCRIPT','STYLE','OPTION','SVG','PATH','CANVAS'].includes(el.tagName))continue;
  let text=[...el.childNodes].filter(x=>x.nodeType===Node.TEXT_NODE).map(x=>x.textContent.trim()).join(' ').trim();
  if(el.matches('input:not([type=checkbox]):not([type=range]):not([type=color]),textarea'))text=el.value||el.placeholder;
  if(!text||!/[\p{L}\p{N}]/u.test(text))continue;
  // Colour samples and renderer canvases are authored artwork, not UI copy.
  if(el.closest('.studio-background-swatch,.color-wheel,.color-picker-wheel,#viewer,#local-avatar'))continue;
  const chain=[];let opacity=1;for(let node=el;node;node=node.parentElement){chain.unshift(node);opacity*=Number(getComputedStyle(node).opacity);}
  let background=[255,255,255];for(const node of chain){const c=rgba(getComputedStyle(node).backgroundColor);background=blend(c,background);}
  const style=getComputedStyle(el),foreground=[...rgba(style.color)];foreground[3]*=opacity;
  const contrast=ratio(blend(foreground,background),background),size=parseFloat(style.fontSize),large=size>=24||(size>=18.66&&Number(style.fontWeight)>=700),minimum=large?3:4.5;
  checked++;if(contrast+.03<minimum)failures.push({selector:el.id?'#'+el.id:el.tagName.toLowerCase()+'.'+el.className,text:text.slice(0,90),contrast:+contrast.toFixed(2),minimum,color:style.color,background:background.map(Math.round)});
 }
 return {checked,failures};
});}
(async()=>{const browser=await chromium.launch({headless:true});try{
 const results={};
 for(const mode of ['companion','vtuber','agent','mobile']){
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const source=mode==='agent'?'static/assets/agent.html':mode==='mobile'?'android/assets/index.html':'static/index.html';
  let html=fs.readFileSync(source,'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'');
  html=html.replace(/<link[^>]*rel="stylesheet"[^>]*>/g,tag=>{const href=/href="([^"]+)"/.exec(tag)?.[1]?.split('?')[0];if(!href)return '';const path=href.startsWith('/static/')?'.'+href:'android/assets'+(href.startsWith('/')?href:'/'+href);return fs.existsSync(path)?'<style>'+fs.readFileSync(path,'utf8')+'</style>':'';});
  await page.route('http://contrast.test/**',r=>r.fulfill({contentType:'text/html',body:html}));await page.goto('http://contrast.test/');
  await page.addStyleTag({content:'*,*::before,*::after{transition:none!important;animation:none!important}'});
  await page.evaluate(mode=>{document.documentElement.classList.remove('sakura-starting');document.documentElement.dataset.uiTheme='light';window.SAKURA_EDITION=mode;document.body.className=['companion','vtuber'].includes(mode)?'native-renderer native-library'+(mode==='vtuber'?' tracking-only':''):'';},mode);
  if(['companion','vtuber'].includes(mode))await page.addScriptTag({content:fs.readFileSync('static/js/'+(mode==='companion'?'companion-studio.js':'vtuber-studio.js'),'utf8').replace('export function','function')});
  if(mode==='agent'){
   for(const script of ['agent-memory-workbench.js','agent-growth.js','agent-studio.js'])await page.addScriptTag({content:fs.readFileSync('static/js/'+script,'utf8')});
   await page.evaluate(()=>{const api=async()=>({enabled:false,journals:[]});installMemoryWorkbench({api,perform:fn=>fn()});installAgentGrowth({api,perform:fn=>fn(),token:'synthetic'});installAgentStudio();});
  }
  await page.evaluate(mode=>{
   for(const el of document.querySelectorAll('.modal-backdrop,.tab-content,[data-model-panel],section,details,main,nav,aside,.hidden,[hidden]')){el.classList.remove('hidden');el.hidden=false;el.style.setProperty('display','block','important');if(el.tagName==='DETAILS')el.open=true;}
   for(const el of document.querySelectorAll('dialog'))el.show();
  },mode);
  results[mode]=await audit(page);
  // Keep the dark palette stable; light-mode rules must stop matching on switch.
  const darkToken=mode==='agent'?'--ag-accent':mode==='mobile'?'--mobile-accent':'--ui-accent';
  await page.evaluate(()=>document.documentElement.dataset.uiTheme='dark');
  const darkAccent=await page.evaluate(token=>getComputedStyle(document.documentElement).getPropertyValue(token).trim(),darkToken);
  assert.equal(darkAccent,'#91ceff',mode+' retains the existing dark theme accent');await page.close();
 }
 fs.mkdirSync('audit-results/ui-button-routing-2026-11-03',{recursive:true});fs.writeFileSync('audit-results/ui-button-routing-2026-11-03/light-text-contrast.json',JSON.stringify(results,null,2));
 for(const [mode,result]of Object.entries(results)){console.log(mode+': '+result.checked+' text elements; '+result.failures.length+' low-contrast elements');if(result.failures.length)console.log(JSON.stringify(result.failures.slice(0,20),null,2));}
 assert.equal(Object.values(results).reduce((sum,row)=>sum+row.failures.length,0),0,'Visible light-theme text needs at least 4.5:1 contrast (large text 3:1).');
}finally{await browser.close();}})().catch(error=>{console.error(error);process.exitCode=1;});
