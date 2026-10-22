// Semantic co-speech gesture planning: a short preparation, expressive stroke,
// then a relaxed retract. Kept separate from authored one-shot animations.
export function classifySpeechGesture(text) {
    const value=String(text||'').toLowerCase().replace(/[’]/g,"'");
    if (/\b(i'm sorry|i understand|that sounds|i'm here|take your time|no worries|lo siento|मुझे समझ|कोई बात नहीं)\b/.test(value)) return 'reassure';
    if (/\b(congratulations|that's great|amazing|awesome|fantastic|we did it|yay|incredible|शानदार|बहुत खूब)\b|!{2,}/.test(value)) return 'celebrate';
    if (/\b(for example|for instance|because|first|second|that means|here's why|the reason|उदाहरण|क्योंकि|मतलब)\b/.test(value)) return 'explain';
    if (/[?？]|\b(why|how|what|when|where|which|who|do you|did you|are you|क्या|क्यों|कैसे|कब|कहाँ)\b/.test(value)) return 'question';
    return 'casual';
}

const clamp=(value,min=0,max=1)=>Math.max(min,Math.min(max,value));
const smooth=(a,b,x)=>{const t=clamp((x-a)/(b-a));return t*t*(3-2*t);};

export function speechGestureWeights(style, phase, beat) {
    const p=clamp(phase),n=Math.max(0,Math.floor(beat)||0);
    // Leave a small beat between phrases; each stroke eases in and retracts.
    const prep=smooth(.02,.24,p),retract=1-smooth(.60,.98,p),stroke=prep*retract;
    const primary=n%2===0?'left':'right';
    let left=primary==='left'?.82:.26,right=primary==='right'?.82:.26;
    if(style==='question'){
        const open=(n%3===0?.72:.48)*stroke;
        left=Math.max(left*stroke,open);right=Math.max(right*stroke,open);
    }else if(style==='explain'){
        left=(primary==='left'?.92:.22)*stroke;right=(primary==='right'?.92:.22)*stroke;
    }else if(style==='celebrate'){
        const open=(n%3===0?.82:.52)*stroke;
        left=Math.max(left*stroke,open);right=Math.max(right*stroke,open);
    }else if(style==='reassure'){
        left*=.62*stroke;right*=.62*stroke;
    }else{
        left*=stroke;right*=stroke;
    }
    return {left:clamp(left),right:clamp(right),stroke};
}
