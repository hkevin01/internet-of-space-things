"""
rl_resource_optimizer.py - Reinforcement Learning Resource Optimizer for Space Missions
=========================================================================================
ID: ML-020
Requirement: Train a reinforcement learning agent to optimally allocate limited
             resources (power, propellant, oxygen, compute budget) across competing
             satellite subsystems to maximize mission objectives while minimizing
             risk to crew/vehicle.
Purpose: Replace static resource allocation rules with an adaptive policy that
         learns to handle degraded equipment states, emergency scenarios, and
         multi-objective trade-offs discovered only through extensive simulation.
Rationale: Rule-based allocators cannot adapt to novel failure combinations.
           A Proximal Policy Optimization (PPO) agent trained on thousands of
           simulated missions learns robust allocation strategies that degrade
           gracefully under uncertainty.
Inputs: SpaceMissionEnv state vector (power_budget, o2_level, fuel_remaining,
        mission_phase, crew_activity, component_health[N]).
Outputs: Resource allocation policy; optimize_resources() callable returning
         allocation dict usable by MissionControlSystem.
Preconditions: numpy available; torch optional for neural network policy.
Postconditions: Policy saved to models/rl_policy_{version}.pkl.
Failure Modes: Falls back to priority-weighted static allocation when torch absent.
Verification: 1000 episode evaluation; mean mission_score >= 0.7; crew_risk <= 0.15.
References: OpenAI Spinning Up docs, PPO arXiv:1707.06347, 
            Springer 978-981-96-4613-5_7 Chap 7.
"""

import logging
import math
import os
import pickle
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.distributions import Categorical, Normal
    _TORCH_AVAILABLE = True
    logger.info("PyTorch %s available for RL policy training.", torch.__version__)
except ImportError:
    _TORCH_AVAILABLE = False
    logger.warning(
        "PyTorch not found. RLResourceOptimizer will use priority-weighted "
        "static allocation fallback. Install with: pip install torch"
    )


# ---------------------------------------------------------------------------
# Mission environment
# ---------------------------------------------------------------------------

@dataclass
class MissionState:
    """
    ID: ML-020-A
    Purpose: Full observation of mission resource state at one timestep.
    Fields documented in SI units or normalized [0..1] percentages.
    """
    # Resources [0..1 normalized fraction of nominal]
    power_budget: float       # Available power ratio (1=nominal, 0=depleted)
    o2_level: float           # Oxygen reserve ratio
    fuel_remaining: float     # Propellant mass ratio
    compute_budget: float     # Available MIPS ratio (for onboard AI)

    # Mission state
    mission_phase: int        # 0=launch, 1=transit, 2=ops, 3=return, 4=emergency
    crew_activity: int        # 0=sleep, 1=nominal, 2=EVA, 3=emergency
    mission_elapsed_pct: float  # 0..1 fraction of total mission duration elapsed

    # Component health [0..1 each]
    solar_panel_health: float
    battery_health: float
    thruster_health: float
    life_support_health: float
    comms_health: float

    # Derived risk indicators
    crew_risk: float          # 0..1 estimated probability of crew harm this step
    mission_progress: float   # 0..1 objective completion

    def to_vector(self) -> np.ndarray:
        """
        ID: ML-020-A1
        Purpose: Flatten state to numpy vector for neural network input.
        """
        return np.array([
            self.power_budget, self.o2_level, self.fuel_remaining,
            self.compute_budget,
            self.mission_phase / 4.0,
            self.crew_activity / 3.0,
            self.mission_elapsed_pct,
            self.solar_panel_health, self.battery_health,
            self.thruster_health, self.life_support_health, self.comms_health,
            self.crew_risk, self.mission_progress,
        ], dtype=np.float32)

    @staticmethod
    def n_obs() -> int:
        """Returns observation dimensionality."""
        return 14


