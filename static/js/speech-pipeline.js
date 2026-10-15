export function splitSpeech(text) {
    const normalized = text.trim().replace(/\s+/gu, ' ');
    if (!normalized) return [];
    // Keep the opening small so local TTS can start before the entire reply
    // finishes rendering. Prefer sentence boundaries over arbitrary cuts.
    if (normalized.length <= 72) return [normalized];
    const sentences = normalized.split(/(?<=[.!?।])\s+/u).filter(Boolean);
    const chunks = [];
    for (const sentence of sentences) {
        let part = '';
        for (const word of sentence.split(/\s+/u)) {
            if (part && part.length + word.length + 1 > 72) {
                chunks.push(part);
                part = '';
            }
            part += (part ? ' ' : '') + word;
        }
        if (part) chunks.push(part);
    }
    const phrases = [];
    for (const chunk of chunks) {
        const last = phrases.length - 1;
        if (last >= 0 && phrases[last].length < 36 && phrases[last].length + chunk.length + 1 <= 72) phrases[last] += ' ' + chunk;
        else phrases.push(chunk);
    }
    return phrases;
}

// Prepare one phrase ahead while the current phrase plays, in original order.
export async function speakPhrases(text, generate, play, isCurrent) {
    const chunks = splitSpeech(text);
    const pending = new Map();
    const prepare = index => {
        if (index < chunks.length && isCurrent()) {
            pending.set(index, Promise.resolve().then(() => generate(chunks[index]))
                .then(audio => ({ audio }), error => ({ error })));
        }
    };
    prepare(0);
    for (let index = 0; index < chunks.length && isCurrent(); index++) {
        const result = await pending.get(index);
        pending.delete(index);
        if (!isCurrent()) return;
        if (result.error) throw result.error;
        // Kokoro serializes inference to avoid CPU contention with tracking.
        // Give the first phrase priority, then synthesize one ahead as it plays.
        prepare(index + 1);
        await play(result.audio, index === 0);
    }
}
