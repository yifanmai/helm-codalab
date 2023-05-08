#!/bin/bash

if [[ $# -ne 1 ]]; then
    echo "Expected exactly one parameter: scenario" >&2
    exit 1
fi

source venv/bin/activate
mkdir -p $VIRTUAL_ENV
cp -r venv/* $VIRTUAL_ENV
helm-run -c run_specs/run_specs_small.conf --suite v1 --api-key-path credentials/proxy_api_key.txt --server-url https://crfm-models.stanford.edu --scenarios-to-run $1 --cache-instances --cache-instances-only
