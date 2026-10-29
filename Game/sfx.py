"""
sfx.py
─────────────────────────────────────────────────────────────
Sound effects synthesised at start-up (no audio files to ship).
If no audio device is available the game simply runs silently.
"""

import array
import math
import random

import pygame


def _render(duration, fn, rate):
    n = int(duration * rate)
    return [fn(i / rate, i / n) for i in range(n)]


def _env(t, attack=0.005, release=1.0):
    """Linear attack, exponential-ish release; t is 0..1 progress."""
    a = min(1.0, t / attack) if attack > 0 else 1.0
    return a * (1 - t) ** (2.5 * release)


class SoundBank:
    def __init__(self, volume=0.6):
        self.enabled = False
        self.muted = False
        self.volume = volume
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(22050, -16, 1, 512)
            rate, _fmt, channels = pygame.mixer.get_init()
            pygame.mixer.set_num_channels(24)
            self._build(rate, channels)
            self.enabled = True
        except Exception:          # no audio device, headless, etc.
            self.enabled = False

    # ── synthesis ───────────────────────────────────────────────
    def _make(self, samples, rate, channels, gain=0.5):
        peak = max(1e-6, max(abs(s) for s in samples))
        scale = 32767 * gain / peak
        data = array.array("h")
        for s in samples:
            v = int(s * scale)
            for _ in range(channels):
                data.append(v)
        return pygame.mixer.Sound(buffer=data.tobytes())

    def _build(self, rate, ch):
        rnd = random.Random(3)
        noise = lambda: rnd.uniform(-1, 1)
        tau = math.tau

        def sweep(f0, f1, dur, wave="sine", noise_mix=0.0, release=1.0):
            phase = [0.0]

            def fn(t, p):
                f = f0 + (f1 - f0) * p
                phase[0] += tau * f / rate
                ph = phase[0]
                if wave == "sine":
                    v = math.sin(ph)
                elif wave == "square":
                    v = 1.0 if math.sin(ph) > 0 else -1.0
                elif wave == "saw":
                    v = (ph / tau) % 1.0 * 2 - 1
                else:  # triangle
                    v = 2 * abs((ph / tau) % 1.0 * 2 - 1) - 1
                v = v * (1 - noise_mix) + noise() * noise_mix
                return v * _env(p, 0.01, release)
            return _render(dur, fn, rate)

        def whoosh(dur, bright=0.15):
            lp = [0.0]

            def fn(t, p):
                lp[0] += (noise() - lp[0]) * bright
                return lp[0] * math.sin(math.pi * p) ** 1.5
            return _render(dur, fn, rate)

        def chord(freqs, dur):
            return _render(dur, lambda t, p: sum(math.sin(tau * f * t) for f in freqs) * _env(p, 0.02, 0.6), rate)

        def mixl(*parts):
            n = max(len(p) for p in parts)
            return [sum(p[i] if i < len(p) else 0 for p in parts) for i in range(n)]

        m = lambda s, g=0.5: self._make(s, rate, ch, g)
        self.sounds = {
            "shoot_1": m(mixl(sweep(420, 160, 0.16, "triangle", 0.15), sweep(2400, 600, 0.03, "square", 0.6)), 0.38),
            "shoot_2": m(sweep(1100, 420, 0.09, "square", 0.1), 0.28),
            "shoot_3": m(mixl(sweep(180, 50, 0.32, "sine", 0.45), whoosh(0.25, 0.3)), 0.5),
            "shoot_4": m(sweep(500, 1500, 0.16, "saw", 0.08), 0.3),
            "swing": m(whoosh(0.16, 0.22), 0.42),
            "hit": m(mixl(sweep(140, 45, 0.2, "sine"), sweep(800, 200, 0.06, "square", 0.8)), 0.62),
            "impact": m(sweep(600, 120, 0.07, "square", 0.7), 0.22),
            "pickup": m(mixl(sweep(523, 523, 0.08, "triangle"),
                             [0] * int(0.06 * rate) + sweep(659, 659, 0.08, "triangle"),
                             [0] * int(0.12 * rate) + sweep(988, 988, 0.14, "triangle")), 0.4),
            "dash": m(whoosh(0.2, 0.45), 0.32),
            "beep": m(sweep(660, 660, 0.14, "sine"), 0.4),
            "fight": m(mixl(chord([523, 659, 784, 1046], 0.6), sweep(200, 90, 0.4, "saw", 0.2)), 0.5),
            "ko": m(mixl(sweep(110, 28, 0.9, "sine"), whoosh(0.6, 0.12)), 0.7),
            "win": m(mixl(chord([523, 659, 784], 0.35), [0] * int(0.3 * rate) + chord([587, 740, 880, 1175], 0.8)), 0.45),
            "click": m(sweep(1500, 900, 0.035, "square", 0.2), 0.18),
        }

    # ── playback ────────────────────────────────────────────────
    def play(self, name, volume=1.0):
        if not self.enabled or self.muted:
            return
        snd = self.sounds.get(name)
        if snd is not None:
            snd.set_volume(max(0.0, min(1.0, self.volume * volume)))
            snd.play()

    def toggle_mute(self):
        self.muted = not self.muted
        return self.muted
