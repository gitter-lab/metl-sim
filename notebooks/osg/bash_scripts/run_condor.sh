#!/bin/bash

set -e

. env/bin/activate

cd ../..

INPUT_FN=$1

# Run the Python script with the specified parameters
python code/condor.py @"$INPUT_FN"