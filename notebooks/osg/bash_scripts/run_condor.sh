#!/bin/bash


set -e

. rosetta_env/bin/activate

echo ${pwd}



# this is here because i need to retar everything in the binary because i forgot to include this package.
pip install tqdm


cd .. 


INPUT_FN=$1

# Run the Python script with the specified parameters
python code/condor.py @"$INPUT_FN"