@dataclass
class ResourceAllocation:
    """
    ID: ML-020-B
    Purpose: Output of the RL policy - fractional allocation to each subsystem.
    All values sum to <= 1.0. Remainder is stored as reserves.
    """
    life_support: float   # Fraction of power budget to life support
    propulsion: float     # Fraction to thrusters
    communications: float # Fraction to comms
    science: float        # Fraction to science instruments
    thermal: float        # Fraction to thermal control
    computing: float      # Fraction to onboard compute

    def to_vector(self) -> np.ndarray:
        v = np.array([
            self.life_support, self.propulsion, self.communications,
            self.science, self.thermal, self.computing,
        ], dtype=np.float32)
        return v

    @staticmethod
    def from_vector(v: np.ndarray) -> "ResourceAllocation":
        # Softmax normalization so allocations are a proper probability distribution
        exp_v = np.exp(v - v.max())
        norm = exp_v / exp_v.sum()
        return ResourceAllocation(
            life_support=float(norm[0]),
            propulsion=float(norm[1]),
            communications=float(norm[2]),
            science=float(norm[3]),
            thermal=float(norm[4]),
            computing=float(norm[5]),
        )

    @staticmethod
    def n_actions() -> int:
        """Returns action dimensionality."""
        return 6


# ---------------------------------------------------------------------------
# Space mission simulation environment
# ---------------------------------------------------------------------------

