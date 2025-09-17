#!/usr/bin/env bash
# get_latest_opinions.sh — writes Parquet and consolidates into ~1GB parts
set -euo pipefail

# ------- CONFIG -------
BUCKET_INDEX="https://storage.courtlistener.com/bulk-data/"
OUTDIR="${PWD}/data"
SPARK_VERSION="3.4.0"
JAVA_PKG="openjdk-11-jdk"
DRIVER_MEM_GB="120g"
LOCAL_CORES="$(nproc)"            # likely 18 on your pod
ARIA_CONN="16"
PARQUET_PARTITIONS_INITIAL="512"  # first write: lots of parts for parallelism
TARGET_FILE_SIZE_GB="1"           # consolidate to ~1GB per file
# ----------------------

mkdir -p "${OUTDIR}"

log(){ printf "\n\033[1;36m[+] %s\033[0m\n" "$*"; }
need_cmd(){ command -v "$1" &>/dev/null || { echo "Missing: $1"; exit 1; } }

# System deps
if command -v apt-get &>/dev/null; then
  log "Installing system deps (aria2, pbzip2, Java 11)..."
  sudo apt-get update -y
  sudo apt-get install -y aria2 pbzip2 ${JAVA_PKG} curl tar python3
fi

need_cmd java
need_cmd curl
need_cmd aria2c
need_cmd pbzip2
need_cmd python3

# Spark install (local)
if [ ! -d "${OUTDIR}/spark-${SPARK_VERSION}-bin-hadoop3" ]; then
  log "Fetching Apache Spark ${SPARK_VERSION}..."
  SPARK_TGZ="spark-${SPARK_VERSION}-bin-hadoop3.tgz"
  curl -L -o "${OUTDIR}/${SPARK_TGZ}" "https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/${SPARK_TGZ}"
  tar -xzf "${OUTDIR}/${SPARK_TGZ}" -C "${OUTDIR}"
fi
SPARK_HOME="${OUTDIR}/spark-${SPARK_VERSION}-bin-hadoop3"
export SPARK_HOME
export PATH="${SPARK_HOME}/bin:${PATH}"

# -------- Discover latest opinions snapshot --------
log "Discovering latest opinions CSV.bz2 from index…"
LATEST_OPINIONS_FILE="$(
  curl -s "${BUCKET_INDEX}" \
  | grep -oE 'opinions-[0-9]{4}-[0-9]{2}-[0-9]{2}\.csv\.bz2' \
  | sort -Vu \
  | tail -n1
)"

[ -z "${LATEST_OPINIONS_FILE}" ] && { echo "Could not find latest opinions file."; exit 1; }

DATE_TAG="${LATEST_OPINIONS_FILE:9:10}"
log "Latest opinions: ${LATEST_OPINIONS_FILE} (date=${DATE_TAG})"

OPINIONS_URL="${BUCKET_INDEX}${LATEST_OPINIONS_FILE}"
OPINIONS_BZ2="${OUTDIR}/${LATEST_OPINIONS_FILE}"
OPINIONS_CSV="${OUTDIR}/opinions-${DATE_TAG}.csv"
PARQUET_DIR_STAGE="${OUTDIR}/opinions-${DATE_TAG}.parquet.stage"
PARQUET_DIR_1GB="${OUTDIR}/opinions-${DATE_TAG}.parquet-1gb"

# -------- Download (parallel) --------
if [ ! -f "${OPINIONS_BZ2}" ]; then
  log "Downloading with aria2c (${ARIA_CONN} conns)…"
  aria2c -x${ARIA_CONN} -s${ARIA_CONN} -k1M -o "$(basename "${OPINIONS_BZ2}")" -d "${OUTDIR}" "${OPINIONS_URL}"
else
  log "Already downloaded: ${OPINIONS_BZ2}"
fi

# -------- Decompress (parallel) --------
if [ ! -f "${OPINIONS_CSV}" ]; then
  log "Decompressing (pbzip2 -p$(nproc))…"
  pbzip2 -d -k -p"${LOCAL_CORES}" "${OPINIONS_BZ2}"
else
  log "Already decompressed: ${OPINIONS_CSV}"
fi

# -------- PySpark job: CSV → Parquet (stage) --------
PYJOB1="${OUTDIR}/opinions_csv_to_parquet_stage.py"
cat > "${PYJOB1}" <<'PY1'
from pyspark.sql import SparkSession
import sys

csv_path = sys.argv[1]
out_dir  = sys.argv[2]
parts    = int(sys.argv[3])

