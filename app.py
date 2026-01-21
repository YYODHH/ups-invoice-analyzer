"""UPS Invoice Analyzer - Streamlit Dashboard.

Run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime

from src.parser import UPSInvoiceParser, load_invoices_from_folder
from src.analyzer import InvoiceAnalyzer
from src.visualizations import (
    create_cost_breakdown_pie,
    create_cost_breakdown_bar,
    create_destination_map,
    create_destination_bar,
    create_trend_chart,
    create_return_reasons_chart,
    create_weight_distribution,
    create_weight_scatter,
    create_service_comparison,
    create_kpi_cards,
    create_duties_breakdown_pie,
    create_duties_by_country_bar,
    create_accessorials_bar,
    create_accessorials_by_country_bar,
    create_accessorials_trend,
)
from src.report import PDFReportGenerator


# Page configuration
st.set_page_config(
    page_title="UPS Invoice Analyzer",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown(
    """
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #351C15;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-top: 0;
    }
    .metric-card {
        background-color: #F5E6D3;
        border-radius: 10px;
        padding: 15px;
        border-left: 4px solid #351C15;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #E8DCD0;
        border-radius: 5px 5px 0 0;
        color: #351C15 !important;
        font-weight: 500;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #D4C4B0;
    }
    .stTabs [aria-selected="true"] {
        background-color: #351C15 !important;
        color: white !important;
        font-weight: 600;
    }
