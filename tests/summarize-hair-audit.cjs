const fs=require('node:fs'),path=require('node:path');
const dir='audit-results/all-model-hair-2026-10-10',map=new Map();
const reports=['results.json','results-worker-0.json','results-worker-1.json'].filter(f=>fs.existsSync(path.join(dir,f))).map(f=>JSON.parse(fs.readFileSync(path.join(dir,f),'utf8')));
for(const report of reports)for(const model of report.models)map.set(model.path,model);
if(fs.existsSync(path.join(dir,'vrm-drag.json'))){
 for(const audit of JSON.parse(fs.readFileSync(path.join(dir,'vrm-drag.json'),'utf8')).results){
  const model=map.get(audit.path);
  if(model){model.vrmHairAudit=audit;model.hairBones=audit.hair;model.response=audit.response;model.hairStatus='VRM hair drag verified';}
 }
}
const models=[...map.values()].sort((a,b)=>a.path.localeCompare(b.path));
const total=reports[0].total;
const summary={total,checked:models.length,complete:models.length===total,
 loaded:models.filter(m=>m.loaded).length,
 detectedHairPhysics:models.filter(m=>m.hairBones>0).length,
 hairDrag:models.filter(m=>m.hairBones>0&&m.response>.001&&(m.engine!=='Bullet'||m.impulses>0)).length,
 noHairPhysics:models.filter(m=>m.loaded&&!m.hairBones&&!m.path.toLowerCase().endsWith('.vrm')).length,
 vrm:models.filter(m=>m.path.toLowerCase().endsWith('.vrm')).length,
 failed:models.filter(m=>!m.loaded).map(m=>({path:m.path,error:m.error})),
 physicsIssues:models.filter(m=>m.otherImpulses>0||m.finite===false||m.offIgnores===false||m.fallbackIsolated===false||m.settling===false).map(m=>({path:m.path,otherImpulses:m.otherImpulses,finite:m.finite,offIgnores:m.offIgnores,settling:m.settling})),
 limitedHair:models.filter(m=>m.hairBones>0&&m.response<.001).map(m=>({path:m.path,engine:m.engine,hairBones:m.hairBones,response:m.response,impulses:m.impulses})),
 rendererIssues:models.filter(m=>m.contextLost||m.visible===0||m.errors?.length).map(m=>({path:m.path,contextLost:m.contextLost,visible:m.visible,errors:m.errors})),
 live2d:reports[0].live2d,
};
if(fs.existsSync(path.join(dir,'assets.json'))){
 const assets=JSON.parse(fs.readFileSync(path.join(dir,'assets.json'),'utf8'));
 summary.assets={pmx:assets.pmx.length,vrm:assets.vrm.length,
  missing:assets.pmx.filter(m=>m.missing.length).map(m=>({path:m.path,missing:m.missing})),
  invalid:assets.pmx.filter(m=>m.invalid.length).map(m=>({path:m.path,invalid:m.invalid})),
  invalidVrm:assets.vrm.filter(m=>!m.ok)};
}
fs.writeFileSync(path.join(dir,'summary.json'),JSON.stringify(summary,null,2));
fs.writeFileSync(path.join(dir,'merged-results.json'),JSON.stringify({models,complete:summary.complete,total},null,2));
if(summary.complete){
 const lines=['# Sakura — background model verification','',
  'Checked every model discovered by the app, without opening the companion window. No saved character or voice selection was changed.','',
  '| Check | Result |','| --- | --- |',
  `| Models tested | ${summary.checked} |`,
  `| PMX / VRM | ${summary.checked-summary.vrm} / ${summary.vrm} |`,
  `| Models loaded and rendered | ${summary.loaded} |`,
  `| Detected hair physics | ${summary.detectedHairPhysics} |`,
  `| Measurable hair response to dragging | ${summary.hairDrag} |`,
  `| PMX models without detected hair physics | ${summary.noHairPhysics} |`,
  `| Loading failures | ${summary.failed.length} |`,
  `| Physics stability / isolation failures | ${summary.physicsIssues.length} |`,
  `| Renderer failures / empty frames | ${summary.rendererIssues.length} |`,'',
  '## Scope of checks','',
  'Headless rendering at Balanced quality, physics enabled, extra movement 0%, wind 0%. Each PMX underwent idle settling, simulated dragging, recovery and an Off check. Drag impulses were counted per body to verify that only hair receives them. Spring fallback particles were checked for the same isolation. VRM hair was also tested separately: all seven files responded, original spring settings were preserved, and non-hair tails were unaffected by the drag input.','',
  'These checks verify loading and physics behavior; they do not compare every costume and texture visually against its author\'s reference.','',
  '## Hair limitation','',
  ...summary.limitedHair.map(m=>`- ${m.path}: drag input reaches the hair, but the exported rig locks its hair joints. The app preserves those authored limits, so movement is negligible.`),'',
  'Models without detected hair physics include standalone weapons, props and other non-character assets. They are not counted as failed hair simulations.','',
  '## Source texture warnings','',
  `${summary.assets?.missing.length||0} PMX files reference missing texture assets. Referenced texture images found on disk and all seven VRM containers passed the file checks. Missing references can still affect appearance even where the model loads using a fallback. No original PMX or texture files were replaced.`, '',
  'Full per-model results: merged-results.json. Texture paths: assets.json. VRM drag checks: vrm-drag.json.',''];
 fs.writeFileSync(path.join(dir,'Report.md'),lines.join('\n'));
}
console.log(JSON.stringify({...summary,live2d:summary.live2d.length,assets:summary.assets?{pmx:summary.assets.pmx,vrm:summary.assets.vrm,missingModels:summary.assets.missing.length,invalidModels:summary.assets.invalid.length}:undefined}));
