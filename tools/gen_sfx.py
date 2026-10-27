# -*- coding: utf-8 -*-
"""程序化合成游戏音效（无外部素材依赖）。

生成 assets/ 下三个 wav（44.1kHz / 16bit / 单声道）：
- breakthrough.wav：突破成功——琶音上行 + 长尾
- victory.wav：战斗胜利——快速上行三和弦
- level_up.wav：升级/完成——明亮双音

用法：python tools/gen_sfx.py [--out assets]
"""
import argparse
import math
import os
import struct
import wave

SR = 44100


def _envelope(pos, total, attack=0.008, release=0.35):
    """简化 ADSR：短 attack + 指数衰减 release。"""
    t = pos / SR
    dur = total / SR
    if t < attack:
        return t / attack
    decay = math.exp(-(t - attack) / max(1e-6, release))
    tail = max(0.0, 1.0 - t / dur)
    return decay * tail


def _tone(freq, dur, amp=0.55, harmonic=0.28):
    samples = []
    total = int(SR * dur)
    for i in range(total):
        if freq <= 0:
            samples.append(0.0)
            continue
        t = i / SR
        env = _envelope(i, total)
        val = math.sin(2 * math.pi * freq * t)
        val += harmonic * math.sin(4 * math.pi * freq * t)      # 二次谐波增亮
        val += 0.12 * math.sin(6 * math.pi * freq * t)
        samples.append(amp * env * val)
    return samples


def _mix(tracks):
    length = max(len(t) for t in tracks)
    out = [0.0] * length
    for track in tracks:
        for i, v in enumerate(track):
            out[i] += v
    peak = max(1e-9, max(abs(v) for v in out))
    scale = 0.5 / peak      # 归一化到 -6dB 附近
    return [v * scale for v in out]


def _silence(dur):
    return [0.0] * int(SR * dur)


def _write(path, samples):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        frames = b"".join(
            struct.pack("<h", max(-32767, min(32767, int(v * 32767))))
            for v in samples
        )
        w.writeframes(frames)


def gen_breakthrough():
    """C5-E5-G5-C6 琶音，每音递进 + 极长尾。"""
    notes = [(523.25, 0.16), (659.25, 0.16), (783.99, 0.18), (1046.50, 0.55)]
    tracks = []
    offset = 0.0
    for freq, dur in notes:
        track = _silence(offset) + _tone(freq, dur, amp=0.6, harmonic=0.3)
        tracks.append(track)
        offset += dur * 0.85
    return _mix(tracks)


def gen_victory():
    """G4-C5-E5-G5 快速上行 + 结尾并奏。"""
    notes = [(392.00, 0.10), (523.25, 0.10), (659.25, 0.10), (783.99, 0.34)]
    tracks = []
    offset = 0.0
    for freq, dur in notes:
        tracks.append(_silence(offset) + _tone(freq, dur, amp=0.5))
        offset += dur * 0.9
    # 结尾和弦（C5+E5+G5 齐鸣）
    chord_at = offset - 0.2
    for freq in (523.25, 659.25, 783.99):
        tracks.append(_silence(chord_at) + _tone(freq, 0.35, amp=0.3))
    return _mix(tracks)


def gen_level_up():
    """A5→E6 双音，短促明亮。"""
    t1 = _tone(880.0, 0.10, amp=0.55, harmonic=0.35)
    t2 = _silence(0.08) + _tone(1318.51, 0.28, amp=0.5, harmonic=0.4)
    return _mix([t1, t2])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="assets")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    gens = {
        "breakthrough.wav": gen_breakthrough,
        "victory.wav": gen_victory,
        "level_up.wav": gen_level_up,
    }
    for name, fn in gens.items():
        path = os.path.join(args.out, name)
        samples = fn()
        _write(path, samples)
        size = os.path.getsize(path)
        print(f"{path}: {len(samples) / SR:.2f}s, {size} bytes")


if __name__ == "__main__":
    main()
