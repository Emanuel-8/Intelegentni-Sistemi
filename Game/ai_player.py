"""
ai_player.py
─────────────────────────────────────────────────────────────
Runs the trained AI inside the game, with three difficulty levels.

The PPO network trained by train_ai.py is executed with plain numpy
(weights exported by export_ai_weights.py), so players do NOT need
PyTorch or Stable-Baselines3 installed.

Difficulty is shaped around the same network:
  Easy   – slow reactions, noisy/stochastic choices, frequent mistakes
  Medium – quicker reactions, sampled (human-like) choices
  Hard   – reacts every frame, deterministic network, plus combat
           reflexes: bullet dodging, melee punishing and aimed shots

If the weights file is missing a scripted tactical bot is used, so the
game always has an opponent.
"""

import math
import os
import random

import numpy as np

from ai_helpers import get_observation, OBS_SIZE

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WEIGHTS_PATH = os.path.join(SCRIPT_DIR, "p2_ai_weights.npz")

# Must match game_env.py
MOVEMENT_DIRS = [
    ( 0,  0), ( 0, -1), ( 0,  1), (-1,  0), ( 1,  0),
    (-1, -1), ( 1, -1), (-1,  1), ( 1,  1),
]
ACTION_NVEC = [9, 2, 2, 2, 2]

DIFFICULTIES = ["Easy", "Medium", "Hard"]

DIFFICULTY_SETTINGS = {
    # think_every : frames between network decisions (reaction time)
    # epsilon     : chance a decision is replaced by a random action
    # sample      : sample from the policy instead of taking its best action
    # temperature : >1 flattens the policy → sloppier choices
    # reflex      : 0 none, 1 basic melee instincts, 2 full combat reflexes
    # reaction    : per-frame chance a reflex fires when it could
    "Easy":   dict(think_every=12, epsilon=0.30, sample=True,  temperature=1.6, reflex=1, reaction=0.20),
    "Medium": dict(think_every=4,  epsilon=0.06, sample=True,  temperature=1.0, reflex=1, reaction=0.75),
    "Hard":   dict(think_every=1,  epsilon=0.0,  sample=False, temperature=1.0, reflex=2, reaction=1.0),
}


class NeuralPolicy:
    """numpy forward pass of the SB3 MlpPolicy actor (Tanh hidden layers)."""

    def __init__(self, path=WEIGHTS_PATH):
        data = np.load(path)
        n = len([k for k in data.files if k.startswith("w")])
        self.layers = [(data[f"w{i}"].astype(np.float32), data[f"b{i}"].astype(np.float32))
                       for i in range(n)]
        if self.layers[0][0].shape[1] != OBS_SIZE:
            raise ValueError("weights do not match the observation size in ai_helpers.py")

    def act(self, obs, sample=False, temperature=1.0, rng=random):
        h = obs
        for w, b in self.layers[:-1]:
            h = np.tanh(w @ h + b)
        w, b = self.layers[-1]
        logits = w @ h + b
        action, i = [], 0
        for n in ACTION_NVEC:
            z = logits[i:i + n]
            i += n
            if sample:
                p = np.exp((z - z.max()) / temperature)
                p /= p.sum()
                action.append(_weighted_choice(p, rng))
            else:
                action.append(int(np.argmax(z)))
        return action


def _weighted_choice(p, rng):
    r = rng.random()
    acc = 0.0
    for idx, pi in enumerate(p):
        acc += pi
        if r < acc:
            return idx
    return len(p) - 1


_shared_policy = None
_policy_error = None


def load_policy():
    """Load the network once; returns None (and remembers why) if unavailable."""
    global _shared_policy, _policy_error
    if _shared_policy is None and _policy_error is None:
        try:
            _shared_policy = NeuralPolicy()
        except Exception as exc:          # missing / corrupt file → scripted bot
            _policy_error = str(exc)
    return _shared_policy


def policy_status():
    load_policy()
    if _shared_policy is not None:
        return "Neural network (PPO)"
    return "Scripted bot (no p2_ai_weights.npz)"