</style>
""",
    unsafe_allow_html=True,
)


def main():
    """Main application entry point."""
    # Header
    st.markdown(
        '<p class="main-header">📦 UPS Invoice Analyzer</p>', unsafe_allow_html=True
    )
    st.markdown(
        '<p class="sub-header">Analyze your UPS shipping costs with detailed breakdowns and trends</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    # Initialize session state
    if "data" not in st.session_state:
        st.session_state.data = None
    if "analyzer" not in st.session_state:
        st.session_state.analyzer = None

    # Sidebar
    with st.sidebar:
        st.header("📁 Data Source")

        # File upload
        uploaded_files = st.file_uploader(
            "Upload UPS Invoice CSVs",
            type=["csv"],
            accept_multiple_files=True,
            help="Upload one or more UPS Billing Data CSV files",
        )

        # Load from folder option
        use_folder = st.checkbox(
            "Load from invoices folder",
            value=True if not uploaded_files else False,
            help="Load all CSV files from the invoices/ folder",
        )

        # Load data button
        if st.button("🔄 Load/Refresh Data", type="primary", width="stretch"):
            load_data(uploaded_files, use_folder)

        # Auto-load on first run if folder option is selected
        if st.session_state.data is None and use_folder and not uploaded_files:
            load_data(None, True)

        st.divider()

        # Filters (only show if data is loaded)
        if st.session_state.analyzer is not None:
            st.header("🔍 Filters")
            filtered_analyzer = apply_filters(st.session_state.analyzer)
        else:
            filtered_analyzer = None

        st.divider()

        # Export options
        if filtered_analyzer is not None:
            st.header("📥 Export")
            export_pdf(filtered_analyzer)

    # Main content
    if filtered_analyzer is None:
        show_welcome_screen()
    else:
        show_dashboard(filtered_analyzer)


def load_data(uploaded_files, use_folder: bool):
    """Load data from uploaded files or folder."""
    parser = UPSInvoiceParser()
    all_data = []

    with st.spinner("Loading invoice data..."):
        # Load uploaded files
        if uploaded_files:
            for file in uploaded_files:
                try:
                    df = parser.parse_file(file, file.name)
                    all_data.append(df)
                    st.sidebar.success(f"Loaded: {file.name}")
                except Exception as e:
                    st.sidebar.error(f"Error loading {file.name}: {e}")

        # Load from folder
        if use_folder and not uploaded_files:
            folder_path = Path("invoices")
            if folder_path.exists():
                csv_files = list(folder_path.glob("*.csv"))
                for csv_file in csv_files:
                    try:
                        with open(csv_file, "rb") as f:
                            df = parser.parse_file(f, csv_file.name)
                            all_data.append(df)
                    except Exception as e:
                        st.sidebar.error(f"Error loading {csv_file.name}: {e}")

                if csv_files:
                    st.sidebar.success(f"Loaded {len(csv_files)} files from invoices/")
            else:
                st.sidebar.warning("invoices/ folder not found")

    if all_data:
        combined_data = pd.concat(all_data, ignore_index=True)
        st.session_state.data = combined_data
        st.session_state.analyzer = InvoiceAnalyzer(combined_data)
        st.sidebar.success(f"✅ {len(combined_data):,} records loaded")
    else:
        st.sidebar.warning("No data loaded")


def apply_filters(analyzer: InvoiceAnalyzer) -> InvoiceAnalyzer:
    """Apply sidebar filters and return filtered analyzer."""
    data = analyzer.data

    # Date range filter
    if data["shipment_date"].notna().any():
        min_date = data["shipment_date"].min().date()
        max_date = data["shipment_date"].max().date()

        date_range = st.date_input(
            "Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )

        if len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date, end_date = min_date, max_date
    else:
        start_date, end_date = None, None

    # Country filter (use recipient_country since this is outbound data)
    countries = sorted(data["recipient_country"].dropna().unique().tolist())
    selected_countries = st.multiselect(
        "Destination Countries",
        options=countries,
        default=None,
        help="Filter by destination country (where shipments go to)",
    )

    # Service filter
    services = sorted(data["service_code"].dropna().unique().tolist())
    service_names = {
        code: analyzer.data[analyzer.data["service_code"] == code]["service_name"].iloc[
            0
        ]
        for code in services
        if not analyzer.data[analyzer.data["service_code"] == code].empty
    }
    service_options = [
        f"{code} - {service_names.get(code, 'Unknown')}" for code in services
    ]

    selected_services_display = st.multiselect(
        "Service Types",
        options=service_options,
        default=None,
        help="Filter by service type",
    )
    selected_services = (
        [s.split(" - ")[0] for s in selected_services_display]
        if selected_services_display
        else None
    )

    # Returns only filter
    returns_only = st.checkbox("Returns only", value=False)

    # Apply filters
    return analyzer.filter_data(
        start_date=str(start_date) if start_date else None,
        end_date=str(end_date) if end_date else None,
        countries=selected_countries if selected_countries else None,
        services=selected_services,
        returns_only=returns_only,
    )


def export_pdf(analyzer: InvoiceAnalyzer):
    """Export PDF report."""
    if st.button("📄 Generate PDF Report", width="stretch"):
        with st.spinner("Generating PDF..."):
            try:
                generator = PDFReportGenerator()
                pdf_bytes = generator.generate_report(analyzer)

                st.download_button(
                    label="⬇️ Download PDF",
                    data=pdf_bytes,
                    file_name=f"ups_invoice_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf",
                    width="stretch",
                )
            except Exception as e:
                st.error(f"Error generating PDF: {e}")


def show_welcome_screen():
    """Show welcome screen when no data is loaded."""
    st.info(
        "👋 Welcome! Upload UPS invoice CSV files or load from the invoices folder to get started."
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        ### 📤 How to get started
        1. **Upload files**: Use the sidebar to upload your UPS Billing Data CSV files
        2. **Or load from folder**: Check "Load from invoices folder" if you have CSVs in the `invoices/` directory
        3. **Click Load/Refresh**: Process the data and view your analysis

        ### 📊 What you'll see
        - **Cost Breakdown**: Freight, fuel surcharges, taxes, and accessorial fees
        - **Destinations**: Shipping volume and costs by country
        - **Trends**: Weekly/monthly cost and volume changes
        - **Returns**: Return rates, reasons, and associated costs
        - **Weights**: Package weight distribution and billing analysis
        - **Services**: Comparison across service types
        - **Top Expenses**: Your most expensive shipments
        """)

    with col2:
        st.markdown("""
        ### 📁 Supported File Format
        This tool supports **UPS Billing Data CSV exports**. These are the detailed invoice
        files you can download from your UPS account.

        The CSV files should contain:
        - Invoice and tracking numbers
        - Shipment dates and details
        - Charge breakdowns (freight, fuel, tax)
        - Origin and destination addresses
        - Package weights and dimensions

        ### 💡 Tips
        - Upload multiple invoices to see trends over time
        - Use filters to focus on specific countries or services
        - Export PDF reports for sharing with your team
        """)


