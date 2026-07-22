"""
StrokeX — NSGA-II Multi-Objective Optimizer
Generates personalized daily rehabilitation plans using pymoo.

Objectives:
  1. Maximize recovery potential (negative for minimization)
  2. Minimize predicted fatigue

Decision Variables:
  - x[0]: potion_reps   (Potion Master — wrist flexion reps)
  - x[1]: shield_reps   (Shield Defender — finger abduction reps)
  - x[2]: rhythm_reps   (Rhythm Maestro — finger tapping reps)

Constraints based on patient severity_score (1-10):
  - Lower severity = more reps allowed
  - Higher severity = stricter limits to prevent overexertion
"""

import numpy as np
from pymoo.core.problem import Problem
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.sampling.rnd import FloatRandomSampling
from pymoo.optimize import minimize as pymoo_minimize
from pymoo.termination import get_termination
from typing import Dict, List, Optional


class RehabProblem(Problem):
    """
    Multi-objective rehabilitation planning problem.
    
    Variables:
        x[0] = potion_reps   [5, max_reps]
        x[1] = shield_reps   [5, max_reps]
        x[2] = rhythm_reps   [5, max_reps]
    
    Objectives (both minimized):
        f1 = -recovery_score  (maximize recovery → minimize negative)
        f2 = fatigue_score    (minimize fatigue)
    
    Constraints:
        g1: total_reps <= max_total (severity-dependent cap)
    """

    def __init__(
        self,
        severity_score: int,
        avg_accuracy: float = 0.5,
        avg_fatigue: float = 0.5,
        streak: int = 0,
    ):
        # Severity-based limits (higher severity = fewer reps allowed)
        self.severity = severity_score
        self.avg_accuracy = avg_accuracy
        self.avg_fatigue = avg_fatigue
        self.streak = streak

        # Calculate max reps per exercise based on severity
        # Severity 1 (mild) → up to 30 reps, Severity 10 (severe) → up to 8 reps
        self.max_reps = max(8, int(35 - (severity_score * 2.5)))
        self.min_reps = max(3, int(8 - severity_score * 0.5))

        # Max total reps across all exercises
        self.max_total = max(15, int(80 - (severity_score * 6)))

        super().__init__(
            n_var=3,
            n_obj=2,
            n_ieq_constr=1,
            xl=np.array([self.min_reps, self.min_reps, self.min_reps]),
            xu=np.array([self.max_reps, self.max_reps, self.max_reps]),
        )

    def _evaluate(self, X, out, *args, **kwargs):
        potion = X[:, 0]
        shield = X[:, 1]
        rhythm = X[:, 2]
        total_reps = potion + shield + rhythm

        # ---- Objective 1: Recovery Score (to be maximized → negated) ----
        # Recovery depends on volume, variety, and patient responsiveness
        volume_score = (potion * 1.0 + shield * 1.2 + rhythm * 0.8)

        # Variety bonus: reward balanced distribution across exercises
        std_dev = np.std(X, axis=1)
        max_std = (self.max_reps - self.min_reps) / 2
        variety_bonus = 1.0 + 0.3 * (1.0 - std_dev / (max_std + 1e-8))

        # Accuracy multiplier: patients with higher accuracy benefit from more reps
        accuracy_mult = 0.7 + 0.6 * self.avg_accuracy

        # Streak bonus: consecutive days amplify recovery (habit building)
        streak_mult = 1.0 + min(self.streak * 0.02, 0.2)  # Up to 20% bonus

        recovery = volume_score * variety_bonus * accuracy_mult * streak_mult
        f1 = -recovery  # Negate for minimization

        # ---- Objective 2: Fatigue Score (to be minimized) ----
        # Fatigue increases with total volume, especially for severe patients
        base_fatigue = total_reps / self.max_total

        # Severity amplifier: more severe patients fatigue faster
        severity_factor = 1.0 + (self.severity - 5) * 0.15

        # Historical fatigue: if patient was already fatigued, reps cost more
        fatigue_memory = 1.0 + self.avg_fatigue * 0.3

        # Diminishing returns: excessive reps beyond a threshold spike fatigue
        overwork_penalty = np.where(
            total_reps > self.max_total * 0.8,
            (total_reps - self.max_total * 0.8) ** 1.5 * 0.01,
            0.0
        )

        f2 = base_fatigue * severity_factor * fatigue_memory + overwork_penalty

        out["F"] = np.column_stack([f1, f2])

        # ---- Constraint: total reps must not exceed max_total ----
        out["G"] = np.column_stack([total_reps - self.max_total])


