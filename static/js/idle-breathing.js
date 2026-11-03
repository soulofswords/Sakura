// Add a small chest rotation, never a torso scale or root translation.
export function restoreIdleBreathing(viewer) {
    for (const entry of [...(viewer._idleBreathOffsets || [])].reverse()) {
        const axis=entry.axis||'x';
        if (Math.abs(entry.bone.rotation[axis] - entry.after) < 1e-6) entry.bone.rotation[axis] = entry.before;
    }
    viewer._idleBreathOffsets = [];
}
export function applyIdleBreathing(viewer, delta, elapsed) {
    if (!viewer.model || viewer.live2d || viewer.userTracking || viewer.vtuberTrackingMode || viewer.dance?.active || viewer.chatReaderActive || viewer.chatReaderMotion
        || (viewer.activity && viewer.activity !== 'idle') || viewer.remoteCollab || viewer.companionRoom?.pose || viewer.companionRoom?.sleeping) {viewer._idlePose=null;return;}
    viewer._idleBreathTime = (viewer._idleBreathTime || 0) + Math.min(.05, Math.max(0, delta));
    const fade = Math.min(1, viewer._idleBreathTime / 1.2);
    const wave = Math.sin(elapsed * Math.PI * 2 / 3.2) * fade;
    const chest = viewer.animationBones?.chest || viewer.animationBones?.torso;
    if (!chest?.bone) return;
    const before = chest.bone.rotation.x;
    chest.bone.rotation.x += wave * .009;
    viewer._idleBreathOffsets = [{bone:chest.bone, before, after:chest.bone.rotation.x}];
    // Original small in-place fidgets. No root movement, scale, foot sliding,
    // imported animation downloads or edits to the authored hello clip.
    const poses=[
        {name:'curious tilt',bones:{head:[0,.025,.045],neck:[0,0,-.018]}},
        {name:'relaxed shoulders',bones:{chest:[-.025,0,0],leftArm:[.025,-.03,.055],rightArm:[.025,.03,-.055]}},
        {name:'thoughtful hands',bones:{head:[.025,0,-.025],leftElbow:[0,-.14,0],rightElbow:[0,.14,0],leftWrist:[.04,0,.025],rightWrist:[.04,0,-.025]}}
    ];
    const dt=Number.isFinite(delta)?Math.min(.05,Math.max(0,delta)):0;
    if(!viewer._idlePose||viewer._idlePose.root!==viewer.model)viewer._idlePose={root:viewer.model,phase:'rest',time:0,index:0,weights:{},pose:null};
    const state=viewer._idlePose;state.time+=dt;
    const durations={rest:14+(state.index%3)*3,in:.9,hold:1.6,out:1.1};
    if(state.time>=durations[state.phase]){
        state.time=0;
        if(state.phase==='rest'){state.phase='in';state.pose=poses[state.index%poses.length];}
        else if(state.phase==='in')state.phase='hold';
        else if(state.phase==='hold')state.phase='out';
        else{state.phase='rest';state.pose=null;state.weights={};state.index++;}
    }
    const ease=x=>x*x*(3-2*x);
    const weight=state.phase==='in'?ease(state.time/.9):state.phase==='hold'?1:state.phase==='out'?1-ease(state.time/1.1):0;
    if(!weight)return;
    state.weights={pose:weight};
    for(const [key,angles] of Object.entries(state.pose.bones)){
        const bone=viewer.animationBones?.[key]?.bone;if(!bone)continue;
        angles.forEach((angle,i)=>{const axis=['x','y','z'][i];if(!angle)return;const before=bone.rotation[axis];bone.rotation[axis]+=angle*weight;viewer._idleBreathOffsets.push({bone,axis,before,after:bone.rotation[axis]});});
    }
}
