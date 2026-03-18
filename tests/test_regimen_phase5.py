import pytest
from datetime import date

from app.models import RegimenEntry
from app.blueprints.regimen.defaults import seed_regimen, REGIMEN_SEED_DATA


class TestRegimenEntryModel:
    """Test RegimenEntry model functionality."""

    def test_regimen_entry_creation(self, db):
        """Test creating a regimen entry."""
        entry = RegimenEntry(
            product_name="CeraVe Moisturizer",
            product_type="Moisturizer",
            frequency="Daily",
            time_of_day="AM",
            started_on=date.today(),
            notes="Hydrating moisturizer with ceramides",
        )
        db.session.add(entry)
        db.session.commit()

        assert entry.id is not None
        assert entry.product_name == "CeraVe Moisturizer"
        assert entry.ended_on is None  # Active by default

    def test_regimen_entry_deactivation(self, db):
        """Test deactivating a regimen entry."""
        entry = RegimenEntry(
            product_name="Test Product",
            product_type="Cleanser",
            frequency="Daily",
            time_of_day="PM",
            started_on=date.today(),
        )
        db.session.add(entry)
        db.session.commit()

        # Deactivate product
        entry.ended_on = date.today()
        db.session.commit()

        # Query active vs inactive
        active = RegimenEntry.query.filter(RegimenEntry.ended_on == None).count()
        inactive = RegimenEntry.query.filter(RegimenEntry.ended_on != None).count()

        assert active >= 0
        assert inactive >= 1

    def test_regimen_entry_relationships(self, db, app):
        """Test that regimen entries don't require session relationship."""
        entry = RegimenEntry(
            product_name="Product",
            product_type="Treatment",
            frequency="Weekly",
            time_of_day="PM",
            started_on=date.today(),
        )
        db.session.add(entry)
        db.session.commit()

        retrieved = RegimenEntry.query.get(entry.id)
        assert retrieved is not None
        assert retrieved.product_name == "Product"


class TestRegimenSeeding:
    """Test regimen seed data functionality."""

    def test_seed_data_count(self):
        """Test that seed data contains expected products."""
        assert len(REGIMEN_SEED_DATA) == 13
        products = [p["product_name"] for p in REGIMEN_SEED_DATA]
        assert "CeraVe Hydrating Cleanser" in products
        assert "The Ordinary UV Filters SPF 45 Serum Sunscreen" in products
        assert "The Ordinary Lactic Acid 5% + HA" in products

    def test_seed_data_structure(self):
        """Test that each seed product has required fields."""
        required_keys = {"product_name", "product_type", "frequency", "time_of_day"}
        for product in REGIMEN_SEED_DATA:
            assert required_keys.issubset(product.keys())
            assert product["product_name"]
            assert product["product_type"]

    def test_seed_regimen_creates_products(self, app):
        """Test that seed_regimen() creates products in DB."""
        with app.app_context():
            initial_count = RegimenEntry.query.count()
            seed_regimen()
            final_count = RegimenEntry.query.count()

            assert final_count >= initial_count

            # Verify specific products exist
            cerave = RegimenEntry.query.filter_by(
                product_name="CeraVe Hydrating Cleanser"
            ).first()
            assert cerave is not None

    def test_seed_regimen_idempotent(self, app):
        """Test that seed_regimen() doesn't duplicate on second run."""
        with app.app_context():
            seed_regimen()
            count_1 = RegimenEntry.query.count()

            seed_regimen()
            count_2 = RegimenEntry.query.count()

            assert count_1 == count_2