def show_dashboard(analyzer: InvoiceAnalyzer):
    """Show the main dashboard with all analysis tabs."""
    summary = analyzer.get_summary()
    kpis = create_kpi_cards(summary)

    # KPI Row
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        st.metric("Total Cost", kpis["total_cost"])
    with col2:
        st.metric("Packages", kpis["total_packages"])
    with col3:
        st.metric("Avg Cost/Pkg", kpis["avg_cost"])
    with col4:
        st.metric("Total Weight", kpis["total_weight"])
    with col5:
        st.metric("Return Rate", kpis["return_rate"])
    with col6:
        st.metric("Invoices", kpis["total_invoices"])

    st.divider()

    # Analysis Tabs
    tabs = st.tabs(
        [
            "📊 Overview",
            "💰 Cost Breakdown",
            "🌍 Destinations",
            "📈 Trends",
            "↩️ Returns",
            "⚖️ Weights",
            "🚚 Services",
            "📦 Duties & Brokerage",
            "🏷️ Accessorials",
            "🔝 Top Expenses",
        ]
    )

    # Overview Tab
    with tabs[0]:
        show_overview_tab(analyzer, summary)

    # Cost Breakdown Tab
    with tabs[1]:
        show_cost_breakdown_tab(analyzer, summary)

    # Destinations Tab
    with tabs[2]:
        show_destinations_tab(analyzer, summary)

    # Trends Tab
    with tabs[3]:
        show_trends_tab(analyzer, summary)

    # Returns Tab
    with tabs[4]:
        show_returns_tab(analyzer)

    # Weights Tab
    with tabs[5]:
        show_weights_tab(analyzer)

    # Services Tab
    with tabs[6]:
        show_services_tab(analyzer, summary)

    # Duties & Brokerage Tab
    with tabs[7]:
        show_duties_tab(analyzer, summary)

    # Accessorials Tab
    with tabs[8]:
        show_accessorials_tab(analyzer, summary)

    # Top Expenses Tab
    with tabs[9]:
        show_top_expenses_tab(analyzer, summary)


def show_overview_tab(analyzer: InvoiceAnalyzer, summary):
    """Show overview tab content."""
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Cost Distribution")
        breakdown = analyzer.analyze_cost_breakdown()
        fig = create_cost_breakdown_pie(breakdown)
        st.plotly_chart(fig, key="overview_cost_pie", width="stretch")

    with col2:
        st.subheader("Top Destinations")
        by_country = analyzer.analyze_by_destination()
        fig = create_destination_bar(by_country, top_n=10, currency=summary.currency)
        st.plotly_chart(fig, key="overview_dest_bar", width="stretch")

    # Trend chart full width
    st.subheader("Cost Trend")
    trends = analyzer.analyze_trends(period="week")
    fig = create_trend_chart(trends, summary.currency)
    st.plotly_chart(fig, key="overview_trend", width="stretch")


def show_cost_breakdown_tab(analyzer: InvoiceAnalyzer, summary):
    """Show cost breakdown tab content."""
    breakdown = analyzer.analyze_cost_breakdown()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("By Charge Type (Pie)")
        fig = create_cost_breakdown_pie(breakdown)
        st.plotly_chart(fig, key="cost_pie", width="stretch")

    with col2:
        st.subheader("By Charge Type (Bar)")
        fig = create_cost_breakdown_bar(breakdown, summary.currency)
        st.plotly_chart(fig, key="cost_bar", width="stretch")

    # Data table
    st.subheader("Detailed Breakdown")
    if not breakdown.empty:
        display_df = breakdown[
            [
                "charge_category_name",
                "discount_amount",
                "net_amount",
                "total_charge",
                "percentage",
            ]
        ].copy()
        display_df.columns = [
            "Charge Type",
            "Discount",
            "Net Amount",
            "Total",
            "% of Total",
        ]
        st.dataframe(
            display_df.style.format(
                {
                    "Discount": "{:,.2f}",
                    "Net Amount": "{:,.2f}",
                    "Total": "{:,.2f}",
                    "% of Total": "{:.1f}%",
                }
            ),
            width="stretch",
            hide_index=True,
        )


