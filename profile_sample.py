import argparse, os, numpy as np, pandas as pd

TEXT_CANDS = ["plain_text","html_with_citations","html","absolute_html","absolute_html_lawbox"]
META_WISHLIST = ["id","cluster_id","court_id","date_filed","type","author_id",
                 "per_curiam","judge_id","source","resource_uri","absolute_url"]

def pick_text(cols):
    for c in TEXT_CANDS:
        if c in cols: return c

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--infile", required=True)               # opinions-YYYY-MM-DD.csv.bz2
    ap.add_argument("--pct", type=float, default=2.5)        # 2–3% range
    ap.add_argument("--cap", type=int, default=1_500_000)    # stop after this many sampled rows
    ap.add_argument("--out", default=None)                   # optional: write the sample (parquet/csv)
    ap.add_argument("--outfmt", choices=["parquet","csv"], default="parquet")
    args = ap.parse_args()

    # 0) Quick schema + a few top rows (fast)
    head = pd.read_csv(args.infile, compression="bz2", nrows=10, on_bad_lines="skip", dtype_backend="pyarrow")
    print("\n=== COLUMNS ===")
    print(list(head.columns))
    print("\n=== FIRST 10 ROWS (biased to top) ===")
    print(head)

    # 1) Uniform Bernoulli sample (single pass, streaming, no unzip)
    p = max(0.0, min(100.0, args.pct)) / 100.0
    rng = np.random.default_rng(42)
    sampled_parts = []
    total = 0

    for chunk in pd.read_csv(args.infile, compression="bz2", chunksize=100_000,
                             on_bad_lines="skip", dtype_backend="pyarrow"):
        total += len(chunk)
        if p > 0:
            mask = rng.random(len(chunk)) < p
            take = chunk.loc[mask]
            if len(take):
                sampled_parts.append(take)
                if args.cap and sum(len(x) for x in sampled_parts) >= args.cap:
                    p = 0.0  # stop enlarging the sample

    sample = pd.concat(sampled_parts, ignore_index=True) if sampled_parts else head
    print(f"\n=== STREAM PASS COMPLETE ===")
    print(f"Scanned rows (compressed stream): {total:,}")
    print(f"Sampled rows (~{args.pct}% capped): {len(sample):,}")

    # 2) What should we take? (suggested fields)
    cols = set(sample.columns)
    text_col = pick_text(cols)
    meta_present = [c for c in META_WISHLIST if c in cols]
    print("\n=== SUGGESTED FIELDS TO TAKE ===")
    print("Text column preference (first present):", text_col or "None found")
    print("Metadata present:", meta_present)

    # 3) Health signals (nulls, lengths, time span, courts)
    # Null rate per suggested field
    print("\n=== NULL RATES (on sample) ===")
    check = meta_present + ([text_col] if text_col else [])
    if check:
        nulls = (sample[check].isna().sum() / len(sample) * 100).round(2).astype("float64")
        for k, v in nulls.items():
            print(f"{k:24s} {v:6.2f}%")
    else:
        print("(no standard fields present to profile)")

    # Text lengths
    if text_col:
        s = sample[text_col].astype("string[pyarrow]").fillna("")
        lens = s.str.len().to_numpy("int64", na_value=0)
        empties = int((lens == 0).sum())
        p50 = int(np.quantile(lens, 0.50)) if len(lens) else 0
        p90 = int(np.quantile(lens, 0.90)) if len(lens) else 0
        p99 = int(np.quantile(lens, 0.99)) if len(lens) else 0
        print("\n=== TEXT LENGTHS ===")
        print(f"empty: {empties:,}   p50: {p50}   p90: {p90}   p99: {p99}")

    # Dates
    if "date_filed" in cols:
        d = pd.to_datetime(sample["date_filed"], errors="coerce")
        print("\n=== DATE RANGE (sample) ===")
        print(f"min: {pd.Series(d).min()}   max: {pd.Series(d).max()}")
        null_dates = int(d.isna().sum())
        print(f"null dates: {null_dates:,}")

    # Courts
    if "court_id" in cols:
        top_courts = sample["court_id"].value_counts(dropna=False).head(10)
        print("\n=== TOP COURTS IN SAMPLE ===")
        print(top_courts)

    # 4) Show rows you can actually read (first + random)
    print("\n=== SAMPLE ROWS (first 5) ===")
    print(sample.head(5))
    if len(sample) > 10:
        print("\n=== SAMPLE ROWS (random 5) ===")
        print(sample.sample(5, random_state=7))

    # 5) Optional: persist the exploration sample for teammates
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        if args.outfmt == "parquet":
            sample.to_parquet(args.out, engine="pyarrow", compression="zstd", index=False)
        else:
            sample.to_csv(args.out, index=False)
        print(f"\nWrote exploration sample → {args.out}")

if __name__ == "__main__":
    main()
