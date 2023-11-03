#!/bin/bash

if [[ $# -ne 1 ]]; then
    echo "Expected exactly one parameter: description" >&2
    exit 1
fi

source venv/bin/activate
mkdir -p $VIRTUAL_ENV
cp -r venv/* $VIRTUAL_ENV
helm-run --run-specs $1 --max-eval-instances 10 --suite v1 --api-key-path credentials/proxy_api_key.txt --server-url https://crfm-models.stanford.edu --cache-instances --cache-instances-only