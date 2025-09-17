#!/usr/bin/env python3
import os, json
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, length, when, lit, regexp_extract, rlike, desc, approx_count_distinct
)
from pyspark.sql.types import StringType

# ----------------------------
# Config (override via env)
# ----------------------------
CSV = os.environ.get("CSV", "/data/opinions-2025-09-04.csv")
OUTDIR = os.environ.get("OUTDIR", "/data/audit")
DRIVER_MEM = os.environ.get("DRIVER_MEM", "16g")
MAX_PART_BYTES = os.environ.get("MAX_PART_BYTES", "64m")
SHUFFLE_PARTS = os.environ.get("SHUFFLE_PARTS", "512")

# What we expect (only for presence check; not enforced)
REQUIRED_COLS = os.environ.get("REQUIRED_COLS", ",".join([
    "id","date_created","date_modified","author_str","per_curiam",
    "joined_by_str","type","sha1","page_count","download_url",
    "local_path","plain_text","html","html_lawbox","html_columbia",
    "html_anon_2020","xml_harvard","html_with_citations",
    "extracted_by_ocr","author_id","cluster_id","precedential_status"
])).split(",")

# Control character class (exclude \n \r \t, but catch nulls and C0/C1 oddities)
CTRL_REGEX = r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]'

# Ensure output dir
os.makedirs(OUTDIR, exist_ok=True)

# ----------------------------
# Spark session
# ----------------------------
spark = (
    SparkSession.builder
    .appName("OpinionsCSV_Audit")
    .master(f"local[{os.cpu_count() or 8}]")
    .config("spark.driver.memory", DRIVER_MEM)
    .config("spark.sql.files.maxPartitionBytes", MAX_PART_BYTES)
    .config("spark.sql.shuffle.partitions", SHUFFLE_PARTS)
    .getOrCreate()
)

# ----------------------------
# Read CSV as strings, multiline-safe
# ----------------------------
df = (
    spark.read
    .option("header", "true")
    .option("multiLine", "true")
    .option("escape", '"')
    .csv(f"file://{CSV}")
)

print("\n=== Schema (from header) ===")
df.printSchema()

cols = df.columns
missing_expected = [c for c in REQUIRED_COLS if c and c not in cols]
if missing_expected:
    print(f"\n[WARN] Missing expected columns: {missing_expected}")
else:
    print("\nAll expected columns present.")

# Handy helpers that treat empty-string as null-ish for our purposes
def is_nullish(c):
    return col(c).isNull() | (length(col(c)) == 0)

# ----------------------------
# Row counts (full, parallel)
# ----------------------------
total_rows = df.count()
print(f"\nTotal rows: {total_rows:,}")

# ----------------------------
# Missing text fields
# ----------------------------
has_plain = "plain_text" in cols
has_htmlwc = "html_with_citations" in cols

null_plain = df.filter(is_nullish("plain_text")).count() if has_plain else None
null_htmlwc = df.filter(is_nullish("html_with_citations")).count() if has_htmlwc else None
both_null = None
if has_plain and has_htmlwc:
    both_null = df.filter(is_nullish("plain_text") & is_nullish("html_with_citations")).count()

print("\n=== Missing Text Stats ===")
if has_plain:
    print(f"plain_text null/empty: {null_plain:,}")
else:
    print("plain_text column not present.")
if has_htmlwc:
    print(f"html_with_citations null/empty: {null_htmlwc:,}")
else:
    print("html_with_citations column not present.")
if both_null is not None:
    print(f"BOTH null/empty (red flag): {both_null:,}")

# ----------------------------
# Length distributions & extremes
# ----------------------------
def length_stats(colname):
    if colname not in cols: return None
    tmp = df.select(length(col(colname)).alias("L"))
    # Approx quantiles (fast)
    qs = [0.50, 0.90, 0.99, 0.999]
    try:
        p50, p90, p99, p999 = tmp.approxQuantile("L", qs, 0.01)
    except Exception:
        p50 = p90 = p99 = p999 = None
    # Buckets
    b = (
        df.select(length(col(colname)).alias("L"))
          .select(when(col("L") <= 1_000, lit("<=1k"))
                  .when((col("L") > 1_000) & (col("L") <= 10_000), lit("1k-10k"))
                  .when((col("L") > 10_000) & (col("L") <= 100_000), lit("10k-100k"))
                  .otherwise(lit(">100k")).alias("bucket"))
          .groupBy("bucket").count().orderBy("bucket")
    )
    buckets = {r["bucket"]: r["count"] for r in b.collect()}
    # Top-5 longest rows with IDs if present
    idcol = "id" if "id" in cols else None
    top_q = df.select(
        *( [col("id")] if idcol else [] ),
        length(col(colname)).alias("len_"+colname)
    ).orderBy(desc("len_"+colname)).limit(5)
    top = [row.asDict() for row in top_q.collect()]
    return {
        "p50": p50, "p90": p90, "p99": p99, "p99_9": p999,
        "buckets": buckets, "top5": top
    }

