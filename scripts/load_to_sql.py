"""
load_to_sql.py
===============
Loads the three cleaned CSVs into your local MySQL database
so the SQL queries can be run directly in VS Code SQL Tools.
"""

import pandas as pd
from sqlalchemy import create_engine

# --------------------------------------------------------------------------
# CONFIG — update these to match your local database
# --------------------------------------------------------------------------
DB_USER     = "root"        # your MySQL username
DB_PASSWORD = "divyanshu"            # your MySQL password (blank if none)
DB_HOST     = "localhost"
DB_PORT     = "3306"
DB_NAME     = "digital_wallet_analytics"

INPUT_DIR   = "data/cleaned"

# --------------------------------------------------------------------------
# CONNECT
# --------------------------------------------------------------------------
engine = create_engine(
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

print("Connected to MySQL.")

# --------------------------------------------------------------------------
# LOAD TABLES
# --------------------------------------------------------------------------
tables = {
    "cleaned_users_dim":            f"{INPUT_DIR}/cleaned_users_dim.csv",
    "cleaned_user_engagement_logs": f"{INPUT_DIR}/cleaned_user_engagement_logs.csv",
    "cleaned_transactions_fact":    f"{INPUT_DIR}/cleaned_transactions_fact.csv",
}

for table_name, filepath in tables.items():
    print(f"Loading {table_name}...")
    df = pd.read_csv(filepath)
    df.to_sql(
        name        = table_name,
        con         = engine,
        if_exists   = "replace",
        index       = False,
        chunksize   = 1000
    )
    print(f"  Done — {len(df):,} rows loaded.")

print("\nAll tables loaded into digital_wallet_analytics database.")
print("Open VS Code SQL Tools and run your queries.")