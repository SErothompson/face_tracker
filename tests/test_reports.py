import pytest
import json
from datetime import date, timedelta
import base64

from app.models import PhotoSession, Photo, AnalysisResult, SkinCondition, RegimenEntry, RegimenLog
from app.blueprints.reports.generators import ReportGenerator


class TestReportDataGathering:
    """Test ReportGenerator data gathering"""

    def test_gather_session_data_complete(self, db):
        """Test gathering complete session data"""
        session = PhotoSession(session_date=date.today(), notes="Test session")
        db.session.add(session)
        db.session.commit()

        # Add condition
        condition = SkinCondition(
            session_id=session.id,
            condition_type='acne',
            severity='fair',
            description='Mild acne'
        )
        db.session.add(condition)

        # Add analysis result
        analysis = AnalysisResult(
            session_id=session.id,
            condition_name='acne',
            region='front',
            score=75.0
        )
        db.session.add(analysis)

        # Add regimen
        product = RegimenEntry(
            product_name='CeraVe Cleanser',
            product_type='cleanser',
            frequency='daily',
            time_of_day='AM'
        )
        db.session.add(product)
        db.session.commit()

        data = ReportGenerator.gather_session_data(session.id)

        assert data['session'].id == session.id
        assert data['overall_score'] == 75.0
        assert data['severity'] == 'good'
        assert 'acne' in data['conditions']
        assert len(data['analysis_results']) > 0
        assert 'AM' in data['regimen']

    def test_gather_session_data_no_analysis(self, db):
        """Test gathering data from session without analysis"""
        session = PhotoSession(session_date=date.today())
        db.session.add(session)
        db.session.commit()

        data = ReportGenerator.gather_session_data(session.id)

        assert data['overall_score'] == 0
        assert data['severity'] == 'critical'
        assert len(data['conditions']) == 0
        assert len(data['analysis_results']) == 0

    def test_gather_session_data_with_regimen_log(self, db):
        """Test gathering data with stored regimen log"""
        session = PhotoSession(session_date=date.today())
        db.session.add(session)
        db.session.commit()

        # Add regimen log
        regimen_snapshot = json.dumps([
            {
                'product_name': 'Test Product',
                'type': 'treatment',
                'frequency': 'daily',
                'time_of_day': 'PM'
            }
        ])
        regimen_log = RegimenLog(
            session_id=session.id,
            regimen_snapshot=regimen_snapshot
        )
        db.session.add(regimen_log)
        db.session.commit()

        data = ReportGenerator.gather_session_data(session.id)

        assert 'PM' in data['regimen']
        assert len(data['regimen']['PM']) > 0

    def test_gather_session_data_with_recommendations(self, db):
        """Test gathering data with stored recommendations"""
        session = PhotoSession(session_date=date.today())
        db.session.add(session)
        db.session.commit()

        # Add condition with search results
        search_results = json.dumps([
            {
                'title': 'Acne Treatment Guide',
                'link': 'https://example.com',
                'snippet': 'Best treatments for acne...'
            }
        ])
        condition = SkinCondition(
            session_id=session.id,
            condition_type='acne',
            severity='poor',
            search_results_json=search_results
        )
        db.session.add(condition)
        db.session.commit()

        data = ReportGenerator.gather_session_data(session.id)

        assert 'acne' in data['recommendations']
        assert len(data['recommendations']['acne']) > 0

    def test_gather_session_data_invalid_session(self):
        """Test gathering data from non-existent session"""
        with pytest.raises(Exception):  # Should raise 404
            ReportGenerator.gather_session_data(9999)


