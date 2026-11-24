/**
 * AudioWorkletProcessor: Smooth 24 kHz Int16 PCM ring-buffer playback resampled to
 * browser AudioContext sampleRate, with clean 2.2x soft-limited loudness boost,
 * full multi-channel output, and instantaneous <1 ms flush on speech barge-in.
 */
class PcmPlaybackProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.sourceRate = 24000;
    this.step = this.sourceRate / sampleRate;
    this.gain = 2.2;
    this.chunks = [];
    this.chunkOffset = 0;
    this.currentSample = 0;
    this.nextSample = 0;
    this.frac = 0;
    this.hasSample = false;
    this.frameCounter = 0;

    this.port.onmessage = (event) => {
      const data = event.data;
      if (!data) return;
      if (data.type === 'flush') {
        this.chunks = [];
        this.chunkOffset = 0;
        this.hasSample = false;
        this.frac = 0;
        return;
      }
      if (data.type === 'pcm' && data.buffer) {
        const byteLen = data.buffer.byteLength - (data.buffer.byteLength % 2);
        if (byteLen <= 0) return;
        const int16 = new Int16Array(data.buffer, 0, byteLen / 2);
        const f32 = new Float32Array(int16.length);
        for (let i = 0; i < int16.length; i++) {
          f32[i] = Math.tanh((int16[i] / 32768.0) * this.gain);
        }
        this.chunks.push(f32);
      }
    };
  }

  _pullSourceSample() {
    while (this.chunks.length > 0) {
      const head = this.chunks[0];
      if (this.chunkOffset < head.length) {
        return head[this.chunkOffset++];
      }
      this.chunks.shift();
      this.chunkOffset = 0;
    }
    return null;
  }

  process(_inputs, outputs) {
    const output = outputs[0];
    if (!output || !output[0]) return true;
    const ch0 = output[0];
    const numCh = output.length;
    let sumSq = 0;

    for (let i = 0; i < ch0.length; i++) {
      if (!this.hasSample) {
        const s0 = this._pullSourceSample();
        const s1 = this._pullSourceSample();
        if (s0 === null) {
          for (let c = 0; c < numCh; c++) output[c][i] = 0;
          continue;
        }
        this.currentSample = s0;
        this.nextSample = s1 !== null ? s1 : s0;
        this.frac = 0;
        this.hasSample = true;
      }

      const sample =
        this.currentSample * (1 - this.frac) + this.nextSample * this.frac;
      for (let c = 0; c < numCh; c++) {
        output[c][i] = sample;
      }
      sumSq += sample * sample;

      this.frac += this.step;
      while (this.frac >= 1.0) {
        this.frac -= 1.0;
        this.currentSample = this.nextSample;
        const nxt = this._pullSourceSample();
        if (nxt === null) {
          this.hasSample = false;
          this.nextSample = 0;
          break;
        }
        this.nextSample = nxt;
      }
    }

    this.frameCounter++;
    if (this.frameCounter % 4 === 0) {
      const rms = Math.sqrt(sumSq / ch0.length);
      this.port.postMessage({ type: 'level', rms });
    }
    return true;
  }
}

registerProcessor('pcm-playback-processor', PcmPlaybackProcessor);