class TestRegimenRoutes:
    """Test regimen management routes."""

    def test_list_regimen_page(self, client, db):
        """Test regimen list page GET."""
        response = client.get("/regimen/")
        assert response.status_code == 200
        assert b"Skincare Regimen" in response.data

    def test_add_regimen_page_get(self, client):
        """Test add regimen page GET."""
        response = client.get("/regimen/add")
        assert response.status_code == 200
        assert b"Add New Skincare Product" in response.data or b"Add Product" in response.data

    def test_add_regimen_post_success(self, client, db):
        """Test adding a product successfully."""
        response = client.post(
            "/regimen/add",
            data={
                "product_name": "Test Cleanser",
                "product_type": "Cleanser",
                "frequency": "Daily",
                "time_of_day": "AM",
                "notes": "Test product",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert b"Test Cleanser" in response.data or b"Added" in response.data

        # Verify product was saved
        product = RegimenEntry.query.filter_by(product_name="Test Cleanser").first()
        assert product is not None
        assert product.product_type == "Cleanser"

    def test_add_regimen_post_missing_name(self, client, db):
        """Test adding product without name fails."""
        response = client.post(
            "/regimen/add",
            data={
                "product_name": "",
                "product_type": "Cleanser",
                "frequency": "Daily",
                "time_of_day": "AM",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert b"required" in response.data.lower() or b"error" in response.data.lower()

    def test_add_regimen_post_missing_type(self, client, db):
        """Test adding product without type fails."""
        response = client.post(
            "/regimen/add",
            data={
                "product_name": "Test Product",
                "product_type": "",
                "frequency": "Daily",
                "time_of_day": "AM",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert b"required" in response.data.lower() or b"error" in response.data.lower()

    def test_edit_regimen_get(self, client, db):
        """Test edit regimen page GET."""
        entry = RegimenEntry(
            product_name="Product to Edit",
            product_type="Treatment",
            frequency="Weekly",
            time_of_day="PM",
            started_on=date.today(),
        )
        db.session.add(entry)
        db.session.commit()

        response = client.get(f"/regimen/{entry.id}/edit")
        assert response.status_code == 200
        assert b"Product to Edit" in response.data

    def test_edit_regimen_post(self, client, db):
        """Test editing a product."""
        entry = RegimenEntry(
            product_name="Original Name",
            product_type="Cleanser",
            frequency="Daily",
            time_of_day="AM",
            started_on=date.today(),
        )
        db.session.add(entry)
        db.session.commit()

        response = client.post(
            f"/regimen/{entry.id}/edit",
            data={
                "product_name": "Updated Name",
                "product_type": "Moisturizer",
                "frequency": "Daily",
                "time_of_day": "PM",
                "notes": "Updated notes",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert b"Updated" in response.data or b"success" in response.data.lower()

        # Verify change was saved
        updated = RegimenEntry.query.get(entry.id)
        assert updated.product_name == "Updated Name"
        assert updated.product_type == "Moisturizer"
        assert updated.time_of_day == "PM"

    def test_deactivate_regimen(self, client, db):
        """Test deactivating a product."""
        entry = RegimenEntry(
            product_name="Product to Deactivate",
            product_type="Sunscreen",
            frequency="Daily",
            time_of_day="AM",
            started_on=date.today(),
        )
        db.session.add(entry)
        db.session.commit()

        response = client.post(
            f"/regimen/{entry.id}/deactivate",
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert b"Deactivated" in response.data or b"success" in response.data.lower()

        # Verify product was deactivated
        deactivated = RegimenEntry.query.get(entry.id)
        assert deactivated.ended_on is not None

    def test_edit_nonexistent_entry(self, client):
        """Test editing non-existent entry returns 404."""
        response = client.get("/regimen/9999/edit")
        assert response.status_code == 404

    def test_deactivate_nonexistent_entry(self, client):
        """Test deactivating non-existent entry returns 404."""
        response = client.post("/regimen/9999/deactivate")
        assert response.status_code == 404


class TestRegimenIntegration:
    """Integration tests for regimen workflow."""

    def test_full_regimen_workflow(self, client, db):
        """Test complete regimen management workflow."""
        # 1. Add product
        response = client.post(
            "/regimen/add",
            data={
                "product_name": "Integration Test Product",
                "product_type": "Serum",
                "frequency": "Daily",
                "time_of_day": "AM",
                "notes": "Testing integration",
            },
            follow_redirects=True,
        )
        assert b"Added" in response.data or b"Integration Test Product" in response.data

        # 2. Verify product in list
        response = client.get("/regimen/")
        assert b"Integration Test Product" in response.data

        # 3. Edit product
        product = RegimenEntry.query.filter_by(
            product_name="Integration Test Product"
        ).first()
        assert product is not None

        response = client.post(
            f"/regimen/{product.id}/edit",
            data={
                "product_name": "Integration Test Updated",
                "product_type": "Serum",
                "frequency": "2x/Day",
                "time_of_day": "AM",
                "notes": "Updated",
            },
            follow_redirects=True,
        )
        assert b"Updated" in response.data or b"Integration Test Updated" in response.data

        # 4. Deactivate product
        response = client.post(
            f"/regimen/{product.id}/deactivate",
            follow_redirects=True,
        )
        assert b"Deactivated" in response.data

        # 5. Verify product is deactivated
        deactivated = RegimenEntry.query.get(product.id)
        assert deactivated.ended_on is not None

    def test_regimen_display_grouped_by_time(self, client, db):
        """Test that regimen list displays products grouped by time of day."""
        # Add AM product
        am_product = RegimenEntry(
            product_name="AM Product",
            product_type="Cleanser",
            frequency="Daily",
            time_of_day="AM",
            started_on=date.today(),
        )
        # Add PM product
        pm_product = RegimenEntry(
            product_name="PM Product",
            product_type="Moisturizer",
            frequency="Daily",
            time_of_day="PM",
            started_on=date.today(),
        )
        db.session.add_all([am_product, pm_product])
        db.session.commit()

        response = client.get("/regimen/")
        assert response.status_code == 200
        assert b"AM Product" in response.data
        assert b"PM Product" in response.data