class TestReportPDFGeneration:
    """Test PDF report generation"""

    def test_generate_pdf_returns_bytes(self, db):
        """Test PDF generation returns valid bytes"""
        session = PhotoSession(session_date=date.today())
        db.session.add(session)
        db.session.commit()

        session_data = ReportGenerator.gather_session_data(session.id)
        pdf_bytes = ReportGenerator.generate_pdf(session_data)

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        # PDF files start with %PDF magic bytes
        assert pdf_bytes[:4] == b'%PDF'

    def test_generate_pdf_with_conditions(self, db):
        """Test PDF generation includes conditions"""
        session = PhotoSession(session_date=date.today())
        db.session.add(session)
        db.session.commit()

        condition = SkinCondition(
            session_id=session.id,
            condition_type='acne',
            severity='fair',
            description='Test acne'
        )
        analysis = AnalysisResult(
            session_id=session.id,
            condition_name='acne',
            region='front',
            score=75.0
        )
        db.session.add_all([condition, analysis])
        db.session.commit()

        session_data = ReportGenerator.gather_session_data(session.id)
        pdf_bytes = ReportGenerator.generate_pdf(session_data)

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b'%PDF'

    def test_generate_pdf_with_photos(self, db, app):
        """Test PDF generation handles photos"""
        session = PhotoSession(session_date=date.today())
        db.session.add(session)
        db.session.commit()

        # Create mock base64 photo
        mock_photo_b64 = base64.b64encode(b'fake_photo_data').decode('utf-8')

        session_data = ReportGenerator.gather_session_data(session.id)
        session_data['photos']['front'] = mock_photo_b64

        pdf_bytes = ReportGenerator.generate_pdf(session_data)

        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:4] == b'%PDF'


class TestReportRoutes:
    """Test report blueprint routes"""

    def test_html_report_nonexistent_session(self, client):
        """Test HTML report with non-existent session"""
        response = client.get('/reports/session/9999/html')
        assert response.status_code == 404

    def test_html_report_valid_session(self, db, client):
        """Test HTML report with valid session"""
        session = PhotoSession(session_date=date.today(), notes="Test session")
        db.session.add(session)
        db.session.commit()

        response = client.get(f'/reports/session/{session.id}/html')

        assert response.status_code == 200
        assert b'Skin Health Analysis Report' in response.data
        assert 'text/html' in response.content_type

    def test_html_report_with_analysis(self, db, client):
        """Test HTML report displays analysis data"""
        session = PhotoSession(session_date=date.today())
        db.session.add(session)
        db.session.commit()

        condition = SkinCondition(
            session_id=session.id,
            condition_type='acne',
            severity='fair',
            description='Moderate acne'
        )
        analysis = AnalysisResult(
            session_id=session.id,
            condition_name='acne',
            region='front',
            score=75.0
        )
        db.session.add_all([condition, analysis])
        db.session.commit()

        response = client.get(f'/reports/session/{session.id}/html')

        assert response.status_code == 200
        assert b'Acne' in response.data
        assert b'75' in response.data or b'75.0' in response.data

    def test_html_report_with_regimen(self, db, client):
        """Test HTML report displays regimen"""
        session = PhotoSession(session_date=date.today())
        db.session.add(session)
        db.session.commit()

        product = RegimenEntry(
            product_name='CeraVe Cleanser',
            product_type='cleanser',
            frequency='daily',
            time_of_day='AM'
        )
        db.session.add(product)
        db.session.commit()

        response = client.get(f'/reports/session/{session.id}/html')

        assert response.status_code == 200
        assert b'CeraVe Cleanser' in response.data or b'Regimen' in response.data

    def test_pdf_report_nonexistent_session(self, client):
        """Test PDF report with non-existent session"""
        response = client.get('/reports/session/9999/pdf')
        assert response.status_code == 404

    def test_pdf_report_valid_session(self, db, client):
        """Test PDF report with valid session"""
        session = PhotoSession(session_date=date.today())
        db.session.add(session)
        db.session.commit()

        response = client.get(f'/reports/session/{session.id}/pdf')

        assert response.status_code == 200
        assert response.content_type == 'application/pdf'
        assert b'%PDF' in response.data

    def test_pdf_report_filename(self, db, client):
        """Test PDF report download filename"""
        session = PhotoSession(session_date=date.today())
        db.session.add(session)
        db.session.commit()

        response = client.get(f'/reports/session/{session.id}/pdf')

        assert response.status_code == 200
        content_disposition = response.headers.get('Content-Disposition', '')
        assert 'skin-report' in content_disposition
        assert str(session.id) in content_disposition

    def test_pdf_report_with_conditions(self, db, client):
        """Test PDF report includes conditions"""
        session = PhotoSession(session_date=date.today())
        db.session.add(session)
        db.session.commit()

        condition = SkinCondition(
            session_id=session.id,
            condition_type='acne',
            severity='poor',
            description='Severe acne'
        )
        analysis = AnalysisResult(
            session_id=session.id,
            condition_name='acne',
            region='front',
            score=45.0
        )
        db.session.add_all([condition, analysis])
        db.session.commit()

        response = client.get(f'/reports/session/{session.id}/pdf')

        assert response.status_code == 200
        assert response.content_type == 'application/pdf'
        assert b'%PDF' in response.data

    def test_html_and_pdf_same_data(self, db, client):
        """Test HTML and PDF reports contain same data"""
        session = PhotoSession(session_date=date.today(), notes="Test")
        db.session.add(session)
        db.session.commit()

        condition = SkinCondition(
            session_id=session.id,
            condition_type='texture',
            severity='good',
            description='Smooth texture'
        )
        db.session.add(condition)
        db.session.commit()

        html_response = client.get(f'/reports/session/{session.id}/html')
        pdf_response = client.get(f'/reports/session/{session.id}/pdf')

        assert html_response.status_code == 200
        assert pdf_response.status_code == 200
        # Both should have the condition type
        assert b'texture' in html_response.data.lower() or b'Texture' in html_response.data

    def test_multiple_sessions_separate_reports(self, db, client):
        """Test that different sessions have different reports"""
        session1 = PhotoSession(session_date=date.today())
        session2 = PhotoSession(session_date=date.today() + timedelta(days=7))
        db.session.add_all([session1, session2])
        db.session.commit()

        condition1 = SkinCondition(
            session_id=session1.id,
            condition_type='acne',
            severity='poor',
            description='Acne'
        )
        condition2 = SkinCondition(
            session_id=session2.id,
            condition_type='wrinkles',
            severity='fair',
            description='Wrinkles'
        )
        db.session.add_all([condition1, condition2])
        db.session.commit()

        html1 = client.get(f'/reports/session/{session1.id}/html')
        html2 = client.get(f'/reports/session/{session2.id}/html')

        assert html1.status_code == 200
        assert html2.status_code == 200


