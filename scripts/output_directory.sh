#!/bin/bash

set -e

if [[ $# -ne 1 ]]; then
    echo "Expected exactly one parameters: dir" >&2
    exit 1
fi

shopt -s extglob
shopt -s dotglob
rm -rf !(stderr|stdout|$1)
mv $1/* .
rmdir $1
