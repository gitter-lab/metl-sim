#!/bin/bash


set -e

# activate the metl-sim environment
. env/bin/activate

# change directories to the root (metl-sim)
cd ../..

# Read parameters from command line arguments
ROSETTA_MAIN_DIR=$1
PDB_FN=$2
RELAX_NSTRUCT=$3
OUT_DIR_BASE=$4
CONDA_PACK_ENV=$5

# Run the Python script with the specified parameters
python code/prepare.py --rosetta_main_dir="$ROSETTA_MAIN_DIR" --pdb_fn="$PDB_FN" --relax_nstruct="$RELAX_NSTRUCT" --out_dir_base="$OUT_DIR_BASE" --conda_pack_env="$CONDA_PACK_ENV"