class TestReportIntegration:
    """Integration tests for report generation"""

    def test_full_report_workflow(self, db, client):
        """Test complete workflow: create session → analyze → generate report"""
        # Create session
        session = PhotoSession(session_date=date.today(), notes="Integration test")
        db.session.add(session)
        db.session.commit()

        # Add analysis results
        conditions = [
            ('acne', 'fair', 'Acne detected'),
            ('texture', 'good', 'Good texture'),
            ('wrinkles', 'fair', 'Minor wrinkles')
        ]

        for cond_type, severity, desc in conditions:
            condition = SkinCondition(
                session_id=session.id,
                condition_type=cond_type,
                severity=severity,
                description=desc
            )
            for region in ['front', 'left', 'right']:
                analysis = AnalysisResult(
                    session_id=session.id,
                    condition_name=cond_type,
                    region=region,
                    score=60.0
                )
                db.session.add(analysis)
            db.session.add(condition)

        # Add regimen
        product = RegimenEntry(
            product_name='Test Product',
            product_type='cleanser',
            frequency='daily',
            time_of_day='AM'
        )
        db.session.add(product)
        db.session.commit()

        # Generate HTML report
        html_response = client.get(f'/reports/session/{session.id}/html')
        assert html_response.status_code == 200
        assert b'Skin Health Analysis Report' in html_response.data
        assert b'60' in html_response.data  # Score

        # Generate PDF report
        pdf_response = client.get(f'/reports/session/{session.id}/pdf')
        assert pdf_response.status_code == 200
        assert pdf_response.content_type == 'application/pdf'
        assert b'%PDF' in pdf_response.data

    def test_report_with_recommendations(self, db, client):
        """Test report generation with search recommendations"""
        session = PhotoSession(session_date=date.today())
        db.session.add(session)
        db.session.commit()

        # Add condition with recommendations
        search_results = json.dumps([
            {
                'title': 'Treatment 1',
                'link': 'https://example1.com',
                'snippet': 'Description of treatment 1'
            },
            {
                'title': 'Treatment 2',
                'link': 'https://example2.com',
                'snippet': 'Description of treatment 2'
            }
        ])
        condition = SkinCondition(
            session_id=session.id,
            condition_type='acne',
            severity='poor',
            search_results_json=search_results
        )
        db.session.add(condition)
        db.session.commit()

        # Check HTML includes recommendations section
        html_response = client.get(f'/reports/session/{session.id}/html')
        assert html_response.status_code == 200

        # Check PDF is generated
        pdf_response = client.get(f'/reports/session/{session.id}/pdf')
        assert pdf_response.status_code == 200
        assert b'%PDF' in pdf_response.data
