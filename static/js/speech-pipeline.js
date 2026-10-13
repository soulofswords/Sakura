export function splitSpeech(text) {
    const normalized = text.trim().replace(/\s+/gu, ' ');
    if (!normalized) return [];
    // One synthesis pass gives ordinary replies continuous, natural intonation.
    if (normalized.length <= 320) return [normalized];
    const sentences = normalized.split(/(?<=[.!?।])\s+/u).filter(Boolean);
    const chunks = [];
    for (const sentence of sentences) {
        let part = '';
        for (const word of sentence.split(/\s+/u)) {
            if (part && part.length + word.length + 1 > 240) {
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
        if (last >= 0 && phrases[last].length + chunk.length + 1 <= 240) phrases[last] += ' ' + chunk;
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
    prepare(1);
    for (let index = 0; index < chunks.length && isCurrent(); index++) {
        const result = await pending.get(index);
        pending.delete(index);
        if (!isCurrent()) return;
        if (result.error) throw result.error;
        prepare(index + 2);
        await play(result.audio, index === 0);
    }
}
