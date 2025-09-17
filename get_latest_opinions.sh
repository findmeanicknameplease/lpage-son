#!/usr/bin/env bash
# get_opinions_2025-09-04.sh
# One-shot pipeline: download → parallel-decompress → CSV→Parquet → consolidate to ~1GB parts
# Tuned for a Runpod box (≈18 vCPU, 250 GB RAM). Uses Spark 3.4 + Java 11.

set -euo pipefail

# ---------- CONFIG ----------
OUTDIR="${PWD}/data"
OPINIONS_URL="https://storage.courtlistener.com/bulk-data/opinions-2025-09-04.csv.bz2"
SPARK_VERSION="3.4.0"
JAVA_PKG="openjdk-11-jdk"
DRIVER_MEM_GB="120g"                 # big driver heap for CSV→Parquet
LOCAL_CORES="$(nproc)"               # likely 18
ARIA_CONN="16"                       # parallel HTTP connections
PARQUET_PARTITIONS_INITIAL="512"     # first pass: many parts for throughput
TARGET_FILE_SIZE_GB="1"              # consolidate to ~1GB parts
KEEP_CSV="${KEEP_CSV:-0}"            # set KEEP_CSV=1 to keep decompressed CSV
# ----------------------------

mkdir -p "${OUTDIR}"

log(){ printf "\n\033[1;36m[+] %s\033[0m\n" "$*"; }
need_cmd(){ command -v "$1" &>/dev/null || { echo "Missing: $1"; exit 1; } }

# --- System deps (Ubuntu/Debian images) ---
if command -v apt-get &>/dev/null; then
  log "Installing system deps (aria2, pbzip2, Java 11, Python, curl, tar)…"
  sudo apt-get update -y
  sudo apt-get install -y aria2 pbzip2 ${JAVA_PKG} python3 curl tar
fi

need_cmd java
need_cmd curl
need_cmd aria2c
need_cmd pbzip2
need_cmd python3

# --- Prepare Spark (local install in OUTDIR) ---
if [ ! -d "${OUTDIR}/spark-${SPARK_VERSION}-bin-hadoop3" ]; then
  log "Fetching Apache Spark ${SPARK_VERSION}…"
  SPARK_TGZ="spark-${SPARK_VERSION}-bin-hadoop3.tgz"
  curl -L -o "${OUTDIR}/${SPARK_TGZ}" "https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/${SPARK_TGZ}"
  tar -xzf "${OUTDIR}/${SPARK_TGZ}" -C "${OUTDIR}"
fi
SPARK_HOME="${OUTDIR}/spark-${SPARK_VERSION}-bin-hadoop3"
export SPARK_HOME
export PATH="${SPARK_HOME}/bin:${PATH}"

# --- Paths for this snapshot ---
DATE_TAG="2025-09-04"
BZ2_PATH="${OUTDIR}/opinions-${DATE_TAG}.csv.bz2"
CSV_PATH="${OUTDIR}/opinions-${DATE_TAG}.csv"
PARQUET_DIR_STAGE="${OUTDIR}/opinions-${DATE_TAG}.parquet.stage"
PARQUET_DIR_1GB="${OUTDIR}/opinions-${DATE_TAG}.parquet-1gb"

# --- Download (parallel)
