#!/bin/bash

source venv/bin/activate
mkdir -p $VIRTUAL_ENV
cp -r venv/* $VIRTUAL_ENV
mkdir benchmark_output
rm run_*/stderr run_*/stdout
cp -r run_*/* benchmark_output
helm-summarize --suite v1
