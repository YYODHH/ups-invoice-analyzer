"""Invoice Analysis Module.

Provides analysis functions for UPS invoice data including:
- Cost breakdowns by charge type
- Destination analysis
- Time-based trends
- Return/RTS analysis
- Weight analysis
- Service type comparison
- Top expense identification
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Any

try:
    import pycountry

    HAS_PYCOUNTRY = True
except ImportError:
    HAS_PYCOUNTRY = False


@dataclass
class AnalysisSummary:
    """Summary statistics for invoice analysis."""

    total_invoices: int
    total_packages: int
    total_cost: float
    total_freight: float
    total_fuel_surcharge: float
    total_tax: float
    total_accessorial: float
    avg_cost_per_package: float
    total_weight_kg: float
    date_range: tuple[str, str] | None
    top_destination_country: str | None
    return_rate: float
    currency: str


class InvoiceAnalyzer:
    """Analyzer for UPS invoice data."""

    def __init__(self, data: pd.DataFrame):
        """Initialize analyzer with parsed invoice data.

        Args:
            data: DataFrame from UPSInvoiceParser
        """
        self.data = data
        self._packages: pd.DataFrame | None = None

    @property
    def packages(self) -> pd.DataFrame:
        """Get unique packages with aggregated charges."""
        if self._packages is None:
            self._packages = self._aggregate_packages()
        return self._packages

    def _aggregate_packages(self) -> pd.DataFrame:
        """Aggregate data by tracking number to get package-level view.

        Per UPS Billing Data structure, each tracking number has multiple rows:
        - package_indicator=1: Package/shipment line with weight data
        - package_indicator=0: Charge-only lines (no weight data)

        This method pulls shipment info from FRT rows with package_indicator=1
        for accurate weight and service data.
        """
        if self.data.empty:
            return pd.DataFrame()

        df = self.data

        # Get shipment info from FRT rows with package_indicator=1
        # These rows have accurate weight data and service names
        frt_rows = df[
            (df["package_indicator"] == "1") & (df["charge_category"] == "FRT")
        ].copy()

        # For shipments without FRT rows, fall back to package_indicator=1 rows
        pkg_rows = df[df["package_indicator"] == "1"].copy()

        # Create base aggregation from FRT rows (preferred)
        if not frt_rows.empty:
            shipment_info = (
                frt_rows.groupby("tracking_number")
                .agg(
                    {
                        "invoice_number": "first",
                        "invoice_date": "first",
                        "shipment_date": "first",
                        "order_reference": "first",
                        "service_code": "first",
                        "charge_description": "first",  # Service name from FRT row
                        "actual_weight": "first",
                        "billed_weight": "first",
                        # Sender (Absender) - col67-73 - Account holder for outbound shipments
                        "sender_name": "first",
                        "sender_city": "first",
                        "sender_country": "first",
                        # Recipient (Empfänger) - col74-81 - Customer for outbound shipments
                        "recipient_name": "first",
                        "recipient_company": "first",
                        "recipient_city": "first",
                        "recipient_country": "first",
                        "shipment_type": "first",
                        "shipment_subtype": "first",
                        "goods_description": "first",
                        "is_return": "first",
                        "source_file": "first",
                    }
                )
                .reset_index()
            )
            # Use charge_description as service_name
            shipment_info["service_name"] = shipment_info["charge_description"]
        else:
            # Fallback to any package rows
            shipment_info = (
                pkg_rows.groupby("tracking_number")
                .agg(
                    {
                        "invoice_number": "first",
                        "invoice_date": "first",
                        "shipment_date": "first",
                        "order_reference": "first",
                        "service_code": "first",
                        "service_name": "first",
                        "actual_weight": "first",
                        "billed_weight": "first",
                        # Sender (Absender) - col67-73 - Account holder for outbound shipments
                        "sender_name": "first",
                        "sender_city": "first",
                        "sender_country": "first",
                        # Recipient (Empfänger) - col74-81 - Customer for outbound shipments
                        "recipient_name": "first",
                        "recipient_company": "first",
                        "recipient_city": "first",
                        "recipient_country": "first",
                        "shipment_type": "first",
                        "shipment_subtype": "first",
                        "goods_description": "first",
                        "is_return": "first",
                        "source_file": "first",
                    }
                )
                .reset_index()
            )

        # Sum charges across ALL rows for each tracking number
        charge_totals = (
            df.groupby("tracking_number")
            .agg(
                {
                    "discount_amount": "sum",
                    "net_amount": "sum",
                    "total_charge": "sum",
                }
            )
            .reset_index()
        )

        # Merge shipment info with charge totals
        packages = shipment_info.merge(charge_totals, on="tracking_number", how="left")

        return packages

    def get_summary(self) -> AnalysisSummary:
        """Get high-level summary statistics."""
        if self.data.empty:
            return AnalysisSummary(
                total_invoices=0,
                total_packages=0,
                total_cost=0,
                total_freight=0,
                total_fuel_surcharge=0,
                total_tax=0,
                total_accessorial=0,
                avg_cost_per_package=0,
                total_weight_kg=0,
                date_range=None,
                top_destination_country=None,
                return_rate=0,
                currency="EUR",
            )

        df = self.data
        packages = self.packages

        # Charge breakdown
        charge_totals = df.groupby("charge_category")["total_charge"].sum()

        # Date range
        valid_dates = df["shipment_date"].dropna()
        date_range = None
        if not valid_dates.empty:
            date_range = (
                valid_dates.min().strftime("%Y-%m-%d"),
                valid_dates.max().strftime("%Y-%m-%d"),
            )

        # Top destination (use recipient_country as this data shows outbound shipments)
        top_dest = None
        if not packages.empty and "recipient_country" in packages.columns:
            country_counts = packages["recipient_country"].value_counts()
            # Filter out None/empty values
            country_counts = country_counts[country_counts.index.notna()]
            if not country_counts.empty:
                top_dest = country_counts.index[0]

        # Return rate
        return_count = (
            packages["is_return"].sum() if "is_return" in packages.columns else 0
        )
        return_rate = (return_count / len(packages) * 100) if len(packages) > 0 else 0

        # Currency (assume first non-null)
        currency = (
            df["currency"].dropna().iloc[0] if df["currency"].notna().any() else "EUR"
        )

        return AnalysisSummary(
            total_invoices=df["invoice_number"].nunique(),
            total_packages=len(packages),
            total_cost=packages["total_charge"].sum(),
            total_freight=charge_totals.get("FRT", 0),
            total_fuel_surcharge=charge_totals.get("FSC", 0),
            total_tax=charge_totals.get("TAX", 0),
            total_accessorial=charge_totals.get("ACC", 0),
            avg_cost_per_package=packages["total_charge"].mean()
            if len(packages) > 0
            else 0,
            total_weight_kg=packages["billed_weight"].sum(),
            date_range=date_range,
            top_destination_country=top_dest,
            return_rate=return_rate,
            currency=currency,
        )

    def analyze_cost_breakdown(self) -> pd.DataFrame:
        """Analyze costs by charge category.

        Returns:
            DataFrame with charge categories and their totals/percentages
        """
        if self.data.empty:
            return pd.DataFrame()

        breakdown = (
            self.data.groupby(["charge_category", "charge_category_name"])
            .agg(
                {
                    "discount_amount": "sum",
                    "net_amount": "sum",
                    "total_charge": "sum",
                }
            )
            .reset_index()
        )

        # Calculate percentages
        total = breakdown["total_charge"].sum()
        breakdown["percentage"] = (breakdown["total_charge"] / total * 100).round(2)

        return breakdown.sort_values("total_charge", ascending=False)

    def analyze_by_destination(self) -> pd.DataFrame:
        """Analyze costs and volume by destination country.

        Note: Uses recipient_country as this invoice data shows outbound shipments
        FROM the account holder TO customers. The recipient_country represents
        where customers/shipments are going to.

        Returns:
            DataFrame with country-level aggregations
        """
        packages = self.packages
        if packages.empty:
            return pd.DataFrame()

        # Filter out rows without recipient_country
        valid_packages = packages[packages["recipient_country"].notna()].copy()
        if valid_packages.empty:
            return pd.DataFrame()

        by_country = (
            valid_packages.groupby("recipient_country")
            .agg(
                {
                    "tracking_number": "count",
                    "total_charge": "sum",
                    "billed_weight": "sum",
                    "is_return": "sum",
                }
            )
            .reset_index()
        )

        by_country.columns = [
            "country_code",
            "package_count",
            "total_cost",
            "total_weight",
            "return_count",
        ]

        # Add country names
        if HAS_PYCOUNTRY:
            by_country["country_name"] = by_country["country_code"].apply(
                self._get_country_name
            )
        else:
            by_country["country_name"] = by_country["country_code"]

        # Calculate averages
        by_country["avg_cost_per_package"] = (
            by_country["total_cost"] / by_country["package_count"]
        ).round(2)

        by_country["return_rate"] = (
            by_country["return_count"] / by_country["package_count"] * 100
        ).round(2)

        return by_country.sort_values("total_cost", ascending=False)

    def analyze_trends(self, period: str = "week") -> pd.DataFrame:
        """Analyze cost and volume trends over time.

        Args:
            period: 'week' or 'month'

        Returns:
            DataFrame with time-series data
        """
        packages = self.packages
        if packages.empty or "shipment_date" not in packages.columns:
            return pd.DataFrame()

        # Remove rows without dates
        packages = packages.dropna(subset=["shipment_date"])
        if packages.empty:
            return pd.DataFrame()

        if period == "week":
            packages["period"] = packages["shipment_date"].dt.strftime("%Y-W%W")
        else:
            packages["period"] = packages["shipment_date"].dt.strftime("%Y-%m")

        trends = (
            packages.groupby("period")
            .agg(
                {
                    "tracking_number": "count",
                    "total_charge": "sum",
                    "billed_weight": "sum",
                }
            )
            .reset_index()
        )

        trends.columns = ["period", "package_count", "total_cost", "total_weight"]
        trends["avg_cost_per_package"] = (
            trends["total_cost"] / trends["package_count"]
        ).round(2)

        return trends.sort_values("period")

    def analyze_returns(self) -> dict[str, Any]:
        """Analyze return shipments.

        Note: The UPS billing data doesn't include explicit return reason codes.
        The shipment_subtype field (e.g., RTS = Return to Sender) is the closest
        indicator of return type.

        Returns:
            Dictionary with return analysis data
        """
        packages = self.packages
        if packages.empty:
            return {
                "summary": {},
                "by_reason": pd.DataFrame(),
                "by_country": pd.DataFrame(),
            }

        returns = packages[packages["is_return"] == True]

        if returns.empty:
            return {
                "summary": {},
                "by_reason": pd.DataFrame(),
                "by_country": pd.DataFrame(),
            }

        # Summary
        summary = {
            "total_returns": len(returns),
            "total_return_cost": returns["total_charge"].sum(),
            "return_rate": len(returns) / len(packages) * 100,
            "avg_return_cost": returns["total_charge"].mean(),
        }

        # By shipment_subtype (closest thing to "reason" in UPS data)
        # e.g., RTS = Return to Sender
        by_reason = pd.DataFrame()
        if "shipment_subtype" in returns.columns:
            by_reason = (
                returns.groupby("shipment_subtype")
                .agg(
                    {
                        "tracking_number": "count",
                        "total_charge": "sum",
                    }
                )
                .reset_index()
            )
            by_reason.columns = ["reason", "count", "total_cost"]
            by_reason = by_reason.sort_values("count", ascending=False)

        # By country (sender for returns - where the return is coming FROM)
        # For RTN shipments: sender=customer returning the package, recipient=account holder
        by_country = (
            returns.groupby("sender_country")
            .agg(
                {
                    "tracking_number": "count",
                    "total_charge": "sum",
                }
            )
            .reset_index()
        )
        by_country.columns = ["country_code", "return_count", "return_cost"]

        # Filter out None/empty values
        by_country = by_country[by_country["country_code"].notna()]

        if HAS_PYCOUNTRY:
            by_country["country_name"] = by_country["country_code"].apply(
                self._get_country_name
            )

        by_country = by_country.sort_values("return_count", ascending=False)

        return {
            "summary": summary,
            "by_reason": by_reason,
            "by_country": by_country,
        }

    def analyze_weights(self) -> dict[str, Any]:
        """Analyze package weights (actual vs billed).

        Returns:
            Dictionary with weight analysis data
        """
        packages = self.packages
        if packages.empty:
            return {"summary": {}, "distribution": pd.DataFrame()}

        # Filter out zero/null weights
        weight_data = packages[
            (packages["billed_weight"] > 0) | (packages["actual_weight"] > 0)
        ].copy()

        if weight_data.empty:
            return {"summary": {}, "distribution": pd.DataFrame()}

        weight_data["weight_diff"] = (
            weight_data["billed_weight"] - weight_data["actual_weight"]
        )

        summary = {
            "total_actual_weight": weight_data["actual_weight"].sum(),
            "total_billed_weight": weight_data["billed_weight"].sum(),
            "avg_actual_weight": weight_data["actual_weight"].mean(),
            "avg_billed_weight": weight_data["billed_weight"].mean(),
            "weight_premium": (
                (
                    weight_data["billed_weight"].sum()
                    - weight_data["actual_weight"].sum()
                )
                / weight_data["actual_weight"].sum()
                * 100
                if weight_data["actual_weight"].sum() > 0
                else 0
            ),
            "packages_with_dim_weight": (weight_data["weight_diff"] > 0).sum(),
        }

        # Weight distribution buckets
        bins = [0, 0.5, 1, 2, 5, 10, 20, 50, float("inf")]
        labels = [
            "0-0.5kg",
            "0.5-1kg",
            "1-2kg",
            "2-5kg",
            "5-10kg",
            "10-20kg",
            "20-50kg",
            "50kg+",
        ]
        weight_data["weight_bucket"] = pd.cut(
            weight_data["billed_weight"], bins=bins, labels=labels
        )

        distribution = (
            weight_data.groupby("weight_bucket", observed=True)
            .agg(
                {
                    "tracking_number": "count",
                    "total_charge": "sum",
                }
            )
            .reset_index()
        )
        distribution.columns = ["weight_range", "package_count", "total_cost"]

        return {
            "summary": summary,
            "distribution": distribution,
            "detail": weight_data[
                ["tracking_number", "actual_weight", "billed_weight", "weight_diff"]
            ],
        }

    def analyze_services(self) -> pd.DataFrame:
        """Analyze costs by service type.

        Returns:
            DataFrame with service-level aggregations
        """
        packages = self.packages
        if packages.empty:
            return pd.DataFrame()

        by_service = (
            packages.groupby(["service_code", "service_name"])
            .agg(
                {
                    "tracking_number": "count",
                    "total_charge": "sum",
                    "billed_weight": "sum",
                }
            )
            .reset_index()
        )

        by_service.columns = [
            "service_code",
            "service_name",
            "package_count",
            "total_cost",
            "total_weight",
        ]

        by_service["avg_cost_per_package"] = (
            by_service["total_cost"] / by_service["package_count"]
        ).round(2)

        return by_service.sort_values("total_cost", ascending=False)

    def analyze_duties_and_brokerage(self) -> dict[str, Any]:
        """Analyze import duties and brokerage costs.

        These are charges for shipments with shipment_subtype=IMP, typically
        under F/D (Free Domicile) payment terms where the sender pays import
        costs at the destination country.

        Returns:
            Dictionary with summary, charge breakdown, by-country analysis, and detail
        """
        if self.data.empty:
            return {
                "summary": {},
                "by_charge_type": pd.DataFrame(),
                "by_country": pd.DataFrame(),
                "detail": pd.DataFrame(),
            }

        df = self.data

        # Filter for IMP (import) shipments - these have duties/brokerage charges
        imp_data = df[df["shipment_subtype"] == "IMP"].copy()

        if imp_data.empty:
            return {
                "summary": {},
                "by_charge_type": pd.DataFrame(),
                "by_country": pd.DataFrame(),
                "detail": pd.DataFrame(),
            }

        # Get unique tracking numbers with IMP charges
        imp_trackings = imp_data["tracking_number"].unique()

        # Summary statistics
        total_cost = imp_data["net_amount"].sum()
        brokerage_cost = imp_data[imp_data["charge_category"] == "BRK"][
            "net_amount"
        ].sum()
        customs_cost = imp_data[imp_data["charge_category"] == "GOV"][
            "net_amount"
        ].sum()
        other_cost = total_cost - brokerage_cost - customs_cost

        summary = {
            "total_cost": total_cost,
            "shipment_count": len(imp_trackings),
            "brokerage_cost": brokerage_cost,
            "customs_cost": customs_cost,
            "other_cost": other_cost,
            "avg_cost_per_shipment": total_cost / len(imp_trackings)
            if len(imp_trackings) > 0
            else 0,
        }

        # Breakdown by charge type (BRK, GOV, etc.)
        by_charge_type = (
            imp_data.groupby(["charge_category", "charge_category_name"])
            .agg(
                {
                    "net_amount": "sum",
                    "tracking_number": "nunique",
                }
            )
            .reset_index()
        )
        by_charge_type.columns = [
            "charge_category",
            "charge_name",
            "total_cost",
            "shipment_count",
        ]
        by_charge_type = by_charge_type.sort_values("total_cost", ascending=False)

        # By destination country (recipient_country - where goods are imported to)
        # Get country from the FRT or first row per tracking
        country_data = (
            imp_data.groupby("tracking_number")
            .agg(
                {
                    "recipient_country": "first",
                    "recipient_name": "first",
                    "recipient_city": "first",
                    "order_reference": "first",
                    "shipment_date": "first",
                    "net_amount": "sum",
                }
            )
            .reset_index()
        )

        by_country = (
            country_data.groupby("recipient_country")
            .agg(
                {
                    "tracking_number": "count",
                    "net_amount": "sum",
                }
            )
            .reset_index()
        )
        by_country.columns = ["country_code", "shipment_count", "total_cost"]
        by_country = by_country[by_country["country_code"].notna()]

        if HAS_PYCOUNTRY:
            by_country["country_name"] = by_country["country_code"].apply(
                self._get_country_name
            )
        else:
            by_country["country_name"] = by_country["country_code"]

        by_country["avg_cost_per_shipment"] = (
            by_country["total_cost"] / by_country["shipment_count"]
        ).round(2)
        by_country = by_country.sort_values("total_cost", ascending=False)

        # Detail: Per-shipment breakdown with BRK and GOV costs
        # Pivot to get BRK and GOV as separate columns
        detail_pivot = imp_data.pivot_table(
            index="tracking_number",
            columns="charge_category",
            values="net_amount",
            aggfunc="sum",
            fill_value=0,
        ).reset_index()

        # Merge with shipment info
        detail = country_data[
            [
                "tracking_number",
                "recipient_country",
                "recipient_name",
                "recipient_city",
                "order_reference",
                "shipment_date",
                "net_amount",
            ]
        ].copy()
        detail.columns = [
            "tracking_number",
            "country",
            "recipient",
            "city",
            "order_reference",
            "shipment_date",
            "total_cost",
        ]

        # Add BRK and GOV columns if they exist
        if "BRK" in detail_pivot.columns:
            detail = detail.merge(
                detail_pivot[["tracking_number", "BRK"]],
                on="tracking_number",
                how="left",
            )
            detail["BRK"] = detail["BRK"].fillna(0)
        else:
            detail["BRK"] = 0

        if "GOV" in detail_pivot.columns:
            detail = detail.merge(
                detail_pivot[["tracking_number", "GOV"]],
                on="tracking_number",
                how="left",
            )
            detail["GOV"] = detail["GOV"].fillna(0)
        else:
            detail["GOV"] = 0

        detail = detail.sort_values("total_cost", ascending=False)

        return {
            "summary": summary,
            "by_charge_type": by_charge_type,
            "by_country": by_country,
            "detail": detail,
        }

    def analyze_accessorials(self) -> dict[str, Any]:
        """Analyze accessorial charges (ACC).

        Accessorial charges include surcharges like:
        - RES: Residential Delivery
        - PFR/PFC: Surge Fees (Residential/Commercial)
        - FIP: International Processing Fee
        - RDS/ESD/LDS: Delivery Area Surcharges
        - SCF: Shipping Correction Fee
        - And more...

        Returns:
            Dictionary with summary, breakdown by charge code, by country, and trends
        """
        if self.data.empty:
            return {
                "summary": {},
                "by_charge_code": pd.DataFrame(),
                "by_country": pd.DataFrame(),
                "trends": pd.DataFrame(),
            }

        df = self.data

        # Filter for ACC (Accessorial) charges
        acc_data = df[df["charge_category"] == "ACC"].copy()

        if acc_data.empty:
            return {
                "summary": {},
                "by_charge_code": pd.DataFrame(),
                "by_country": pd.DataFrame(),
                "trends": pd.DataFrame(),
            }

        # Summary statistics
        total_cost = acc_data["net_amount"].sum()
        total_rows = len(acc_data)
        unique_trackings = acc_data["tracking_number"].nunique()

        # Top charge types
        residential_cost = acc_data[acc_data["charge_code"] == "RES"][
            "net_amount"
        ].sum()
        surge_cost = acc_data[acc_data["charge_code"].isin(["PFR", "PFC"])][
            "net_amount"
        ].sum()
        area_surcharge_cost = acc_data[
            acc_data["charge_code"].isin(["RDS", "ESD", "LDS", "HIS", "AKS"])
        ]["net_amount"].sum()

        summary = {
            "total_cost": total_cost,
            "charge_count": total_rows,
            "shipment_count": unique_trackings,
            "residential_cost": residential_cost,
            "surge_cost": surge_cost,
            "area_surcharge_cost": area_surcharge_cost,
            "avg_per_shipment": total_cost / unique_trackings
            if unique_trackings > 0
            else 0,
        }

        # Breakdown by charge code
        by_charge_code = (
            acc_data.groupby(["charge_code", "charge_description"])
            .agg(
                {
                    "net_amount": "sum",
                    "tracking_number": "nunique",
                }
            )
            .reset_index()
        )
        by_charge_code.columns = [
            "charge_code",
            "description",
            "total_cost",
            "shipment_count",
        ]
        by_charge_code = by_charge_code.sort_values("total_cost", ascending=False)

        # By destination country
        # First get country per tracking, then sum accessorial costs
        tracking_country = (
            df[df["recipient_country"].notna()]
            .groupby("tracking_number")["recipient_country"]
            .first()
            .reset_index()
        )

        acc_by_tracking = (
            acc_data.groupby("tracking_number")["net_amount"].sum().reset_index()
        )
        acc_by_tracking.columns = ["tracking_number", "acc_cost"]

        acc_with_country = acc_by_tracking.merge(
            tracking_country, on="tracking_number", how="left"
        )

        by_country = (
            acc_with_country.groupby("recipient_country")
            .agg(
                {
                    "tracking_number": "count",
                    "acc_cost": "sum",
                }
            )
            .reset_index()
        )
        by_country.columns = ["country_code", "shipment_count", "total_cost"]
        by_country = by_country[by_country["country_code"].notna()]

        if HAS_PYCOUNTRY:
            by_country["country_name"] = by_country["country_code"].apply(
                self._get_country_name
            )
        else:
            by_country["country_name"] = by_country["country_code"]

        by_country["avg_per_shipment"] = (
            by_country["total_cost"] / by_country["shipment_count"]
        ).round(2)
        by_country = by_country.sort_values("total_cost", ascending=False)

        # Trends over time
        trends = pd.DataFrame()
        if (
            "shipment_date" in acc_data.columns
            and acc_data["shipment_date"].notna().any()
        ):
            acc_data_with_dates = acc_data[acc_data["shipment_date"].notna()].copy()
            acc_data_with_dates["period"] = acc_data_with_dates[
                "shipment_date"
            ].dt.strftime("%Y-%m")

            trends = (
                acc_data_with_dates.groupby("period")
                .agg(
                    {
                        "net_amount": "sum",
                        "tracking_number": "nunique",
                    }
                )
                .reset_index()
            )
            trends.columns = ["period", "total_cost", "shipment_count"]
            trends = trends.sort_values("period")

        return {
            "summary": summary,
            "by_charge_code": by_charge_code,
            "by_country": by_country,
            "trends": trends,
        }

    def get_top_expenses(self, n: int = 20) -> pd.DataFrame:
        """Get the most expensive packages.

        Args:
            n: Number of top packages to return

        Returns:
            DataFrame with top N most expensive packages
        """
        packages = self.packages
        if packages.empty:
            return pd.DataFrame()

        # Build column list dynamically based on what's available
        # For outbound SHP shipments: recipient is the customer
        desired_cols = [
            "tracking_number",
            "order_reference",
            "shipment_date",
            "recipient_name",  # Customer for outbound SHP shipments
            "recipient_company",
            "recipient_city",
            "recipient_country",
            "sender_name",  # Account holder for most shipments
            "sender_country",
            "service_name",
            "billed_weight",
            "goods_description",
            "total_charge",
            "shipment_type",
            "is_return",
        ]
        # Only include columns that exist in packages
        available_cols = [col for col in desired_cols if col in packages.columns]
        top = packages.nlargest(n, "total_charge")[available_cols].copy()

        return top

    def filter_data(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        countries: list[str] | None = None,
        services: list[str] | None = None,
        returns_only: bool = False,
    ) -> "InvoiceAnalyzer":
        """Create a new analyzer with filtered data.

        Args:
            start_date: Filter shipments from this date (YYYY-MM-DD)
            end_date: Filter shipments until this date (YYYY-MM-DD)
            countries: List of destination country codes to include (recipient_country)
            services: List of service codes to include
            returns_only: Only include return shipments

        Returns:
            New InvoiceAnalyzer with filtered data
        """
        filtered = self.data.copy()

        if start_date:
            filtered = filtered[filtered["shipment_date"] >= start_date]

        if end_date:
            filtered = filtered[filtered["shipment_date"] <= end_date]

        if countries:
            # Use recipient_country as this data shows outbound shipments
            filtered = filtered[filtered["recipient_country"].isin(countries)]

        if services:
            filtered = filtered[filtered["service_code"].isin(services)]

        if returns_only:
            filtered = filtered[filtered["is_return"] == True]

        return InvoiceAnalyzer(filtered)

    @staticmethod
    def _get_country_name(code: str) -> str:
        """Get country name from ISO code."""
        if not HAS_PYCOUNTRY or not code:
            return code or "Unknown"
        try:
            country = pycountry.countries.get(alpha_2=code)
            return country.name if country else code
        except Exception:
            return code
