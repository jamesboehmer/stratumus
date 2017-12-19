#!/bin/bash

THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

stratumus --root $THIS_DIR/testdata --out $THIS_DIR/configs "$@"
