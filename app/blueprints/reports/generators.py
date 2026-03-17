import json
import os
import io
import base64
from app.models import PhotoSession, AnalysisResult, SkinCondition, RegimenEntry, RegimenLog


def image_to_base64(filepath):
    """Convert image file to base64 string for embedding."""
    try:
        with open(filepath, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception:
        return None


def organize_regimen(regimen_list):
    """Organize regimen by time of day."""
    organized = {
        'AM': [],
        'PM': [],
        'Treatments': []
    }

    for product in regimen_list:
        time_of_day = product.get('time_of_day', 'Treatments')
        if time_of_day not in organized:
            time_of_day = 'Treatments'
        organized[time_of_day].append(product)

    return organized


def determine_severity(score):
    """Determine severity level from score (0-100)."""
    if score >= 80:
        return 'excellent'
    elif score >= 60:
        return 'good'
    elif score >= 40:
        return 'fair'
    elif score >= 20:
        return 'poor'
    else:
        return 'critical'


class ReportGenerator:
    """Generate PDF and HTML reports from session data."""

    @staticmethod
    def gather_session_data(session_id):
        """Gather all data needed for report generation."""
        session = PhotoSession.query.get_or_404(session_id)

        # Get all photos
        photos_by_angle = {p.angle: p for p in session.photos}

        # Load and prepare photos as base64 for embedding
        photos_base64 = {}
        for angle, photo in photos_by_angle.items():
            filepath = os.path.join("uploads", photo.filepath)
            if os.path.exists(filepath):
                photos_base64[angle] = image_to_base64(filepath)
            else:
                photos_base64[angle] = None

        # Get analysis results (all regions)
        analysis_results = AnalysisResult.query.filter_by(session_id=session_id).all()

        # Get conditions
        conditions = SkinCondition.query.filter_by(session_id=session_id).all()
        conditions_by_type = {c.condition_type: c for c in conditions}

        # Calculate overall score
        scores = [r.score for r in analysis_results]
        overall_score = sum(scores) / len(scores) if scores else 0

        # Determine severity
        severity = determine_severity(overall_score)

        # Get regimen at time of session
        regimen_log = RegimenLog.query.filter_by(session_id=session_id).first()
        if regimen_log:
            try:
                regimen_snapshot = json.loads(regimen_log.regimen_snapshot)
            except:
                regimen_snapshot = []
        else:
            # Fallback: Get current active regimen
            active_regimen = RegimenEntry.query.filter(
                RegimenEntry.ended_on == None
            ).all()
            regimen_snapshot = [
                {
                    'product_name': p.product_name,
                    'type': p.product_type,
                    'frequency': p.frequency,
                    'time_of_day': p.time_of_day
                }
                for p in active_regimen
            ]

        # Get recommendations if available
        recommendations = {}
        for condition in conditions:
            if condition.search_results_json:
                try:
                    recommendations[condition.condition_type] = json.loads(
                        condition.search_results_json
                    )[:3]  # Top 3 results
                except:
                    pass

        return {
            'photos': photos_base64,
            'analysis_results': analysis_results,
            'conditions': conditions_by_type,
            'overall_score': round(overall_score, 1),
            'severity': severity,
            'regimen': organize_regimen(regimen_snapshot),
            'recommendations': recommendations,
            'session': session
        }

    @staticmethod
    def generate_pdf(session_data):
        """Generate PDF report using ReportLab."""
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Table, PageBreak, Spacer,
            Image as RLImage, TableStyle
        )
        from reportlab.lib import colors
        from datetime import datetime

        # Create PDF in memory
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, topMargin=0.5*inch)

        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2C3E50'),
            spaceAfter=6,
            alignment=1  # Center
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#34495E'),
            spaceAfter=12,
            spaceBefore=12
        )

        # Build story (list of elements)
        story = []

        # Header
        story.append(Paragraph("Skin Health Analysis Report", title_style))
        session = session_data.get('session')
        session_date = session.session_date.strftime('%B %d, %Y') if session else 'N/A'
        story.append(Paragraph(f"Session Date: {session_date}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))

        # Overall Score
        overall_score = session_data.get('overall_score', 0)
        severity = session_data.get('severity', 'unknown').upper()
        story.append(Paragraph("Overall Skin Health Score", heading_style))
        score_data = [
            [f"{overall_score}", "/ 100"],
            [severity, "Severity"]
        ]
        score_table = Table(score_data, colWidths=[2*inch, 2*inch])
        score_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (0, 0), 16),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ]))
        story.append(score_table)
        story.append(PageBreak())

        # Photos Section
        story.append(Paragraph("Analysis Photos", heading_style))
        photos = session_data.get('photos', {})
        if photos:
            photo_elements = []
            for angle in ['front', 'left', 'right']:
                if angle in photos and photos[angle]:
                    try:
                        photo_bytes = base64.b64decode(photos[angle])
                        photo_buffer = io.BytesIO(photo_bytes)
                        photo_elements.append(
                            RLImage(photo_buffer, width=1.5*inch, height=1.5*inch)
                        )
                    except:
                        photo_elements.append(
                            Paragraph(f"{angle.title()} - Photo Unavailable", styles['Normal'])
                        )
                else:
                    photo_elements.append(
                        Paragraph(f"{angle.title()} - Photo Not Found", styles['Normal'])
                    )

            if photo_elements:
                photos_table = Table([photo_elements], colWidths=[1.8*inch]*3)
                story.append(photos_table)
        story.append(PageBreak())

        # Conditions Section
        story.append(Paragraph("Detected Skin Conditions", heading_style))
        conditions = session_data.get('conditions', {})
        analysis_results = session_data.get('analysis_results', [])

        for cond_type, condition in conditions.items():
            story.append(Paragraph(f"{cond_type.title()}", styles['Heading3']))

            # Condition details
            cond_severity = condition.severity.upper()
            cond_desc = condition.description or "No description available"
            story.append(Paragraph(f"Severity: {cond_severity}", styles['Normal']))
            story.append(Paragraph(cond_desc, styles['Normal']))

            # Scores for this condition
            cond_scores = [r for r in analysis_results if r.condition_name == cond_type]
            if cond_scores:
                score_rows = [['Region', 'Score']]
                for result in cond_scores:
                    score_rows.append([result.region.title(), str(round(result.score))])

                scores_table = Table(score_rows, colWidths=[2.5*inch, 1*inch])
                scores_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495E')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 11),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ]))
                story.append(scores_table)

            story.append(Spacer(1, 0.3*inch))

        story.append(PageBreak())

        # Regimen Section
        story.append(Paragraph("Current Skincare Regimen", heading_style))
        regimen = session_data.get('regimen', {})
        for period, products in regimen.items():
            if products:
                story.append(Paragraph(f"{period} Products", styles['Heading3']))
                for product in products:
                    product_name = product.get('product_name', 'Unknown')
                    frequency = product.get('frequency', '')
                    freq_text = f" ({frequency})" if frequency else ""
                    story.append(Paragraph(f"• {product_name}{freq_text}", styles['Normal']))

        story.append(PageBreak())

        # Recommendations Section
        recommendations = session_data.get('recommendations', {})
        if recommendations:
            story.append(Paragraph("Recommended Treatments", heading_style))
            for cond_type, results in recommendations.items():
                story.append(Paragraph(f"For {cond_type.title()}", styles['Heading3']))
                for result in results:
                    title = result.get('title', 'Unknown')
                    snippet = result.get('snippet', '')[:100]
                    story.append(Paragraph(f"<b>{title}</b>", styles['Normal']))
                    if snippet:
                        story.append(Paragraph(snippet, styles['Normal']))
                story.append(Spacer(1, 0.2*inch))

        # Footer
        story.append(Spacer(1, 0.3*inch))
        footer_text = f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"
        story.append(Paragraph(footer_text, styles['Normal']))
        story.append(Paragraph(
            "⚠️ This report is for informational purposes only. "
            "Always consult with a dermatologist for professional advice.",
            styles['Normal']
        ))

        # Build PDF
        doc.build(story)
        pdf_buffer.seek(0)
        return pdf_buffer.getvalue()
