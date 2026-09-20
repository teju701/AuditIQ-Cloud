import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

vendors = [
    ("V001", "Tata Consultancy Services", "27AABCT1234A1Z5"),
    ("V002", "Infosys Limited", "29AABCI5678B2Z3"),
    ("V003", "Wipro Technologies", "29AABCW9012C3Z1"),
    ("V004", "HCL Technologies", "06AABCH3456D4Z9"),
    ("V005", "Tech Mahindra", "27AABCT7890E5Z7"),
    ("V006", "Reliance Industries", "27AAACR5055K1ZT"),
    ("V007", "HDFC Bank Ltd", "27AAHCH4118H1ZK"),
    ("V008", "Fraudulent Vendor A", "27AABCT1234A1Z5"),  # duplicate GSTIN as V001
    ("V009", "Shell India", "07AABCS1234F6Z2"),
    ("V010", "Siemens India", "27AABCS5678G7Z4"),
]

departments = ["IT", "Finance", "Operations", "HR", "Marketing", "Legal"]
categories = ["Software", "Hardware", "Consulting", "Maintenance", "Travel", "Office Supplies"]

rows = []
base_date = datetime(2024, 1, 1)

for i in range(500):
    vendor = random.choice(vendors)
    dept = random.choice(departments)
    cat = random.choice(categories)
    invoice_date = base_date + timedelta(days=random.randint(0, 364))
    due_date = invoice_date + timedelta(days=30)

    # Normal amount
    amount = round(random.uniform(5000, 500000), 2)

    # Plant anomalies
    if i % 50 == 0:
        amount = round(random.choice([10000, 50000, 100000, 500000]), 2)  # round numbers

    if i % 75 == 0:
        payment_date = due_date + timedelta(days=random.randint(31, 90))  # late payment
    else:
        payment_date = due_date - timedelta(days=random.randint(1, 15))

    has_po = random.random() > 0.1
    if i % 40 == 0:
        has_po = False  # no PO

    rows.append({
        "transaction_id": f"TXN{str(i+1).zfill(4)}",
        "vendor_id": vendor[0],
        "vendor_name": vendor[1],
        "gstin": vendor[2],
        "department": dept,
        "category": cat,
        "invoice_date": invoice_date.strftime("%Y-%m-%d"),
        "due_date": due_date.strftime("%Y-%m-%d"),
        "payment_date": payment_date.strftime("%Y-%m-%d"),
        "amount": amount,
        "has_purchase_order": has_po,
        "invoice_number": f"INV-{random.randint(100000, 999999)}",
        "approved_by": random.choice(["Ravi Kumar", "Priya Sharma", "Amit Patel", "Sneha Reddy"]),
        "status": random.choice(["Paid", "Paid", "Paid", "Pending", "Disputed"])
    })

df = pd.DataFrame(rows)
df.to_csv("data/transactions.csv", index=False)
print(f"Dataset generated: {len(df)} transactions saved to data/transactions.csv")
print(df.head())