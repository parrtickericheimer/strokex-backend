import numpy as np
from pymoo.core.problem import ElementwiseProblem
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.optimize import minimize
from pymoo.operators.sampling.rnd import FloatRandomSampling
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM

class RehabOptimizationProblem(ElementwiseProblem):
    def __init__(self, current_level, avg_success, avg_pain):
        # Variables: [Target Reps (10 to 50), Target Level Diff (-1 to +1), Target ROM multiplier (0.8 to 1.2)]
        super().__init__(n_var=3, n_obj=3, n_ieq_constr=0, xl=np.array([10, -1, 0.8]), xu=np.array([50, 1, 1.2]))
        self.current_level = current_level
        self.avg_success = avg_success
        self.avg_pain = avg_pain

    def _evaluate(self, x, out, *args, **kwargs):
        reps = x[0]
        level_diff = x[1]
        rom_mult = x[2]

        # Objective 1: Maximize Recovery (-f1 because pymoo minimizes)
        # Higher reps and higher ROM is better for recovery, assuming success is good.
        recovery_score = (reps * 0.5) + (level_diff * 10) + (rom_mult * 20)
        if self.avg_success > 0.8:
            recovery_score += 10 # Reward pushing if they are doing well

        # Objective 2: Minimize Fatigue/Pain (f2)
        # Higher reps and level increase fatigue. High pain from previous sessions penalizes high reps.
        fatigue_score = (reps * 0.3) + (level_diff * 15)
        if self.avg_pain > 5:
            fatigue_score += (self.avg_pain * 5) # Heavy penalty for pain
        if self.avg_success < 0.5:
            fatigue_score += 20 # Penalty for being too hard

        # Objective 3: Maximize Engagement (-f3)
        # Avoid stagnation: if level diff is 0 and success is high, penalize.
        engagement_score = abs(level_diff) * 5
        if self.avg_success > 0.8 and level_diff <= 0:
            engagement_score -= 10 # Should have increased difficulty

        out["F"] = [-recovery_score, fatigue_score, -engagement_score]

def calculate_next_prescription(past_sessions):
    """
    past_sessions: dict containing stats per game.
    e.g. {'potion': {'avg_success': 0.85, 'avg_pain': 2, 'current_level': 1}}
    """
    plan = {}
    for game, stats in past_sessions.items():
        problem = RehabOptimizationProblem(
            current_level=stats.get('current_level', 1),
            avg_success=stats.get('avg_success', 1.0),
            avg_pain=stats.get('avg_pain', 0)
        )
        
        algorithm = NSGA2(
            pop_size=40,
            n_offsprings=10,
            sampling=FloatRandomSampling(),
            crossover=SBX(prob=0.9, eta=15),
            mutation=PM(eta=20),
            eliminate_duplicates=True
        )

        res = minimize(problem, algorithm, ('n_gen', 40), seed=1, verbose=False)
        
        # Select the best trade-off (e.g. the one that balances all 3 best)
        # For simplicity, pick the solution with the lowest combined normalized score (Euclidean distance to ideal [min, min, min])
        F = res.F
        weights = np.array([0.4, 0.4, 0.2]) # Prioritize recovery and fatigue over engagement slightly
        
        if F is not None and len(F) > 0:
            # Normalize F
            F_min = F.min(axis=0)
            F_max = F.max(axis=0)
            range_F = F_max - F_min
            range_F[range_F == 0] = 1 # avoid div by zero
            F_norm = (F - F_min) / range_F
            
            # Find best index based on weights
            weighted_F = F_norm * weights
            best_idx = np.argmin(np.sum(weighted_F, axis=1))
            
            best_x = res.X[best_idx]
            reps = int(round(best_x[0]))
            level_diff = int(round(best_x[1]))
            rom_mult = float(best_x[2])
            
            # Constraints check
            new_level = max(1, stats.get('current_level', 1) + level_diff)
            
            plan[game] = {
                "reps": reps,
                "level": new_level,
                "target_rom": rom_mult # Multiplier for baseline or max_rom
            }
        else:
            # Fallback
            plan[game] = {"reps": 15, "level": stats.get('current_level', 1), "target_rom": 1.0}
            
    return plan