def show_destinations_tab(analyzer: InvoiceAnalyzer, summary):
    """Show destinations tab content."""
    by_country = analyzer.analyze_by_destination()

    # Map
    st.subheader("Shipments by Destination Country")
    fig = create_destination_map(by_country)
    st.plotly_chart(fig, key="dest_map", width="stretch")

    # Bar chart
    st.subheader("Top 15 Destinations by Cost")
    fig = create_destination_bar(by_country, top_n=15, currency=summary.currency)
    st.plotly_chart(fig, key="dest_bar", width="stretch")

    # Data table
    st.subheader("Country Details")
    if not by_country.empty:
        display_df = by_country[
            [
                "country_name",
                "country_code",
                "package_count",
                "total_cost",
                "avg_cost_per_package",
                "total_weight",
                "return_rate",
            ]
        ].copy()
        display_df.columns = [
            "Country",
            "Code",
            "Packages",
            "Total Cost",
            "Avg Cost",
            "Weight (kg)",
            "Return %",
        ]
        st.dataframe(
            display_df.style.format(
                {
                    "Packages": "{:,}",
                    "Total Cost": "{:,.2f}",
                    "Avg Cost": "{:,.2f}",
                    "Weight (kg)": "{:,.1f}",
                    "Return %": "{:.1f}%",
                }
            ),
            width="stretch",
            hide_index=True,
        )


def show_trends_tab(analyzer: InvoiceAnalyzer, summary):
    """Show trends tab content."""
    col1, col2 = st.columns([3, 1])

    with col2:
        period = st.radio("Time Period", ["week", "month"], horizontal=True)

    trends = analyzer.analyze_trends(period=period)

    st.subheader(f"Cost & Volume Trends (by {period})")
    fig = create_trend_chart(trends, summary.currency)
    st.plotly_chart(fig, key="trends_chart", width="stretch")

    # Data table
    st.subheader("Period Details")
    if not trends.empty:
        display_df = trends.copy()
        display_df.columns = [
            "Period",
            "Packages",
            "Total Cost",
            "Weight (kg)",
            "Avg Cost/Pkg",
        ]
        st.dataframe(
            display_df.style.format(
                {
                    "Packages": "{:,}",
                    "Total Cost": "{:,.2f}",
                    "Weight (kg)": "{:,.1f}",
                    "Avg Cost/Pkg": "{:,.2f}",
                }
            ),
            width="stretch",
            hide_index=True,
        )


def show_returns_tab(analyzer: InvoiceAnalyzer):
    """Show returns analysis tab content."""
    returns_data = analyzer.analyze_returns()
    summary_data = returns_data.get("summary", {})

    if not summary_data:
        st.info("No return shipments found in the data.")
        return

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Returns", f"{summary_data.get('total_returns', 0):,}")
    with col2:
        st.metric("Return Cost", f"{summary_data.get('total_return_cost', 0):,.2f}")
    with col3:
        st.metric("Return Rate", f"{summary_data.get('return_rate', 0):.1f}%")
    with col4:
        st.metric("Avg Return Cost", f"{summary_data.get('avg_return_cost', 0):,.2f}")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Return Reasons")
        by_reason = returns_data.get("by_reason", pd.DataFrame())
        fig = create_return_reasons_chart(by_reason)
        st.plotly_chart(fig, key="returns_reasons", width="stretch")

    with col2:
        st.subheader("Returns by Country")
        by_country = returns_data.get("by_country", pd.DataFrame())
        if not by_country.empty:
            st.dataframe(
                by_country.style.format(
                    {
                        "return_count": "{:,}",
                        "return_cost": "{:,.2f}",
                    }
                ),
                width="stretch",
                hide_index=True,
            )


