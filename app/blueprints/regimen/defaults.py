from datetime import date
from app.models import RegimenEntry
from app.extensions import db


REGIMEN_SEED_DATA = [
    # AM Routine (4 products)
    {
        "product_name": "CeraVe Hydrating Cleanser",
        "product_type": "Cleanser",
        "frequency": "Daily",
        "time_of_day": "AM",
        "notes": "Gentle milk cleanser, twice daily",
    },
    {
        "product_name": "Neutrogena Hydro Boost",
        "product_type": "Serum",
        "frequency": "Daily",
        "time_of_day": "AM",
        "notes": "Hyaluronic acid serum for hydration",
    },
    {
        "product_name": "CeraVe Moisturizing Cream (AM)",
        "product_type": "Moisturizer",
        "frequency": "Daily",
        "time_of_day": "AM",
        "notes": "Lightweight moisturizer with ceramides",
    },
    {
        "product_name": "EltaMD SPF 46",
        "product_type": "SPF/Sunscreen",
        "frequency": "Daily",
        "time_of_day": "AM",
        "notes": "Daily mineral sunscreen, essential for UV protection",
    },
    # PM Routine (3 products)
    {
        "product_name": "CeraVe Cleanser (PM)",
        "product_type": "Cleanser",
        "frequency": "Daily",
        "time_of_day": "PM",
        "notes": "Gentle cleanser to remove makeup and daily buildup",
    },
    {
        "product_name": "CeraVe Retinol Serum",
        "product_type": "Treatment",
        "frequency": "Daily",
        "time_of_day": "PM",
        "notes": "Retinol 0.3% for anti-aging, start 2-3x/week if new",
    },
    {
        "product_name": "CeraVe Moisturizing Cream (PM)",
        "product_type": "Moisturizer",
        "frequency": "Daily",
        "time_of_day": "PM",
        "notes": "Richer moisturizer for nighttime repair",
    },
    # Weekly Treatments (3 products)
    {
        "product_name": "CeraVe SA Cleanser",
        "product_type": "Exfoliant",
        "frequency": "2x/Week",
        "time_of_day": "Anytime",
        "notes": "Salicylic acid cleanser for exfoliation, 2x weekly max",
    },
    {
        "product_name": "The Ordinary AHA+BHA Peeling Solution",
        "product_type": "Treatment",
        "frequency": "Weekly",
        "time_of_day": "PM",
        "notes": "Chemical exfoliant peel, once weekly for 10 minutes",
    },
    {
        "product_name": "Freeman Clay Mask",
        "product_type": "Mask",
        "frequency": "Weekly",
        "time_of_day": "Anytime",
        "notes": "Charcoal clay mask for deep cleaning, 1x weekly",
    },
]


def seed_regimen():
    """
    Seed the database with the user's current skincare regimen.

    Only imports products if the database is empty (prevents duplicates).
    Products are marked as started today.
    """
    # Check if products already exist
    existing_count = RegimenEntry.query.count()
    if existing_count > 0:
        print(f"Regimen already seeded ({existing_count} products exist). Skipping.")
        return

    print(f"Seeding {len(REGIMEN_SEED_DATA)} skincare products...")

    for product_data in REGIMEN_SEED_DATA:
        entry = RegimenEntry(
            product_name=product_data["product_name"],
            product_type=product_data["product_type"],
            frequency=product_data["frequency"],
            time_of_day=product_data["time_of_day"],
            started_on=date.today(),
            notes=product_data.get("notes", ""),
        )
        db.session.add(entry)

    try:
        db.session.commit()
        print(f"✓ Successfully seeded {len(REGIMEN_SEED_DATA)} products")
    except Exception as e:
        db.session.rollback()
        print(f"✗ Error seeding regimen: {str(e)}")
        raise
