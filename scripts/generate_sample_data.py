"""Generate the bundled demo dataset.

The dataset is produced by this committed, seeded script rather than shipped
as an opaque CSV, so a reader can see exactly what was planted and check
that SmartAnalyst finds it.

Planted deliberately:

* a strong revenue-to-cost correlation
* a right-skewed unit_price distribution
* missing values in rating and delivery_days
* bulk-order outliers in units, carried by the wholesale channel
* exact duplicate rows, as real exports contain
* seasonality across order_date

Run from the repository root:

    python scripts/generate_sample_data.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20260810
N = 5000
OUTPUT = Path("data/sample_orders.csv")

DUPLICATE_COUNT = 40
RATING_NULL_SHARE = 0.22
DELIVERY_NULL_SHARE = 0.09


def build() -> pd.DataFrame:
    """Return the dataset. Deterministic: same seed, same frame, every time."""
    rng = np.random.default_rng(SEED)

    dates = pd.to_datetime("2024-01-01") + pd.to_timedelta(rng.integers(0, 730, N), unit="D")
    # Demand peaks mid-year and dips in winter.
    seasonality = 1.0 + 0.35 * np.sin((dates.month - 1) / 12 * 2 * np.pi)

    category = rng.choice(
        ["Apparel", "Footwear", "Accessories", "Outerwear"], N, p=[0.35, 0.28, 0.22, 0.15]
    )
    region = rng.choice(["North", "South", "East", "West"], N)
    channel = rng.choice(["Online", "Retail", "Wholesale"], N, p=[0.55, 0.32, 0.13])
    segment = rng.choice(["Consumer", "Corporate", "Home Office"], N, p=[0.60, 0.25, 0.15])

    units = rng.integers(1, 12, N).astype(float)
    # Planted outliers, sourced realistically: wholesale buys in bulk, so the
    # extreme quantities belong to a channel rather than being sprinkled at
    # random. This also gives the demo a genuine pattern to discover.
    wholesale = channel == "Wholesale"
    units[wholesale] = rng.integers(40, 400, int(wholesale.sum()))

    # Gamma gives the right-skew that real price distributions have.
    unit_price = np.round(rng.gamma(3.0, 18.0, N) + 5, 2)
    discount = np.round(
        rng.choice([0.0, 0.05, 0.10, 0.15, 0.25], N, p=[0.50, 0.20, 0.15, 0.10, 0.05]), 2
    )

    revenue = np.round(units * unit_price * (1 - discount) * seasonality, 2)
    # Planted correlation: cost tracks revenue at a noisy margin.
    cost = np.round(revenue * rng.normal(0.62, 0.04, N).clip(0.40, 0.85), 2)
    profit = np.round(revenue - cost, 2)

    delivery_days = rng.integers(1, 15, N).astype(float)
    rating = rng.integers(1, 6, N).astype(float)
    # Planted nulls: not everyone leaves a review, and some deliveries are open.
    rating[rng.random(N) < RATING_NULL_SHARE] = np.nan
    delivery_days[rng.random(N) < DELIVERY_NULL_SHARE] = np.nan

    frame = pd.DataFrame(
        {
            "order_id": np.arange(1, N + 1),
            "order_date": dates,
            "region": region,
            "category": category,
            "channel": channel,
            "customer_segment": segment,
            "units": units.astype(int),
            "unit_price": unit_price,
            "discount_pct": discount,
            "revenue": revenue,
            "cost": cost,
            "profit": profit,
            "delivery_days": delivery_days,
            "rating": rating,
        }
    ).sort_values("order_date", kind="stable").reset_index(drop=True)

    # Planted duplicates. Dropping order_id from the copies makes them exact
    # repeats, which is what a double-exported report actually looks like.
    duplicates = frame.sample(DUPLICATE_COUNT, random_state=SEED)
    return pd.concat([frame, duplicates], ignore_index=True)


if __name__ == "__main__":
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frame = build()
    frame.to_csv(OUTPUT, index=False)
    print(f"Wrote {OUTPUT} with {len(frame):,} rows and {len(frame.columns)} columns")
