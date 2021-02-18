#!/bin/bash

# echo some HTCondor job information
echo _CONDOR_JOB_IWD $_CONDOR_JOB_IWD
echo Cluster $cluster
echo Process $process
echo RunningOn $runningon

# this makes it easier to set up the environments, since the PWD we are running in is not $HOME
export HOME=$PWD

# move transferred rosetta files to the rosetta working directory
mv 3_10_* rosetta_working_dir
cd rosetta_working_dir
chmod +x 3_10_rosetta_scripts.static.linuxgccrelease
chmod +x 3_10_residue_energy_breakdown.static.linuxgccrelease
# this combines the databases into a single database? why is this necessary, why not just
# make database.tar and transfer it
cat 3_10_databasea* > database.tar
tar -xf database.tar
cd ..

# set up miniconda and add it to path
wget -q https://repo.anaconda.com/miniconda/Miniconda3-py38_4.9.2-Linux-x86_64.sh
bash Miniconda3-py38_4.9.2-Linux-x86_64.sh -b -p ~/miniconda3
export PATH=$HOME/miniconda3/bin:$PATH

# set up appropriate conda environment
source "$HOME/miniconda3/etc/profile.d/conda.sh"
hash -r
conda config --set always_yes yes --set changeps1 no
conda env create -f env.yml

# activate environment and list out packages
conda activate rosettafy_condor
conda list

# create an output directory for storing all npy files
mkdir output
mkdir output/condor_logs

# make sure shell scripts are executable
chmod +x ~/code/relax.sh
chmod +x ~/code/clean_up_working_dir.sh

# launch our python run script with argument file number
python code/run.py args_gb1/$1.txt --job_id=$1 --pdb_fn="pdb_files/gb1_clean_0007.pdb"
# python code/run.py args_gb1/random-10.txt --job_id=$1 --pdb_fn="pdb_files/gb1_clean_0007.pdb"

