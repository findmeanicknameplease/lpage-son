#!/usr/bin/env bash
set -euo pipefail

# =======================
# Ultra-fast Opinions ETL
# =======================

# --- Logging ---
log(){ printf "[%(%F %T)T] %s\n" -1 "$*"; }
die(){ printf "[%(%F %T)T] ERROR: %s\n" -1 "$*" >&2; exit 1; }

# --- Tunables (env overrides allowed) ---
OPINIONS_URL="${OPINIONS_URL:-https://storage.courtlistener.com/bulk-data/opinions-2025-09-04.csv.bz2}"
DATA_DIR="${DATA_DIR:-./data}"
OUT_ROOT="${OUT_ROOT:-${DATA_DIR}/opinions-$(basename "$OPINIONS_URL" | sed -E 's/^opinions-([0-9]{4}-[0-9]{2}-[0-9]{2}).*/\1/')}"
SPARK_HOME="${SPARK_HOME:-${DATA_DIR}/spark-3.4.0-bin-hadoop3}"
TARGET_FILE_SIZE_GB="${TARGET_FILE_SIZE_GB:-1}"                   # ~1 GiB parquet parts
PARQUET_CODEC="${PARQUET_CODEC:-zstd}"                            # zstd is fast+compact
CSV_HAS_HEADER="${CSV_HAS_HEADER:-true}"
CSV_PERMISSIVE="${CSV_PERMISSIVE:-true}"
SKIP_TEST="${SKIP_TEST:-1}"                                       # skip bzip2 -tv (saves time)
KEEP_CSV="${KEEP_CSV:-1}"                                         # keep raw CSV after parquet
KEEP_STAGE="${KEEP_STAGE:-0}"                                     # keep stage parquet after coalesce

# --- Hardware-aware knobs ---
CORES_TOTAL="$(nproc)"
CORES_SAFE="${CORES_SAFE:-$(( CORES_TOTAL > 8 ? CORES_TOTAL-2 : (CORES_TOTAL>2?CORES_TOTAL-1:1) ))}"  # leave 1–2 cores headroom
MEM_KB="$(awk '/MemTotal/ {print $2}' /proc/meminfo)"
MEM_GB="$(( MEM_KB / 1024 / 1024 ))"
# Use ~70% of RAM for the Spark driver; clamp to [8, 200] GiB sensible band
DRIVER_MEM_GB_RAW=$(( (MEM_GB * 70) / 100 ))
DRIVER_MEM_GB=$(( DRIVER_MEM_GB_RAW < 8 ? 8 : (DRIVER_MEM_GB_RAW > 200 ? 200 : DRIVER_MEM_GB_RAW) ))

# Parallelism: 3x cores is a good rule for shuffle-heavy work
PARALLELISM_DEFAULT=$(( CORES_SAFE * 3 ))

# --- Derived paths ---
BZ2="${DATA_DIR}/$(basename "${OPINIONS_URL}")"
CSV="${OUT_ROOT}.csv"
OUT_DIR="${OUT_ROOT}"
PARQUET_STAGE="${OUT_DIR}/parquet_stage"
PARQUET_1GB="${OUT_DIR}/parquet_1gb"
TMP_DIR="${TMP_DIR:-${DATA_DIR}/.tmp}"
SPARK_LOCAL_DIRS="${SPARK_LOCAL_DIRS:-${DATA_DIR}/.spark_local}"

mkdir -p "${DATA_DIR}" "${OUT_DIR}" "${TMP_DIR}" "${SPARK_LOCAL_DIRS}"

# --- Helpers ---
bytes_to_human() { # prints GiB with 1 decimal
  awk -v b="$1" 'BEGIN{printf "%.1f", b/1024/1024/1024}'
}

check_disk(){
  local need_bytes="$1"
  local avail_bytes
  avail_bytes="$(df -Pk "${DATA_DIR}" | awk 'NR==2{print $4*1024}')"
  local need_h="$(bytes_to_human "$need_bytes")"
  local avail_h="$(bytes_to_human "$avail_bytes")"
  log "Disk: need ≈ ${need_h} GiB, available ≈ ${avail_h} GiB"
  (( avail_bytes > need_bytes )) || die "Not enough disk space in ${DATA_DIR}"
}

