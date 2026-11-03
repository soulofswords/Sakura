const fs=require('fs'),path=require('path'),http=require('http'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const root=process.cwd(),server=http.createServer((req,res)=>{if(req.url==='/__room-fixture'){res.setHeader('Content-Type','text/html');res.end('<!doctype html><title>Room test</title>');return;}const file=path.resolve(root,'.'+req.url.split('?')[0]);if(!file.startsWith(root+path.sep)||!fs.existsSync(file)){res.writeHead(404);res.end();return;}res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':'text/html');res.end(fs.readFileSync(file));});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;
 try{browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1100,height:760}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/features/task-monitor',route=>route.fulfill({json:{state:'awaiting_approval',title:'Create the approved report',step:'files.write',completed_steps:2}}));
  await page.goto('http://127.0.0.1:'+server.address().port+'/__room-fixture');
  // Isolated Three.js fixture: no PC app, microphone, model provider or services.
  await page.setContent('<style>body{margin:0;background:#20252d;color:white;font:16px sans-serif}aside{position:absolute;right:0;top:0;width:290px;padding:20px;background:#20252d}canvas{display:block}</style><script type="importmap">{"imports":{"three":"/static/vendor/three/build/three.module.js"}}</script><aside data-companion-content="background"></aside>');
  const result=await page.evaluate(async()=>{
   const THREE=await import('/static/vendor/three/build/three.module.js'),{installCompanionRoom}=await import('/static/js/companion-room.js');
   window.SAKURA_EDITION='companion';const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(45,800/760,.01,100),renderer=new THREE.WebGLRenderer({antialias:true});renderer.setSize(800,760);document.body.append(renderer.domElement);
   scene.add(new THREE.HemisphereLight(0xffffff,0x666666,2));const model=new THREE.Group(),body=new THREE.Mesh(new THREE.CapsuleGeometry(.16,.65,4,8),new THREE.MeshLambertMaterial({color:0xa5c8e8}));body.position.y=.7;model.add(body);const head=new THREE.Mesh(new THREE.SphereGeometry(.17),new THREE.MeshLambertMaterial({color:0xffddca}));head.position.y=1.3;model.add(head);scene.add(model);
   const viewer={model,scene,camera,renderer,animationBones:{},controls:{target:new THREE.Vector3(0,.7,0),update(){camera.lookAt(this.target);}}};
   for(const key of ['torso','head','leftArm','rightArm','leftThigh','rightThigh']){const bone=new THREE.Bone();model.add(bone);viewer.animationBones[key]={bone};}
   camera.position.set(0,1,4);const room=installCompanionRoom(viewer);document.querySelector('#companion-room-controls input').click();if(!room.enabled)throw Error('Room toggle failed: '+document.querySelector('#companion-room-controls [role=status]').textContent);
   if(!room.act('desk'))throw Error('Desk action refused');for(let i=0;i<240;i++)room.update(1/60);renderer.render(scene,camera);
   window.testRoom=room;window.testRenderer=renderer;window.testViewer=viewer;
   return {enabled:room.enabled,children:room.room.children.length,location:model.position.toArray(),error:renderer.getContext().getError()};
  });assert(result.enabled);assert(result.children>=10);assert.equal(result.error,0);
  await page.waitForFunction(()=>window.testRoom?.monitorData?.state==='awaiting_approval');
  assert.equal(await page.evaluate(()=>testRoom.monitorData.completed_steps),2);
  assert.equal(await page.locator('[data-room-task-status]').textContent(),'Create the approved report · awaiting_approval · files.write');
  await page.evaluate(()=>{testRoom.act('bed');for(let i=0;i<1000;i++)testRoom.update(1/60);testRenderer.render(testViewer.scene,testViewer.camera);});
  const folder='audit-results/companion-room-2026-11-03';fs.mkdirSync(folder,{recursive:true});await page.screenshot({path:folder+'/room-fixture.png'});
  await page.locator('#companion-room-controls [data-room-home]').click();assert.equal(await page.evaluate(()=>testRoom.pose),null);await page.locator('#companion-room-controls input').uncheck();assert.equal(await page.evaluate(()=>testRoom.enabled),false);await page.evaluate(async()=>{
   const THREE=await import('/static/vendor/three/build/three.module.js');
   const mesh=new THREE.Group();testViewer.scene.add(mesh);
   testViewer.pmxStage={enabled:true,selected:'stage',records:[{id:'stage',path:'pmx/Stages/test/stage.pmx'}],meshes:new Map([['stage',mesh]])};
  });
  await page.selectOption('[data-room-source]','imported');
  await page.locator('#companion-room-controls input').check();
  assert.equal(await page.evaluate(()=>testRoom.enabled),true);
  assert.equal(await page.locator('[data-room-points]').isVisible(),true);
  await page.evaluate(()=>testViewer.model.position.x=.5);
  await page.locator('[data-room-mark="desk"]').click();
  assert.equal(await page.evaluate(()=>testRoom.capabilities().includes('desk')),true);
  await page.locator('[data-room-home]').click();
  assert.equal(await page.evaluate(()=>testRoom.act('desk')),true);
  await page.evaluate(()=>{for(let i=0;i<900;i++)testRoom.update(1/60);});
  assert.ok(Math.abs(await page.evaluate(()=>testViewer.model.position.x)-.5)<.001);
  await page.locator('#companion-room-controls input').uncheck();
  assert.deepEqual(errors,[]);
  console.log('PASS: actual WebGL procedural room, checkbox/action/stop/off controls; fixture screenshot saved.');
 }finally{await browser?.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
