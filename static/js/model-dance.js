import {presentHand} from './hand-presentation.js?v=palms64';
// Original procedural routines retargeted to the currently loaded 3D rig.
export default class ModelDance {
    constructor(viewer){this.viewer=viewer;this.active=null;}
    supported(){const v=this.viewer;return !!(v.model&&!v.live2d&&!v.vtuberTrackingMode&&!v.userTracking&&v.animationBones?.torso&&v.animationBones?.leftArm&&v.animationBones?.rightArm);}
    start(style='groove'){
        if(!this.supported())return false;
        this.stop(true);
        const v=this.viewer;
        if(!['groove','step','wave','twist','disco','march','victory','defeat','hands_both','hand_left','hand_right'].includes(style))return false;
        this.active={style,time:0,root:v.model,blend:0,stopping:false,
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
        const result=['victory','defeat'].includes(a.style);
        const hands=['hands_both','hand_left','hand_right'].includes(a.style);
        if(a.time>(result?3.2:hands?4:18))a.stopping=true;
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
        if(hands){
            a.root.position.copy(a.basePosition);a.root.rotation.copy(a.baseRotation);
            const left=a.style!=='hand_right',right=a.style!=='hand_left';
            pose('torso',0,0,0);pose('chest',0,0,0);pose('neck',0,0,0);pose('head',0,0,0);
            pose('leftArm',0,-.10,vrm?1.35:-.72);pose('rightArm',0,.10,vrm?-1.35:.72);
            pose('leftElbow',0,-.18,0);pose('rightElbow',0,.18,0);
            pose('leftWrist',0,0,0);pose('rightWrist',0,0,0);
            if(left)presentHand(v,'left',t);if(right)presentHand(v,'right',t);
            for(const finger of v.conversationFingers||[]){
                if((finger.side==='left'&&left)||(finger.side==='right'&&right)){
                    finger.curl*=1-t;finger.bone.rotation.copy(finger.rest);
                }
            }
            v.physics.allowIdleSleep=false;v._avoidArmClipping?.();return true;
        }
        if(result){
            // A short, restrained reaction; grounded again before fading out.
            // Root motion feeds the existing hair/clothing physics naturally.
            const win=a.style==='victory';
            const jump=win&&a.time>.35&&a.time<1.55?Math.sin(Math.PI*(a.time-.35)/1.2):0;
            const height=Math.max(.1,Math.abs((v.animationBones.head?.bone.getWorldPosition(v.model.position.clone()).y??0)-a.basePosition.y));
            a.root.position.copy(a.basePosition);a.root.position.y+=Math.max(0,jump)*height*.055*t;
            a.root.rotation.copy(a.baseRotation);
            pose('torso',win?-.025:.10,0,0);pose('chest',win?-.035:.06,0,0);
            pose('neck',win?-.035:.10,0,0);pose('head',win?-.08:.23,0,win?Math.sin(a.time*5)*.025:.025);
            const lift=win?.85:0;
            pose('leftArm',win?-.12:.04,-.10,v.vrm?1.35-lift:-.72+lift);
            pose('rightArm',win?-.12:.04,.10,v.vrm?-1.35+lift:.72-lift);
            pose('leftElbow',0,win?-.75:-.18,0);pose('rightElbow',0,win?.75:.18,0);
            pose('leftThigh',jump*.04,0,0);pose('rightThigh',jump*.04,0,0);
            pose('leftKnee',-jump*.07,0,0);pose('rightKnee',-jump*.07,0,0);
            v.physics.allowIdleSleep=false;v._avoidArmClipping?.();return true;
        }
        if(['twist','disco','march'].includes(a.style)){
            const twist=a.style==='twist',disco=a.style==='disco';
            a.root.position.copy(a.basePosition);a.root.position.y+=(disco?.035:twist?.015:.07)*bounce*t;
            a.root.rotation.copy(a.baseRotation);a.root.rotation.y+=twist?pulse*.20*t:0;
            pose('torso',0,twist?pulse*.16:0,disco?sway*.10:0);
            pose('chest',0,twist?-pulse*.20:0,0);pose('head',0,twist?-pulse*.08:0,disco?-sway*.06:0);
            const left=disco?.95+.35*pulse:twist?.30:.20+.15*pulse;
            const right=disco?.18:twist?.30:.20-.15*pulse;
            pose('leftArm',disco?-.35:-pulse*.12,-.15,vrm?1.35-left:-.72+left);
            pose('rightArm',pulse*.12,.15,vrm?-1.35+right:.72-right);
            pose('leftElbow',0,twist?-.9:-.35,0);pose('rightElbow',0,twist?.9:.35,0);
            pose('leftWrist',disco?pulse*.25:0,0,0);pose('rightWrist',0,0,0);
            const lift=a.style==='march'?.32:0;
            pose('leftThigh',Math.max(0,pulse)*lift,twist?pulse*.12:0,0);
            pose('rightThigh',Math.max(0,-pulse)*lift,twist?pulse*.12:0,0);
            pose('leftKnee',-Math.max(0,pulse)*lift*.6,0,0);pose('rightKnee',-Math.max(0,-pulse)*lift*.6,0,0);
            v.physics.allowIdleSleep=false;v._avoidArmClipping?.();return true;
        }
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
