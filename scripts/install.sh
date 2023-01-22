#!/bin/bash

set -e

python3 -m pip install virtualenv
python3 -m virtualenv --always-copy -p python3.8 venv
source venv/bin/activate
pip install crfm-helm==v0.2.0
python3 -c 'import spacy; spacy.cli.download("en_core_web_sm")'
