import pandas as pd
import numpy as np

# load the small sample
df = pd.read_csv("first20k.csv")

print("\n=== Columns ===")
print(df.columns.tolist())

print("\n=== First 5 rows ===")
print(df.head())

print("\n=== Null rates (fraction of missing values per column) ===")
print((df.isna().mean()*100).round(2).sort_values(ascending=False))

# identify which text-like column exists
TEXT_CANDS = ["plain_text","html_with_citations","html","absolute_html","absolute_html_lawbox"]
text_col = next((c for c in TEXT_CANDS if c in df.columns), None)
print("\n=== Text column detected ===")
print(text_col)

# quick text length stats if present
if text_col:
    s = df[text_col].astype(str).fillna("")
    lens = s.str.len().to_numpy("int64")
    print("\n=== Text length distribution (chars) ===")
    for q in (0.5,0.9,0.99):
        print(f"p{int(q*100)}: {int(np.quantile(lens,q))}")
    print(f"empty: {(lens==0).sum()} / {len(lens)}")

# date range
if "date_filed" in df.columns:
    d = pd.to_datetime(df["date_filed"], errors="coerce")
    print("\n=== Date filed range (sample) ===")
    print(f"min: {d.min()}  max: {d.max()}  nulls: {d.isna().sum()}")

# top courts
if "court_id" in df.columns:
    print("\n=== Top courts (sample) ===")
    print(df["court_id"].value_counts().head(10))
PY