# --- Step 0: Make sure Spark exists (download if missing, resume-capable) ---
ensure_spark(){
  if [[ -x "${SPARK_HOME}/bin/spark-submit" ]]; then
    log "Spark found at ${SPARK_HOME}"
    return 0
  fi
  log "Spark not found; fetching Spark 3.4.0 (Hadoop 3)…"
  local url="https://archive.apache.org/dist/spark/spark-3.4.0/spark-3.4.0-bin-hadoop3.tgz"
  local tgz="${DATA_DIR}/spark-3.4.0-bin-hadoop3.tgz"
  if command -v aria2c >/dev/null 2>&1; then
    aria2c -c -x 8 -s 8 -k 1M -d "${DATA_DIR}" -o "$(basename "$tgz")" "$url"
  else
    curl -fL --retry 5 -C - -o "${tgz}" "$url"
  fi
  tar -xzf "${tgz}" -C "${DATA_DIR}"
  [[ -x "${SPARK_HOME}/bin/spark-submit" ]] || die "Spark extraction failed."
}

# --- Step 1: Download opinions bz2 (fast + resumable) ---
download_bz2(){
  log "Target dataset: ${OPINIONS_URL}"
  if [[ -s "${BZ2}" ]]; then
    log "Found existing bz2 at ${BZ2} (resuming if incomplete)."
  fi
  # Rough disk budget: bz2 + csv (~3x bz2) + stage parquet (~csv size) + final parquet (~csv size)
  # Conservative: need ~6x bz2 for headroom.
  local bz2_size_remote_est="60000000000" # fallback 60GB if HEAD fails
  local head_size
  head_size="$(curl -sI "${OPINIONS_URL}" | awk -F': ' 'tolower($1)=="content-length"{print $2}' || true)"
  [[ -n "${head_size}" ]] && bz2_size_remote_est="${head_size%$'\r'}"
  check_disk $(( bz2_size_remote_est * 6 ))

  if command -v aria2c >/dev/null 2>&1; then
    aria2c -c -x 16 -s 16 -k 4M -d "${DATA_DIR}" -o "$(basename "${BZ2}")" "${OPINIONS_URL}"
  else
    curl -fL --retry 10 --retry-delay 2 -C - -o "${BZ2}" "${OPINIONS_URL}"
  fi
  [[ -s "${BZ2}" ]] || die "Download failed: ${BZ2} is empty"
}

# --- Step 2: Decompress bz2 -> CSV (skip test pass by default) ---
decompress_csv(){
  log "Decompressing → ${CSV} (this is I/O heavy, uses many cores)…"
  if command -v pbzip2 >/dev/null 2>&1; then
    # pbzip2 auto-detects cores; use -p if you want to clamp: -p "${CORES_SAFE}"
    if command -v pv >/dev/null 2>&1; then
      pv "${BZ2}" | pbzip2 -dc > "${CSV}"
    else
      pbzip2 -dc "${BZ2}" > "${CSV}"
    fi
  else
    bzip2 -dc "${BZ2}" > "${CSV}"
  fi
  [[ -s "${CSV}" ]] || die "CSV decompression produced an empty file."
  log "CSV size now $(bytes_to_human "$(stat -c%s "${CSV}")") GiB"
}

# --- Step 3: Spark CSV → Parquet (stage) ---
csv_to_parquet_stage(){
  log "Launching Spark stage write (CSV → Parquet)…"
  export PATH="${SPARK_HOME}/bin:${PATH}"
  export SPARK_LOCAL_DIRS
  # Create Python job
  local job="${OUT_DIR}/csv_to_parquet.py"
  cat > "${job}" <<'PY'
from pyspark.sql import SparkSession
import sys
csv_in, out_dir = sys.argv[1], sys.argv[2]
spark = (SparkSession.builder
         .appName("CSV_to_Parquet_Stage")
         .config("spark.sql.parquet.compression.codec","zstd")
         .config("spark.sql.files.maxPartitionBytes", str(256 * 1024 * 1024))  # 256MiB per input split
         .getOrCreate())
df = (spark.read
      .option("header", sys.argv[3])
      .option("multiLine","true")
      .option("escape","\"")
      .option("quote","\"")
      .option("mode","PERMISSIVE" if sys.argv[4]=="true" else "FAILFAST")
      .csv(csv_in))
df.write.mode("overwrite").parquet(out_dir)
spark.stop()
PY

  # Calculate shuffle partitions near 3x cores (not too tiny)
  local SHUFFLE_PARTS="${SPARK_SHUFFLE_PARTS:-$PARALLELISM_DEFAULT}"

  spark-submit \
    --master "local[${CORES_SAFE}]" \
    --driver-memory "${DRIVER_MEM_GB}g" \
    --conf "spark.local.dir=${SPARK_LOCAL_DIRS}" \
    --conf "spark.sql.shuffle.partitions=${SHUFFLE_PARTS}" \
    --conf "spark.default.parallelism=${SHUFFLE_PARTS}" \
    --conf "spark.memory.offHeap.enabled=true" \
    --conf "spark.memory.offHeap.size=$(( DRIVER_MEM_GB / 2 ))g" \
    --conf "spark.network.timeout=600s" \
    --conf "spark.executor.heartbeatInterval=60s" \
    --conf "spark.sql.parquet.compression.codec=${PARQUET_CODEC}" \
    --conf "spark.serializer=org.apache.spark.serializer.KryoSerializer" \
    --conf "spark.kryoserializer.buffer=32m" \
    --conf "spark.kryoserializer.buffer.max=512m" \
    "${job}" "${CSV}" "${PARQUET_STAGE}" "${CSV_HAS_HEADER}" "${CSV_PERMISSIVE}"

  [[ -d "${PARQUET_STAGE}" ]] || die "Stage parquet not produced."
  local sz
  sz="$(du -sb "${PARQUET_STAGE}" | awk '{print $1}')"
  log "Stage parquet size ≈ $(bytes_to_human "${sz}") GiB at ${PARQUET_STAGE}"
}

