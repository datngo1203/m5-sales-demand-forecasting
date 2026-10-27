#!/usr/bin/env bash
set -euo pipefail
target=/m5/processed_m5
hdfs dfs -mkdir -p "$target"
# Existing files are never overwritten; verify the complete byte stream after upload.
for file in /source/*.parquet; do
  if ! hdfs dfs -test -e "$target/$(basename "$file")"; then
    hdfs dfs -put "$file" "$target/"
  fi
done
source_hash=$(cat /source/*.parquet | sha256sum | cut -d' ' -f1)
hdfs_hash=$(hdfs dfs -cat "$target/*.parquet" | sha256sum | cut -d' ' -f1)
if [ "$source_hash" != "$hdfs_hash" ]; then
  echo "Source and HDFS bytes differ; existing HDFS data left untouched" >&2
  exit 1
fi
echo "source_and_hdfs_sha256=$source_hash"
hdfs dfs -count "$target"
hdfs dfsadmin -report
hdfs fsck "$target" -files -blocks
