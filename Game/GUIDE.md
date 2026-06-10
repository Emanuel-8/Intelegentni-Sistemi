# Training an AI to Play Your Game
## A Complete Beginner's Guide

---

## What is Reinforcement Learning?

Imagine teaching a dog a new trick. You don't explain it — you just give it a
treat when it does something right and ignore it (or say "no") when it does
something wrong. Over thousands of repetitions the dog figures out the trick
on its own.

**Reinforcement Learning (RL) works exactly the same way**, except the "dog"
is a neural network and the "treats" are numbers called **rewards**.

In your case:
- The AI controls **Player 2**
- Every game frame it observes the state of the game (health, positions, etc.)
- It picks an action (move, attack, dash, shoot…)
- The game responds and the AI receives a **reward** (positive = good, negative = bad)
- After millions of frames it learns which actions lead to winning

The specific algorithm we use is called **PPO** (Proximal Policy Optimisation)
— it's the most popular RL algorithm in use today, used to train bots in
OpenAI Five, AlphaStar, and many others.

---

## Files Overview

```
your-game-folder/
│
├── game.py            ← Your ORIGINAL game (don't change this)
├── game_with_ai.py    ← Modified game where P2 is the AI
│
├── ai_helpers.py      ← Converts game state → numbers the AI understands
├── game_env.py        ← The training arena (game without graphics)
├── train_ai.py        ← Run this to train the AI
│
├── p2_ai.zip          ← Created AFTER training — the AI's "brain"
└── checkpoints/       ← Intermediate saves during training
```

**You only need to run two commands** — the rest is automatic.

---

## Step 1 — Install Python Packages

Open a terminal in your game folder and run:

```bash
pip install stable-baselines3[extra] gymnasium pygame numpy
```

This installs:
- **stable-baselines3** — the RL library (contains PPO)
- **gymnasium** — the standard interface for RL environments
- **pygame** — already have it, but listed here just in case
- **numpy** — used for the observation vectors

> **On macOS/Linux** you might need `pip3` instead of `pip`.

---

## Step 2 — Train the AI

```bash
python train_ai.py
```

You will see output like this:

```
[1/4]  Checking the game environment...  ✓
[2/4]  Starting 4 parallel game environments...  Ready.
[3/4]  Building the PPO neural network...  Model ready.
[4/4]  Training for 1,000,000 timesteps…

| rollout/ep_rew_mean | -45.3 |   ← reward starts negative (AI losing)
| rollout/ep_rew_mean |  12.7 |   ← reward climbing (AI improving)
| rollout/ep_rew_mean | 185.4 |   ← AI winning most matches
```

**Training time** depends on your machine:
- 1,000,000 steps → ~20-40 minutes (basic fighting ability)
- 3,000,000 steps → ~60-120 minutes (decent, adaptive play)
- 5,000,000 steps → ~2-3 hours     (strong, strategic play)

You can **press Ctrl+C** at any time — the latest checkpoint is saved and you
can resume later or just use what you have.

When finished, a file called `p2_ai.zip` will appear in your folder. That's
the trained brain.

---

## Step 3 — Play Against the AI

```bash
python game_with_ai.py
```

Player 2 is now controlled by the AI. You play as Player 1 with WASD. The
game is otherwise identical to your original.

---

## Step 4 — Making the AI Better

If the AI doesn't feel strong enough after the default 3,000,000 steps, train
for longer. Open `train_ai.py` and change this line if you want more time:

```python
TOTAL_TIMESTEPS = 5_000_000   # longer training for stronger play
```

### What if the AI feels boring or too passive?

That's controlled by the **reward function** in `game_env.py`. The current
training setup rewards actual damage and match outcome, while discouraging
idle farming.

```python
def _compute_reward(self):
    reward = 0.0

    if p1_dmg > 0:
        reward += p1_dmg * 0.75   # reward dealing damage to the opponent

    if p2_dmg > 0:
        reward -= p2_dmg * 0.9    # penalise taking damage yourself

    if self.p1.is_dead():
        reward += 400.0           # big win bonus for killing P1

    if self.p2.is_dead():
        reward -= 400.0           # big loss penalty for dying

    reward -= 0.05                # small step penalty to discourage stalling
```

After changing rewards, delete `p2_ai.zip` and train again from scratch.

### What if you want a harder P1 training bot?

The P1 bot in `game_env.py` (the `_run_p1_bot` method) is intentionally
straightforward so the AI can learn the basics first. Once the AI is decent,
you can make P1 smarter by having it dodge or strafe, forcing the AI to
develop better tactics.

---

## How It All Works (the technical version)

### Observation (what the AI "sees")
Each frame, 22 numbers are fed into the neural network:

| # | Value |
|---|-------|
| 0-1 | P2's position on the map (normalised) |
| 2-3 | P1's position on the map |
| 4-5 | Both players' health |
| 6 | P2's stamina |
| 7-9 | Direction and distance to P1 |
| 10-11 | Which way P2 is facing |
| 12-13 | Whether P2 has a ranged weapon and how much ammo |
| 14-16 | Cooldown timers (dash, melee, shoot) |
| 17-19 | State flags (is dashing, P1 attacking, P1 dashing) |
| 20-21 | Direction to nearest weapon pickup |

### Action (what the AI can do each frame)
The AI picks 5 things simultaneously:
```
[movement direction]  0-8   (stand, up, down, left, right, diagonals)
[sprint]              0-1   (on / off)
[dash]                0-1   (trigger / don't)
[melee attack]        0-1   (trigger / don't)
[shoot]               0-1   (trigger / don't)
```

### The neural network
It's a simple 3-layer fully-connected network:
```
22 inputs → 64 neurons → 64 neurons → 5 action outputs
```
PPO adjusts the 8,000+ weights in this network to maximise cumulative reward.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'stable_baselines3'`**
→ Run `pip install stable-baselines3[extra]`

**`p2_ai.zip not found`**
→ You need to run `train_ai.py` first to generate it.

**AI just stands still / walks into walls**
→ Not enough training. Increase TOTAL_TIMESTEPS and train again.

**`SubprocVecEnv` crash on Windows**
→ Open `train_ai.py` and replace `SubprocVecEnv` with `DummyVecEnv`.
  It will be slower but works fine.

**Game runs slowly during `game_with_ai.py`**
→ The AI prediction is very fast (< 1ms). If the game is slow it's unrelated
  to the AI — check your pygame display settings.

---

## Quick Reference

| Command | What it does |
|---------|-------------|
| `python train_ai.py` | Train the AI (creates p2_ai.zip) |
| `python game_with_ai.py` | Play against the trained AI |
| `python game.py` | Original 2-human game (unchanged) |
