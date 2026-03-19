from datetime import date
from app.models import RegimenEntry
from app.extensions import db


REGIMEN_SEED_DATA = [
    # AM Routine (7 steps)
    {
        "product_name": "CeraVe Hydrating Cleanser",
        "product_type": "Cleanser",
        "frequency": "Daily",
        "time_of_day": "AM",
        "notes": "Massage 30 seconds, rinse with lukewarm water",
    },
    {
        "product_name": "The Ordinary Niacinamide 10% + Zinc 1%",
        "product_type": "Serum",
        "frequency": "Daily",
        "time_of_day": "AM",
        "notes": "A few drops across face; targets redness and uneven tone; niacinamide + zinc",
    },
    {
        "product_name": "The Ordinary Alpha Arbutin 2% + Hyaluronic Acid",
        "product_type": "Serum",
        "frequency": "Daily",
        "time_of_day": "AM",
        "notes": "Apply before Vitamin C, thinner water-based formula goes first; targets dark spots and uneven tone",
    },
    {
        "product_name": "The Ordinary Ascorbyl Glucoside Solution 12%",
        "product_type": "Serum",
        "frequency": "Daily",
        "time_of_day": "AM",
        "notes": "A few drops after Alpha Arbutin; antioxidant protection, brightening; stable & gentle Vitamin C",
    },
    {
        "product_name": "Neutrogena Hydro Boost Eye Cream",
        "product_type": "Eye Cream",
        "frequency": "Daily",
        "time_of_day": "AM",
        "notes": "Tap gently with ring finger, never rub",
    },
    {
        "product_name": "CeraVe Moisturizing Cream",
        "product_type": "Moisturizer",
        "frequency": "Daily",
        "time_of_day": "AM",
        "notes": "Apply evenly across face and neck; ceramides + hyaluronic acid",
    },
    {
        "product_name": "The Ordinary UV Filters SPF 45 Serum Sunscreen",
        "product_type": "SPF/Sunscreen",
        "frequency": "Daily",
        "time_of_day": "AM",
        "notes": "Final step every morning even indoors; lightweight broad-spectrum UVA/UVB, no white cast",
    },
    # PM Routine (4 steps)
    {
        "product_name": "CeraVe Hydrating Cleanser",
        "product_type": "Cleanser",
        "frequency": "Daily",
        "time_of_day": "PM",
        "notes": "Removes daily buildup, preps skin for treatment",
    },
    {
        "product_name": "RoC Retinol Correxion Line Smoothing Serum",
        "product_type": "Treatment",
        "frequency": "Daily",
        "time_of_day": "PM",
        "notes": "Start 2-3 nights/week only; builds collagen, reduces wrinkles; avoid eye area",
    },
    {
        "product_name": "Neutrogena Hydro Boost Eye Cream",
        "product_type": "Eye Cream",
        "frequency": "Daily",
        "time_of_day": "PM",
        "notes": "Store in fridge for extra depuffing effect",
    },
    {
        "product_name": "CeraVe Moisturizing Cream",
        "product_type": "Moisturizer",
        "frequency": "Daily",
        "time_of_day": "PM",
        "notes": "Slightly more generous at night while skin repairs",
    },
    # 2-3x Per Week (Evening - replace retinol on these nights)
    {
        "product_name": "The Ordinary Lactic Acid 5% + HA",
        "product_type": "Exfoliant",
        "frequency": "2x/Week",
        "time_of_day": "PM",
        "notes": "Apply after cleansing, leave 10 min, rinse off thoroughly then moisturize; never use same night as retinol",
    },
    # Supplementary / As Needed
    {
        "product_name": "The Ordinary Alpha Arbutin 2% + HA (PM)",
        "product_type": "Serum",
        "frequency": "As needed",
        "time_of_day": "PM",
        "notes": "Optional on non-retinol evenings after cleansing, before moisturizer; pairs well with Lactic Acid nights",
    },
]


def seed_regimen(user_id=None):
    """
    Seed the database with the user's current skincare regimen.

    Only imports products if the database is empty (prevents duplicates).
    Products are marked as started today.

    Args:
        user_id: Optional user ID to associate products with. If None,
                 products are created without a user association.
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
            user_id=user_id,
        )
        db.session.add(entry)

    try:
        db.session.commit()
        print(f"✓ Successfully seeded {len(REGIMEN_SEED_DATA)} products")
    except Exception as e:
        db.session.rollback()
        print(f"✗ Error seeding regimen: {str(e)}")
        raise