print("\n=== Length Distributions ===")
len_plain = length_stats("plain_text")
len_htmlwc = length_stats("html_with_citations")

def print_len(name, stats):
    if not stats:
        print(f"{name}: column not present.")
        return
    print(f"{name}: p50={stats['p50']}, p90={stats['p90']}, p99={stats['p99']}, p99.9={stats['p99_9']}")
    print(f"{name} buckets: {stats['buckets']}")
    print(f"{name} longest (top 5 by char length):")
    for i, t in enumerate(stats["top5"], 1):
        print(f"  {i}. {t}")

print_len("plain_text", len_plain)
print_len("html_with_citations", len_htmlwc)

# ----------------------------
# Control characters (counts + examples)
# ----------------------------
def ctrl_check(colname):
    if colname not in cols: return None
    mask = col(colname).rlike(CTRL_REGEX)
    cnt = df.filter(mask).count()
    examples = []
    # Try to fetch a few examples: id + short preview
    select_cols = []
    if "id" in cols: select_cols.append(col("id"))
    select_cols += [
        regexp_extract(col(colname), r'(.*)', 0).alias("snippet")  # full, we will truncate when printing
    ]
    ex_rows = df.filter(mask).select(*select_cols).limit(5).collect()
    for r in ex_rows:
        d = r.asDict()
        if "snippet" in d and isinstance(d["snippet"], str) and len(d["snippet"]) > 200:
            d["snippet"] = d["snippet"][:200] + "…"
        examples.append(d)
    return {"count": cnt, "examples": examples}

print("\n=== Control Characters (C0/C1) ===")
ctrl_plain = ctrl_check("plain_text")
ctrl_htmlwc = ctrl_check("html_with_citations")
ctrl_html = ctrl_check("html") if "html" in cols else None

def print_ctrl(name, stats):
    if stats is None:
        print(f"{name}: column not present or check skipped.")
        return
    print(f"{name}: rows containing control chars = {stats['count']:,}")
    for i, ex in enumerate(stats["examples"], 1):
        print(f"  ex{i}: {ex}")

print_ctrl("plain_text", ctrl_plain)
print_ctrl("html_with_citations", ctrl_htmlwc)
print_ctrl("html", ctrl_html)

# ----------------------------
# Top categorical values
# ----------------------------
def top_vals(colname, k=10):
    if colname not in cols: return None
    t = (df.groupBy(colname).count().orderBy(desc("count")).limit(k)).collect()
    return [(r[colname], r["count"]) for r in t]

print("\n=== Top Values ===")
top_type = top_vals("type")
if top_type is None:
    print("type: column not present.")
else:
    print("type (top 10):")
    for v, c in top_type: print(f"  {repr(v)}: {c:,}")

top_prec = top_vals("precedential_status")
if top_prec is None:
    print("precedential_status: column not present.")
else:
    print("precedential_status (top 10):")
    for v, c in top_prec: print(f"  {repr(v)}: {c:,}")

# ----------------------------
# Save summary JSON
# ----------------------------
summary = {
    "csv_path": CSV,
    "total_rows": total_rows,
    "missing_expected_columns": missing_expected,
    "missing": {
        "plain_text": null_plain,
        "html_with_citations": null_htmlwc,
        "both_plain_and_htmlwc": both_null
    },
    "lengths": {
        "plain_text": len_plain,
        "html_with_citations": len_htmlwc
    },
    "control_chars": {
        "plain_text": ctrl_plain,
        "html_with_citations": ctrl_htmlwc,
        "html": ctrl_html
    },
    "top_values": {
        "type": top_type,
        "precedential_status": top_prec
    }
}
with open(os.path.join(OUTDIR, "audit_summary.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(f"\nSaved JSON summary → {os.path.join(OUTDIR, 'audit_summary.json')}")
print("\nAudit complete.")