def show_weights_tab(analyzer: InvoiceAnalyzer):
    """Show weight analysis tab content."""
    weight_data = analyzer.analyze_weights()
    summary_data = weight_data.get("summary", {})

    if not summary_data:
        st.info("No weight data available.")
        return

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Total Actual Weight",
            f"{summary_data.get('total_actual_weight', 0):,.1f} kg",
        )
    with col2:
        st.metric(
            "Total Billed Weight",
            f"{summary_data.get('total_billed_weight', 0):,.1f} kg",
        )
    with col3:
        st.metric("Dim Weight Premium", f"{summary_data.get('weight_premium', 0):.1f}%")
    with col4:
        st.metric(
            "Pkgs w/ Dim Weight", f"{summary_data.get('packages_with_dim_weight', 0):,}"
        )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Weight Distribution")
        distribution = weight_data.get("distribution", pd.DataFrame())
        fig = create_weight_distribution(distribution)
        st.plotly_chart(fig, key="weight_dist", width="stretch")

    with col2:
        st.subheader("Actual vs Billed Weight")
        detail = weight_data.get("detail", pd.DataFrame())
        fig = create_weight_scatter(detail)
        st.plotly_chart(fig, key="weight_scatter", width="stretch")


def show_services_tab(analyzer: InvoiceAnalyzer, summary):
    """Show service comparison tab content."""
    by_service = analyzer.analyze_services()

    st.subheader("Service Type Comparison")
    fig = create_service_comparison(by_service, summary.currency)
    st.plotly_chart(fig, key="services_chart", width="stretch")

    # Data table
    st.subheader("Service Details")
    if not by_service.empty:
        display_df = by_service[
            [
                "service_name",
                "service_code",
                "package_count",
                "total_cost",
                "avg_cost_per_package",
                "total_weight",
            ]
        ].copy()
        display_df.columns = [
            "Service",
            "Code",
            "Packages",
            "Total Cost",
            "Avg Cost",
            "Weight (kg)",
        ]
        st.dataframe(
            display_df.style.format(
                {
                    "Packages": "{:,}",
                    "Total Cost": "{:,.2f}",
                    "Avg Cost": "{:,.2f}",
                    "Weight (kg)": "{:,.1f}",
                }
            ),
            width="stretch",
            hide_index=True,
        )


