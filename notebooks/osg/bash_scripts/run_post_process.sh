#!/bin/bash


set -e

. env/bin/activate

cd ..

echo ${pwd}


# Read parameters from command line arguments
JOB_MAIN_DIR=$1

# Run the Python script with the specified parameters
python code/process_run.py stats --main_run_dirs notebooks/condor/"$JOB_MAIN_DIR"



