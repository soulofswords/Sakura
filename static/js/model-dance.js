// Original procedural routines retargeted to the currently loaded 3D rig.
export default class ModelDance {
    constructor(viewer){this.viewer=viewer;this.active=null;}
    supported(){const v=this.viewer;return !!(v.model&&!v.live2d&&!v.vtuberTrackingMode&&!v.userTracking&&v.animationBones?.torso&&v.animationBones?.leftArm&&v.animationBones?.rightArm);}
    start(style='groove'){
        if(!this.supported())return false;
        this.stop(true);
        const v=this.viewer;
        this.active={style:['groove','step','wave'].includes(style)?style:'groove',time:0,root:v.model,blend:0,stopping:false,
            basePosition:v.model.position.clone(),baseRotation:v.model.rotation.clone()};
        // Always start from a finite pose. A previous idle gesture supplies
        // the blend-in; the physics solver keeps hair/clothing inertia.
        this.active.startPose=Object.fromEntries(Object.entries(v.animationBones).map(([key,e])=>[key,e.bone.rotation.clone()]));
        return true;
    }
    stop(immediate=false){
        const a=this.active;if(!a)return;
        if(!immediate){a.stopping=true;return;}
        if(a.root===this.viewer.model){a.root.position.copy(a.basePosition);a.root.rotation.copy(a.baseRotation);
            for(const [key,e]of Object.entries(this.viewer.animationBones))if(a.startPose[key])e.bone.rotation.copy(e.rest);}
        this.active=null;
    }
    update(delta){
        const a=this.active,v=this.viewer;if(!a)return false;
        if(a.root!==v.model||!this.supported()){this.stop(true);return false;}
        const dt=Math.max(0,Math.min(.05,delta));a.time+=dt;
        if(a.time>18)a.stopping=true;
        a.blend+=(Number(!a.stopping)-a.blend)*(1-Math.exp(-dt/.35));
        if(a.stopping&&a.blend<.005){this.stop(true);return false;}
        const beat=a.time*Math.PI*2*1.6,sway=Math.sin(beat*.5),pulse=Math.sin(beat),bounce=(1-Math.cos(beat))*.5;
        const t=a.blend,vrm=!!v.vrm;
        a.root.position.copy(a.basePosition);a.root.position.y+=bounce*.12*t;
        a.root.position.x+=sway*(a.style==='step'?.45:.16)*t;
        a.root.rotation.copy(a.baseRotation);a.root.rotation.y+=sway*.06*t;
        const pose=(key,x,y,z)=>{const e=v.animationBones[key];if(!e)return;
            const origin=a.stopping?e.rest:a.startPose[key]||e.rest;
            e.bone.rotation.set(origin.x+(e.rest.x+x-origin.x)*t,origin.y+(e.rest.y+y-origin.y)*t,origin.z+(e.rest.z+z-origin.z)*t,e.rest.order);
        };
        pose('torso',pulse*.035,sway*.1,sway*.075);pose('chest',-.025, -sway*.06,-sway*.035);pose('head',bounce*.035,-sway*.08,-sway*.04);
        const wave=a.style==='wave',liftL=wave?.42+(Math.sin(beat*.5)+1)*.28:.18+(sway+1)*.14,liftR=wave?.42+(Math.sin(beat*.5+1.2)+1)*.28:.18+(1-sway)*.14;
        pose('leftArm',pulse*.10,-.10-liftL*.2,vrm?1.35-liftL:-.72+liftL);
        pose('rightArm',-pulse*.10,.10+liftR*.2,vrm?-1.35+liftR:.72-liftR);
        pose('leftElbow',0,-.24-liftL*.55,-.04);pose('rightElbow',0,.24+liftR*.55,.04);
        pose('leftWrist',pulse*.12,0,-.05+liftL*.12);pose('rightWrist',-pulse*.12,0,.05-liftR*.12);
        pose('leftThigh',Math.max(0,pulse)*.08,0,sway*.025);pose('rightThigh',Math.max(0,-pulse)*.08,0,sway*.025);
        pose('leftKnee',-.06-bounce*.06,0,0);pose('rightKnee',-.06-bounce*.06,0,0);
        v.physics.allowIdleSleep=false;v._avoidArmClipping?.();
        return true;
    }
}
