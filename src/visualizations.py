"""Visualization Module.

Creates Plotly charts for UPS invoice analysis.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    import pycountry

    HAS_PYCOUNTRY = True
except ImportError:
    HAS_PYCOUNTRY = False


def _alpha2_to_alpha3(code: str) -> str | None:
    """Convert ISO alpha-2 country code to alpha-3."""
    if not HAS_PYCOUNTRY or not code:
        return None
    try:
        country = pycountry.countries.get(alpha_2=code)
        return country.alpha_3 if country else None
    except Exception:
        return None


# Color palette
COLORS = {
    "primary": "#351C15",  # UPS Brown
    "secondary": "#FFB500",  # UPS Yellow
    "accent": "#00857C",  # Teal
    "light": "#F5E6D3",  # Light brown
    "freight": "#351C15",
    "fuel": "#FFB500",
    "tax": "#00857C",
    "accessorial": "#D85820",
    "other": "#7B6B63",
}

CHARGE_COLORS = {
    "Freight": COLORS["freight"],
    "Fuel Surcharge": COLORS["fuel"],
    "Tax (VAT)": COLORS["tax"],
    "Accessorial": COLORS["accessorial"],
    "Exemption/Credit": COLORS["accent"],
    "Information Only": COLORS["light"],
    "Other": COLORS["other"],
}


def create_cost_breakdown_pie(breakdown_df: pd.DataFrame) -> go.Figure:
    """Create pie chart showing cost breakdown by charge type."""
    if breakdown_df.empty:
        return _empty_chart("No data available")

    fig = px.pie(
        breakdown_df,
        values="total_charge",
        names="charge_category_name",
        title="Cost Breakdown by Charge Type",
        color="charge_category_name",
        color_discrete_map=CHARGE_COLORS,
        hole=0.4,
    )

    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>Amount: %{value:,.2f}<br>Percentage: %{percent}<extra></extra>",
    )

    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        margin=dict(t=60, b=80, l=20, r=20),
    )

    return fig


def create_cost_breakdown_bar(
    breakdown_df: pd.DataFrame, currency: str = "EUR"
) -> go.Figure:
    """Create bar chart showing cost breakdown by charge type."""
    if breakdown_df.empty:
        return _empty_chart("No data available")

    fig = px.bar(
        breakdown_df,
        x="charge_category_name",
        y="total_charge",
        title="Costs by Charge Category",
        color="charge_category_name",
        color_discrete_map=CHARGE_COLORS,
        text="total_charge",
    )

    fig.update_traces(
        texttemplate="%{text:,.0f}",
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Amount: %{y:,.2f} "
        + currency
        + "<extra></extra>",
    )

    fig.update_layout(
        xaxis_title="",
        yaxis_title=f"Total Cost ({currency})",
        showlegend=False,
        margin=dict(t=60, b=40, l=60, r=20),
    )

    return fig


def create_destination_map(by_country_df: pd.DataFrame) -> go.Figure:
    """Create choropleth map showing shipping volume by country."""
    if by_country_df.empty:
        return _empty_chart("No destination data available")

    # Make a copy to avoid modifying original
    df = by_country_df.copy()

    # Convert alpha-2 to alpha-3 codes for Plotly choropleth
    if HAS_PYCOUNTRY:
        df["country_code_alpha3"] = df["country_code"].apply(_alpha2_to_alpha3)
        # Filter out rows where conversion failed
        df = df[df["country_code_alpha3"].notna()]
        location_col = "country_code_alpha3"
    else:
        location_col = "country_code"

    if df.empty:
        return _empty_chart("No valid country data available")

    fig = px.choropleth(
        df,
        locations=location_col,
        color="package_count",
        hover_name="country_name",
        hover_data={
            location_col: False,
            "country_code": True,
            "package_count": True,
            "total_cost": ":.2f",
            "avg_cost_per_package": ":.2f",
        },
        color_continuous_scale="YlOrBr",
        title="Shipments by Destination Country",
    )

    fig.update_layout(
        geo=dict(
            showframe=False,
            showcoastlines=True,
            projection_type="natural earth",
            showland=True,
            landcolor="rgb(243, 243, 243)",
        ),
        margin=dict(t=60, b=20, l=20, r=20),
    )

    return fig


def create_destination_bar(
    by_country_df: pd.DataFrame, top_n: int = 15, currency: str = "EUR"
) -> go.Figure:
    """Create bar chart showing top destinations by cost."""
    if by_country_df.empty:
        return _empty_chart("No destination data available")

    top_countries = by_country_df.head(top_n)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=top_countries["country_name"],
            y=top_countries["total_cost"],
            name="Total Cost",
            marker_color=COLORS["primary"],
            text=top_countries["package_count"].apply(lambda x: f"{x} pkgs"),
            textposition="outside",
            hovertemplate=(
                "<b>%{x}</b><br>"
                f"Cost: %{{y:,.2f}} {currency}<br>"
                "Packages: %{text}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title=f"Top {top_n} Destinations by Cost",
        xaxis_title="",
        yaxis_title=f"Total Cost ({currency})",
        xaxis_tickangle=-45,
        margin=dict(t=60, b=100, l=60, r=20),
    )

    return fig


def create_trend_chart(trends_df: pd.DataFrame, currency: str = "EUR") -> go.Figure:
    """Create line chart showing cost and volume trends over time."""
    if trends_df.empty:
        return _empty_chart("No trend data available")

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Scatter(
            x=trends_df["period"],
            y=trends_df["total_cost"],
            name="Total Cost",
            line=dict(color=COLORS["primary"], width=3),
            mode="lines+markers",
            hovertemplate=f"Cost: %{{y:,.2f}} {currency}<extra></extra>",
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=trends_df["period"],
            y=trends_df["package_count"],
            name="Package Count",
            line=dict(color=COLORS["secondary"], width=3, dash="dash"),
            mode="lines+markers",
            hovertemplate="Packages: %{y}<extra></extra>",
        ),
        secondary_y=True,
    )

    fig.update_layout(
        title="Cost and Volume Trends Over Time",
        xaxis_title="Period",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=80, b=40, l=60, r=60),
        hovermode="x unified",
    )

    fig.update_yaxes(title_text=f"Total Cost ({currency})", secondary_y=False)
    fig.update_yaxes(title_text="Package Count", secondary_y=True)

    return fig


def create_return_reasons_chart(by_reason_df: pd.DataFrame) -> go.Figure:
    """Create horizontal bar chart showing return types.

    Note: UPS billing data uses shipment_subtype (e.g., RTS = Return to Sender)
    as the closest indicator of return type, not explicit return reasons.
    """
    if by_reason_df.empty:
        return _empty_chart("No return data available")

    # Truncate long reason texts
    by_reason_df = by_reason_df.copy()
    by_reason_df["reason_short"] = by_reason_df["reason"].apply(
        lambda x: x[:40] + "..." if isinstance(x, str) and len(x) > 40 else x
    )

    fig = px.bar(
        by_reason_df.head(15),
        y="reason_short",
        x="count",
        orientation="h",
        title="Return Types",
        color="total_cost",
        color_continuous_scale="YlOrBr",
        text="count",
    )

    fig.update_traces(
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Count: %{x}<br>Cost: %{marker.color:,.2f}<extra></extra>",
    )

    fig.update_layout(
        xaxis_title="Number of Returns",
        yaxis_title="",
        yaxis=dict(autorange="reversed"),
        margin=dict(t=60, b=40, l=200, r=40),
        coloraxis_colorbar_title="Cost",
    )

    return fig


def create_weight_distribution(distribution_df: pd.DataFrame) -> go.Figure:
    """Create bar chart showing package weight distribution."""
    if distribution_df.empty:
        return _empty_chart("No weight data available")

    fig = px.bar(
        distribution_df,
        x="weight_range",
        y="package_count",
        title="Package Weight Distribution",
        color="total_cost",
        color_continuous_scale="YlOrBr",
        text="package_count",
    )

    fig.update_traces(
        textposition="outside",
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Packages: %{y}<br>"
            "Total Cost: %{marker.color:,.2f}<extra></extra>"
        ),
    )

    fig.update_layout(
        xaxis_title="Weight Range",
        yaxis_title="Number of Packages",
        margin=dict(t=60, b=40, l=60, r=40),
        coloraxis_colorbar_title="Cost",
    )

    return fig


def create_weight_scatter(weight_detail_df: pd.DataFrame) -> go.Figure:
    """Create scatter plot comparing actual vs billed weight."""
    if weight_detail_df.empty:
        return _empty_chart("No weight data available")

    # Sample if too many points
    df = weight_detail_df
    if len(df) > 1000:
        df = df.sample(n=1000, random_state=42)

    fig = px.scatter(
        df,
        x="actual_weight",
        y="billed_weight",
        title="Actual vs Billed Weight",
        opacity=0.6,
        color="weight_diff",
        color_continuous_scale="RdYlGn_r",
        hover_data=["tracking_number"],
    )

    # Add diagonal line (y=x)
    max_val = max(df["actual_weight"].max(), df["billed_weight"].max())
    fig.add_trace(
        go.Scatter(
            x=[0, max_val],
            y=[0, max_val],
            mode="lines",
            name="Equal Weight Line",
            line=dict(color="gray", dash="dash"),
        )
    )

    fig.update_layout(
        xaxis_title="Actual Weight (kg)",
        yaxis_title="Billed Weight (kg)",
        margin=dict(t=60, b=40, l=60, r=40),
        coloraxis_colorbar_title="Difference",
    )

    return fig


def create_service_comparison(
    by_service_df: pd.DataFrame, currency: str = "EUR"
) -> go.Figure:
    """Create grouped bar chart comparing services."""
    if by_service_df.empty:
        return _empty_chart("No service data available")

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=by_service_df["service_name"],
            y=by_service_df["total_cost"],
            name="Total Cost",
            marker_color=COLORS["primary"],
            yaxis="y",
            offsetgroup=1,
            hovertemplate=f"<b>%{{x}}</b><br>Total Cost: %{{y:,.2f}} {currency}<extra></extra>",
        )
    )

    fig.add_trace(
        go.Bar(
            x=by_service_df["service_name"],
            y=by_service_df["avg_cost_per_package"],
            name="Avg Cost/Package",
            marker_color=COLORS["secondary"],
            yaxis="y2",
            offsetgroup=2,
            hovertemplate=f"<b>%{{x}}</b><br>Avg Cost: %{{y:,.2f}} {currency}<extra></extra>",
        )
    )

    fig.update_layout(
        title="Service Type Comparison",
        xaxis_title="",
        yaxis=dict(
            title=dict(
                text=f"Total Cost ({currency})",
                font=dict(color=COLORS["primary"]),
            ),
        ),
        yaxis2=dict(
            title=dict(
                text=f"Avg Cost per Package ({currency})",
                font=dict(color=COLORS["secondary"]),
            ),
            overlaying="y",
            side="right",
        ),
        barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_tickangle=-45,
        margin=dict(t=80, b=100, l=60, r=60),
    )

    return fig


def create_duties_breakdown_pie(
    by_charge_type_df: pd.DataFrame, currency: str = "EUR"
) -> go.Figure:
    """Create pie chart showing duties/brokerage breakdown by charge type."""
    if by_charge_type_df.empty:
        return _empty_chart("No duties/brokerage data available")

    # Custom colors for BRK and GOV
    colors = {
        "Brokerage": COLORS["secondary"],  # Yellow
        "Government Charges": COLORS["accent"],  # Teal
    }

    fig = px.pie(
        by_charge_type_df,
        values="total_cost",
        names="charge_name",
        title="Duties & Brokerage Breakdown",
        color="charge_name",
        color_discrete_map=colors,
        hole=0.4,
    )

    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate=f"<b>%{{label}}</b><br>Amount: %{{value:,.2f}} {currency}<br>Percentage: %{{percent}}<extra></extra>",
    )

    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        margin=dict(t=60, b=80, l=20, r=20),
    )

    return fig


def create_duties_by_country_bar(
    by_country_df: pd.DataFrame, top_n: int = 15, currency: str = "EUR"
) -> go.Figure:
    """Create bar chart showing duties/brokerage costs by destination country."""
    if by_country_df.empty:
        return _empty_chart("No country data available")

    top_countries = by_country_df.head(top_n)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=top_countries["country_name"],
            y=top_countries["total_cost"],
            name="Total Cost",
            marker_color=COLORS["accent"],
            text=top_countries["shipment_count"].apply(lambda x: f"{x} shipments"),
            textposition="outside",
            hovertemplate=(
                "<b>%{x}</b><br>"
                f"Import Costs: %{{y:,.2f}} {currency}<br>"
                "%{text}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title=f"Import Costs by Destination Country (Top {top_n})",
        xaxis_title="",
        yaxis_title=f"Total Import Costs ({currency})",
        xaxis_tickangle=-45,
        margin=dict(t=60, b=100, l=60, r=20),
    )

    return fig


def create_accessorials_bar(
    by_charge_code_df: pd.DataFrame, top_n: int = 15, currency: str = "EUR"
) -> go.Figure:
    """Create horizontal bar chart showing accessorial charges by type."""
    if by_charge_code_df.empty:
        return _empty_chart("No accessorial data available")

    top_charges = by_charge_code_df.head(top_n)

    # Create label with code and description
    top_charges = top_charges.copy()
    top_charges["label"] = (
        top_charges["charge_code"] + " - " + top_charges["description"].str[:30]
    )

    fig = px.bar(
        top_charges,
        y="label",
        x="total_cost",
        orientation="h",
        title=f"Accessorial Charges by Type (Top {top_n})",
        color="total_cost",
        color_continuous_scale="YlOrBr",
        text="shipment_count",
    )

    fig.update_traces(
        texttemplate="%{text} shipments",
        textposition="outside",
        hovertemplate=f"<b>%{{y}}</b><br>Cost: %{{x:,.2f}} {currency}<br>Shipments: %{{text}}<extra></extra>",
    )

    fig.update_layout(
        xaxis_title=f"Total Cost ({currency})",
        yaxis_title="",
        yaxis=dict(autorange="reversed"),
        margin=dict(t=60, b=40, l=200, r=60),
        coloraxis_showscale=False,
    )

    return fig


def create_accessorials_by_country_bar(
    by_country_df: pd.DataFrame, top_n: int = 15, currency: str = "EUR"
) -> go.Figure:
    """Create bar chart showing accessorial costs by destination country."""
    if by_country_df.empty:
        return _empty_chart("No country data available")

    top_countries = by_country_df.head(top_n)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=top_countries["country_name"],
            y=top_countries["total_cost"],
            name="Total Cost",
            marker_color=COLORS["accessorial"],
            text=top_countries["shipment_count"].apply(lambda x: f"{x} shipments"),
            textposition="outside",
            hovertemplate=(
                "<b>%{x}</b><br>"
                f"Accessorial Costs: %{{y:,.2f}} {currency}<br>"
                "%{text}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title=f"Accessorial Costs by Destination (Top {top_n})",
        xaxis_title="",
        yaxis_title=f"Total Accessorial Costs ({currency})",
        xaxis_tickangle=-45,
        margin=dict(t=60, b=100, l=60, r=20),
    )

    return fig


def create_accessorials_trend(
    trends_df: pd.DataFrame, currency: str = "EUR"
) -> go.Figure:
    """Create line chart showing accessorial costs trend over time."""
    if trends_df.empty:
        return _empty_chart("No trend data available")

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Scatter(
            x=trends_df["period"],
            y=trends_df["total_cost"],
            name="Total Cost",
            line=dict(color=COLORS["accessorial"], width=3),
            mode="lines+markers",
            hovertemplate=f"Cost: %{{y:,.2f}} {currency}<extra></extra>",
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=trends_df["period"],
            y=trends_df["shipment_count"],
            name="Shipments",
            line=dict(color=COLORS["secondary"], width=3, dash="dash"),
            mode="lines+markers",
            hovertemplate="Shipments: %{y}<extra></extra>",
        ),
        secondary_y=True,
    )

    fig.update_layout(
        title="Accessorial Costs Over Time",
        xaxis_title="Period",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=80, b=40, l=60, r=60),
        hovermode="x unified",
    )

    fig.update_yaxes(title_text=f"Total Cost ({currency})", secondary_y=False)
    fig.update_yaxes(title_text="Shipment Count", secondary_y=True)

    return fig


def create_kpi_cards(summary) -> dict:
    """Create KPI card data from summary.

    Returns dict with KPI values for display.
    """
    return {
        "total_cost": f"{summary.total_cost:,.2f} {summary.currency}",
        "total_packages": f"{summary.total_packages:,}",
        "avg_cost": f"{summary.avg_cost_per_package:,.2f} {summary.currency}",
        "total_weight": f"{summary.total_weight_kg:,.1f} kg",
        "return_rate": f"{summary.return_rate:.1f}%",
        "total_invoices": f"{summary.total_invoices}",
        "freight_pct": f"{(summary.total_freight / summary.total_cost * 100):.1f}%"
        if summary.total_cost > 0
        else "0%",
        "fuel_pct": f"{(summary.total_fuel_surcharge / summary.total_cost * 100):.1f}%"
        if summary.total_cost > 0
        else "0%",
    }


def _empty_chart(message: str) -> go.Figure:
    """Create empty chart with message."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=16, color="gray"),
    )
    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


def create_visualizations(analyzer) -> dict:
    """Create all visualizations from analyzer.

    Args:
        analyzer: InvoiceAnalyzer instance

    Returns:
        Dictionary of Plotly figures
    """
    summary = analyzer.get_summary()
    currency = summary.currency

    return {
        "cost_breakdown_pie": create_cost_breakdown_pie(
            analyzer.analyze_cost_breakdown()
        ),
        "cost_breakdown_bar": create_cost_breakdown_bar(
            analyzer.analyze_cost_breakdown(), currency
        ),
        "destination_map": create_destination_map(analyzer.analyze_by_destination()),
        "destination_bar": create_destination_bar(
            analyzer.analyze_by_destination(), currency=currency
        ),
        "trend_chart": create_trend_chart(analyzer.analyze_trends(), currency),
        "return_reasons": create_return_reasons_chart(
            analyzer.analyze_returns()["by_reason"]
        ),
        "weight_distribution": create_weight_distribution(
            analyzer.analyze_weights()["distribution"]
        ),
        "weight_scatter": create_weight_scatter(
            analyzer.analyze_weights().get("detail", pd.DataFrame())
        ),
        "service_comparison": create_service_comparison(
            analyzer.analyze_services(), currency
        ),
    }