spark = (SparkSession.builder
         .appName("OpinionsCSVtoParquetStage")
         .config("spark.sql.files.maxRecordsPerFile", 200000)
         .config("spark.sql.parquet.compression.codec", "zstd")
         .config("spark.sql.csv.parser.columnPruning.enabled", "true")
         .getOrCreate())

df = (spark.read
      .option("header", "true")
      .option("multiLine", "true")
      .option("escape", "\"")
      .option("quote", "\"")
      .option("mode", "PERMISSIVE")
      .csv(csv_path))

cols = [
    "id","cluster_id","author_str","type","per_curiam","date_filed",
    "sha1","download_url","plain_text","html_with_citations",
    "extracted_by_ocr","joined_by_ocr","judge","page_count","precedential_status"
]
existing = [c for c in cols if c in df.columns]
df2 = df.select(*existing).repartition(parts)

(df2.write
    .mode("overwrite")
    .option("compression","zstd")
    .parquet(out_dir))

spark.stop()
PY1

# Stage write (many parts for speed)
[ -d "${PARQUET_DIR_STAGE}" ] && rm -rf "${PARQUET_DIR_STAGE}"
log "CSV → Parquet (stage) with Spark …"
spark-submit \
  --driver-memory "${DRIVER_MEM_GB}" \
  --conf "spark.sql.shuffle.partitions=${PARQUET_PARTITIONS_INITIAL}" \
  --conf "spark.sql.files.maxPartitionBytes=256m" \
  --conf "spark.sql.parquet.compression.codec=zstd" \
  --master "local[$((LOCAL_CORES-2))]" \
  "${PYJOB1}" "${OPINIONS_CSV}" "${PARQUET_DIR_STAGE}" "${PARQUET_PARTITIONS_INITIAL}"

# -------- Compute total size & target num files (~1GB each) --------
log "Measuring staged Parquet size…"
TOTAL_BYTES=$(python3 - <<PY
import os, sys
root = "${PARQUET_DIR_STAGE}"
total = 0
for dp,_,files in os.walk(root):
    for f in files:
        if f.endswith(".parquet"):
            total += os.path.getsize(os.path.join(dp,f))
print(total)
PY
)

if [ -z "${TOTAL_BYTES}" ]; then
  echo "Failed to measure Parquet size."
  exit 1
fi

GB=$((1024*1024*1024))
TARGET="${TARGET_FILE_SIZE_GB}"
NUM_FILES=$(( (TOTAL_BYTES + (TARGET*GB) - 1) / (TARGET*GB) ))
[ "${NUM_FILES}" -lt 1 ] && NUM_FILES=1

log "Total staged size: $((TOTAL_BYTES/GB)) GB → target ~${TARGET}GB files → num_files=${NUM_FILES}"

# -------- Consolidate to ~1GB parts --------
PYJOB2="${OUTDIR}/consolidate_parquet_to_1gb.py"
cat > "${PYJOB2}" <<'PY2'
from pyspark.sql import SparkSession
import sys

in_dir   = sys.argv[1]
out_dir  = sys.argv[2]
num_out  = int(sys.argv[3])

spark = (SparkSession.builder
         .appName("ConsolidateParquetTo1GB")
         .config("spark.sql.parquet.compression.codec", "zstd")
         .getOrCreate())

df = spark.read.parquet(in_dir)
# coalesce(num_out) → roughly num_out files (Spark writes one file per partition)
(df.coalesce(num_out)
   .write
   .mode("overwrite")
   .option("compression","zstd")
   .parquet(out_dir))

spark.stop()
PY2

[ -d "${PARQUET_DIR_1GB}" ] && rm -rf "${PARQUET_DIR_1GB}"
log "Consolidating to ~1GB parts (${NUM_FILES} files)…"
spark-submit \
  --driver-memory "${DRIVER_MEM_GB}" \
  --conf "spark.sql.parquet.compression.codec=zstd" \
  --master "local[$((LOCAL_CORES-2))]" \
  "${PYJOB2}" "${PARQUET_DIR_STAGE}" "${PARQUET_DIR_1GB}" "${NUM_FILES}"

# -------- Cleanup stage parquet, optional CSV cleanup --------
log "Cleaning up staged Parquet…"
rm -rf "${PARQUET_DIR_STAGE}"

# Uncomment if you want to reclaim space immediately:
# log "Removing decompressed CSV to reclaim space…"
# rm -f "${OPINIONS_CSV}"

log "DONE. Final Parquet (~1GB parts) at: ${PARQUET_DIR_1GB}"
