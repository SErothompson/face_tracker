from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from datetime import datetime, date

from app.models import RegimenEntry
from app.extensions import db

regimen_bp = Blueprint(
    "regimen",
    __name__,
    url_prefix="/regimen",
    template_folder="templates",
)


@regimen_bp.route("/", methods=["GET"])
def list_regimen():
    """
    List all skincare products organized by time of use.

    Returns:
        Rendered template with products grouped by AM/PM/weekly
    """
    # Get all active regimen entries (ended_on is NULL)
    active_entries = RegimenEntry.query.filter(
        RegimenEntry.ended_on == None
    ).order_by(RegimenEntry.time_of_day, RegimenEntry.product_name).all()

    # Get all inactive entries for history display (optional)
    inactive_entries = RegimenEntry.query.filter(
        RegimenEntry.ended_on != None
    ).order_by(RegimenEntry.ended_on.desc()).all()

    # Group active entries into 4 sections matching the regimen structure:
    # Morning Routine, Evening Routine, Weekly Treatments, Supplementary
    am_routine = []
    pm_routine = []
    weekly_treatments = []
    supplementary = []

    for entry in active_entries:
        freq = (entry.frequency or "").lower()
        time = entry.time_of_day or "Anytime"

        if freq in ("daily", "2x/day"):
            if time == "AM":
                am_routine.append(entry)
            elif time == "PM":
                pm_routine.append(entry)
            else:
                supplementary.append(entry)
        elif freq in ("weekly", "2x/week", "3x/week", "bi-weekly"):
            weekly_treatments.append(entry)
        else:
            # "As needed" and anything else
            supplementary.append(entry)

    # Also build regimen_by_time for backward compatibility (dashboard, reports)
    regimen_by_time = {}
    for entry in active_entries:
        time = entry.time_of_day or "Anytime"
        if time not in regimen_by_time:
            regimen_by_time[time] = []
        regimen_by_time[time].append(entry)

    return render_template(
        "regimen/list.html",
        am_routine=am_routine,
        pm_routine=pm_routine,
        weekly_treatments=weekly_treatments,
        supplementary=supplementary,
        regimen_by_time=regimen_by_time,
        active_entries=active_entries,
        inactive_entries=inactive_entries,
    )


@regimen_bp.route("/add", methods=["GET", "POST"])
def add_regimen():
    """
    Add a new skincare product to the regimen.

    GET: Display form to add new product
    POST: Save new product to database

    Returns:
        Rendered form (GET) or redirect to list (POST)
    """
    if request.method == "POST":
        try:
            product_name = request.form.get("product_name", "").strip()
            product_type = request.form.get("product_type", "").strip()
            frequency = request.form.get("frequency", "daily").strip()
            time_of_day = request.form.get("time_of_day", "AM").strip()
            notes = request.form.get("notes", "").strip()

            if not product_name:
                flash("Product name is required", "error")
                return redirect(url_for("regimen.add_regimen"))

            if not product_type:
                flash("Product type is required", "error")
                return redirect(url_for("regimen.add_regimen"))

            # Create new entry
            entry = RegimenEntry(
                product_name=product_name,
                product_type=product_type,
                frequency=frequency,
                time_of_day=time_of_day,
                started_on=date.today(),
                notes=notes,
            )
            db.session.add(entry)
            db.session.commit()

            flash(f"Added {product_name} to regimen", "success")
            return redirect(url_for("regimen.list_regimen"))

        except Exception as e:
            db.session.rollback()
            flash(f"Error adding product: {str(e)}", "error")
            return redirect(url_for("regimen.add_regimen"))

    # GET: Show form
    product_types = [
        "Cleanser",
        "Toner",
        "Serum",
        "Eye Cream",
        "Moisturizer",
        "SPF/Sunscreen",
        "Treatment",
        "Spot Treatment",
        "Mask",
        "Exfoliant",
        "Occlusive",
        "Balm/Recovery",
        "Other",
    ]
    frequencies = [
        "Daily",
        "2x/Day",
        "2x/Week",
        "3x/Week",
        "Weekly",
        "Bi-weekly",
        "As needed",
    ]
    times = ["AM", "PM", "Anytime"]

    return render_template(
        "regimen/add.html",
        product_types=product_types,
        frequencies=frequencies,
        times=times,
    )


@regimen_bp.route("/<int:regimen_id>/edit", methods=["GET", "POST"])
def edit_regimen(regimen_id):
    """
    Edit an existing skincare product.

    GET: Display form with current product data
    POST: Save changes to database

    Args:
        regimen_id: RegimenEntry ID

    Returns:
        Rendered form (GET) or redirect to list (POST)
    """
    entry = RegimenEntry.query.get_or_404(regimen_id)

    if request.method == "POST":
        try:
            entry.product_name = request.form.get("product_name", "").strip()
            entry.product_type = request.form.get("product_type", "").strip()
            entry.frequency = request.form.get("frequency", "daily").strip()
            entry.time_of_day = request.form.get("time_of_day", "AM").strip()
            entry.notes = request.form.get("notes", "").strip()

            if not entry.product_name:
                flash("Product name is required", "error")
                return redirect(url_for("regimen.edit_regimen", regimen_id=regimen_id))

            if not entry.product_type:
                flash("Product type is required", "error")
                return redirect(url_for("regimen.edit_regimen", regimen_id=regimen_id))

            db.session.commit()
            flash(f"Updated {entry.product_name}", "success")
            return redirect(url_for("regimen.list_regimen"))

        except Exception as e:
            db.session.rollback()
            flash(f"Error updating product: {str(e)}", "error")
            return redirect(url_for("regimen.edit_regimen", regimen_id=regimen_id))

    # GET: Show form
    product_types = [
        "Cleanser",
        "Toner",
        "Serum",
        "Eye Cream",
        "Moisturizer",
        "SPF/Sunscreen",
        "Treatment",
        "Spot Treatment",
        "Mask",
        "Exfoliant",
        "Occlusive",
        "Balm/Recovery",
        "Other",
    ]
    frequencies = [
        "Daily",
        "2x/Day",
        "2x/Week",
        "3x/Week",
        "Weekly",
        "Bi-weekly",
        "As needed",
    ]
    times = ["AM", "PM", "Anytime"]

    return render_template(
        "regimen/add.html",
        entry=entry,
        product_types=product_types,
        frequencies=frequencies,
        times=times,
    )


@regimen_bp.route("/<int:regimen_id>/deactivate", methods=["POST"])
def deactivate_regimen(regimen_id):
    """
    Deactivate a skincare product (soft delete by setting end date).

    Args:
        regimen_id: RegimenEntry ID

    Returns:
        Redirect to regimen list
    """
    entry = RegimenEntry.query.get_or_404(regimen_id)

    try:
        entry.ended_on = date.today()
        db.session.commit()
        flash(f"Deactivated {entry.product_name}", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deactivating product: {str(e)}", "error")

    return redirect(url_for("regimen.list_regimen"))
