import json
import time
from duckduckgo_search import DDGS
from app.models import RegimenEntry

# Condition-to-ingredient mappings for smart recommendations
CONDITION_INGREDIENTS = {
    "acne": ["salicylic acid", "BHA", "benzoyl peroxide", "niacinamide"],
    "texture": ["AHA", "glycolic acid", "lactic acid", "chemical exfoliant"],
    "dark_spots": ["vitamin C", "kojic acid", "azelaic acid", "retinol"],
    "wrinkles": ["retinol", "retinoids", "peptides", "hyaluronic acid"],
    "redness": ["niacinamide", "centella asiatica", "zinc", "ceramides"],
    "under_eye": ["caffeine", "peptides", "hyaluronic acid", "vitamin K"]
}

# Product suggestions by condition
PRODUCT_SUGGESTIONS = {
    "acne": "Add a BHA cleanser or toner (salicylic acid 2%), use daily",
    "texture": "Add a gentle AHA exfoliant (glycolic or lactic acid), 2-3x/week",
    "dark_spots": "Add Vitamin C serum (15-20% L-ascorbic acid), AM only",
    "wrinkles": "Use retinol nightly, start 0.3% and gradually increase",
    "redness": "Add niacinamide serum (4-5%) to calm inflammation",
    "under_eye": "Use caffeine eye cream or peptide eye serum twice daily"
}


class SkinRemedySearcher:
    """Search for skincare remedies and generate recommendations."""

    def __init__(self):
        self.ddgs = DDGS()

    def search_condition_remedies(self, condition_name, max_results=5):
        """
        Search DuckDuckGo for remedies for a skin condition.

        Args:
            condition_name: e.g., "acne", "dark_spots"
            max_results: Number of results to fetch (default 5)

        Returns:
            list: [{title, link, snippet}, ...]
        """
        query = f"{condition_name} skincare treatment remedies dermatologist"

        try:
            results = []
            for result in self.ddgs.text(query, max_results=max_results):
                results.append({
                    "title": result.get("title", ""),
                    "link": result.get("href", ""),
                    "snippet": result.get("body", "")[:200]  # Limit snippet
                })

            return results
        except Exception as e:
            print(f"Search error for {condition_name}: {e}")
            return []

    def parse_search_results(self, ddgs_results):
        """
        Format DuckDuckGo results for storage and display.

        Args:
            ddgs_results: List of search result dicts

        Returns:
            str: JSON string of formatted results
        """
        return json.dumps(ddgs_results)

    def suggest_ingredients_for_condition(self, condition_name, regimen_products):
        """
        Check if key ingredients exist in current regimen.

        Args:
            condition_name: Condition type
            regimen_products: List of RegimenEntry objects

        Returns:
            dict: {missing_ingredients: [...], present: [...]}
        """
        if condition_name not in CONDITION_INGREDIENTS:
            return {"missing": [], "present": []}

        key_ingredients = CONDITION_INGREDIENTS[condition_name]
        regimen_text = " ".join([
            f"{p.product_name} {p.notes or ''}".lower()
            for p in regimen_products
        ])

        missing = []
        present = []

        for ingredient in key_ingredients:
            if ingredient.lower() in regimen_text:
                present.append(ingredient)
            else:
                missing.append(ingredient)

        return {"missing": missing, "present": present}

    def get_regimen_suggestions(self, session_id, conditions_by_type, regimen_products):
        """
        Generate rule-based regimen suggestions based on detected conditions.

        Args:
            session_id: PhotoSession ID
            conditions_by_type: Dict of SkinCondition objects keyed by condition_type
            regimen_products: List of active RegimenEntry objects

        Returns:
            dict: {condition_name: suggestion_text, ...}
        """
        suggestions = {}

        for condition_name, condition_obj in conditions_by_type.items():
            # Only suggest for poor conditions (score < 60)
            if condition_obj.severity in ["poor", "critical"]:
                # Check if ingredients are missing
                ingredient_check = self.suggest_ingredients_for_condition(
                    condition_name,
                    regimen_products
                )

                if ingredient_check["missing"]:
                    # Generate suggestion
                    base_suggestion = PRODUCT_SUGGESTIONS.get(
                        condition_name,
                        f"Consider adding a product with {', '.join(ingredient_check['missing'][:2])}"
                    )
                    suggestions[condition_name] = {
                        "suggestion": base_suggestion,
                        "missing_ingredients": ingredient_check["missing"],
                        "has_ingredients": ingredient_check["present"]
                    }

        return suggestions

    def get_all_recommendations(self, session_id, conditions_list, regimen_products):
        """
        Get complete recommendations: search results + suggestions.

        Args:
            session_id: PhotoSession ID
            conditions_list: List of SkinCondition objects
            regimen_products: List of RegimenEntry objects

        Returns:
            dict: {condition_name: {search_results, suggestion}, ...}
        """
        recommendations = {}

        for condition in conditions_list:
            # Get search results
            search_results = []
            try:
                search_results = self.search_condition_remedies(condition.condition_type)
                time.sleep(0.5)  # Rate limiting
            except Exception as e:
                print(f"Error searching for {condition.condition_type}: {e}")

            # Get suggestion
            suggestions = self.get_regimen_suggestions(
                session_id,
                {condition.condition_type: condition},
                regimen_products
            )

            recommendation = {
                "search_results": search_results,
                "suggestion": suggestions.get(condition.condition_type),
                "condition": condition.condition_type,
                "severity": condition.severity
            }

            recommendations[condition.condition_type] = recommendation

        return recommendations
