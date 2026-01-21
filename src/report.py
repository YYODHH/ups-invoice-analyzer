"""PDF Report Generator.

Generates PDF summary reports for UPS invoice analysis.
"""

import io
from datetime import datetime
from fpdf import FPDF


class PDFReportGenerator:
    """Generate PDF reports from invoice analysis."""

    def __init__(self):
        self.pdf = None

    def generate_report(self, analyzer, charts: dict | None = None) -> bytes:
        """Generate a PDF report from analyzer data.

        Args:
            analyzer: InvoiceAnalyzer instance with data
            charts: Optional dict of Plotly figures to include

        Returns:
            PDF content as bytes
        """
        self.pdf = FPDF()
        self.pdf.set_auto_page_break(auto=True, margin=15)

        # Add pages
        self._add_title_page(analyzer)
        self._add_summary_page(analyzer)
        self._add_cost_breakdown_page(analyzer)
        self._add_destination_page(analyzer)
        self._add_returns_page(analyzer)
        self._add_top_expenses_page(analyzer)

        # Output to bytes
        return bytes(self.pdf.output())

    def _add_title_page(self, analyzer):
        """Add title page."""
        self.pdf.add_page()
        self.pdf.set_font("Helvetica", "B", 28)

        # Title
        self.pdf.set_y(80)
        self.pdf.cell(
            0,
            20,
            "UPS Invoice Analysis Report",
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )

        # Subtitle with date range
        summary = analyzer.get_summary()
        self.pdf.set_font("Helvetica", "", 14)

        if summary.date_range:
            date_range_text = (
                f"Period: {summary.date_range[0]} to {summary.date_range[1]}"
            )
        else:
            date_range_text = "Period: All dates"

        self.pdf.cell(0, 10, date_range_text, align="C", new_x="LMARGIN", new_y="NEXT")

        # Generated date
        self.pdf.set_y(self.pdf.get_y() + 20)
        self.pdf.set_font("Helvetica", "I", 10)
        self.pdf.cell(
            0,
            10,
            f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            align="C",
        )

    def _add_summary_page(self, analyzer):
        """Add summary statistics page."""
        self.pdf.add_page()
        summary = analyzer.get_summary()

        self._add_section_title("Executive Summary")

        # Key metrics table
        metrics = [
            ("Total Cost", f"{summary.total_cost:,.2f} {summary.currency}"),
            ("Total Packages", f"{summary.total_packages:,}"),
            ("Total Invoices", f"{summary.total_invoices}"),
            (
                "Average Cost per Package",
                f"{summary.avg_cost_per_package:,.2f} {summary.currency}",
            ),
            ("Total Weight", f"{summary.total_weight_kg:,.1f} kg"),
            ("Return Rate", f"{summary.return_rate:.1f}%"),
        ]

        self._add_metrics_table(metrics)

        # Cost breakdown
        self.pdf.set_y(self.pdf.get_y() + 15)
        self._add_section_title("Cost Components", level=2)

        cost_breakdown = [
            ("Freight Charges", f"{summary.total_freight:,.2f} {summary.currency}"),
            (
                "Fuel Surcharges",
                f"{summary.total_fuel_surcharge:,.2f} {summary.currency}",
            ),
            ("Tax (VAT)", f"{summary.total_tax:,.2f} {summary.currency}"),
            (
                "Accessorial Charges",
                f"{summary.total_accessorial:,.2f} {summary.currency}",
            ),
        ]

        self._add_metrics_table(cost_breakdown)

    def _add_cost_breakdown_page(self, analyzer):
        """Add detailed cost breakdown page."""
        self.pdf.add_page()
        self._add_section_title("Cost Breakdown by Charge Type")

        breakdown = analyzer.analyze_cost_breakdown()
        if breakdown.empty:
            self.pdf.set_font("Helvetica", "I", 10)
            self.pdf.cell(0, 10, "No cost data available")
            return

        # Table header
        self.pdf.set_font("Helvetica", "B", 10)
        col_widths = [60, 40, 40, 30]
        headers = ["Charge Type", "Discount", "Net Amount", "% of Total"]

        for i, header in enumerate(headers):
            self.pdf.cell(col_widths[i], 8, header, border=1, align="C")
        self.pdf.ln()

        # Table rows
        self.pdf.set_font("Helvetica", "", 10)
        summary = analyzer.get_summary()

        for _, row in breakdown.iterrows():
            self.pdf.cell(
                col_widths[0], 7, str(row["charge_category_name"])[:30], border=1
            )
            self.pdf.cell(
                col_widths[1], 7, f"{row['discount_amount']:,.2f}", border=1, align="R"
            )
            self.pdf.cell(
                col_widths[2], 7, f"{row['net_amount']:,.2f}", border=1, align="R"
            )
            self.pdf.cell(
                col_widths[3], 7, f"{row['percentage']:.1f}%", border=1, align="R"
            )
            self.pdf.ln()

    def _add_destination_page(self, analyzer):
        """Add destination analysis page."""
        self.pdf.add_page()
        self._add_section_title("Shipping by Destination")

        by_country = analyzer.analyze_by_destination()
        if by_country.empty:
            self.pdf.set_font("Helvetica", "I", 10)
            self.pdf.cell(0, 10, "No destination data available")
            return

        # Show top 15 destinations
        top_countries = by_country.head(15)

        # Table header
        self.pdf.set_font("Helvetica", "B", 9)
        col_widths = [40, 25, 35, 30, 30, 25]
        headers = [
            "Country",
            "Packages",
            "Total Cost",
            "Avg Cost",
            "Weight (kg)",
            "Return %",
        ]

        for i, header in enumerate(headers):
            self.pdf.cell(col_widths[i], 8, header, border=1, align="C")
        self.pdf.ln()

        # Table rows
        self.pdf.set_font("Helvetica", "", 9)
        summary = analyzer.get_summary()

        for _, row in top_countries.iterrows():
            country_name = str(row.get("country_name", row["country_code"]))[:20]
            self.pdf.cell(col_widths[0], 7, country_name, border=1)
            self.pdf.cell(
                col_widths[1], 7, f"{row['package_count']:,}", border=1, align="R"
            )
            self.pdf.cell(
                col_widths[2], 7, f"{row['total_cost']:,.2f}", border=1, align="R"
            )
            self.pdf.cell(
                col_widths[3],
                7,
                f"{row['avg_cost_per_package']:,.2f}",
                border=1,
                align="R",
            )
            self.pdf.cell(
                col_widths[4], 7, f"{row['total_weight']:,.1f}", border=1, align="R"
            )
            self.pdf.cell(
                col_widths[5], 7, f"{row['return_rate']:.1f}%", border=1, align="R"
            )
            self.pdf.ln()

    def _add_returns_page(self, analyzer):
        """Add returns analysis page."""
        self.pdf.add_page()
        self._add_section_title("Return Shipments Analysis")

        returns_data = analyzer.analyze_returns()
        summary_data = returns_data.get("summary", {})

        if not summary_data:
            self.pdf.set_font("Helvetica", "I", 10)
            self.pdf.cell(0, 10, "No return shipments in data")
            return

        # Return summary metrics
        metrics = [
            ("Total Returns", f"{summary_data.get('total_returns', 0):,}"),
            ("Total Return Cost", f"{summary_data.get('total_return_cost', 0):,.2f}"),
            ("Return Rate", f"{summary_data.get('return_rate', 0):.1f}%"),
            ("Average Return Cost", f"{summary_data.get('avg_return_cost', 0):,.2f}"),
        ]
        self._add_metrics_table(metrics)

        # Return types (by shipment_subtype, e.g., RTS = Return to Sender)
        by_reason = returns_data.get("by_reason", None)
        if by_reason is not None and not by_reason.empty:
            self.pdf.set_y(self.pdf.get_y() + 10)
            self._add_section_title("Return Types", level=2)

            self.pdf.set_font("Helvetica", "B", 9)
            col_widths = [100, 30, 40]
            headers = ["Type", "Count", "Total Cost"]

            for i, header in enumerate(headers):
                self.pdf.cell(col_widths[i], 8, header, border=1, align="C")
            self.pdf.ln()

            self.pdf.set_font("Helvetica", "", 9)
            for _, row in by_reason.head(10).iterrows():
                reason_text = str(row["reason"])[:55] if row["reason"] else "Unknown"
                self.pdf.cell(col_widths[0], 7, reason_text, border=1)
                self.pdf.cell(
                    col_widths[1], 7, f"{row['count']:,}", border=1, align="R"
                )
                self.pdf.cell(
                    col_widths[2], 7, f"{row['total_cost']:,.2f}", border=1, align="R"
                )
                self.pdf.ln()

    def _add_top_expenses_page(self, analyzer):
        """Add top expenses page."""
        self.pdf.add_page()
        self._add_section_title("Most Expensive Shipments")

        top_expenses = analyzer.get_top_expenses(n=15)
        if top_expenses.empty:
            self.pdf.set_font("Helvetica", "I", 10)
            self.pdf.cell(0, 10, "No shipment data available")
            return

        # Simplified table for top expenses
        self.pdf.set_font("Helvetica", "B", 8)
        col_widths = [35, 25, 30, 30, 25, 25, 20]
        headers = [
            "Tracking #",
            "Reference",
            "Recipient",
            "City",
            "Country",
            "Service",
            "Cost",
        ]

        for i, header in enumerate(headers):
            self.pdf.cell(col_widths[i], 7, header, border=1, align="C")
        self.pdf.ln()

        self.pdf.set_font("Helvetica", "", 8)
        for _, row in top_expenses.iterrows():
            tracking = (
                str(row.get("tracking_number", ""))[-12:]
                if row.get("tracking_number")
                else ""
            )
            ref = (
                str(row.get("order_reference", ""))[:12]
                if row.get("order_reference")
                else ""
            )
            recipient = (
                str(row.get("recipient_name", ""))[:15]
                if row.get("recipient_name")
                else ""
            )
            city = (
                str(row.get("recipient_city", ""))[:15]
                if row.get("recipient_city")
                else ""
            )
            country = (
                str(row.get("recipient_country", ""))[:5]
                if row.get("recipient_country")
                else ""
            )
            service = (
                str(row.get("service_name", ""))[:12] if row.get("service_name") else ""
            )

            self.pdf.cell(col_widths[0], 6, tracking, border=1)
            self.pdf.cell(col_widths[1], 6, ref, border=1)
            self.pdf.cell(col_widths[2], 6, recipient, border=1)
            self.pdf.cell(col_widths[3], 6, city, border=1)
            self.pdf.cell(col_widths[4], 6, country, border=1, align="C")
            self.pdf.cell(col_widths[5], 6, service, border=1)
            self.pdf.cell(
                col_widths[6], 6, f"{row['total_charge']:,.0f}", border=1, align="R"
            )
            self.pdf.ln()

    def _add_section_title(self, title: str, level: int = 1):
        """Add a section title."""
        if level == 1:
            self.pdf.set_font("Helvetica", "B", 16)
            self.pdf.set_text_color(53, 28, 21)  # UPS Brown
            self.pdf.cell(0, 12, title, new_x="LMARGIN", new_y="NEXT")
            self.pdf.set_draw_color(53, 28, 21)
            self.pdf.line(10, self.pdf.get_y(), 200, self.pdf.get_y())
            self.pdf.set_y(self.pdf.get_y() + 5)
        else:
            self.pdf.set_font("Helvetica", "B", 12)
            self.pdf.set_text_color(0, 0, 0)
            self.pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")

        self.pdf.set_text_color(0, 0, 0)

    def _add_metrics_table(self, metrics: list[tuple[str, str]]):
        """Add a two-column metrics table."""
        self.pdf.set_font("Helvetica", "", 11)

        for label, value in metrics:
            self.pdf.set_font("Helvetica", "", 11)
            self.pdf.cell(80, 8, label + ":", border=0)
            self.pdf.set_font("Helvetica", "B", 11)
            self.pdf.cell(60, 8, value, border=0, new_x="LMARGIN", new_y="NEXT")
