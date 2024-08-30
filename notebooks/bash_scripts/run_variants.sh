#!/bin/bash


set -e

. rosetta_env/bin/activate

echo ${pwd}

cd .. 


# Read parameters from command line arguments
TYPE=$1
PDB_FN=$2
=$3

# Run the Python script with the specified parameters
python code/variants.py random --pdb_fn="$PDB_FN" 



