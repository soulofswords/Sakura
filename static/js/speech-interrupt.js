export function isSpeechInterrupt(text, wakePhrase = 'hey sakura') {
    let value=String(text).toLowerCase().replace(/[,.!?।]/gu,' ').replace(/\s+/gu,' ').trim();
    const wake=String(wakePhrase).toLowerCase().trim();
    if(wake && value.startsWith(wake+' '))value=value.slice(wake.length).trim();
    return /^(?:(?:please )?(?:stop(?: speaking| talking)?|wait(?: a second| a moment)?|hold on|pause)(?: please)?|रुको|रुक जाओ|बस|ruko|ruk jao)$/u.test(value);
}

// Runs only while speech plays and the user has enabled/used microphone input.
// Non-command audio is discarded; it never becomes a new chat message.
export function createSpeechInterrupt({createMic,allowed,wakePhrase,interrupt,recognize}) {
    let mic=null,epoch=0;
    function stop(){++epoch;mic?.stop();mic=null;}
    async function start(deviceId='') {
        if(mic || !allowed())return;
        const token=++epoch;
        mic=createMic(async blob=>{
            try{
                const text=await recognize(blob);
                if(token===epoch && allowed() && isSpeechInterrupt(text,wakePhrase()))await interrupt();
            }catch(_){/* A failed command check must not interrupt playback. */}
        },()=>{}, {minimumSpeechMs:120,pauseMs:300,maximumMs:3000});
        try{await mic.start(deviceId);}catch(_){if(token===epoch)stop();}
    }
    return {start,stop};
}