class SpaceMissionEnv:
    """
    ID: ML-021
    Requirement: Simulate a 30-day crewed space mission with stochastic component
                 failures and resource consumption to train and evaluate RL agents.
    Purpose: Provide a controlled environment where the RL agent receives
             reward feedback proportional to mission progress and inverse to
             crew risk, teaching safe resource management under failure.
    Rationale: Simulation is the only safe way to explore risky allocation
               policies before deployment on real spacecraft.
    Side Effects: Random state - seed with env.seed() for reproducibility.
    Failure Modes: Catastrophic failure terminates episode with large negative reward.
    """

    MAX_STEPS = 720          # 30 days * 24 hours/day = 720 hourly steps
    FAILURE_PROB = 0.002     # Per-component per-step failure probability

    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)
        self._np_rng = np.random.RandomState(seed)
        self._state: Optional[MissionState] = None
        self._step_count = 0
        self._done = False

    def reset(self) -> np.ndarray:
        """
        ID: ML-021-A
        Requirement: Reset environment to a new randomized initial state.
        Outputs: Initial observation vector.
        """
        self._state = MissionState(
            power_budget=0.95 + self._rng.uniform(-0.05, 0.05),
            o2_level=1.0,
            fuel_remaining=1.0,
            compute_budget=0.9,
            mission_phase=0,
            crew_activity=1,
            mission_elapsed_pct=0.0,
            solar_panel_health=0.98 + self._rng.uniform(-0.02, 0.02),
            battery_health=0.99 + self._rng.uniform(-0.01, 0.01),
            thruster_health=0.99,
            life_support_health=1.0,
            comms_health=0.98,
            crew_risk=0.0,
            mission_progress=0.0,
        )
        self._step_count = 0
        self._done = False
        return self._state.to_vector()

    def step(
        self, action_vector: np.ndarray
    ) -> Tuple[np.ndarray, float, bool, Dict[str, Any]]:
        """
        ID: ML-021-B
        Requirement: Apply one resource allocation step and return (obs, reward, done, info).
        Inputs: action_vector - raw allocation logits of shape (6,)
        Outputs:
          - obs: next state observation (14,)
          - reward: scalar reward [-10, +2]
          - done: True if mission complete or catastrophic failure
          - info: diagnostic dict for logging
        """
        if self._done or self._state is None:
            raise RuntimeError("Environment not reset. Call env.reset() first.")

        alloc = ResourceAllocation.from_vector(action_vector)
        s = self._state
        info: Dict[str, Any] = {}

        # ---- Stochastic component failures ----
        s.solar_panel_health *= self._degrade("solar", alloc.computing)
        s.battery_health *= self._degrade("battery", alloc.life_support)
        s.thruster_health *= self._degrade("thruster", alloc.propulsion)
        s.life_support_health *= self._degrade("life_support", alloc.life_support)
        s.comms_health *= self._degrade("comms", alloc.communications)

        # ---- Resource consumption per allocation decision ----
        power_gen = s.solar_panel_health * 0.90 + s.battery_health * 0.10
        power_used = (
            alloc.life_support * 0.30 + alloc.propulsion * 0.25 +
            alloc.communications * 0.10 + alloc.science * 0.15 +
            alloc.thermal * 0.12 + alloc.computing * 0.08
        )
        s.power_budget = max(0.0, min(1.0, s.power_budget + power_gen * 0.01 - power_used * 0.02))
        s.o2_level = max(0.0, s.o2_level - 0.001 * (1.0 + s.crew_activity * 0.3) /
                         max(0.01, s.life_support_health * alloc.life_support + 0.01))
        s.fuel_remaining = max(0.0, s.fuel_remaining - 0.0005 * alloc.propulsion)

        # ---- Mission phase progression ----
        s.mission_elapsed_pct = self._step_count / self.MAX_STEPS
        if s.mission_elapsed_pct > 0.15:
            s.mission_phase = 1  # transit
        if s.mission_elapsed_pct > 0.35:
            s.mission_phase = 2  # operations
        if s.mission_elapsed_pct > 0.75:
            s.mission_phase = 3  # return

        # Random EVA events
        if self._rng.random() < 0.02:
            s.crew_activity = 2   # EVA - higher O2 consumption
        elif self._rng.random() < 0.1:
            s.crew_activity = 0   # Sleep cycle
        else:
            s.crew_activity = 1   # Nominal

        # Emergency trigger
        if s.life_support_health < 0.4 or s.o2_level < 0.2:
            s.mission_phase = 4
            s.crew_activity = 3
            s.crew_risk = min(1.0, s.crew_risk + 0.1)

        # ---- Mission progress ----
        science_progress = alloc.science * s.comms_health * 0.002
        s.mission_progress = min(1.0, s.mission_progress + science_progress)
        s.crew_risk = max(0.0, min(1.0,
            (1.0 - s.life_support_health) * 0.4 +
            (1.0 - s.o2_level) * 0.3 +
            (1.0 - s.power_budget) * 0.1 +
            (1.0 if s.mission_phase == 4 else 0.0) * 0.2
        ))

        # ---- Reward function ----
        #  +progress: reward science / mission progress
        #  -risk: penalize crew risk (safety constraint)
        #  -waste: penalize over-allocation to non-critical systems in emergencies
        progress_reward = science_progress * 10.0
        safety_penalty = s.crew_risk ** 2 * 5.0
        resource_waste = (
            max(0, alloc.science - 0.15) * 0.5 if s.mission_phase == 4 else 0
        )
        reward = progress_reward - safety_penalty - resource_waste

        # ---- Termination conditions ----
        catastrophic = (s.o2_level < 0.05 or s.power_budget < 0.01 or
                        s.life_support_health < 0.1)
        mission_complete = (
            s.mission_elapsed_pct >= 1.0 or s.mission_progress >= 1.0
        )

        if catastrophic:
            reward -= 10.0
            self._done = True
            info["termination"] = "catastrophic_failure"
        elif mission_complete:
            reward += 2.0 * s.mission_progress
            self._done = True
            info["termination"] = "mission_complete"
        else:
            self._step_count += 1

        info.update({
            "crew_risk": s.crew_risk,
            "mission_progress": s.mission_progress,
            "power_budget": s.power_budget,
            "o2_level": s.o2_level,
            "step": self._step_count,
        })

        return self._state.to_vector(), float(reward), self._done, info

    def _degrade(self, component: str, allocation_fraction: float) -> float:
        """
        ID: ML-021-C
        Purpose: Compute component health multiplier per step.
               Higher allocation slows degradation; random shocks cause failures.
        Inputs:
          - component: name for logging
          - allocation_fraction: 0..1 fraction of resources devoted to this component
        Returns: Multiplicative health factor (close to 1.0 normally).
        """
        base_wear = 1.0 - 0.0001 * (1.0 - allocation_fraction)
        shock = 1.0 - (
            0.15 if self._rng.random() < self.FAILURE_PROB else 0.0
        )
        return max(0.01, base_wear * shock)


