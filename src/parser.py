"""UPS Invoice CSV Parser.

Parses UPS Billing Data CSV exports (no headers) and extracts key fields
into a structured DataFrame for analysis.
"""

import pandas as pd
import io
from datetime import datetime
from typing import BinaryIO


# UPS Billing Data CSV column mapping (0-indexed)
# Based on UPS Billing Data export format (verified against actual invoices)
#
# IMPORTANT: The charge columns are:
# - col51 = Rabatt (Discount amount) - the discount applied
# - col52 = Nettotarif (Net amount) - the actual charge AFTER discount
# Sum of col52 = Invoice total (col10)
#
COLUMN_MAPPING = {
    "version": 0,
    "account_number": 1,
    "shipper_number": 2,
    "country_code": 3,
    "invoice_date": 4,
    "invoice_number": 5,
    "invoice_type": 6,  # I=Invoice, E=Adjustment
    "invoice_type_detail": 7,
    "vat_number": 8,
    "currency": 9,
    "invoice_total": 10,  # Total invoice amount (same for all rows in invoice)
    "shipment_date": 11,
    "reference_1": 13,
    "order_reference": 15,  # e.g., #201630
    "payment_terms": 17,  # F/C, P/P
    "package_indicator": 18,  # 1=package line, 0=charge line
    "tracking_number": 20,
    "actual_weight": 26,
    "actual_weight_unit": 27,
    "billed_weight": 28,
    "billed_weight_unit": 29,
    "package_type": 30,  # PKG
    "zone": 31,
    "service_code": 33,  # 353, 354, 355, 755, etc.
    "shipment_type": 34,  # RTN (Return), etc.
    "shipment_subtype": 35,  # RTS (Return to Sender), ADC (Address Correction), etc.
    "charge_category": 43,  # FRT, FSC, TAX, ACC, EXM, INF
    "charge_code": 44,  # 011, 067, FSC, 01, RET, etc.
    "charge_description": 45,  # TB Standard, Fuel Surcharge, Tax, etc.
    "discount_amount": 51,  # Rabatt - the discount (NOT used for totals)
    "net_amount": 52,  # Nettotarif - the actual charge after discount (THIS is summed)
    # Sender (Absender) - col67-73
    "sender_name": 67,
    "sender_street": 68,
    "sender_city": 70,
    "sender_postal": 72,
    "sender_country": 73,
    # Recipient (Empfänger) - col74-81
    "recipient_name": 74,
    "recipient_company": 75,
    "recipient_street": 76,
    "recipient_city": 78,
    "recipient_postal": 80,
    "recipient_country": 81,
    "pickup_date": 116,
    "delivery_date": 117,
    "declared_value": 129,
    "goods_description": 130,
    "entered_weight_note": 174,  # Weight entered by shipper (for adjustment rows)
    "audited_weight_note": 175,  # Weight audited by UPS (for adjustment rows)
}

# Service code to name mapping
# NOTE: This mapping is unreliable as multiple service codes map to the same service.
# The service_code appears to encode both service type AND route/pricing tier.
# Always use charge_description from the FRT row for accurate service names.
# This dict is kept for backward compatibility but should not be relied upon.
SERVICE_CODES = {
    "007": "WW Express Saver",
    "704": "WW Standard",
    "004": "TB Standard",
    "003": "TB Standard",
    "005": "TB Standard",
    "031": "TB Standard",
    "041": "TB Standard",
    "000": "Address Correction",
    "353": "TB Standard Undeliverable Return",
    "354": "TB Standard Undeliverable Return",
    "355": "TB Standard Undeliverable Return",
    "402": "TB Standard Undeliverable Return",
    "755": "WW Standard Undeliverable Return",
    "857": "WW Express Saver Undeliverable Return",
    "001": "Dom. Standard",
}

# Charge category descriptions
CHARGE_CATEGORIES = {
    "FRT": "Freight",
    "FSC": "Fuel Surcharge",
    "TAX": "Tax (VAT)",
    "ACC": "Accessorial",
    "EXM": "Exemption/Credit",
    "INF": "Information Only",
    "MSC": "Miscellaneous",
    "BRK": "Brokerage",
    "GOV": "Government Charges",
    "DAS": "Delivery Area Surcharge",
    "RES": "Residential Surcharge",
}


