#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="${DATA_DIR:-/data}"
SPARK_VER="3.4.0"
SPARK_ARCH="spark-${SPARK_VER}-bin-hadoop3"
SPARK_DIR="${DATA_DIR}/${SPARK_ARCH}"
SPARK_TGZ="${DATA_DIR}/${SPARK_ARCH}.tgz"
SPARK_URL="https://archive.apache.org/dist/spark/spark-${SPARK_VER}/${SPARK_ARCH}.tgz"

CSV="${DATA_DIR}/opinions-2025-09-04.csv"

echo "[info] Using DATA_DIR=${DATA_DIR}"

# Ensure data dir exists
mkdir -p "${DATA_DIR}"

# Get Spark only if missing
if [[ ! -d "${SPARK_DIR}" ]]; then
  echo "[info] Fetching Spark to ${SPARK_TGZ}"
  curl -L --fail --continue-at - --output "${SPARK_TGZ}" "${SPARK_URL}"
  echo "[info] Extracting Spark into ${DATA_DIR}"
  tar -xzf "${SPARK_TGZ}" -C "${DATA_DIR}"
fi

# Quick file sanity
if [[ ! -f "${CSV}" ]]; then
  echo "[error] CSV not found at ${CSV}" >&2
  exit 1
fi

echo "[info] CSV size:"
ls -lh "${CSV}"

echo "[info] First 3 non-empty lines (raw):"
# Huge lines are fine; just show a few
grep -m 3 -n '.' "${CSV}" | sed -n '1,3p'

echo "[info] Header (robust, via Python csv):"
python3 - <<'PY'
import csv, sys
with open("/data/opinions-2025-09-04.csv", newline='', encoding='utf-8') as f:
    r = csv.reader(f)
    header = next(r, None)
    if header is None:
        print("[warn] Empty file")
        sys.exit(0)
    print(",".join(header))
PY

echo "[info] Sample 5 records (robust, via Python csv):"
python3 - <<'PY'
import csv, itertools
with open("/data/opinions-2025-09-04.csv", newline='', encoding='utf-8') as f:
    r = csv.reader(f)
    header = next(r, None)
    for row in itertools.islice(r, 5):
        print(row)
PY

# Optional: schema sniff with Spark (local)
# "${SPARK_DIR}/bin/spark-shell" -i /dev/stdin <<'SCALA'
# val df = spark.read.option("header","true").option("inferSchema","true")
#   .option("mode","DROPMALFORMED")
#   .csv("file:///data/opinions-2025-09-04.csv")
# df.printSchema()
# df.show(5, truncate=false)
# SCALA

echo "[done] Peek complete."
