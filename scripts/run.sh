#!/bin/bash

if [[ $# -ne 2 ]]; then
    echo "Expected exactly two parameters: group model" >&2
    exit 1
fi

source venv/bin/activate
mkdir -p $VIRTUAL_ENV
cp -r venv/* $VIRTUAL_ENV
helm-run -c run_specs/run_specs_small.conf --max-eval-instances 10 --suite v1 --api-key-path credentials/proxy_api_key.txt --server-url https://crfm-models.stanford.edu --groups-to-run $1 --models-to-run $2 --cache-instances
rm benchmark_output/runs/latest
rm -rf benchmark_output/runs/v1/eval_cache
rm -rf benchmark_output/scenarios