def generate_plan(
    severity_score: int,
    recent_sessions: Optional[List[Dict]] = None,
    streak: int = 0,
    pop_size: int = 40,
    n_gen: int = 60,
) -> Dict:
    """
    Generate an optimized daily rehabilitation plan using NSGA-II.
    
    Args:
        severity_score: Patient severity (1-10)
        recent_sessions: List of recent game session dicts with accuracy/fatigue
        streak: Current consecutive day streak
        pop_size: NSGA-II population size
        n_gen: Number of generations
    
    Returns:
        Dict with potion_reps, shield_reps, rhythm_reps, and metadata
    """
    # Calculate averages from recent sessions
    avg_accuracy = 0.5
    avg_fatigue = 0.5
    if recent_sessions and len(recent_sessions) > 0:
        accuracies = [s.get("accuracy", 0.5) for s in recent_sessions]
        fatigues = [s.get("reported_fatigue", 0.5) for s in recent_sessions]
        avg_accuracy = float(np.mean(accuracies))
        avg_fatigue = float(np.mean(fatigues))

    # Define the problem
    problem = RehabProblem(
        severity_score=severity_score,
        avg_accuracy=avg_accuracy,
        avg_fatigue=avg_fatigue,
        streak=streak,
    )

    # Configure NSGA-II
    algorithm = NSGA2(
        pop_size=pop_size,
        sampling=FloatRandomSampling(),
        crossover=SBX(prob=0.9, eta=15),
        mutation=PM(eta=20),
        eliminate_duplicates=True,
    )

    termination = get_termination("n_gen", n_gen)

    # Run optimization
    res = pymoo_minimize(
        problem,
        algorithm,
        termination,
        seed=42,
        verbose=False,
    )

    # Select the best compromise solution (knee point)
    # Using the solution closest to the ideal point
    if res.F is not None and len(res.F) > 0:
        # Normalize objectives
        f_min = res.F.min(axis=0)
        f_max = res.F.max(axis=0)
        f_range = f_max - f_min + 1e-8
        f_normalized = (res.F - f_min) / f_range

        # Find solution closest to ideal (0, 0)
        distances = np.sqrt(np.sum(f_normalized ** 2, axis=1))
        best_idx = np.argmin(distances)

        best_x = res.X[best_idx]
        best_f = res.F[best_idx]
    else:
        # Fallback: use severity-based defaults
        default_reps = max(5, 20 - severity_score * 2)
        best_x = np.array([default_reps, default_reps, default_reps])
        best_f = np.array([0, 0])

    potion_reps = int(np.round(best_x[0]))
    shield_reps = int(np.round(best_x[1]))
    rhythm_reps = int(np.round(best_x[2]))

    return {
        "potion_reps": potion_reps,
        "shield_reps": shield_reps,
        "rhythm_reps": rhythm_reps,
        "total_reps": potion_reps + shield_reps + rhythm_reps,
        "metadata": {
            "severity_score": severity_score,
            "avg_accuracy": round(avg_accuracy, 3),
            "avg_fatigue": round(avg_fatigue, 3),
            "streak": streak,
            "recovery_score": round(float(-best_f[0]), 2),
            "predicted_fatigue": round(float(best_f[1]), 3),
            "pareto_solutions_count": len(res.F) if res.F is not None else 0,
            "max_reps_per_exercise": problem.max_reps,
            "max_total_reps": problem.max_total,
        }
    }


# ============================================================
# Quick test
# ============================================================
if __name__ == "__main__":
    # Test with different severity levels
    for severity in [2, 5, 8]:
        print(f"\n{'='*50}")
        print(f"Severity Score: {severity}")
        print(f"{'='*50}")
        plan = generate_plan(
            severity_score=severity,
            recent_sessions=[
                {"accuracy": 0.85, "reported_fatigue": 0.3},
                {"accuracy": 0.78, "reported_fatigue": 0.45},
            ],
            streak=3,
        )
        print(f"Potion Master reps: {plan['potion_reps']}")
        print(f"Shield Defender reps: {plan['shield_reps']}")
        print(f"Rhythm Maestro reps: {plan['rhythm_reps']}")
        print(f"Total reps: {plan['total_reps']}")
        print(f"Recovery score: {plan['metadata']['recovery_score']}")
        print(f"Predicted fatigue: {plan['metadata']['predicted_fatigue']}")
