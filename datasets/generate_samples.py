"""
generate_samples.py — Produces realistic sample datasets for AI Data Analyst.

Run: python generate_samples.py

Outputs:
  sample_sales.csv       (1000+ rows, multiple months/regions/products, with
                           intentional missing values, duplicates, and anomalies)
  sample_customers.csv   (customer master data)
  sample_feedback.csv    (free-text customer feedback for ChromaDB semantic search demo)

NOTE: Some rows in sample_sales.csv are intentionally corrupted / duplicated /
extreme for testing the Data Quality and Anomaly Detection features.
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(7)

REGIONS = ["North", "South", "East", "West"]
CATEGORIES = ["Electronics", "Furniture", "Office Supplies", "Apparel"]
PRODUCTS = {
    "Electronics": ["Wireless Mouse", "USB-C Hub", "27in Monitor", "Mechanical Keyboard", "Webcam"],
    "Furniture": ["Office Chair", "Standing Desk", "Bookshelf", "Filing Cabinet"],
    "Office Supplies": ["Notebook Pack", "Printer Paper", "Stapler", "Pen Set"],
    "Apparel": ["T-Shirt", "Hoodie", "Cap", "Jacket"],
}
SEGMENTS = ["Consumer", "Corporate", "Small Business"]

N_CUSTOMERS = 120
N_ROWS = 1100

# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------
customer_ids = [f"CUST-{i:04d}" for i in range(1, N_CUSTOMERS + 1)]
first_names = ["Aarav", "Vivaan", "Aditya", "Priya", "Ananya", "Diya", "Ishaan", "Kabir",
               "Meera", "Rohan", "Saanvi", "Tara", "Vihaan", "Zara", "Arjun", "Kiara"]
last_names = ["Sharma", "Verma", "Iyer", "Nair", "Gupta", "Reddy", "Rao", "Mehta",
              "Patel", "Singh", "Das", "Kapoor", "Chopra", "Bose", "Menon"]

customers_df = pd.DataFrame({
    "customer_id": customer_ids,
    "customer_name": [f"{rng.choice(first_names)} {rng.choice(last_names)}" for _ in range(N_CUSTOMERS)],
    "segment": rng.choice(SEGMENTS, N_CUSTOMERS, p=[0.5, 0.3, 0.2]),
    "region": rng.choice(REGIONS, N_CUSTOMERS),
})
customers_df.to_csv("sample_customers.csv", index=False)

# ---------------------------------------------------------------------------
# Sales (main analytical dataset)
# ---------------------------------------------------------------------------
dates = pd.date_range("2024-01-01", "2024-12-31", freq="D")
rows = []
order_id = 1
for _ in range(N_ROWS):
    d = rng.choice(dates)
    # Slight upward trend + weekday seasonality
    day_factor = 1.15 if pd.Timestamp(d).dayofweek < 5 else 0.85
    trend_factor = 1 + (pd.Timestamp(d) - dates[0]).days / len(dates) * 0.4

    category = rng.choice(CATEGORIES)
    product = rng.choice(PRODUCTS[category])
    region = rng.choice(REGIONS)
    cust = rng.choice(customer_ids)
    cust_name = customers_df.loc[customers_df.customer_id == cust, "customer_name"].values[0]

    qty = int(rng.integers(1, 12))
    base_price = {"Electronics": 60, "Furniture": 150, "Office Supplies": 12, "Apparel": 25}[category]
    unit_price = base_price * rng.uniform(0.8, 1.3)
    sales = round(qty * unit_price * day_factor * trend_factor, 2)
    profit_margin = rng.uniform(-0.05, 0.35)  # occasional loss-making sales
    profit = round(sales * profit_margin, 2)

    rows.append({
        "order_id": f"ORD-{order_id:05d}",
        "date": pd.Timestamp(d).strftime("%Y-%m-%d"),
        "customer_id": cust,
        "customer_name": cust_name,
        "region": region,
        "category": category,
        "product": product,
        "quantity": qty,
        "sales": sales,
        "profit": profit,
    })
    order_id += 1

sales_df = pd.DataFrame(rows)

# --- Intentional data-quality issues (documented) ---------------------------

# 1) Missing values: blank out ~2% of 'profit' and ~1.5% of 'region'
missing_profit_idx = rng.choice(sales_df.index, size=int(0.02 * len(sales_df)), replace=False)
sales_df.loc[missing_profit_idx, "profit"] = np.nan
missing_region_idx = rng.choice(sales_df.index, size=int(0.015 * len(sales_df)), replace=False)
sales_df.loc[missing_region_idx, "region"] = np.nan

# 2) Duplicate rows: append 25 exact duplicates
dupes = sales_df.sample(25, random_state=1)
sales_df = pd.concat([sales_df, dupes], ignore_index=True)

# 3) Intentional anomalies: extreme sales spikes/drops for anomaly-detection testing
anomaly_idx = rng.choice(sales_df.index, size=12, replace=False)
for i, idx in enumerate(anomaly_idx):
    if i % 3 == 0:
        sales_df.loc[idx, "sales"] = round(sales_df["sales"].mean() * rng.uniform(15, 25), 2)  # spike
    elif i % 3 == 1:
        sales_df.loc[idx, "profit"] = round(-sales_df["sales"].mean() * rng.uniform(2, 4), 2)  # deep loss
    else:
        sales_df.loc[idx, "quantity"] = int(rng.integers(200, 500))  # bulk-order outlier

sales_df = sales_df.sample(frac=1, random_state=2).reset_index(drop=True)  # shuffle
sales_df.to_csv("sample_sales.csv", index=False)

# ---------------------------------------------------------------------------
# Feedback (for ChromaDB semantic search demo)
# ---------------------------------------------------------------------------
delivery_complaints = [
    "My order arrived over a week late and there was no update on tracking.",
    "Delivery was delayed by 10 days, very frustrating experience with no communication.",
    "The package took forever to arrive, courier kept postponing the delivery date.",
    "Extremely disappointed — delivery was supposed to be 3 days but took 2 weeks.",
    "Late delivery again for the third time this month, please fix your logistics.",
    "The shipment got stuck at the local hub for days before finally being delivered.",
]
product_complaints = [
    "The keyboard stopped working within a week of purchase, poor build quality.",
    "Product arrived damaged, the monitor screen had a crack on delivery.",
    "Not satisfied with the chair, it wobbles and the armrest is loose.",
    "The fabric on the hoodie started fraying after just two washes.",
]
positive_feedback = [
    "Excellent product quality and fast shipping, will definitely order again!",
    "Really happy with the standing desk, sturdy and easy to assemble.",
    "Great customer support, they resolved my issue within minutes.",
    "The monitor exceeded my expectations, crisp display and great value.",
    "Fast delivery and well packaged, very satisfied with the purchase.",
    "Love the office chair, very comfortable for long work hours.",
]
neutral_feedback = [
    "The product is okay, does what it says but nothing special.",
    "Average experience overall, delivery was on time though.",
    "It's fine for the price, wouldn't call it premium quality.",
]

all_feedback = (
    [(t, "delivery_complaint") for t in delivery_complaints] * 6 +
    [(t, "product_complaint") for t in product_complaints] * 6 +
    [(t, "positive") for t in positive_feedback] * 6 +
    [(t, "neutral") for t in neutral_feedback] * 6
)
rng.shuffle(all_feedback)

feedback_rows = []
for i, (text, tag) in enumerate(all_feedback):
    cust = rng.choice(customer_ids)
    d = rng.choice(dates)
    feedback_rows.append({
        "feedback_id": f"FB-{i+1:04d}",
        "customer_id": cust,
        "date": pd.Timestamp(d).strftime("%Y-%m-%d"),
        "feedback": text,
        "category": tag,
    })

feedback_df = pd.DataFrame(feedback_rows)
feedback_df.to_csv("sample_feedback.csv", index=False)

print(f"sample_sales.csv: {len(sales_df)} rows")
print(f"sample_customers.csv: {len(customers_df)} rows")
print(f"sample_feedback.csv: {len(feedback_df)} rows")
print("NOTE: sample_sales.csv intentionally contains ~2% missing 'profit', ~1.5% missing "
      "'region', 25 duplicate rows, and 12 injected anomalies for testing Data Quality "
      "and Anomaly Detection features.")
