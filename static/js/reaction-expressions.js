const moods={
    sparkle:/sparkl|twinkl|star.?eyes|キラ|きら|星目|星星眼/i,
    happy:/happy|joy|smile|cheer|笑|嬉|喜|开心|にこ/i,
    surprised:/surpris|shock|wow|驚|びっくり|惊|吃惊/i,
    concerned:/sad|worr|concern|困|悲|哀|心配|难过/i,
    amused:/amuse|laugh|grin|にや|ニヤ|笑い|大笑/i,
    focused:/focus|serious|think|真剣|考|思考|认真/i,
};
export function reactionMood(text){
    if(/(?:sorry|hurt|struggling|frustrat|unfortunately|careful|दुख|परेशान|अफसोस)/i.test(text))return 'concerned';
    if(/(?:wow|whoa|unexpected|surpris|shocking|अरे वाह|हैरान)/i.test(text))return 'surprised';
    if(/(?:haha|hilarious|funny|made me laugh|मज़ेदार|मजेदार)/i.test(text))return 'amused';
    if(/(?:watch out|strategy|focus|aim|carefully|ध्यान)/i.test(text))return 'focused';
    return 'happy';
}
export function availableReactionExpressions(viewer){
    // Never trigger costume switches, hidden accessories, eye closures or
    // phonemes merely because an imported expression has a similar filename.
    const unsafe=/outfit|cloth|dress|nude|undress|remove|toggle|accessor|stocking|weapon|hide|衣|服|脱|消|口|mouth|blink|ウィンク|まばたき|eyeclose/i;
    return (viewer.getMorphNames?.()||[]).filter(name=>typeof name==='string'&&!unsafe.test(name))
        .map(name=>({name,moods:Object.entries(moods).filter(([,pattern])=>pattern.test(name)).map(([mood])=>mood)})).filter(e=>e.moods.length);
}
// Companion tracking is an add-on: the user's face and hands drive the rig,
// but AI reactions keep running. Only pure VTuber tracking mutes them.
const aiLayersMuted = v => (v.vtuberTrackingMode || v.userTracking) && !v.companionTracking;
export default class ReactionExpressions {
    constructor(viewer){this.viewer=viewer;this.entries=[];}
    begin(text,detectedMood=null){
        const v=this.viewer;if(aiLayersMuted(v)||!v.model||v.areAiExpressionsAutomatic?.()===false)return false;
        if(v.areAiExpressionsAutomatic?.())v.clearManualExpression?.();
        this.clear();this.root=v.live2d||v.model;
        const available=availableReactionExpressions(v),mood=Object.hasOwn(moods,detectedMood)?detectedMood:reactionMood(text);
        const selected=available.find(e=>e.moods.includes(mood))
            ||(['amused','sparkle'].includes(mood)?available.find(e=>e.moods.includes('happy')):null);
        if(!selected)return false;
        this.entries=[{name:selected.name,weight:0,target:1}];
        v.reactionExpressionInfo={mood,name:selected.name,available:available.length};return true;
    }
    stop(){for(const e of this.entries)e.target=0;}
    clear(){
        if(this.root===(this.viewer.live2d||this.viewer.model))for(const e of this.entries){
            if(this.viewer.manualExpressions?.has(e.name))continue;
            if(this.viewer.live2d)this.viewer.live2d.removeExpression(e.name);else this.viewer.setMorph(e.name,0);
        }
        this.entries=[];this.viewer.reactionExpressionInfo=null;
    }
    update(delta){
        const v=this.viewer;
        if(aiLayersMuted(v)||v.areAiExpressionsAutomatic?.()===false||this.root!==(v.live2d||v.model)){this.clear();return;}
        for(const e of this.entries){
            e.weight+=(e.target-e.weight)*(1-Math.exp(-Math.min(.1,Math.max(0,delta))/.28));
            // PMX smiles can include mouth vertices. Keep audio vowels clear.
            const amount=e.weight*(v.activity==='talking'&&!v.live2d ? .6 : 1);
            if(v.manualExpressions?.has(e.name))continue;
            if(v.live2d)v.live2d.setExpression(e.name,amount);else v.setMorph(e.name,amount*.65);
        }
        if(this.entries.length&&this.entries.every(e=>e.target===0&&e.weight<.005))this.clear();
    }
}