class AIController:
    """Produces one input tuple per frame: (dx, dy, sprint, dash, melee, shoot)."""

    def __init__(self, difficulty="Medium", seed=None):
        self.difficulty = difficulty
        self.cfg = DIFFICULTY_SETTINGS[difficulty]
        self.policy = load_policy()
        self.rng = random.Random(seed)
        self.frame = 0
        self.held = (0, 0, False)
        self.strafe = self.rng.choice((-1, 1))
        self.opp_prev = None
        self.my_prev = None
        self.stuck_frames = 0
        self.detour = 0

    # ── public ──────────────────────────────────────────────────
    def get_input(self, me, opp, arena, bullets):
        self.frame += 1
        cfg = self.cfg
        dash = melee = shoot = False
        if self.frame % cfg["think_every"] == 0 or self.frame == 1:
            if self.rng.random() < cfg["epsilon"]:
                action = [self.rng.randrange(n) for n in ACTION_NVEC]
            elif self.policy is not None:
                # the network was trained as P2: get_observation(opponent, self)
                obs = get_observation(opp, me, arena, bullets)
                action = self.policy.act(obs, cfg["sample"], cfg["temperature"], self.rng)
            else:
                action = self._scripted(me, opp, arena)
            move_idx, sprint, dash, melee, shoot = action
            dx, dy = MOVEMENT_DIRS[int(move_idx)]
            self.held = (dx, dy, bool(sprint))
        dx, dy, sprint = self.held
        inp = [dx, dy, sprint, bool(dash), bool(melee), bool(shoot)]

        # opponent velocity estimate (for anticipating their approach)
        ovx = ovy = 0.0
        if self.opp_prev is not None:
            ovx, ovy = opp.x - self.opp_prev[0], opp.y - self.opp_prev[1]
        self.opp_prev = (opp.x, opp.y)

        self._navigate(inp, me, opp, arena)
        if cfg["reflex"] and self.rng.random() < cfg["reaction"]:
            self._reflexes(inp, me, opp, arena, bullets, ovx, ovy, full=cfg["reflex"] >= 2)
        return tuple(inp)

    # ── obstacle navigation ─────────────────────────────────────
    def _navigate(self, inp, me, opp, arena):
        """The network never learned pathfinding (its training bots always came
        to it).  When it tries to approach but a wall is in the way, or it has
        been pushing against something, follow the BFS path instead."""
        moving = inp[0] or inp[1]
        if self.my_prev is not None and moving and me.dash_timer == 0:
            moved = math.hypot(me.x - self.my_prev[0], me.y - self.my_prev[1])
            self.stuck_frames = self.stuck_frames + 1 if moved < 1.0 else 0
        self.my_prev = (me.x, me.y)
        if self.stuck_frames > 12:
            self.detour = 45
            self.stuck_frames = 0

        # the network's goal: the opponent, or the weapon it is heading for
        tx, ty = opp.x, opp.y
        if arena.weapon_pickups and not me.weapon.projectile and moving:
            pu = min(arena.weapon_pickups, key=lambda w: math.hypot(w.x - me.x, w.y - me.y))
            to_pu = (pu.x - me.x) * inp[0] + (pu.y - me.y) * inp[1]
            to_op = (opp.x - me.x) * inp[0] + (opp.y - me.y) * inp[1]
            if to_pu > to_op:
                tx, ty = pu.x, pu.y
        approaching = moving and ((tx - me.x) * inp[0] + (ty - me.y) * inp[1]) > 0
        if self.detour > 0 or (approaching and not _clear_line_xy(me.x, me.y, tx, ty, arena, 28)):
            self.detour = max(0, self.detour - 1)
            step = nav_for(arena.map).direction(me.x, me.y, tx, ty)
            if step is not None:
                inp[0], inp[1] = step

    # ── fallback brain when no weights are available ────────────
    def _scripted(self, me, opp, arena):
        tx, ty = opp.x, opp.y
        dist = math.hypot(tx - me.x, ty - me.y)
        if not me.weapon.projectile and arena.weapon_pickups:
            pu = min(arena.weapon_pickups, key=lambda w: math.hypot(w.x - me.x, w.y - me.y))
            if math.hypot(pu.x - me.x, pu.y - me.y) < dist * 0.9:
                tx, ty = pu.x, pu.y
        dx, dy = tx - me.x, ty - me.y
        if me.weapon.projectile and me.ammo != 0 and (tx, ty) == (opp.x, opp.y):
            if dist < 300:      # keep shooting distance
                dx, dy = -dx, -dy
            elif dist < 480:    # strafe
                dx, dy = -dy * self.strafe, dx * self.strafe
                if self.rng.random() < 0.01:
                    self.strafe *= -1
        move_idx = _closest_dir(dx, dy)
        melee = dist < 125
        shoot = me.weapon.projectile and dist < 650
        dash = dist > 350 and self.rng.random() < 0.03
        return [move_idx, int(dist > 250), int(dash), int(melee), int(shoot)]

    # ── reflex layer on top of the network ──────────────────────
    def _reflexes(self, inp, me, opp, arena, bullets, ovx, ovy, full):
        dx, dy = opp.x - me.x, opp.y - me.y
        dist = math.hypot(dx, dy) or 1.0
        ux, uy = dx / dist, dy / dist
        can_dash = me.cooldown_timer == 0 and me.stamina >= me.dash_stamina_cost and me.dash_timer == 0
        swing_ready = me.attack_cooldown_timer == 0 and me.attack_timer == 0

        # keep the blade pointed at the opponent until the swing connects
        if me.attack_timer > 0 and not me.attack_hit_registered:
            inp[0], inp[1] = ux, uy
            return

        if full:
            # dodge the most dangerous incoming bullet
            threat = _incoming_bullet(me, bullets)
            if threat is not None:
                b, t_hit = threat
                side = 1 if (me.x - b.x) * -b.dy + (me.y - b.y) * b.dx > 0 else -1
                inp[0], inp[1] = -b.dy * side, b.dx * side
                inp[2] = True
                inp[3] = t_hit < 12 and can_dash
                return

            # sidestep a swing that is about to land
            opp_threat = (opp.attack_timer > 0 and not opp.attack_hit_registered
                          and opp.facing_dx * -ux + opp.facing_dy * -uy > 0.5)
            if opp_threat and dist < 160 and can_dash:
                inp[0], inp[1] = -ux - uy * self.strafe, -uy + ux * self.strafe
                inp[2], inp[3], inp[4] = True, True, False
                return

        # swing so the active frames meet the opponent where they will be
        lead = 4 if full else 0
        px, py = opp.x + ovx * lead - me.x, opp.y + ovy * lead - me.y
        pdist = math.hypot(px, py) or 1.0
        if swing_ready and 36 < pdist < 124 and 20 < dist < 175:
            inp[0], inp[1] = px / pdist, py / pdist
            inp[4] = True
            return

        if not full:
            return

        opp_ready = opp.attack_cooldown_timer < 6
        has_ammo = me.weapon.projectile and me.ammo != 0
        if not swing_ready and opp_ready and dist < 190:
            # our blade is recovering and theirs is not: back off
            inp[0], inp[1] = -ux, -uy
            inp[2] = True
            inp[3] = dist < 120 and can_dash
            return
        if swing_ready and not opp_ready and dist < 320:
            # they whiffed: close in to punish
            inp[0], inp[1] = ux, uy
            inp[2] = True
            return

        # aimed shots: turn to face the opponent, fire once aligned
        if has_ammo and dist < 760 and _clear_line(me, opp, arena):
            facing_dot = me.facing_dx * ux + me.facing_dy * uy
            if dist > 150:
                inp[0], inp[1] = ux, uy
                inp[2] = dist > 450
            inp[5] = facing_dot > 0.985 and me.shoot_cooldown_timer == 0


