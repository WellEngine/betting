from __future__ import annotations

import math
from typing import Dict


EPSILON = 1e-9
MIN_LAMBDA = 0.35


def _clamp_probability(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def poisson_pmf(lmbda: float, k: int) -> float:
    return (math.exp(-lmbda) * (lmbda ** k)) / math.factorial(k)


def poisson_cdf(lmbda: float, k: int) -> float:
    return sum(poisson_pmf(lmbda, i) for i in range(k + 1))


def calculate_totals_probabilities(*, lambda_home: float, lambda_away: float) -> Dict[str, Dict[str, float]]:
    """
    Прямой расчёт тоталов через сумму Пуассона.

    Если:
        H ~ Poisson(lambda_home)
        A ~ Poisson(lambda_away)

    Тогда:
        T = H + A ~ Poisson(lambda_home + lambda_away)
    """
    lambda_home = max(lambda_home, MIN_LAMBDA)
    lambda_away = max(lambda_away, MIN_LAMBDA)
    lambda_total = lambda_home + lambda_away

    p_under_1_5 = poisson_cdf(lambda_total, 1)
    p_under_2_5 = poisson_cdf(lambda_total, 2)
    p_under_3_5 = poisson_cdf(lambda_total, 3)

    p_over_1_5 = 1.0 - p_under_1_5
    p_over_2_5 = 1.0 - p_under_2_5

    return {
        "expected_goals": {
            "home": round(lambda_home, 3),
            "away": round(lambda_away, 3),
            "total": round(lambda_total, 3),
        },
        "totals": {
            "over_1_5": round(_clamp_probability(p_over_1_5), 4),
            "under_1_5": round(_clamp_probability(p_under_1_5), 4),
            "over_2_5": round(_clamp_probability(p_over_2_5), 4),
            "under_2_5": round(_clamp_probability(p_under_2_5), 4),
            "under_3_5": round(_clamp_probability(p_under_3_5), 4),
        },
    }
