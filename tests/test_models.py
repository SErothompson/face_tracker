import json
from datetime import date

from app.models import (
    AnalysisResult,
    ComparisonResult,
    Photo,
    PhotoSession,
    RegimenEntry,
    RegimenLog,
    SkinCondition,
)


def test_create_photo_session(db):
    session = PhotoSession(session_date=date(2026, 3, 17), notes="First session")
    db.session.add(session)
    db.session.commit()

    result = PhotoSession.query.first()
    assert result is not None
    assert result.session_date == date(2026, 3, 17)
    assert result.notes == "First session"


def test_photo_session_with_photos(db):
    session = PhotoSession(session_date=date(2026, 3, 17))
    db.session.add(session)
    db.session.flush()

    for angle in ("front", "left", "right"):
        photo = Photo(
            session_id=session.id,
            angle=angle,
            filename=f"{angle}.jpg",
            filepath=f"abc123/{angle}.jpg",
        )
        db.session.add(photo)

    db.session.commit()

    result = PhotoSession.query.first()
    assert len(result.photos) == 3
    angles = {p.angle for p in result.photos}
    assert angles == {"front", "left", "right"}


def test_cascade_delete_session(db):
    session = PhotoSession(session_date=date(2026, 3, 17))
    db.session.add(session)
    db.session.flush()

    photo = Photo(
        session_id=session.id,
        angle="front",
        filename="front.jpg",
        filepath="abc/front.jpg",
    )
    db.session.add(photo)
    db.session.commit()

    assert Photo.query.count() == 1
    db.session.delete(session)
    db.session.commit()
    assert Photo.query.count() == 0


def test_analysis_result(db):
    session = PhotoSession(session_date=date(2026, 3, 17))
    db.session.add(session)
    db.session.flush()

    ar = AnalysisResult(
        session_id=session.id,
        condition_name="acne",
        region="forehead",
        score=75.5,
        details_json=json.dumps({"blob_count": 3}),
    )
    db.session.add(ar)
    db.session.commit()

    result = AnalysisResult.query.first()
    assert result.condition_name == "acne"
    assert result.score == 75.5
    details = json.loads(result.details_json)
    assert details["blob_count"] == 3


def test_skin_condition(db):
    session = PhotoSession(session_date=date(2026, 3, 17))
    db.session.add(session)
    db.session.flush()

    sc = SkinCondition(
        session_id=session.id,
        condition_type="acne",
        severity="mild",
        description="Minor acne detected",
    )
    db.session.add(sc)
    db.session.commit()

    result = SkinCondition.query.first()
    assert result.severity == "mild"


def test_regimen_entry(db):
    entry = RegimenEntry(
        product_name="CeraVe Hydrating Facial Cleanser",
        product_type="cleanser",
        frequency="daily",
        time_of_day="morning",
        started_on=date(2026, 1, 1),
    )
    db.session.add(entry)
    db.session.commit()

    result = RegimenEntry.query.first()
    assert result.product_name == "CeraVe Hydrating Facial Cleanser"
    assert result.ended_on is None


def test_regimen_log(db):
    session = PhotoSession(session_date=date(2026, 3, 17))
    db.session.add(session)
    db.session.flush()

    log = RegimenLog(
        session_id=session.id,
        log_date=date(2026, 3, 17),
        regimen_snapshot=json.dumps([{"product": "CeraVe Cleanser"}]),
    )
    db.session.add(log)
    db.session.commit()

    result = RegimenLog.query.first()
    snapshot = json.loads(result.regimen_snapshot)
    assert len(snapshot) == 1


def test_comparison_result(db):
    s1 = PhotoSession(session_date=date(2026, 3, 10))
    s2 = PhotoSession(session_date=date(2026, 3, 17))
    db.session.add_all([s1, s2])
    db.session.flush()

    cr = ComparisonResult(
        session_a_id=s1.id,
        session_b_id=s2.id,
        angle="front",
        ssim_score=0.92,
        changes_summary="Minor improvements in acne",
    )
    db.session.add(cr)
    db.session.commit()

    result = ComparisonResult.query.first()
    assert result.ssim_score == 0.92
    assert result.session_a.session_date == date(2026, 3, 10)
    assert result.session_b.session_date == date(2026, 3, 17)


def test_dashboard_route(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Dashboard" in response.data
