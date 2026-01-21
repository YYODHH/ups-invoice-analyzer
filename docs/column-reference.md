# UPS Billing Data CSV Column Reference

This document describes the columns in UPS Billing Data CSV exports, based on analysis of actual invoice data.

**Legend:**
- ✅ Confirmed - meaning verified against multiple data points
- ⚠️ Inferred - meaning derived from data patterns, may need verification
- ❓ Unclear - meaning not fully understood

---

## Row Structure

**IMPORTANT:** Each tracking number has multiple rows. Each row represents a different charge or information line for the same shipment.

| package_indicator | Meaning | Has Weight Data? | Typical charge_category |
|-------------------|---------|------------------|------------------------|
| `1` | Package/shipment line | Yes | FRT, INF |
| `0` | Charge-only line | No | FSC, ACC, TAX, BRK, GOV, EXM |
| `3` | Unknown (rare, 3 occurrences) | Yes | FRT |

To get accurate shipment data, filter for `package_indicator=1` and `charge_category=FRT`.

---

## Invoice-Level Fields

These fields have the same value for all rows within an invoice.

| Column | Index | Confidence | Description | Sample Values |
|--------|-------|------------|-------------|---------------|
| `version` | col0 | ✅ | CSV format version | `2.1` |
| `account_number` | col1 | ✅ | UPS account number | `0000XXXXXX` |
| `shipper_number` | col2 | ✅ | UPS shipper number (same as account) | `0000XXXXXX` |
| `country_code` | col3 | ✅ | Account country | `DE` |
| `invoice_date` | col4 | ✅ | Invoice issue date | `2026-01-07` |
| `invoice_number` | col5 | ✅ | Invoice identifier | `000123456789` |
| `invoice_type` | col6 | ✅ | `I`=Import shipments + Returns, `E`=European/Domestic (non-import) | `I`, `E` |
| `invoice_type_detail` | col7 | ❓ | Sub-type identifier | `1`, `5`, `6` |
| `vat_number` | col8 | ✅ | VAT registration number | `DEXXXXXXXXX` |
| `currency` | col9 | ✅ | Billing currency | `EUR` |
| `invoice_total` | col10 | ✅ | Total invoice amount (header-level, same for all rows) | `21124.52` |

### Invoice Type Notes

| invoice_type | invoice_type_detail | Contains | Description |
|--------------|---------------------|----------|-------------|
| `E` | `1` | SHP (NSD, ISD) + ADJ + MIS | European/Domestic shipments and adjustments |
| `I` | `5` | SHP (IMP only) | Import shipments (with customs/brokerage) |
| `I` | `6` | RTN (RTS) | Return to Sender shipments |

---

## Shipment-Level Fields

These fields are consistent across all rows for the same tracking number.

| Column | Index | Confidence | Description | Sample Values |
|--------|-------|------------|-------------|---------------|
| `tracking_number` | col20 | ✅ | UPS tracking number | `1ZXXXXXXXXXXXXXXXX` |
| `reference_1` | col13 | ⚠️ | Reference field (often same as tracking) | `1ZXXXXXXXXXXXXXXXX` |
| `order_reference` | col15 | ✅ | Customer order reference | `#123456`, `#789012` |
| `shipment_date` | col11 | ✅ | Date shipment was processed | `2025-12-23` |
| `payment_terms` | col17 | ✅ | Payment arrangement | `P/P`, `F/C`, `F/D` |
| `shipment_type` | col34 | ✅ | Type of shipment record | `SHP`, `RTN`, `ADJ`, `MIS` |
| `shipment_subtype` | col35 | ✅ | Shipment sub-classification | See table below |
| `service_code` | col33 | ⚠️ | UPS service identifier | `007`, `353`, `704` |
| `zone` | col31 | ⚠️ | Shipping zone (pricing tier) | `08`, `09`, `29`, `30` |
| `package_type` | col30 | ✅ | Package classification | `PKG` |

### shipment_type Values

| Value | Meaning | Description |
|-------|---------|-------------|
| `SHP` | Shipment | Regular outbound shipments |
| `RTN` | Return | Return shipments (RTS - Return to Sender) |
| `ADJ` | Adjustment | Billing adjustments, corrections |
| `MIS` | Miscellaneous | Service charges (no tracking number) |

### shipment_subtype Values

