"""
PPO Optimization Agent — Training Pipeline
Blockchain-Enabled Digital Twin Framework — Phase 4

Trains a Stable-Baselines3 PPO agent inside a Gymnasium environment whose
dynamics are driven by the Phase-2 `DigitalTwin`. Reward shaping mirrors the
clinical priorities encoded in `pipelines/ppo_feature_engineering.py`:

  + reward stable oxygenation in target band (94–98% SpO2)
  - penalize hypoxia (<90%), barotrauma (TidalVol > 600 mL),
    excessive PEEP (> 15) and excessive FiO2 (> 80%)

The trained policy weights are written to:
    ml/models/ppo_policy.zip
    ml/models/ppo_train_metadata.json

Run:
    python ml/ppo_training.py --timesteps 50000 --profile-mix normal,ards,copd
    # smoke test (no real RL, just verifies the env contract):
    python ml/ppo_training.py --smoke

The smoke path runs without `stable-baselines3` installed; the full path
requires `stable-baselines3>=2.0` and `gymnasium>=0.29`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

import numpy as np

# Make the repo root importable when run as a script.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from services.digital_twin import DigitalTwin, SAFE_BOUNDS  # noqa: E402
from services.data_simulator import (  # noqa: E402
    SimulationConfig,
    VentilatorDataSimulator,
)


# ─── Action grid (discrete, clinician-style adjustments) ─────────────────────
# 9 actions: {hold} ∪ {±step on PEEP, FiO2, TidalVol}.
PEEP_STEP = 1.0     # cmH2O per click
FIO2_STEP = 5.0     # %  per click
TV_STEP = 25.0      # mL per click

ACTION_TABLE: List[Tuple[str, float, float, float]] = [
    ("HOLD",      0.0,        0.0,       0.0),
    ("PEEP_UP",   +PEEP_STEP, 0.0,       0.0),
    ("PEEP_DOWN", -PEEP_STEP, 0.0,       0.0),
    ("FIO2_UP",   0.0,        +FIO2_STEP, 0.0),
    ("FIO2_DOWN", 0.0,        -FIO2_STEP, 0.0),
    ("TV_UP",     0.0,        0.0,       +TV_STEP),
    ("TV_DOWN",   0.0,        0.0,       -TV_STEP),
    ("DEESC",     -PEEP_STEP, -FIO2_STEP, 0.0),  # safe wean combo
    ("ESCAL",     +PEEP_STEP, +FIO2_STEP, 0.0),  # rescue combo
]
N_ACTIONS = len(ACTION_TABLE)

# Observation: [SpO2, PEEP, FiO2, TidalVol, HR, MAP, RespRate]
OBS_KEYS = ["SpO2", "PEEP", "FiO2", "TidalVol", "HR", "MAP", "RespRate"]


# ─── Reward shaping ──────────────────────────────────────────────────────────
def compute_reward(spo2: float, peep: float, fio2: float, tv: float) -> float:
    r = 0.0
    # Bonus for being in the target band.
    if 94.0 <= spo2 <= 98.0:
        r += 1.0
    # Penalize hypoxia (steep, scaled by depth).
    if spo2 < 90.0:
        r -= 5.0 + (90.0 - spo2) * 0.5
    elif spo2 < 94.0:
        r -= 0.5 * (94.0 - spo2)
    # Penalize hyperoxia drift (>99 with high FiO2).
    if spo2 > 99.0 and fio2 > 60.0:
        r -= 0.3
    # VILI / barotrauma penalty.
    if tv > 600.0:
        r -= 0.6 + 0.005 * (tv - 600.0)
    # Excessive PEEP haemodynamic penalty.
    if peep > 15.0:
        r -= 0.4 + 0.1 * (peep - 15.0)
    # Excessive FiO2 toxicity penalty.
    if fio2 > 80.0:
        r -= 0.3 + 0.02 * (fio2 - 80.0)
    return float(r)


# ─── Gymnasium environment wrapping the Digital Twin ─────────────────────────
class _LazyGym:
    """Import gymnasium on demand so the smoke path works without it."""

    @staticmethod
    def get():
        try:
            import gymnasium as gym
            from gymnasium import spaces
        except ImportError as exc:
            raise ImportError(
                "gymnasium is required for full PPO training. "
                "Install with: pip install 'gymnasium>=0.29' 'stable-baselines3>=2.0'"
            ) from exc
        return gym, spaces


def make_ventilator_env(
    profile: str = "ards",
    seed: int = 0,
    episode_steps: int = 96,
    history_warmup: int = 24,
):
    """Factory returning a fresh `gymnasium.Env` instance."""
    gym, spaces = _LazyGym.get()

    class VentilatorTwinEnv(gym.Env):
        """One-patient episode: simulator drives 'truth', twin drives short rollouts."""

        metadata = {"render_modes": []}

        def __init__(self):
            super().__init__()
            self.action_space = spaces.Discrete(N_ACTIONS)
            # Bounded observation; raw values (PPO will normalize via VecNormalize if used).
            low = np.array([60.0, SAFE_BOUNDS["PEEP"][0], SAFE_BOUNDS["FiO2"][0],
                            SAFE_BOUNDS["TidalVol"][0], 30.0, 30.0, 5.0], dtype=np.float32)
            high = np.array([100.0, SAFE_BOUNDS["PEEP"][1], SAFE_BOUNDS["FiO2"][1],
                             SAFE_BOUNDS["TidalVol"][1], 200.0, 130.0, 50.0], dtype=np.float32)
            self.observation_space = spaces.Box(low=low, high=high, dtype=np.float32)
            self._profile = profile
            self._episode_steps = int(episode_steps)
            self._history_warmup = int(history_warmup)
            self._seed_base = int(seed)
            self._epoch = 0
            self._sim: Optional[VentilatorDataSimulator] = None
            self._twin: Optional[DigitalTwin] = None
            self._step_idx = 0
            self._cur: Optional[Dict[str, float]] = None
            self._stay_id = 900000

        def _spawn_simulator(self, ep_seed: int) -> None:
            cfg = SimulationConfig(
                profile=self._profile,
                packet_loss_probability=0.0,   # deterministic for training stability
                artifact_probability=0.0,
                trend_strength=0.04,
                seed=ep_seed,
            )
            self._sim = VentilatorDataSimulator(config=cfg)
            self._twin = DigitalTwin(stay_id=self._stay_id)
            warm = self._sim.generate_batch(stay_id=self._stay_id, steps=self._history_warmup)
            # Twin calibrates from warmup window.
            self._twin.calibrate([
                {k: r[k] for k in OBS_KEYS if r.get(k) is not None}
                for r in warm if all(r.get(k) is not None for k in OBS_KEYS)
            ])
            self._cur = warm[-1]

        def _obs(self) -> np.ndarray:
            assert self._cur is not None
            return np.array([float(self._cur.get(k, 0.0) or 0.0) for k in OBS_KEYS],
                            dtype=np.float32)

        def reset(self, *, seed: Optional[int] = None, options: Optional[Dict] = None):
            super().reset(seed=seed)
            self._epoch += 1
            ep_seed = self._seed_base + self._epoch
            self._spawn_simulator(ep_seed)
            self._step_idx = 0
            return self._obs(), {"profile": self._profile, "seed": ep_seed}

        def step(self, action: int):
            assert self._cur is not None and self._sim is not None and self._twin is not None
            name, dpeep, dfio2, dtv = ACTION_TABLE[int(action)]
            # Apply clinician-style adjustment to current settings, clamp to safe bounds.
            new_peep = float(np.clip(self._cur["PEEP"] + dpeep, *SAFE_BOUNDS["PEEP"]))
            new_fio2 = float(np.clip(self._cur["FiO2"] + dfio2, *SAFE_BOUNDS["FiO2"]))
            new_tv = float(np.clip(self._cur["TidalVol"] + dtv, *SAFE_BOUNDS["TidalVol"]))

            # Use the twin to predict the next SpO2 under the new settings.
            sim_out = self._twin.simulate(
                proposed={"PEEP": new_peep, "FiO2": new_fio2, "TidalVol": new_tv},
                current_spo2=float(self._cur["SpO2"]),
                steps=1,
                noise_scale=0.5,
            )
            next_spo2 = float(sim_out["trajectory"][-1])

            # Pull the next "ground-truth" record from the simulator and overlay our settings.
            nxt = self._sim.next_record(stay_id=self._stay_id)
            if nxt.get("SpO2") is None:
                nxt["SpO2"] = next_spo2
            # Blend twin prediction with simulator ground truth (twin influences the trajectory
            # so the policy gradient flows through actions that change settings).
            nxt["SpO2"] = 0.6 * next_spo2 + 0.4 * float(nxt["SpO2"])
            nxt["PEEP"] = new_peep
            nxt["FiO2"] = new_fio2
            nxt["TidalVol"] = new_tv

            reward = compute_reward(nxt["SpO2"], new_peep, new_fio2, new_tv)
            self._cur = nxt
            self._step_idx += 1

            terminated = self._cur["SpO2"] < 80.0  # hard fail = patient crash
            truncated = self._step_idx >= self._episode_steps
            info = {"action_name": name, "spo2": self._cur["SpO2"]}
            return self._obs(), reward, terminated, truncated, info

    return VentilatorTwinEnv()


# ─── Training driver ─────────────────────────────────────────────────────────
@dataclass
class TrainConfig:
    timesteps: int = 50_000
    profile_mix: List[str] = field(default_factory=lambda: ["normal", "ards", "copd"])
    n_envs: int = 4
    seed: int = 42
    learning_rate: float = 3e-4
    n_steps: int = 256
    batch_size: int = 64
    gamma: float = 0.99
    out_dir: str = os.path.join(REPO_ROOT, "ml", "models")
    artifact_name: str = "ppo_policy.zip"
    metadata_name: str = "ppo_train_metadata.json"


def train(cfg: TrainConfig) -> Dict:
    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.vec_env import DummyVecEnv, VecMonitor
    except ImportError as exc:
        raise ImportError(
            "stable-baselines3 is required for training. "
            "Install with: pip install 'stable-baselines3>=2.0' 'gymnasium>=0.29'"
        ) from exc

    os.makedirs(cfg.out_dir, exist_ok=True)

    def env_fn(rank: int):
        prof = cfg.profile_mix[rank % len(cfg.profile_mix)]
        return lambda: make_ventilator_env(profile=prof, seed=cfg.seed + rank * 1000)

    vec_env = VecMonitor(DummyVecEnv([env_fn(i) for i in range(cfg.n_envs)]))

    model = PPO(
        "MlpPolicy",
        vec_env,
        learning_rate=cfg.learning_rate,
        n_steps=cfg.n_steps,
        batch_size=cfg.batch_size,
        gamma=cfg.gamma,
        verbose=1,
        seed=cfg.seed,
        policy_kwargs={"net_arch": [128, 128]},
    )

    t0 = time.time()
    model.learn(total_timesteps=cfg.timesteps, progress_bar=False)
    train_seconds = time.time() - t0

    artifact_path = os.path.join(cfg.out_dir, cfg.artifact_name)
    model.save(artifact_path)

    metadata = {
        "config": asdict(cfg),
        "train_seconds": round(train_seconds, 2),
        "artifact_path": artifact_path,
        "n_actions": N_ACTIONS,
        "obs_keys": OBS_KEYS,
        "action_table": [{"name": n, "dPEEP": p, "dFiO2": f, "dTV": t} for n, p, f, t in ACTION_TABLE],
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    meta_path = os.path.join(cfg.out_dir, cfg.metadata_name)
    with open(meta_path, "w") as fh:
        json.dump(metadata, fh, indent=2)

    return {"artifact": artifact_path, "metadata": meta_path, "train_seconds": train_seconds}


def evaluate(model_path: str, profile: str = "ards", episodes: int = 10, seed: int = 1234) -> Dict:
    """Quick evaluation: mean episode return + time-in-target SpO2."""
    try:
        from stable_baselines3 import PPO
    except ImportError as exc:
        raise ImportError("stable-baselines3 required for evaluate()") from exc

    model = PPO.load(model_path)
    returns: List[float] = []
    in_target_ratios: List[float] = []
    hypoxia_ratios: List[float] = []
    for ep in range(episodes):
        env = make_ventilator_env(profile=profile, seed=seed + ep)
        obs, _ = env.reset()
        ep_return = 0.0
        in_target = 0
        hypoxia = 0
        steps = 0
        while True:
            action, _ = model.predict(obs, deterministic=True)
            obs, r, term, trunc, _ = env.step(int(action))
            ep_return += float(r)
            spo2 = float(obs[0])
            if 94.0 <= spo2 <= 98.0:
                in_target += 1
            if spo2 < 90.0:
                hypoxia += 1
            steps += 1
            if term or trunc:
                break
        returns.append(ep_return)
        in_target_ratios.append(in_target / max(1, steps))
        hypoxia_ratios.append(hypoxia / max(1, steps))
    return {
        "profile": profile,
        "episodes": episodes,
        "mean_return": round(float(np.mean(returns)), 2),
        "std_return": round(float(np.std(returns)), 2),
        "mean_time_in_target": round(float(np.mean(in_target_ratios)), 4),
        "mean_hypoxia_fraction": round(float(np.mean(hypoxia_ratios)), 4),
    }


# ─── Smoke test (no SB3 / gymnasium dependency) ──────────────────────────────
def smoke() -> Dict:
    """
    Verify env contract using only numpy + the in-repo twin/simulator.
    Mirrors `step()` semantics without needing gymnasium.
    """
    sim = VentilatorDataSimulator(SimulationConfig(profile="ards", seed=7))
    twin = DigitalTwin(stay_id=999)
    warm = sim.generate_batch(stay_id=999, steps=24)
    twin.calibrate([
        {k: r[k] for k in OBS_KEYS if r.get(k) is not None}
        for r in warm if all(r.get(k) is not None for k in OBS_KEYS)
    ])
    cur = warm[-1]
    total = 0.0
    rng = np.random.default_rng(0)
    actions_taken = []
    for _ in range(48):
        a = int(rng.integers(0, N_ACTIONS))
        name, dpeep, dfio2, dtv = ACTION_TABLE[a]
        new_peep = float(np.clip(cur["PEEP"] + dpeep, *SAFE_BOUNDS["PEEP"]))
        new_fio2 = float(np.clip(cur["FiO2"] + dfio2, *SAFE_BOUNDS["FiO2"]))
        new_tv = float(np.clip(cur["TidalVol"] + dtv, *SAFE_BOUNDS["TidalVol"]))
        sim_out = twin.simulate(
            proposed={"PEEP": new_peep, "FiO2": new_fio2, "TidalVol": new_tv},
            current_spo2=float(cur["SpO2"]),
            steps=1,
            noise_scale=0.5,
        )
        next_spo2 = float(sim_out["trajectory"][-1])
        nxt = sim.next_record(stay_id=999)
        if nxt.get("SpO2") is None:
            nxt["SpO2"] = next_spo2
        nxt["SpO2"] = 0.6 * next_spo2 + 0.4 * float(nxt["SpO2"])
        nxt["PEEP"] = new_peep
        nxt["FiO2"] = new_fio2
        nxt["TidalVol"] = new_tv
        total += compute_reward(nxt["SpO2"], new_peep, new_fio2, new_tv)
        cur = nxt
        actions_taken.append(name)
    return {
        "smoke": True,
        "n_actions_executed": len(actions_taken),
        "total_reward": round(total, 2),
        "final_spo2": round(float(cur["SpO2"]), 2),
        "actions_distribution": {n: actions_taken.count(n) for n in {a for a in actions_taken}},
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Train PPO ventilator policy via Digital Twin env")
    p.add_argument("--timesteps", type=int, default=50_000)
    p.add_argument("--profile-mix", type=str, default="normal,ards,copd",
                   help="Comma-separated profiles round-robined across n-envs")
    p.add_argument("--n-envs", type=int, default=4)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--learning-rate", type=float, default=3e-4)
    p.add_argument("--smoke", action="store_true",
                   help="Run smoke test only (no SB3, no training)")
    p.add_argument("--evaluate-only", type=str, default=None,
                   help="Path to ppo_policy.zip — skip training, just evaluate")
    args = p.parse_args()

    if args.smoke:
        out = smoke()
        print(json.dumps(out, indent=2))
        return

    if args.evaluate_only:
        out = evaluate(args.evaluate_only)
        print(json.dumps(out, indent=2))
        return

    cfg = TrainConfig(
        timesteps=args.timesteps,
        profile_mix=[s.strip() for s in args.profile_mix.split(",") if s.strip()],
        n_envs=args.n_envs,
        seed=args.seed,
        learning_rate=args.learning_rate,
    )
    print(f"[ppo_training] Starting training: {asdict(cfg)}")
    out = train(cfg)
    print(json.dumps(out, indent=2))

    print("\n[ppo_training] Quick evaluation on ARDS profile:")
    eval_out = evaluate(out["artifact"], profile="ards", episodes=5)
    print(json.dumps(eval_out, indent=2))


if __name__ == "__main__":
    main()