class NavGrid:
    """Coarse walkable grid of a map + BFS distance field, used to walk around obstacles."""

    CELL = 40

    def __init__(self, game_map, radius=34):
        from ai_helpers import WIDTH, HEIGHT
        c = self.CELL
        self.cols, self.rows = WIDTH // c, HEIGHT // c
        self.free = [[not game_map.collides_with_obstacle(x * c + c / 2, y * c + c / 2, radius)
                      for x in range(self.cols)] for y in range(self.rows)]
        self._target = None
        self._dist = None

    def cell(self, x, y):
        return (max(0, min(self.cols - 1, int(x // self.CELL))),
                max(0, min(self.rows - 1, int(y // self.CELL))))

    def _flood(self, target):
        INF = 1 << 30
        dist = [[INF] * self.cols for _ in range(self.rows)]
        tx, ty = target
        dist[ty][tx] = 0
        frontier = [target]
        while frontier:
            nxt = []
            for cx, cy in frontier:
                d = dist[cy][cx] + 1
                for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = cx + ox, cy + oy
                    if 0 <= nx < self.cols and 0 <= ny < self.rows and self.free[ny][nx] and dist[ny][nx] > d:
                        dist[ny][nx] = d
                        nxt.append((nx, ny))
            frontier = nxt
        return dist

    def direction(self, x, y, tx, ty):
        """Unit vector for the next step from (x, y) towards (tx, ty) around obstacles."""
        target = self.cell(tx, ty)
        if target != self._target:
            self._target, self._dist = target, self._flood(target)
        cx, cy = self.cell(x, y)
        dist = self._dist
        best, best_d = None, dist[cy][cx]
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                nx, ny = cx + ox, cy + oy
                if (ox or oy) and 0 <= nx < self.cols and 0 <= ny < self.rows and self.free[ny][nx]:
                    if ox and oy and not (self.free[cy][nx] and self.free[ny][cx]):
                        continue        # don't cut corners
                    if dist[ny][nx] < best_d:
                        best, best_d = (nx, ny), dist[ny][nx]
        if best is None:
            return None
        wx = (best[0] + 0.5) * self.CELL - x
        wy = (best[1] + 0.5) * self.CELL - y
        n = math.hypot(wx, wy) or 1.0
        return wx / n, wy / n


_nav_cache = {}


def nav_for(game_map):
    nav = _nav_cache.get(id(game_map))
    if nav is None:
        nav = _nav_cache[id(game_map)] = NavGrid(game_map)
    return nav


def _closest_dir(dx, dy):
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return 0
    best, best_dot = 0, -2.0
    length = math.hypot(dx, dy)
    for i, (mx, my) in enumerate(MOVEMENT_DIRS[1:], start=1):
        dot = (mx * dx + my * dy) / (length * math.hypot(mx, my))
        if dot > best_dot:
            best, best_dot = i, dot
    return best


def _incoming_bullet(me, bullets):
    """Returns (bullet, frames_until_hit) for the soonest bullet on a collision course."""
    best = None
    for b in bullets:
        if b.owner is me:
            continue
        rx, ry = me.x - b.x, me.y - b.y
        vx, vy = b.dx * b.speed, b.dy * b.speed
        vv = vx * vx + vy * vy
        if vv == 0:
            continue
        t = (rx * vx + ry * vy) / vv
        if t < 0 or t > 26:
            continue
        cx, cy = b.x + vx * t - me.x, b.y + vy * t - me.y
        if math.hypot(cx, cy) < me.radius + b.radius + 10:
            if best is None or t < best[1]:
                best = (b, t)
    return best


def _clear_line(me, opp, arena):
    return _clear_line_xy(me.x, me.y, opp.x, opp.y, arena, 8)


def _clear_line_xy(x0, y0, x1, y1, arena, radius):
    steps = max(4, int(math.hypot(x1 - x0, y1 - y0) // 30))
    for i in range(1, steps):
        t = i / steps
        if arena.map.collides_with_obstacle(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, radius):
            return False
    return True
