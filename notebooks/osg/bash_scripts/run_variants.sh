#!/bin/bash


set -e

. env/bin/activate

echo ${pwd}

cd ../.. 


PDB_FN=$1
NUMBER_VARIANTS=$2
MAX_NUM_SUBS=$3
MIN_NUM_SUBS=$4
SEED=$5

# Run the Python script with the specified parameters
python code/variants.py subvariants --pdb_fn="$PDB_FN" --target_num="$NUMBER_VARIANTS" --max_num_subs="$MAX_NUM_SUBS" --min_num_subs="$MIN_NUM_SUBS" --seed="$SEED"