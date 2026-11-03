const assert=require('node:assert/strict');
const http=require('node:http');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
 const root=path.resolve(__dirname,'..');
 const server=http.createServer((req,res)=>{
  res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:");
  if(req.url==='/probe.js'){res.setHeader('Content-Type','application/javascript');return res.end(`try {let blocked=false;try{new Function('return 1')();}catch{blocked=true;}const app=new PIXI.Application({width:32,height:32,autoStart:false});const sprite=PIXI.Sprite.from(PIXI.Texture.WHITE);sprite.width=sprite.height=32;sprite.tint=0xff0000;app.stage.addChild(sprite);app.renderer.render(app.stage);window.result={blocked,red:Array.from(app.renderer.extract.pixels(app.stage).slice(0,4))};app.destroy(true);}catch(error){window.result={error:error.message};}`);}
  if(req.url==='/'){res.setHeader('Content-Type','text/html');return res.end('<script src="/static/vendor/live2d/pixi.min.js"></script><script src="/static/vendor/live2d/unsafe-eval.min.js"></script><script src="/static/vendor/live2d/cubism4.min.js"></script><script src="/probe.js"></script>');}
  const file=path.join(root,req.url);
  if(!file.startsWith(root+path.sep)||!fs.existsSync(file)){res.statusCode=404;return res.end();}
  res.setHeader('Content-Type','application/javascript');res.end(fs.readFileSync(file));
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let browser;
 try{
  browser=await chromium.launch({headless:true,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  const page=await browser.newPage();
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  const result=await page.evaluate(()=>window.result);
  assert.equal(result.blocked,true);assert.ok(result.red[0]>200&&result.red[1]<20);console.log('Live2D Pixi renders with unsafe-eval blocked:',result);
 }finally{await browser?.close();server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
