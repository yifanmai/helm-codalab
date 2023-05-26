#!/bin/bash

set -e

python3 -m pip install virtualenv
python3 -m virtualenv --always-copy -p python3.8 venv
source venv/bin/activate
pip install git+https://github.com/stanford-crfm/helm.git@codalab-hack
pip install -r https://raw.githubusercontent.com/stanford-crfm/helm/codalab-hack/requirements-freeze.txt
python3 -c 'import spacy; spacy.cli.download("en_core_web_sm")'