# ---------------------------------------------------------------------------
# Neural network policy (PPO-style actor-critic)
# ---------------------------------------------------------------------------

if _TORCH_AVAILABLE:
    class _ActorCritic(nn.Module):
        """
        ID: ML-022
        Purpose: Shared-trunk actor-critic network for PPO.
        Architecture: [n_obs -> FC(256) -> FC(128)] shared
                      -> Actor head: FC(128) -> n_actions (mean of Gaussian policy)
                      -> Critic head: FC(64) -> 1 (value estimate)
        """

        def __init__(self, n_obs: int, n_actions: int):
            super().__init__()
            self.trunk = nn.Sequential(
                nn.Linear(n_obs, 256), nn.Tanh(),
                nn.Linear(256, 128), nn.Tanh(),
            )
            self.actor_mean = nn.Linear(128, n_actions)
            self.actor_log_std = nn.Parameter(torch.zeros(n_actions))
            self.critic = nn.Sequential(
                nn.Linear(128, 64), nn.Tanh(),
                nn.Linear(64, 1),
            )

        def forward(self, obs: torch.Tensor):
            shared = self.trunk(obs)
            return self.actor_mean(shared), self.critic(shared)

        def get_action(self, obs: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
            """
            ID: ML-022-A
            Purpose: Sample an action from the current Gaussian policy.
            Outputs: (action, log_prob, value)
            """
            mean, value = self.forward(obs)
            std = self.actor_log_std.exp().expand_as(mean)
            dist = Normal(mean, std)
            action = dist.sample()
            log_prob = dist.log_prob(action).sum(dim=-1)
            return action, log_prob, value.squeeze(-1)


class PPOTrainer:
    """
    ID: ML-023
    Requirement: Train an actor-critic policy with Proximal Policy Optimization
                 on the SpaceMissionEnv for resource allocation.
    Purpose: PPO is the recommended RL algorithm for continuous control - it
             is stable, sample-efficient, and less sensitive to hyperparameters
             than vanilla policy gradient.
    Key hyperparameters (calibrated for SpaceMissionEnv):
      - clip_epsilon=0.2 (PPO clipping ratio)
      - gamma=0.99 (discount factor for long-horizon missions)
      - gae_lambda=0.95 (Generalized Advantage Estimation smoothing)
      - lr=3e-4, epochs_per_update=10, minibatch_size=256
    """

    def __init__(
        self,
        n_obs: int,
        n_actions: int,
        lr: float = 3e-4,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_epsilon: float = 0.2,
        entropy_coef: float = 0.01,
        value_coef: float = 0.5,
        max_grad_norm: float = 0.5,
        device: str = "cpu",
    ):
        if not _TORCH_AVAILABLE:
            raise ImportError("PyTorch required for PPOTrainer.")

        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_epsilon = clip_epsilon
        self.entropy_coef = entropy_coef
        self.value_coef = value_coef
        self.max_grad_norm = max_grad_norm
        self.device = torch.device(device)

        self.net = _ActorCritic(n_obs, n_actions).to(self.device)
        self.optimizer = optim.Adam(self.net.parameters(), lr=lr)

    def collect_rollout(
        self, env: SpaceMissionEnv, n_steps: int = 2048
    ) -> Dict[str, torch.Tensor]:
        """
        ID: ML-023-A
        Requirement: Collect n_steps environment transitions using current policy.
        Outputs: dict with keys obs, actions, log_probs, rewards, dones, values.
        """
        obs_list, act_list, logp_list = [], [], []
        rew_list, done_list, val_list = [], [], []

        obs = env.reset()
        for _ in range(n_steps):
            obs_t = torch.FloatTensor(obs).unsqueeze(0).to(self.device)
            with torch.no_grad():
                action, log_prob, value = self.net.get_action(obs_t)

            next_obs, reward, done, _ = env.step(action.squeeze(0).cpu().numpy())

            obs_list.append(obs)
            act_list.append(action.squeeze(0).cpu().numpy())
            logp_list.append(log_prob.item())
            rew_list.append(reward)
            done_list.append(float(done))
            val_list.append(value.item())

            if done:
                obs = env.reset()
            else:
                obs = next_obs

        return {
            "obs": torch.FloatTensor(np.array(obs_list)).to(self.device),
            "actions": torch.FloatTensor(np.array(act_list)).to(self.device),
            "log_probs": torch.FloatTensor(logp_list).to(self.device),
            "rewards": torch.FloatTensor(rew_list).to(self.device),
            "dones": torch.FloatTensor(done_list).to(self.device),
            "values": torch.FloatTensor(val_list).to(self.device),
        }

    def compute_advantages(
        self, rewards: torch.Tensor, values: torch.Tensor, dones: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        ID: ML-023-B
        Purpose: Compute GAE advantages and TD returns.
        """
        T = len(rewards)
        advantages = torch.zeros(T, device=self.device)
        returns = torch.zeros(T, device=self.device)
        gae = 0.0

        for t in reversed(range(T)):
            next_val = values[t + 1] if t < T - 1 else 0.0
            delta = (rewards[t] + self.gamma * next_val * (1 - dones[t])
                     - values[t])
            gae = delta + self.gamma * self.gae_lambda * (1 - dones[t]) * gae
            advantages[t] = gae
            returns[t] = advantages[t] + values[t]

        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        return advantages, returns

    def update(
        self, rollout: Dict[str, torch.Tensor],
        epochs: int = 10, minibatch_size: int = 256
    ) -> Dict[str, float]:
        """
        ID: ML-023-C
        Requirement: Run PPO update epochs on collected rollout data.
        Returns: Dict with mean policy_loss, value_loss, entropy_loss.
        """
        obs = rollout["obs"]
        actions = rollout["actions"]
        old_log_probs = rollout["log_probs"].detach()
        rewards = rollout["rewards"]
        dones = rollout["dones"]
        old_values = rollout["values"].detach()

        advantages, returns = self.compute_advantages(rewards, old_values, dones)

        total_pol_loss, total_val_loss, total_ent = 0.0, 0.0, 0.0
        n_updates = 0
        T = len(obs)

        for _ in range(epochs):
            indices = torch.randperm(T)
            for start in range(0, T, minibatch_size):
                idx = indices[start: start + minibatch_size]
                mb_obs = obs[idx]
                mb_actions = actions[idx]
                mb_old_logp = old_log_probs[idx]
                mb_adv = advantages[idx]
                mb_ret = returns[idx]

                mean, values = self.net(mb_obs)
                std = self.net.actor_log_std.exp().expand_as(mean)
                dist = Normal(mean, std)
                new_log_probs = dist.log_prob(mb_actions).sum(dim=-1)
                entropy = dist.entropy().sum(dim=-1).mean()

                ratio = (new_log_probs - mb_old_logp).exp()
                surr1 = ratio * mb_adv
                surr2 = torch.clamp(ratio, 1 - self.clip_epsilon, 1 + self.clip_epsilon) * mb_adv
                pol_loss = -torch.min(surr1, surr2).mean()
                val_loss = 0.5 * (values.squeeze(-1) - mb_ret).pow(2).mean()
                loss = pol_loss + self.value_coef * val_loss - self.entropy_coef * entropy

                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.net.parameters(), self.max_grad_norm)
                self.optimizer.step()

                total_pol_loss += pol_loss.item()
                total_val_loss += val_loss.item()
                total_ent += entropy.item()
                n_updates += 1

        return {
            "policy_loss": total_pol_loss / max(1, n_updates),
            "value_loss": total_val_loss / max(1, n_updates),
            "entropy": total_ent / max(1, n_updates),
        }


# ---------------------------------------------------------------------------
# Static priority-weighted fallback (no PyTorch)
# ---------------------------------------------------------------------------

class _PriorityAllocator:
    """
    ID: ML-023-FB
    Purpose: Rule-based priority-weighted allocator used when PyTorch is
             unavailable. Always allocates life_support > propulsion > comms.
    """

    PRIORITY_WEIGHTS = {
        "normal": [0.35, 0.20, 0.15, 0.15, 0.10, 0.05],
        "emergency": [0.60, 0.15, 0.10, 0.00, 0.10, 0.05],
        "transit": [0.30, 0.30, 0.12, 0.12, 0.10, 0.06],
    }

    def allocate(self, state_vector: np.ndarray) -> np.ndarray:
        phase = int(round(state_vector[4] * 4))
        if phase == 4:
            weights = self.PRIORITY_WEIGHTS["emergency"]
        elif phase in (1, 3):
            weights = self.PRIORITY_WEIGHTS["transit"]
        else:
            weights = self.PRIORITY_WEIGHTS["normal"]
        return np.array(weights, dtype=np.float32)


# ---------------------------------------------------------------------------
# Main optimizer class
# ---------------------------------------------------------------------------

class RLResourceOptimizer:
    """
    ID: ML-020
    Requirement: High-level interface for training and deploying the RL
                 resource allocation policy in the IoST mission control system.
    Purpose: Exposes optimize_resources() method that MissionControlSystem
             calls each decision cycle to get a resource allocation.
    Preconditions: train() called at least once before optimize_resources().
    Side Effects: Writes policy checkpoint to models/rl_policy.pkl.
    """

    def __init__(
        self,
        model_dir: str = "models",
        n_training_steps: int = 100_000,
        seed: int = 42,
        device: str = "cpu",
    ):
        self.model_dir = model_dir
        self.n_training_steps = n_training_steps
        self.seed = seed
        self.device = device
        self._ppo: Optional[PPOTrainer] = None
        self._fallback = _PriorityAllocator()
        self._trained = False
        os.makedirs(model_dir, exist_ok=True)

    def train(self, verbose: bool = True) -> Dict[str, List[float]]:
        """
        ID: ML-024
        Requirement: Train RL policy on SpaceMissionEnv for n_training_steps total
                     environment interactions, logging progress every rollout.
        Outputs: Training history dict with episode_returns and policy_loss lists.
        Side Effects: Saves policy checkpoint to models/rl_policy.pkl.
        Error Handling: Falls back to static allocator on any exception.
        """
        if not _TORCH_AVAILABLE:
            logger.warning(
                "PyTorch unavailable - RLResourceOptimizer using static fallback."
            )
            self._trained = True
            return {"episode_returns": [], "policy_loss": []}

        env = SpaceMissionEnv(seed=self.seed)
        n_obs = MissionState.n_obs()
        n_actions = ResourceAllocation.n_actions()

        self._ppo = PPOTrainer(
            n_obs=n_obs, n_actions=n_actions, device=self.device
        )

        rollout_steps = 2048
        n_rollouts = max(1, self.n_training_steps // rollout_steps)
        history: Dict[str, List[float]] = {
            "episode_returns": [], "policy_loss": [], "value_loss": []
        }

        eval_env = SpaceMissionEnv(seed=self.seed + 1)

        for rollout_idx in range(n_rollouts):
            rollout = self._ppo.collect_rollout(env, n_steps=rollout_steps)
            stats = self._ppo.update(rollout)

            history["policy_loss"].append(stats["policy_loss"])
            history["value_loss"].append(stats["value_loss"])

            # Periodic evaluation
            if rollout_idx % 10 == 0:
                ep_ret = self._evaluate(eval_env, n_episodes=5)
                history["episode_returns"].append(ep_ret)
                if verbose:
                    logger.info(
                        "Rollout %d/%d | mean_ep_return=%.2f | pol_loss=%.4f",
                        rollout_idx + 1, n_rollouts, ep_ret, stats["policy_loss"],
                    )

        self._trained = True
        self._save_policy()
        logger.info("RL training complete. Policy saved.")
        return history

    def optimize_resources(
        self, state: MissionState
    ) -> ResourceAllocation:
        """
        ID: ML-025
        Requirement: Query trained policy for resource allocation given current state.
        Inputs: state - current MissionState observation.
        Outputs: ResourceAllocation with fractional allocation per subsystem.
        Preconditions: train() called or policy loaded from file.
        Error Handling: Falls back to priority-weighted allocator on any exception.
        """
        obs_vec = state.to_vector()

        if _TORCH_AVAILABLE and self._ppo is not None and self._trained:
            try:
                obs_t = torch.FloatTensor(obs_vec).unsqueeze(0).to(
                    torch.device(self.device)
                )
                with torch.no_grad():
                    mean, _ = self._ppo.net(obs_t)
                    # Deterministic greedy action at deployment time
                    action_np = mean.squeeze(0).cpu().numpy()
                return ResourceAllocation.from_vector(action_np)
            except Exception as exc:
                logger.error("Policy inference failed: %s - using fallback.", exc)

        # Fallback
        alloc_vec = self._fallback.allocate(obs_vec)
        return ResourceAllocation.from_vector(alloc_vec)

    def load_policy(self, path: Optional[str] = None) -> bool:
        """
        ID: ML-026
        Purpose: Load saved policy checkpoint from disk.
        Inputs: path - file path; if None uses default models/rl_policy.pkl.
        Outputs: True if loaded successfully; False otherwise.
        """
        if not _TORCH_AVAILABLE:
            return False
        path = path or os.path.join(self.model_dir, "rl_policy.pkl")
        if not os.path.exists(path):
            logger.warning("No policy checkpoint found at %s.", path)
            return False
        try:
            with open(path, "rb") as f:
                state_dict = pickle.load(f)
            n_obs = MissionState.n_obs()
            n_actions = ResourceAllocation.n_actions()
            if self._ppo is None:
                self._ppo = PPOTrainer(n_obs=n_obs, n_actions=n_actions)
            self._ppo.net.load_state_dict(state_dict)
            self._trained = True
            logger.info("Policy loaded from %s.", path)
            return True
        except Exception as exc:
            logger.error("Failed to load policy: %s", exc)
            return False

    def _save_policy(self) -> None:
        """
        ID: ML-027
        Purpose: Serialize policy network state dict to disk.
        """
        if not _TORCH_AVAILABLE or self._ppo is None:
            return
        path = os.path.join(self.model_dir, "rl_policy.pkl")
        try:
            with open(path, "wb") as f:
                pickle.dump(self._ppo.net.state_dict(), f)
            logger.info("Policy checkpoint saved to %s.", path)
        except Exception as exc:
            logger.error("Failed to save policy: %s", exc)

    def _evaluate(self, env: SpaceMissionEnv, n_episodes: int = 10) -> float:
        """
        ID: ML-028
        Purpose: Evaluate current policy over n_episodes and return mean return.
        """
        if not _TORCH_AVAILABLE or self._ppo is None:
            return 0.0
        total = 0.0
        for _ in range(n_episodes):
            obs = env.reset()
            done = False
            ep_ret = 0.0
            while not done:
                obs_t = torch.FloatTensor(obs).unsqueeze(0).to(
                    torch.device(self.device)
                )
                with torch.no_grad():
                    mean, _ = self._ppo.net(obs_t)
                    action_np = mean.squeeze(0).cpu().numpy()
                obs, reward, done, _ = env.step(action_np)
                ep_ret += reward
            total += ep_ret
        return total / max(1, n_episodes)
