from typing import Dict


class SkinHealthScorer:
    """
    Aggregates individual condition scores into an overall skin health score.

    All individual condition scores are 0-100 where 100 = healthiest.
    Overall score follows the same scale.

    Weights:
    - Acne: 25% (most visible)
    - Texture: 20% (affects appearance significantly)
    - Dark Spots: 15% (noticeable but less urgent)
    - Wrinkles: 15% (progressive, important to track)
    - Redness: 15% (indicates active inflammation)
    - Under-Eye: 10% (localized but noticeable)
    """

    WEIGHTS = {
        "acne": 0.25,
        "texture": 0.20,
        "dark_spots": 0.15,
        "wrinkles": 0.15,
        "redness": 0.15,
        "under_eye": 0.10,
    }

    @classmethod
    def normalize_condition_score(cls, raw_score: int, condition: str) -> int:
        """
        Normalize a condition's severity score to 0-100 (where 100 = healthiest).

        Args:
            raw_score: Detector output severity (0-100 scale)
            condition: Condition name (used for reference)

        Returns:
            Normalized score 0-100 (100 = healthiest skin)
        """
        # Invert: detector gives 0-100 where higher = more severe
        # We want 0-100 where 100 = healthiest
        return max(0, min(100, 100 - raw_score))

    @classmethod
    def calculate_overall_score(cls, condition_scores: Dict[str, int]) -> int:
        """
        Calculate overall skin health score from individual condition scores.

        Args:
            condition_scores: Dict mapping condition name -> normalized score (0-100)
                             Expected keys: acne, texture, dark_spots, wrinkles, under_eye

        Returns:
            Overall skin health score (0-100, where 100 = healthiest)
        """
        total_weight = 0
        weighted_sum = 0

        for condition, weight in cls.WEIGHTS.items():
            if condition in condition_scores:
                score = condition_scores[condition]
                weighted_sum += score * weight
                total_weight += weight

        # If not all conditions provided, scale up weights to 100%
        if total_weight > 0:
            overall_score = weighted_sum / total_weight
        else:
            overall_score = 50  # Default mid-range if no scores

        return max(0, min(100, int(overall_score)))

    @classmethod
    def score_to_severity_label(cls, score: int) -> str:
        """
        Convert numeric score to human-readable severity label.

        Args:
            score: Score 0-100 (100 = healthiest)

        Returns:
            Severity label: "Excellent", "Good", "Fair", "Poor", or "Critical"
        """
        if score >= 80:
            return "Excellent"
        elif score >= 60:
            return "Good"
        elif score >= 40:
            return "Fair"
        elif score >= 20:
            return "Poor"
        else:
            return "Critical"

    @classmethod
    def score_to_badge_color(cls, score: int) -> str:
        """
        Convert numeric score to Bootstrap badge color.

        Args:
            score: Score 0-100 (100 = healthiest)

        Returns:
            Bootstrap color: "success", "info", "warning", "danger"
        """
        if score >= 60:
            return "success"
        elif score >= 40:
            return "warning"
        else:
            return "danger"