| Value | Meaning | shipment_type | Description |
|-------|---------|---------------|-------------|
| `NSD` | Non-document Standard Domestic | SHP | Domestic/EU packages |
| `ISD` | International Standard | SHP | International shipments |
| `DSD` | Document Standard Domestic | SHP | Document shipments |
| `IMP` | Import | SHP | Import shipments with customs/brokerage |
| `RTS` | Return to Sender | RTN | Undeliverable returns |
| `ADJ` | Adjustment | ADJ | General billing adjustments |
| `RADJ` | Rate Adjustment | ADJ | Rate/price corrections |
| `ADC` | Address Correction | ADJ | Address correction charges |
| `SVCH` | Service Charge | MIS | Weekly service fees |

### payment_terms Values

| Value | Meaning | Description |
|-------|---------|-------------|
| `P/P` | Prepaid | Sender pays shipping |
| `F/D` | Free Domicile | Seller pays all costs to destination (incl. import duties) |
| `F/C` | Freight Collect | Recipient pays shipping |

### service_code → Service Name Mapping

**NOTE:** Multiple service codes can map to the same service name. The code appears to encode both service type AND route/pricing tier. For example:
- US/CA shipments use code `007` (WW Express Saver)
- GB shipments use code `704` (WW Standard)  
- FR/IT/EU shipments use codes `003`, `004`, `005` (TB Standard variants)

**Always use `charge_description` from the `FRT` row for the actual service name.**

| service_code | Actual Service (from charge_description) |
|--------------|------------------------------------------|
| `007` | WW Express Saver |
| `704` | WW Standard |
| `003`, `004`, `005`, `031`, `041` | TB Standard |
| `000` | Address Correction |
| `006` | WW Standard |
| `010` | WW Express Saver |
| `353`, `354`, `355`, `402` | TB Standard Undeliverable Return |
| `755` | WW Standard Undeliverable Return |
| `857` | WW Express Saver Undeliverable Return |
| `042` | TB Express Saver |
| `001` | Dom. Standard |

---

## Charge Fields

These fields vary per row (each row = one charge type).

| Column | Index | Confidence | Description | Sample Values |
|--------|-------|------------|-------------|---------------|
| `package_indicator` | col18 | ✅ | Row type indicator | `0`, `1`, `3` |
| `charge_category` | col43 | ✅ | Charge classification | `FRT`, `FSC`, `ACC`, `TAX` |
| `charge_code` | col44 | ⚠️ | Specific charge identifier | `011`, `01`, `SCF`, `067` |
| `charge_description` | col45 | ✅ | Human-readable charge name | `TB Standard`, `Treibstoffzuschl.` |
| `discount_amount` | col51 | ✅ | Discount applied (Rabatt) | `4.09`, `0.0` |
| `net_amount` | col52 | ✅ | **Actual charge after discount (Nettotarif)** | `2.13`, `0.09` |

### charge_category Values

| Value | Name | Description |
|-------|------|-------------|
| `FRT` | Freight | Base shipping charge |
| `FSC` | Fuel Surcharge | Fuel surcharge |
| `ACC` | Accessorial | Additional services (residential, surge, etc.) |
| `TAX` | Tax | VAT/Tax charges |
| `BRK` | Brokerage | Customs brokerage fees |
| `GOV` | Government | Customs duties (Zoll) |
| `EXM` | Exemption | Exemptions/credits (informational) |
| `INF` | Information | Informational lines (no charge) |
| `MSC` | Miscellaneous | Weekly service fee |

### Calculating Totals

**Sum `net_amount` to get total charges.** The `discount_amount` column shows what was discounted from the base rate, not an additional charge.

```
Total Cost = SUM(net_amount)
```

Verified: `SUM(net_amount)` ≈ `invoice_total` for each invoice (minor rounding differences).

---

## Address Fields

### Sender (Absender) - col67-73

| Column | Index | Confidence | Description | Fill Rate |
|--------|-------|------------|-------------|-----------|
| `sender_name` | col67 | ✅ | Sender company/person name | 87% |
| `sender_street` | col68 | ✅ | Sender street address | 87% |
| `sender_city` | col70 | ✅ | Sender city | 87% |
| `sender_postal` | col72 | ✅ | Sender postal code | 87% |
| `sender_country` | col73 | ✅ | Sender country (ISO 2-letter) | 87% |

### Recipient (Empfänger) - col74-81

| Column | Index | Confidence | Description | Fill Rate |
|--------|-------|------------|-------------|-----------|
| `recipient_name` | col74 | ✅ | Recipient person name | 66% |
| `recipient_company` | col75 | ✅ | Recipient company name | 87% |
| `recipient_street` | col76 | ✅ | Recipient street address | 87% |
| `recipient_city` | col78 | ✅ | Recipient city | 87% |
| `recipient_postal` | col80 | ✅ | Recipient postal code | 87% |
| `recipient_country` | col81 | ✅ | Recipient country (ISO 2-letter) | 87% |