def show_duties_tab(analyzer: InvoiceAnalyzer, summary):
    """Show duties & brokerage analysis tab content."""
    duties_data = analyzer.analyze_duties_and_brokerage()
    summary_data = duties_data.get("summary", {})

    if not summary_data:
        st.info(
            "No duties or brokerage charges found in the data. These charges appear on shipments with F/D (Free Domicile) payment terms."
        )
        return

    # Summary metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric(
            "Total Import Costs",
            f"{summary_data.get('total_cost', 0):,.2f} {summary.currency}",
        )
    with col2:
        st.metric("Shipments", f"{summary_data.get('shipment_count', 0):,}")
    with col3:
        st.metric(
            "Brokerage Fees",
            f"{summary_data.get('brokerage_cost', 0):,.2f} {summary.currency}",
        )
    with col4:
        st.metric(
            "Customs Duties",
            f"{summary_data.get('customs_cost', 0):,.2f} {summary.currency}",
        )
    with col5:
        st.metric(
            "Avg/Shipment",
            f"{summary_data.get('avg_cost_per_shipment', 0):,.2f} {summary.currency}",
        )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Cost Breakdown")
        by_charge_type = duties_data.get("by_charge_type", pd.DataFrame())
        fig = create_duties_breakdown_pie(by_charge_type, summary.currency)
        st.plotly_chart(fig, key="duties_pie", use_container_width=True)

    with col2:
        st.subheader("By Destination Country")
        by_country = duties_data.get("by_country", pd.DataFrame())
        fig = create_duties_by_country_bar(
            by_country, top_n=10, currency=summary.currency
        )
        st.plotly_chart(fig, key="duties_country_bar", use_container_width=True)

    # Detail table
    st.subheader("Shipment Details")
    detail = duties_data.get("detail", pd.DataFrame())
    if not detail.empty:
        display_df = detail.copy()
        display_df["shipment_date"] = pd.to_datetime(
            display_df["shipment_date"]
        ).dt.strftime("%Y-%m-%d")
        display_df.columns = [
            "Tracking #",
            "Country",
            "Recipient",
            "City",
            "Order Ref",
            "Date",
            "Total",
            "Brokerage",
            "Customs",
        ]
        st.dataframe(
            display_df.style.format(
                {
                    "Total": "{:,.2f}",
                    "Brokerage": "{:,.2f}",
                    "Customs": "{:,.2f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )


def show_accessorials_tab(analyzer: InvoiceAnalyzer, summary):
    """Show accessorials analysis tab content."""
    acc_data = analyzer.analyze_accessorials()
    summary_data = acc_data.get("summary", {})

    if not summary_data:
        st.info("No accessorial charges found in the data.")
        return

    # Summary metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric(
            "Total Accessorials",
            f"{summary_data.get('total_cost', 0):,.2f} {summary.currency}",
        )
    with col2:
        st.metric("Shipments Affected", f"{summary_data.get('shipment_count', 0):,}")
    with col3:
        st.metric(
            "Residential Fees",
            f"{summary_data.get('residential_cost', 0):,.2f} {summary.currency}",
        )
    with col4:
        st.metric(
            "Surge Fees", f"{summary_data.get('surge_cost', 0):,.2f} {summary.currency}"
        )
    with col5:
        st.metric(
            "Area Surcharges",
            f"{summary_data.get('area_surcharge_cost', 0):,.2f} {summary.currency}",
        )

    st.divider()

    # Charts row
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Charges by Type")
        by_charge_code = acc_data.get("by_charge_code", pd.DataFrame())
        fig = create_accessorials_bar(
            by_charge_code, top_n=12, currency=summary.currency
        )
        st.plotly_chart(fig, key="acc_bar", use_container_width=True)

    with col2:
        st.subheader("By Destination Country")
        by_country = acc_data.get("by_country", pd.DataFrame())
        fig = create_accessorials_by_country_bar(
            by_country, top_n=10, currency=summary.currency
        )
        st.plotly_chart(fig, key="acc_country_bar", use_container_width=True)

    # Trend chart
    st.subheader("Accessorial Costs Over Time")
    trends = acc_data.get("trends", pd.DataFrame())
    fig = create_accessorials_trend(trends, summary.currency)
    st.plotly_chart(fig, key="acc_trend", use_container_width=True)

    # Detail table
    st.subheader("Charge Type Details")
    by_charge_code = acc_data.get("by_charge_code", pd.DataFrame())
    if not by_charge_code.empty:
        display_df = by_charge_code.copy()
        display_df.columns = ["Code", "Description", "Total Cost", "Shipments"]
        st.dataframe(
            display_df.style.format(
                {
                    "Total Cost": "{:,.2f}",
                    "Shipments": "{:,}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )


def show_top_expenses_tab(analyzer: InvoiceAnalyzer, summary):
    """Show top expenses tab content."""
    col1, col2 = st.columns([3, 1])

    with col2:
        n_items = st.slider("Number of items", min_value=10, max_value=50, value=20)

    top_expenses = analyzer.get_top_expenses(n=n_items)

    st.subheader(f"Top {n_items} Most Expensive Shipments")

    if top_expenses.empty:
        st.info("No shipment data available.")
        return

    # Format for display
    display_df = top_expenses.copy()
    display_df["shipment_date"] = pd.to_datetime(
        display_df["shipment_date"]
    ).dt.strftime("%Y-%m-%d")
    display_df = display_df[
        [
            "tracking_number",
            "order_reference",
            "shipment_date",
            "recipient_name",
            "recipient_city",
            "recipient_country",
            "service_name",
            "billed_weight",
            "total_charge",
            "is_return",
        ]
    ]
    display_df.columns = [
        "Tracking #",
        "Reference",
        "Date",
        "Recipient",
        "City",
        "Country",
        "Service",
        "Weight (kg)",
        f"Cost ({summary.currency})",
        "Return?",
    ]

    st.dataframe(
        display_df.style.format(
            {
                "Weight (kg)": "{:.1f}",
                f"Cost ({summary.currency})": "{:,.2f}",
            }
        ),
        width="stretch",
        hide_index=True,
    )


if __name__ == "__main__":
    main()