# --- Step 4: Plan ~1 GiB file count and coalesce ---
coalesce_to_target(){
  log "Planning ~${TARGET_FILE_SIZE_GB} GiB output parts…"
  local total_bytes target_bytes num_files
  total_bytes="$(du -sb "${PARQUET_STAGE}" | awk '{print $1}')"
  target_bytes=$(( TARGET_FILE_SIZE_GB * 1024 * 1024 * 1024 ))
  num_files=$(( (total_bytes + target_bytes - 1) / target_bytes ))
  (( num_files < 1 )) && num_files=1
  log "Stage ≈ $(bytes_to_human "${total_bytes}") GiB → ${num_files} file(s)."

  log "Coalescing to ${PARQUET_1GB} with ${num_files} partitions…"
  rm -rf "${PARQUET_1GB}"

  local job2="${OUT_DIR}/parquet_coalesce.py"
  cat > "${job2}" <<'PY2'
from pyspark.sql import SparkSession
import sys
in_dir, out_dir, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
spark = (SparkSession.builder
         .appName("Parquet_Coalesce_To_Target")
         .config("spark.sql.parquet.compression.codec","zstd")
         .getOrCreate())
df = spark.read.parquet(in_dir)
(df.coalesce(n)
   .write.mode("overwrite")
   .option("compression","zstd")
   .parquet(out_dir))
spark.stop()
PY2

  # Use same Spark settings
  local SHUFFLE_PARTS="${SPARK_SHUFFLE_PARTS:-$PARALLELISM_DEFAULT}"

  spark-submit \
    --master "local[${CORES_SAFE}]" \
    --driver-memory "${DRIVER_MEM_GB}g" \
    --conf "spark.local.dir=${SPARK_LOCAL_DIRS}" \
    --conf "spark.sql.shuffle.partitions=${SHUFFLE_PARTS}" \
    --conf "spark.default.parallelism=${SHUFFLE_PARTS}" \
    --conf "spark.sql.parquet.compression.codec=${PARQUET_CODEC}" \
    "${job2}" "${PARQUET_STAGE}" "${PARQUET_1GB}" "${num_files}"

  [[ -d "${PARQUET_1GB}" ]] || die "Final parquet not produced."
  local final_sz
  final_sz="$(du -sb "${PARQUET_1GB}" | awk '{print $1}')"
  log "Final parquet ≈ $(bytes_to_human "${final_sz}") GiB at ${PARQUET_1GB}"
}

# --- Step 5: Optional cleanup to save space ---
maybe_cleanup(){
  if [[ "${KEEP_CSV}" == "0" && -f "${CSV}" ]]; then
    log "Removing CSV (${CSV}) to save space…"; rm -f "${CSV}"
  fi
  if [[ "${KEEP_STAGE}" == "0" && -d "${PARQUET_STAGE}" ]]; then
    log "Removing stage parquet (${PARQUET_STAGE})…"; rm -rf "${PARQUET_STAGE}"
  fi
}

# --- Main flow ---
main(){
  log "Cores: total=${CORES_TOTAL}, using=${CORES_SAFE}; Mem=${MEM_GB} GiB; Spark driver=${DRIVER_MEM_GB}g"
  ensure_spark
  download_bz2
  if [[ "${SKIP_TEST}" != "1" ]]; then
    log "Testing bz2 integrity (pbzip2/bzip2)…"
    if command -v pbzip2 >/dev/null 2>&1; then pbzip2 -tv "${BZ2}"; else bzip2 -tv "${BZ2}"; fi
  else
    log "Skipping explicit test; streaming decompress will fail fast if corrupt."
  fi
  decompress_csv
  csv_to_parquet_stage
  coalesce_to_target
  maybe_cleanup
  log "DONE. Final dataset: ${PARQUET_1GB}"
}

main "$@"
