#!/bin/bash

source venv/bin/activate
mkdir -p $VIRTUAL_ENV
cp -r venv/* $VIRTUAL_ENV
rm run_*/stderr run_*/stdout
mkdir benchmark_output
cp -r run_*/* benchmark_output
helm-summarize --suite v1
