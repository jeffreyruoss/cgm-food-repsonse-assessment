"""PDF report generation for physician exports."""
from fpdf import FPDF
from datetime import datetime
import tempfile
import os


class DoctorReportPDF(FPDF):
    """Custom PDF class for doctor's reports."""

    def header(self):
        self.set_font('Helvetica', 'B', 16)
        self.cell(0, 10, 'CGM Food Response Assessment Report', 0, 1, 'C')
        self.set_font('Helvetica', '', 10)
        self.cell(0, 5, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')


def generate_doctor_report(
    summary_stats: dict,
    crash_events: list,
    food_triggers: list = None,
    date_range: tuple = None,
    patient_notes: str = None
) -> bytes:
    """
    Generate a PDF report for physician review.

    Args:
        summary_stats: Dict with overall statistics
        crash_events: List of crash event dicts
        food_triggers: List of foods that triggered crashes
        date_range: Tuple of (start_date, end_date)
        patient_notes: Additional notes from patient

    Returns:
        PDF as bytes
    """
    pdf = DoctorReportPDF()
    pdf.add_page()

    # Date range section
    if date_range:
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Report Period', 0, 1)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, f'{date_range[0]} to {date_range[1]}', 0, 1)
        pdf.ln(5)

    # Executive Summary
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, 'Executive Summary', 0, 1)
    pdf.set_font('Helvetica', '', 10)

    total_crashes = summary_stats.get('total_crashes', 0)
    avg_duration = summary_stats.get('avg_duration', 0)
    avg_drop = summary_stats.get('avg_drop_magnitude', 0)

    summary_text = f"""
In the reporting period, the patient experienced {total_crashes} reactive hypoglycemia events.

Key Metrics:
• Total Crash Events: {total_crashes}
• Average Drop Magnitude: {avg_drop:.1f} mg/dL
• Average Event Duration: {avg_duration:.0f} minutes
• Maximum Drop: {summary_stats.get('max_drop_magnitude', 0):.1f} mg/dL
• Worst Velocity: {abs(summary_stats.get('worst_velocity', 0)):.2f} mg/dL/min
"""

    for line in summary_text.strip().split('\n'):
        pdf.cell(0, 6, line.strip(), 0, 1)
    pdf.ln(5)

    # Primary Triggers
    if food_triggers:
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Primary Food Triggers', 0, 1)
        pdf.set_font('Helvetica', '', 10)

        for i, trigger in enumerate(food_triggers[:5], 1):
            food = trigger.get('food_name', 'Unknown')
            crashes = trigger.get('crash_count', 0)
            avg_vel = abs(trigger.get('avg_velocity', 0))
            pdf.cell(0, 6, f'{i}. {food} - {crashes} crashes, avg velocity: {avg_vel:.2f} mg/dL/min', 0, 1)
        pdf.ln(5)

    # Detailed Crash Events
    if crash_events:
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Crash Event Details', 0, 1)

        # Table header
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(40, 7, 'Date/Time', 1, 0, 'C')
        pdf.cell(30, 7, 'Duration', 1, 0, 'C')
        pdf.cell(35, 7, 'Drop (mg/dL)', 1, 0, 'C')
        pdf.cell(40, 7, 'Velocity', 1, 0, 'C')
        pdf.cell(45, 7, 'Start -> End', 1, 1, 'C')

        pdf.set_font('Helvetica', '', 9)
        for event in crash_events[:15]:  # Limit to 15 events
            start_time = event.get('start_time', '')
            if hasattr(start_time, 'strftime'):
                start_time = start_time.strftime('%Y-%m-%d %I:%M %p')

            pdf.cell(40, 6, str(start_time)[:16], 1, 0, 'C')
            pdf.cell(30, 6, f"{event.get('duration_minutes', 0):.0f} min", 1, 0, 'C')
            pdf.cell(35, 6, f"{event.get('drop_magnitude', 0):.1f}", 1, 0, 'C')
            pdf.cell(40, 6, f"{abs(event.get('max_velocity', 0)):.2f} mg/dL/min", 1, 0, 'C')
            pdf.cell(45, 6, f"{event.get('start_glucose', 0):.0f} -> {event.get('end_glucose', 0):.0f}", 1, 1, 'C')

        pdf.ln(5)

    # Recommendations section
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, 'Pattern Analysis', 0, 1)
    pdf.set_font('Helvetica', '', 10)

    recommendations = [
        "• Consider evaluating for reactive hypoglycemia if crash events are frequent",
        "• High-carb, low-protein meals appear to correlate with faster glucose drops",
        "• Suggest mixed meals with adequate protein and fiber to slow glucose absorption",
        "• Patient may benefit from smaller, more frequent meals",
    ]

    for rec in recommendations:
        pdf.cell(0, 6, rec, 0, 1)
    pdf.ln(5)

    # Patient notes
    if patient_notes:
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Patient Notes', 0, 1)
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 6, patient_notes)

    # Disclaimer
    pdf.ln(10)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.multi_cell(0, 4,
        'Disclaimer: This report is generated from patient-uploaded CGM and food log data. '
        'Data accuracy depends on proper device calibration and complete food logging. '
        'This report is intended to supplement, not replace, clinical judgment.'
    )

    # Return as bytes
    return bytes(pdf.output())


def save_report_to_file(pdf_bytes: bytes, filename: str = None) -> str:
    """Save PDF bytes to a file and return the path."""
    if filename is None:
        filename = f"cgm_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    filepath = os.path.join(tempfile.gettempdir(), filename)
    with open(filepath, 'wb') as f:
        f.write(pdf_bytes)
    return filepath
