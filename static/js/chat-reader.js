// Read-only speech queue. It never generates replies or requests camera access.
export default class ChatReader {
    constructor({speak, play, stopAudio, status}) {
        Object.assign(this, {speak, play, stopAudio, status});
        this.generation = 0; this.enabled = false; this.queue = []; this.seen = new Set();
    }
    start() { this.stop(); this.enabled = true; }
    stop() {
        ++this.generation; this.enabled = false; this.queue = []; this.seen.clear();
        this.controller?.abort(); this.controller = null; this.stopAudio();
    }
    enqueue(messages) {
        if (!this.enabled) return;
        for (const message of messages) {
            if (!message.id || this.seen.has(message.id) || !message.text?.trim()) continue;
            this.seen.add(message.id);
            this.queue.push(message);
        }
        this.queue = this.queue.filter(m => Date.now() - m.timestamp < 90000).slice(-20);
        while (this.seen.size > 1000) this.seen.delete(this.seen.values().next().value);
        this.drain();
    }
    async drain() {
        const generation = this.generation;
        if (!this.enabled || this.running === generation) return;
        this.running = generation;
        const controller = new AbortController(); this.controller = controller;
        try {
            while (this.enabled && generation === this.generation && this.queue.length) {
                const message = this.queue.shift();
                if (Date.now() - message.timestamp > 90000) continue;
                const text = `${message.author || 'Viewer'} says, ${message.text}`.slice(0,600);
                this.status(text);
                try {
                    const audio = await this.speak(text, controller.signal);
                    if (!this.enabled || generation !== this.generation) return;
                    if (audio) await this.play(audio);
                } catch (error) {
                    if (generation === this.generation) this.status(`Chat Reader: ${error.message}`);
                }
            }
        } finally { if (this.running === generation) this.running = null; }
    }
}
