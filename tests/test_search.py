import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import date, timedelta

from app.models import PhotoSession, SkinCondition, RegimenEntry, AnalysisResult
from app.blueprints.search.client import SkinRemedySearcher


class TestSkinRemedySearcher:
    """Test SkinRemedySearcher methods"""

    def test_search_condition_remedies_acne(self):
        """Test searching for acne remedies"""
        with patch('app.blueprints.search.client.DDGS') as mock_ddgs:
            mock_instance = MagicMock()
            mock_ddgs.return_value = mock_instance
            mock_instance.text.return_value = [
                {
                    'title': 'Best Acne Treatments for Oily Skin',
                    'href': 'https://example.com/acne-treatment',
                    'body': 'Salicylic acid BHA and benzoyl peroxide are effective...'
                },
                {
                    'title': 'Dermatologist Recommended Acne Serum',
                    'href': 'https://example.com/acne-serum',
                    'body': 'Niacinamide helps reduce inflammation...'
                }
            ]

            # Create searcher AFTER patching DDGS
            searcher = SkinRemedySearcher()
            results = searcher.search_condition_remedies('acne')

            assert isinstance(results, list)
            assert len(results) > 0
            assert 'acne' in results[0]['title'].lower()

    def test_search_condition_remedies_dark_spots(self):
        """Test searching for dark spots remedies"""
        with patch('app.blueprints.search.client.DDGS') as mock_ddgs:
            mock_instance = MagicMock()
            mock_ddgs.return_value = mock_instance
            mock_instance.text.return_value = [
                {
                    'title': 'Vitamin C for Hyperpigmentation',
                    'href': 'https://example.com/vitamin-c',
                    'body': 'L-ascorbic acid is most effective form...'
                }
            ]

            searcher = SkinRemedySearcher()
            results = searcher.search_condition_remedies('dark_spots')

            assert len(results) > 0
            # Check for standard result fields
            assert 'title' in results[0]
            assert 'link' in results[0]
            assert 'snippet' in results[0]

    def test_search_condition_remedies_empty_results(self):
        """Test search with no results"""
        searcher = SkinRemedySearcher()

        with patch('app.blueprints.search.client.DDGS') as mock_ddgs:
            mock_instance = MagicMock()
            mock_ddgs.return_value = mock_instance
            mock_instance.text.return_value = []

            results = searcher.search_condition_remedies('acne')

            assert isinstance(results, list)
            assert len(results) == 0

    def test_parse_search_results_valid(self):
        """Test parsing valid search results"""
        searcher = SkinRemedySearcher()

        raw_results = [
            {
                'title': 'Best Acne Treatments',
                'href': 'https://example.com/acne',
                'body': 'Salicylic acid and benzoyl peroxide...'
            },
            {
                'title': 'Acne Prevention Tips',
                'href': 'https://example.com/prevention',
                'body': 'Keep skin clean and avoid pore-clogging products...'
            }
        ]

        parsed = searcher.parse_search_results(raw_results)

        # parse_search_results returns JSON string
        assert isinstance(parsed, str)
        recovered = json.loads(parsed)
        assert len(recovered) == 2
        assert recovered[0]['title'] == 'Best Acne Treatments'
        assert recovered[0]['href'] == 'https://example.com/acne'

    def test_parse_search_results_empty(self):
        """Test parsing empty search results"""
        searcher = SkinRemedySearcher()
        parsed = searcher.parse_search_results([])
        assert isinstance(parsed, str)
        recovered = json.loads(parsed)
        assert recovered == []

    def test_suggest_ingredients_for_condition_acne(self):
        """Test ingredient suggestions for acne"""
        searcher = SkinRemedySearcher()

        regimen = [
            RegimenEntry(product_name='CeraVe Cleanser', notes='gentle cleanser'),
            RegimenEntry(product_name='Salicylic Acid Toner', notes='BHA exfoliant')
        ]

        suggestions = searcher.suggest_ingredients_for_condition('acne', regimen)

        assert isinstance(suggestions, dict)
        assert 'missing' in suggestions or 'present' in suggestions
        assert isinstance(suggestions.get('missing', []), list)
        assert isinstance(suggestions.get('present', []), list)

    def test_suggest_ingredients_for_condition_dark_spots(self):
        """Test ingredient suggestions for dark spots"""
        searcher = SkinRemedySearcher()

        regimen = [
            RegimenEntry(product_name='CeraVe Moisturizer', notes='basic moisturizer')
        ]

        suggestions = searcher.suggest_ingredients_for_condition('dark_spots', regimen)

        # Missing vitamin C for dark spots
        assert isinstance(suggestions, dict)
        missing = suggestions.get('missing', [])
        # Should have missing ingredients since we lack vitamin C
        assert len(missing) > 0
        # Vitamin C should be in the missing list
        vitamin_c_found = any('vitamin c' in ing.lower() for ing in missing)
        assert vitamin_c_found

    def test_suggest_ingredients_all_conditions_mapped(self):
        """Test that all conditions have ingredient mappings"""
        searcher = SkinRemedySearcher()
        conditions = ['acne', 'texture', 'dark_spots', 'wrinkles', 'redness', 'under_eye']

        regimen = [RegimenEntry(product_name='Basic Cleanser', notes='')]

        for condition in conditions:
            suggestions = searcher.suggest_ingredients_for_condition(condition, regimen)
            assert isinstance(suggestions, dict)
            # Should have either missing or present ingredients
            assert 'missing' in suggestions or 'present' in suggestions

    def test_get_regimen_suggestions_empty_regimen(self, db):
        """Test regimen suggestions with no current products"""
        searcher = SkinRemedySearcher()
        session = PhotoSession(session_date=date.today())
        db.session.add(session)
        db.session.commit()

        # Create a condition with poor severity
        condition = SkinCondition(
            session_id=session.id,
            condition_type='acne',
            severity='poor',
            description='Test acne'
        )
        db.session.add(condition)
        db.session.commit()

        conditions_by_type = {'acne': condition}
        suggestions = searcher.get_regimen_suggestions(session.id, conditions_by_type, [])

        assert isinstance(suggestions, dict)
        # With empty regimen and poor acne, should suggest adding ingredients
        if 'acne' in suggestions:
            assert 'suggestion' in suggestions['acne']

    def test_get_regimen_suggestions_with_regimen(self, db):
        """Test regimen suggestions with existing products"""
        searcher = SkinRemedySearcher()
        session = PhotoSession(session_date=date.today())
        db.session.add(session)
        db.session.commit()

        # Create a poor acne condition
        condition = SkinCondition(
            session_id=session.id,
            condition_type='acne',
            severity='poor',
            description='Test acne'
        )
        db.session.add(condition)

        # Add a basic product (not addressing acne well)
        product = RegimenEntry(
            product_name='CeraVe Moisturizer',
            product_type='moisturizer',
            frequency='daily',
            time_of_day='AM'
        )
        db.session.add(product)
        db.session.commit()

        regimen = RegimenEntry.query.filter(RegimenEntry.ended_on == None).all()
        conditions_by_type = {'acne': condition}
        suggestions = searcher.get_regimen_suggestions(
            session.id,
            conditions_by_type,
            regimen
        )

        assert isinstance(suggestions, dict)

    def test_search_results_json_format(self):
        """Test that search results can be serialized to JSON"""
        with patch('app.blueprints.search.client.DDGS') as mock_ddgs:
            mock_instance = MagicMock()
            mock_ddgs.return_value = mock_instance
            mock_instance.text.return_value = [
                {
                    'title': 'Treatment',
                    'href': 'https://example.com',
                    'body': 'Description...'
                }
            ]

            searcher = SkinRemedySearcher()
            results = searcher.search_condition_remedies('acne')
            json_str = json.dumps(results)

            # Should be able to serialize and deserialize
            recovered = json.loads(json_str)
            assert len(recovered) == 1
            assert 'title' in recovered[0]


class TestSearchRoutes:
    """Test search blueprint routes"""

    def test_recommendations_route_nonexistent_session(self, client):
        """Test recommendations page with non-existent session"""
        response = client.get('/search/recommendations/9999')
        assert response.status_code == 404

    def test_condition_detail_route_nonexistent(self, client):
        """Test condition detail with non-existent session/condition"""
        response = client.get('/search/condition/9999/acne')
        assert response.status_code == 404