### CRITICAL: Who is the Customer?

**This data represents OUTBOUND shipments from YOUR COMPANY (the account holder).**

| shipment_type | sender | recipient | Who is "customer"? |
|---------------|--------|-----------|-------------------|
| `SHP` | Your Company | External party | **Recipient** is the customer |
| `RTN` | External party (returning) | Your Company | **Sender** is the original customer |
| `ADJ` | Often duplicated or empty | Often duplicated or empty | Unreliable |

**Recommendation:** 
- For SHP shipments: display `recipient_name` and `recipient_country` as the customer
- For RTN shipments: display `sender_name` and `sender_country` as the customer (they are returning the package)

---

## Weight Fields

| Column | Index | Confidence | Description | Notes |
|--------|-------|------------|-------------|-------|
| `actual_weight` | col26 | ✅ | Actual package weight | Only on `package_indicator=1` rows |
| `actual_weight_unit` | col27 | ✅ | Weight unit | `K` (kilograms) |
| `billed_weight` | col28 | ✅ | Billed weight (may include dimensional) | Only on `package_indicator=1` rows |
| `billed_weight_unit` | col29 | ✅ | Weight unit | `K` (kilograms) |
| `declared_value` | col129 | ⚠️ | Declared customs value | Often 0 |

**NOTE:** Weight values are only populated on rows where `package_indicator=1`. On charge-only rows (`package_indicator=0`), weights are 0.

---

## Date Fields

| Column | Index | Confidence | Description | Fill Rate |
|--------|-------|------------|-------------|-----------|
| `shipment_date` | col11 | ✅ | Shipment/billing date | 100% |
| `pickup_date` | col116 | ⚠️ | Actual pickup date | 21% |
| `delivery_date` | col117 | ⚠️ | Actual delivery date | 5% |

---

## Other Fields

| Column | Index | Confidence | Description | Fill Rate |
|--------|-------|------------|-------------|-----------|
| `goods_description` | col130 | ✅ | Package contents description | 21% |

### Adjustment/Correction Notes (col174, col175)

These columns appear on adjustment rows (especially "Versandkorrekturgebühr" - Shipping Correction Fee):

| Column | Index | Description | Sample Value |
|--------|-------|-------------|--------------|
| `entered_weight_note` | col174 | Weight originally entered by shipper | `ENTERED WEIGHT: 5.0 KGS` |
| `audited_weight_note` | col175 | Weight as audited/verified by UPS | `AUDITED WEIGHT: 10.5 KGS` |

These fields explain why a weight correction charge was applied - the audited weight was higher than the entered weight.

**Note:** Column 174 was previously mapped as `return_reason` but this is incorrect. It's a general notes/reason field for adjustments.

---

## Zone Reference

Zones appear to represent distance-based pricing tiers:

| Zone | Typical Countries | Interpretation |
|------|-------------------|----------------|
| `08` | US, CA, AU, JP, KR, NZ, AE, SG | Intercontinental (far) |
| `09` | Mixed EU + some intercontinental | Medium distance |
| `29` | Mixed EU + intercontinental | Medium-far distance |
| `30` | EU countries (GB, AT, FR, IT, NL, etc.) | Intra-Europe |

---

## Summary: Recommended Aggregation Logic

When aggregating by tracking number:

```python
# For each tracking number:
# 1. Get shipment info from FRT row with package_indicator=1
frt_row = df[(df['package_indicator'] == '1') & (df['charge_category'] == 'FRT')].first()

# 2. Service name from charge_description (NOT service_code mapping)
service_name = frt_row['charge_description']

# 3. Weights from the FRT row
actual_weight = frt_row['actual_weight']
billed_weight = frt_row['billed_weight']

# 4. Customer info depends on shipment_type
if shipment_type == 'SHP':
    customer_name = recipient_name  # Outbound: recipient is customer
    customer_country = recipient_country
elif shipment_type == 'RTN':
    customer_name = sender_name  # Returns: sender is customer (returning package)
    customer_country = sender_country
else:
    customer_name = recipient_name  # Default to recipient
    customer_country = recipient_country

# 5. Total cost = sum of all net_amount for this tracking
total_cost = df.groupby('tracking_number')['net_amount'].sum()
```

---

## Unknown/Unmapped Columns

The CSV has ~175 columns. Many are unmapped. Columns not documented here were either:
- Empty in all sampled data
- Contained redundant information
- Purpose could not be determined

If you need additional columns mapped, examine the raw CSV at specific indices.
