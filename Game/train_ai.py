"""
train_ai.py
─────────────────────────────────────────────────────────────
Trains the AI to play as Player 2 using Proximal Policy
Optimisation (PPO) — one of the most popular and reliable
Reinforcement Learning algorithms.

How to run
──────────
    python train_ai.py

What happens
────────────
1. The game environment is sanity-checked.
2. Several parallel copies of the game are started (no window)
   so training is faster.
3. PPO watches the AI play, collects its reward signals, and
   slowly updates the neural network to make better decisions.
4. Checkpoints are saved every 50 000 steps to ./checkpoints/
5. The final model is saved as p2_ai.zip — this is what
   game_with_ai.py will load.

Time estimate
─────────────
• 1 000 000 steps  → ~20-40 min on a modern CPU  (basic play)
• 3 000 000 steps  → ~60-120 min                 (decent play)
• 5 000 000 steps  → ~2-3 hrs                    (strong play)

You can stop early with Ctrl+C; the last checkpoint is kept.
"""

import os
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecMonitor

from game_env import ArenaFightEnv


def _get_device():
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "auto"
    except Exception:
        return "auto"


# ── How many CPU cores to use for parallel environments ─────────
# Each environment runs an independent game simultaneously.
# More = faster training, but don't exceed your CPU count.
N_ENVS = max(1, min(8, os.cpu_count() or 1))

# ── Total number of game-frames the AI will experience ──────────
# 1,000,000 = basic play, 3,000,000 = stronger behaviour
TOTAL_TIMESTEPS = 1_000_000


def make_env():
    """Factory function required by SubprocVecEnv (parallel envs)."""
    def _init():
        return ArenaFightEnv()
    return _init


def main():
    print("=" * 62)
    print("  Arena Fighters — AI Training")
    print("=" * 62)

    # ── Step 1: verify the environment is correctly set up ───────
    print("\n[1/4]  Checking the game environment...")
    test_env = ArenaFightEnv()
    check_env(test_env, warn=True)
    test_env.close()
    print("       Environment looks good!\n")

    # ── Step 2: spin up parallel game instances ──────────────────
    print(f"[2/4]  Starting {N_ENVS} parallel game environments...")
    try:
        vec_env = SubprocVecEnv([make_env() for _ in range(N_ENVS)])
    except Exception as exc:
        print("       SubprocVecEnv failed, falling back to DummyVecEnv.")
        print(f"       Failure reason: {exc}")
        vec_env = DummyVecEnv([make_env() for _ in range(N_ENVS)])
    vec_env = VecMonitor(vec_env)   # records episode rewards / lengths
    print("       Ready.\n")

    # ── Step 3: create the PPO model ─────────────────────────────
    print("[3/4]  Building the PPO neural network...")
    model = PPO(
        policy          = "MlpPolicy",  # Multi-Layer Perceptron (fully connected)
        env             = vec_env,
        learning_rate   = 3e-4,         # how fast the network updates
        n_steps         = 2048,         # frames collected per update
        batch_size      = 64,           # samples per gradient step
        n_epochs        = 10,           # passes over the data each update
        gamma           = 0.99,         # discount factor (care about future)
        gae_lambda      = 0.95,         # advantage estimation smoothing
        clip_range      = 0.2,          # PPO clipping (keeps updates stable)
        ent_coef        = 0.01,         # entropy bonus → encourages exploration
        policy_kwargs   = dict(net_arch=[128, 128]),  # larger net for 32-float obs
        verbose         = 1,            # print progress
        tensorboard_log = "./tb_logs/", # optional: view with tensorboard
        device          = _get_device(),
    )
    print(f"       Model ready on device: {model.device}.\n")

    # ── Step 4: train! ───────────────────────────────────────────
    os.makedirs("checkpoints", exist_ok=True)
    os.makedirs("tb_logs", exist_ok=True)

    checkpoint_cb = CheckpointCallback(
        save_freq   = 50_000 // N_ENVS,   # every 50k real steps
        save_path   = "./checkpoints/",
        name_prefix = "p2_ai",
        verbose     = 1,
    )

    print(f"[4/4]  Training for {TOTAL_TIMESTEPS:,} timesteps…")
    print("       Checkpoints → ./checkpoints/")
    print("       Press Ctrl+C to stop early.\n")

    try:
        model.learn(
            total_timesteps = TOTAL_TIMESTEPS,
            callback        = checkpoint_cb,
            progress_bar    = True,
        )
    except KeyboardInterrupt:
        print("\n  Training interrupted — saving current model…")

    # ── Save the final model ─────────────────────────────────────
    model.save("p2_ai")
    vec_env.close()

    print("\n" + "=" * 62)
    print("  Done! Model saved to:  p2_ai.zip")
    print("  Run the game with:     python game_with_ai.py")
    print("=" * 62)


if __name__ == "__main__":
    main()