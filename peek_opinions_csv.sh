#!/usr/bin/env bash
set -euo pipefail

# --- Config (adjust paths if needed)
OUTDIR="${PWD}/data"
DATE_TAG="2025-09-04"
CSV="${OUTDIR}/opinions-${DATE_TAG}.csv"
SPARK_VERSION="3.4.0"
DRIVER_MEM="24g"          # plenty for a peek; not huge
CORES="$(nproc)"

# Spark bootstrap (same as before; skip if you already set SPARK_HOME)
if [ ! -d "${OUTDIR}/spark-${SPARK_VERSION}-bin-hadoop3" ]; then
  curl -L -o "${OUTDIR}/spark-${SPARK_VERSION}-bin-hadoop3.tgz" \
    "https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop3.tgz"
  tar -xzf "${OUTDIR}/spark-${SPARK_VERSION}-bin-hadoop3.tgz" -C "${OUTDIR}"
fi
export SPARK_HOME="${OUTDIR}/spark-${SPARK_VERSION}-bin-hadoop3"
export PATH="${SPARK_HOME}/bin:${PATH}"

# PySpark job path
PEEK_PY="${OUTDIR}/peek_opinions_csv.py"
cat > "${PEEK_PY}" <<'PY'
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, length, expr, approx_count_distinct, rand, when

import os, sys, json

csv_path = sys.argv[1]
out_dir  = sys.argv[2]
sample_n = int(sys.argv[3])   # number of rows to emit to JSONL
rand_seed= 42

spark = (SparkSession.builder
         .appName("OpinionsCSVQuickPeek")
         .config("spark.sql.session.timeZone","UTC")
         .getOrCreate())

# Read with the same tolerant options we’ll use later
df = (spark.read
      .option("header","true")
      .option("multiLine","true")
      .option("escape","\"")
      .option("quote","\"")
      .option("mode","PERMISSIVE")
      .csv(csv_path))

print("\n=== Schema ===")
df.printSchema()

# Core columns we care about
want = [
  "id","cluster_id","author_str","type","per_curiam","date_filed",
  "sha1","download_url","plain_text","html_with_citations",
  "extracted_by_ocr","joined_by_ocr","judge","page_count","precedential_status"
]
existing = [c for c in want if c in df.columns]
missing  = [c for c in want if c not in df.columns]
if missing:
    print("\n[WARN] Missing expected columns:", missing)

dfw = df.select(*existing)

# Basic sanity metrics (fast-ish)
print("\n=== Basic metrics (approx where possible) ===")
metrics = dfw.agg(
    approx_count_distinct("id").alias("approx_distinct_id"),
    approx_count_distinct("cluster_id").alias("approx_distinct_cluster_id")
).collect()[0].asDict()
print(json.dumps(metrics, indent=2))

# Null and content checks
checks = dfw.selectExpr(
    "count(1) as total_rows",
    "sum(case when id is null then 1 else 0 end) as null_id",
    "sum(case when cluster_id is null then 1 else 0 end) as null_cluster_id",
    "sum(case when plain_text is null then 1 else 0 end) as null_plain_text",
    "sum(case when html_with_citations is null then 1 else 0 end) as null_html",
    "sum(case when plain_text is null and html_with_citations is null then 1 else 0 end) as both_texts_null"
).collect()[0].asDict()
print("\n=== Null/content checks ===")
print(json.dumps(checks, indent=2))

# Length distribution snapshot
lens = (dfw
  .select(length(col("plain_text")).alias("len_plain"),
          length(col("html_with_citations")).alias("len_html"))
  .summary("count","min","25%","50%","75%","max")
  .toPandas())
print("\n=== Length summary (plain_text, html_with_citations) ===")
print(lens)

# Quick histogram-ish buckets (useful to spot outliers)
buckets = (dfw
  .select(length(col("plain_text")).alias("L"))
  .selectExpr(
      "case "
      "when L is null then 'null'"
      "when L < 500 then '<500'"
      "when L < 2000 then '500-2k'"
      "when L < 10000 then '2k-10k'"
      "when L < 50000 then '10k-50k'"
      "else '>=50k' end as bucket")
  .groupBy("bucket").count()
  .orderBy("count", ascending=False))
print("\n=== plain_text length buckets ===")
buckets.show(20, truncate=False)

# Spot control chars (NUL and C0 except LF/CR/TAB)
badchar_cnt = dfw.selectExpr(
  "sum(case when regexp_like(plain_text, '[\\x00\\x01-\\x08\\x0B\\x0C\\x0E-\\x1F]') then 1 else 0 end) as rows_with_ctrl_in_plain",
  "sum(case when regexp_like(html_with_citations, '[\\x00\\x01-\\x08\\x0B\\x0C\\x0E-\\x1F]') then 1 else 0 end) as rows_with_ctrl_in_html"
).collect()[0].asDict()
print("\n=== Control character scan ===")
print(json.dumps(badchar_cnt, indent=2))

# Value distribution for 'type' and 'precedential_status'
for colname in [c for c in ["type","precedential_status"] if c in dfw.columns]:
    print(f"\n=== Top values: {colname} ===")
    dfw.groupBy(colname).count().orderBy("count", ascending=False).show(20, truncate=False)

# Sample a few rows for visual inspection (stable seed)
sample_df = (dfw.orderBy(rand(rand_seed)).limit(sample_n)
             .select("id","cluster_id","type","date_filed",
                     "author_str","precedential_status",
                     "extracted_by_ocr","joined_by_ocr",
                     "judge",
                     "plain_text","html_with_citations"))

# Write a tiny JSONL you can open in an editor
out_jsonl = os.path.join(out_dir, f"opinions_peek_{sample_n}.jsonl")
(sample_df
  .coalesce(1)
  .write.mode("overwrite")
  .option("compression","none")
  .json(out_jsonl))
print(f"\n[OK] Wrote sample JSON (ndjson-like directory) to: {out_jsonl}")
print("      Tip: the file will be in that directory; Spark writes part-*.json")

# Also show 2 random rows (IDs only) inline
print("\n=== Two random row IDs (inline) ===")
sample_df.select("id","cluster_id","type","date_filed").show(2, truncate=False)

spark.stop()
PY

# Make an output folder for the peek artifacts
PEEK_OUT="${OUTDIR}/peek"
mkdir -p "${PEEK_OUT}"

# Run peek (prints schema & stats; writes a tiny sample)
spark-submit \
  --driver-memory "${DRIVER_MEM}" \
  --master "local[$((CORES-2))]" \
  "${PEEK_PY}" "${CSV}" "${PEEK_OUT}" 10000

echo -e "\n✅ Peek complete.\nLook in: ${PEEK_OUT}\n- stats printed above\n- sample JSONL dir: opinions_peek_10000\n"
