"""Generate a deterministic, portfolio-sized sales dataset."""

import calendar
import csv
import random
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "data" / "sales_large.csv"
ROW_COUNT = 1_500
RANDOM_SEED = 20260829

PRODUCTS = {
    "Keyboard": (299, 175, 1.15),
    "Mouse": (129, 65, 1.35),
    "Monitor": (1399, 930, 0.85),
    "Webcam": (459, 235, 0.90),
    "Headset": (699, 360, 0.82),
    "Dock": (899, 510, 0.78),
    "Laptop Stand": (399, 190, 0.88),
    "Office Chair": (1699, 1050, 0.62),
}
REGIONS = ["East", "North", "South", "West", "Central"]
REGION_WEIGHTS = [1.25, 0.95, 1.00, 1.18, 0.72]
CHANNELS = ["Online", "Retail", "Partner"]
CHANNEL_WEIGHTS = [1.35, 0.95, 0.70]
CUSTOMER_SEGMENTS = ["Consumer", "SME", "Enterprise"]
SEGMENT_WEIGHTS = [1.15, 1.05, 0.80]


def choose_month(randomizer: random.Random) -> tuple[int, int]:
    """Choose an 18-month period with growth and year-end seasonality."""
    months = [(year, month) for year in (2025, 2026) for month in range(1, 13)]
    months = months[:18]
    weights = []
    for index, (_, month) in enumerate(months):
        seasonal = 1.35 if month in {11, 12} else 1.12 if month in {3, 6} else 1.0
        weights.append((1 + index * 0.018) * seasonal)
    return randomizer.choices(months, weights=weights, k=1)[0]


def generate_rows(row_count: int = ROW_COUNT) -> list[dict[str, object]]:
    """Build realistic-looking orders with repeatable patterns and anomalies."""
    randomizer = random.Random(RANDOM_SEED)
    product_names = list(PRODUCTS)
    product_weights = [PRODUCTS[name][2] for name in product_names]
    rows: list[dict[str, object]] = []

    for offset in range(row_count):
        year, month = choose_month(randomizer)
        day = randomizer.randint(1, calendar.monthrange(year, month)[1])
        product = randomizer.choices(product_names, weights=product_weights, k=1)[0]
        region = randomizer.choices(REGIONS, weights=REGION_WEIGHTS, k=1)[0]
        channel = randomizer.choices(CHANNELS, weights=CHANNEL_WEIGHTS, k=1)[0]
        segment = randomizer.choices(
            CUSTOMER_SEGMENTS, weights=SEGMENT_WEIGHTS, k=1
        )[0]
        base_price, base_cost, _ = PRODUCTS[product]

        quantity = randomizer.choices([1, 2, 3, 4, 5, 6], [30, 26, 20, 12, 8, 4], k=1)[0]
        segment_discount = {"Consumer": 1.0, "SME": 0.96, "Enterprise": 0.92}[segment]
        channel_factor = {"Online": 0.98, "Retail": 1.03, "Partner": 0.94}[channel]
        unit_price = round(
            base_price * segment_discount * channel_factor * randomizer.uniform(0.97, 1.04),
            2,
        )
        unit_cost = round(base_cost * randomizer.uniform(0.96, 1.07), 2)
        revenue = quantity * unit_price

        refund_probability = 0.045
        refund_probability += 0.045 if region == "East" else 0
        refund_probability += 0.035 if product in {"Monitor", "Office Chair"} else 0
        refund_probability += 0.018 if channel == "Online" else 0
        if randomizer.random() < refund_probability:
            refund_ratio = randomizer.choice([0.25, 0.5, 1.0])
            refund_amount = round(revenue * refund_ratio, 2)
        else:
            refund_amount = 0.0

        rows.append(
            {
                "order_id": 20_001 + offset,
                "date": date(year, month, day).isoformat(),
                "region": region,
                "product": product,
                "channel": channel,
                "customer_segment": segment,
                "customer_id": f"C{randomizer.randint(1, 420):04d}",
                "quantity": quantity,
                "unit_price": unit_price,
                "unit_cost": unit_cost,
                "refund_amount": refund_amount,
            }
        )

    return sorted(rows, key=lambda row: (row["date"], row["order_id"]))


def main() -> None:
    rows = generate_rows()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows)} rows: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