class UPSInvoiceParser:
    """Parser for UPS Billing Data CSV files."""

    def __init__(self):
        self.raw_data: pd.DataFrame | None = None
        self.parsed_data: pd.DataFrame | None = None

    def parse_file(self, file: BinaryIO, filename: str = "uploaded") -> pd.DataFrame:
        """Parse a single CSV file from a file-like object.

        Args:
            file: File-like object containing CSV data
            filename: Name of the file (for metadata)

        Returns:
            DataFrame with parsed invoice data
        """
        content = file.read()
        if isinstance(content, bytes):
            # Try different encodings - UPS exports often use latin-1 or cp1252
            for encoding in ["utf-8", "latin-1", "cp1252"]:
                try:
                    content = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                content = content.decode("utf-8", errors="replace")

        return self.parse_csv_content(content, filename)

    def parse_csv_content(
        self, content: str, filename: str = "uploaded"
    ) -> pd.DataFrame:
        """Parse CSV content string.

        Args:
            content: CSV content as string
            filename: Name of the source file

        Returns:
            DataFrame with parsed invoice data
        """
        # Read CSV without headers
        df = pd.read_csv(
            io.StringIO(content),
            header=None,
            dtype=str,
            on_bad_lines="skip",
        )

        self.raw_data = df

        # Extract relevant columns
        parsed = pd.DataFrame()

        # Map columns that exist
        max_col = len(df.columns)

        for field_name, col_idx in COLUMN_MAPPING.items():
            if col_idx < max_col:
                parsed[field_name] = df.iloc[:, col_idx]
            else:
                parsed[field_name] = None

        # Add source filename
        parsed["source_file"] = filename

        # Convert data types
        parsed = self._convert_types(parsed)

        # Add derived fields
        parsed = self._add_derived_fields(parsed)

        self.parsed_data = parsed
        return parsed

    def parse_multiple_files(self, files: list[tuple[BinaryIO, str]]) -> pd.DataFrame:
        """Parse multiple CSV files and combine into single DataFrame.

        Args:
            files: List of (file_object, filename) tuples

        Returns:
            Combined DataFrame with all invoice data
        """
        all_data = []

        for file_obj, filename in files:
            try:
                df = self.parse_file(file_obj, filename)
                all_data.append(df)
            except Exception as e:
                print(f"Error parsing {filename}: {e}")
                continue

        if not all_data:
            return pd.DataFrame()

        combined = pd.concat(all_data, ignore_index=True)
        self.parsed_data = combined
        return combined

    def _convert_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert column data types."""
        # Numeric columns
        numeric_cols = [
            "invoice_total",
            "actual_weight",
            "billed_weight",
            "discount_amount",
            "net_amount",
            "declared_value",
        ]

        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # Date columns
        date_cols = ["invoice_date", "shipment_date", "pickup_date", "delivery_date"]

        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        # Clean string columns - strip whitespace
        string_cols = [
            "tracking_number",
            "charge_category",
            "charge_code",
            "charge_description",
            "sender_name",
            "sender_street",
            "sender_city",
            "sender_country",
            "recipient_name",
            "recipient_company",
            "recipient_street",
            "recipient_city",
            "recipient_country",
            "entered_weight_note",
            "audited_weight_note",
            "goods_description",
            "service_code",
            "shipment_type",
            "shipment_subtype",
        ]
        for col in string_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
                df[col] = df[col].replace({"nan": None, "": None})

        return df

    def _add_derived_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add calculated/derived fields."""
        # Total charge is just net_amount (Nettotarif - the actual charge after discount)
        # The discount_amount column shows how much was discounted, not an additional charge
        df["total_charge"] = df["net_amount"]

        # Service name: Use charge_description from FRT rows as primary source
        # The charge_description on FRT rows contains the actual service name (e.g., "TB Standard", "WW Express Saver")
        # Fall back to SERVICE_CODES mapping only if charge_description is empty
        df["service_name"] = df.apply(
            lambda row: row["charge_description"]
            if row["charge_category"] == "FRT"
            and pd.notna(row["charge_description"])
            and row["charge_description"].strip()
            else SERVICE_CODES.get(row["service_code"], "Other"),
            axis=1,
        )

        # Charge category name
        df["charge_category_name"] = (
            df["charge_category"].map(CHARGE_CATEGORIES).fillna("Other")
        )

        # Is this a package line (vs charge-only line)?
        df["is_package_line"] = df["package_indicator"] == "1"

        # Is this a return shipment?
        df["is_return"] = df["shipment_type"] == "RTN"

        # Weight difference (billed vs actual)
        df["weight_difference"] = df["billed_weight"] - df["actual_weight"]

        # Extract week and month for trend analysis
        if df["shipment_date"].notna().any():
            df["shipment_week"] = df["shipment_date"].dt.isocalendar().week
            df["shipment_month"] = df["shipment_date"].dt.to_period("M").astype(str)
            df["shipment_year_month"] = df["shipment_date"].dt.strftime("%Y-%m")

        return df

    def get_packages(self) -> pd.DataFrame:
        """Get unique packages with aggregated charges.

        Per UPS Billing Data structure, each tracking number has multiple rows:
        - package_indicator=1: Package/shipment line with weight data
        - package_indicator=0: Charge-only lines (no weight data)

        This method aggregates by tracking number, pulling shipment info
        from the FRT row with package_indicator=1 for accurate data.

        Returns:
            DataFrame with one row per package, charges aggregated
        """
        if self.parsed_data is None:
            return pd.DataFrame()

        df = self.parsed_data

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

    def get_charge_breakdown(self) -> pd.DataFrame:
        """Get charges broken down by category.

        Returns:
            DataFrame with charges grouped by charge category
        """
        if self.parsed_data is None:
            return pd.DataFrame()

        df = self.parsed_data

        breakdown = (
            df.groupby(["charge_category", "charge_category_name"])
            .agg(
                {
                    "discount_amount": "sum",
                    "net_amount": "sum",
                    "total_charge": "sum",
                    "tracking_number": "nunique",
                }
            )
            .reset_index()
        )

        breakdown.columns = [
            "charge_category",
            "charge_category_name",
            "discount_amount",
            "net_amount",
            "total_charge",
            "package_count",
        ]

        return breakdown.sort_values("total_charge", ascending=False)


def load_invoices_from_folder(folder_path: str) -> pd.DataFrame:
    """Load all CSV invoices from a folder.

    Args:
        folder_path: Path to folder containing invoice CSVs

    Returns:
        Combined DataFrame with all invoice data
    """
    import os
    from pathlib import Path

    folder = Path(folder_path)
    csv_files = list(folder.glob("*.csv"))

    if not csv_files:
        return pd.DataFrame()

    parser = UPSInvoiceParser()
    all_data = []

    for csv_path in csv_files:
        try:
            with open(csv_path, "rb") as f:
                df = parser.parse_file(f, csv_path.name)
                all_data.append(df)
        except Exception as e:
            print(f"Error loading {csv_path.name}: {e}")
            continue

    if not all_data:
        return pd.DataFrame()

    return pd.concat(all_data, ignore_index=True)
