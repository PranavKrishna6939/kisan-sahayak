/**
 * AudioWorkletProcessor: Captures mono mic audio, resamples from AudioContext sampleRate
 * to 16,000 Hz Int16 PCM, and emits 320-sample (20 ms) binary buffers + RMS level.
 *
 * Includes a speaking-state echo gate: while the agent is speaking, faint speaker bleed
 * or brief room clicks are gated to silence until sustained deliberate speech crosses
 * the barge-in threshold (~300 ms above RMS 0.032).
 */
class MicCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetRate = 16000;
    this.ratio = sampleRate / this.targetRate;
    this.inputBuffer = [];
    this.pos = 0;
    this.outChunkSize = 320; // 20 ms at 16 kHz
    this.outBuf = new Int16Array(this.outChunkSize);
    this.outIdx = 0;
    this.muted = false;
    this.botSpeaking = false;
    this.bargeInStreak = 0;
    this.bargeInHoldFrames = 0;

    this.port.onmessage = (event) => {
      if (!event.data) return;
      if (typeof event.data.muted === 'boolean') {
        this.muted = event.data.muted;
      }
      if (typeof event.data.botSpeaking === 'boolean') {
        this.botSpeaking = event.data.botSpeaking;
        if (!this.botSpeaking) {
          this.bargeInStreak = 0;
          this.bargeInHoldFrames = 0;
        }
      }
    };
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    const channel = input[0];

    if (this.muted) {
      this.port.postMessage({ type: 'level', rms: 0 });
      return true;
    }

    let sumSq = 0;
    for (let i = 0; i < channel.length; i++) {
      const s = channel[i];
      sumSq += s * s;
      this.inputBuffer.push(s);
    }
    const rms = Math.sqrt(sumSq / channel.length);

    while (this.pos + 1 < this.inputBuffer.length) {
      const idx = Math.floor(this.pos);
      const frac = this.pos - idx;
      const sample =
        this.inputBuffer[idx] * (1 - frac) + this.inputBuffer[idx + 1] * frac;
      const clamped = Math.max(-1, Math.min(1, sample));
      this.outBuf[this.outIdx++] =
        clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
      this.pos += this.ratio;

      if (this.outIdx >= this.outChunkSize) {
        let shouldGateToSilence = false;

        if (this.botSpeaking) {
          // Require sustained clear human speech (rms >= 0.032 for 15 consecutive 20ms frames = 300ms)
          // to pass through while agent is speaking, blocking speaker bleed & brief noise spikes.
          if (rms >= 0.032) {
            this.bargeInStreak++;
            if (this.bargeInStreak >= 15) {
              this.bargeInHoldFrames = 25; // keep open for 500ms once deliberate speech starts
            }
          } else {
            this.bargeInStreak = Math.max(0, this.bargeInStreak - 2);
          }

          if (this.bargeInHoldFrames > 0) {
            this.bargeInHoldFrames--;
          } else {
            shouldGateToSilence = true;
          }
        }

        const copy = shouldGateToSilence
          ? new Int16Array(this.outChunkSize)
          : new Int16Array(this.outBuf);

        this.port.postMessage(
          { type: 'audio', pcm: copy.buffer, rms: shouldGateToSilence ? 0 : rms },
          [copy.buffer]
        );
        this.outIdx = 0;
      }
    }

    const consumed = Math.floor(this.pos);
    if (consumed > 0) {
      this.inputBuffer.splice(0, consumed);
      this.pos -= consumed;
    }

    return true;
  }
}

registerProcessor('mic-capture-processor', MicCaptureProcessor);
