#!/bin/bash

# echo some HTCondor job information
echo "Date: $(date)"
echo "Host: $(hostname)"
echo "System: $(uname -spo)"
echo "_CONDOR_JOB_IWD: $_CONDOR_JOB_IWD"
echo "Cluster: $CLUSTER"
echo "Process: $PROCESS"
echo "RunningOn: $RUNNINGON"

# this makes it easier to set up the environments, since the PWD we are running in is not $HOME
export HOME=$PWD

# download rosetta binaries and database from SQUID to the rosetta working directory
cd rosetta_working_dir || exit
wget http://proxy.chtc.wisc.edu/SQUID/sgelman2/rosetta/3_10_databaseaa
wget http://proxy.chtc.wisc.edu/SQUID/sgelman2/rosetta/3_10_databaseab
wget http://proxy.chtc.wisc.edu/SQUID/sgelman2/rosetta/3_10_databaseac
wget http://proxy.chtc.wisc.edu/SQUID/sgelman2/rosetta/3_10_rosetta_scripts.static.linuxgccrelease

# set the rosetta binaries to be executable
chmod +x rosetta_scripts.static.linuxgccrelease

# this combines the split database tar files into a single database
cat 3_10_databasea* > database.tar
tar -xf database.

# cd back to the root directory
cd ..

# set up miniconda and add it to path
wget -q https://repo.anaconda.com/miniconda/Miniconda3-py38_4.9.2-Linux-x86_64.sh
bash Miniconda3-py38_4.9.2-Linux-x86_64.sh -b -p ~/miniconda3
export PATH=$HOME/miniconda3/bin:$PATH

# set up conda environment from env.yml
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

# launch our python run script with argument file number
python code/energize.py args_gb1/"$1".txt --job_id="$1" --cluster="$CLUSTER" --process="$PROCESS"
# python code/energize.py args_gb1/random-10.txt --job_id=$1 --pdb_fn="raw_pdb_files/gb1_clean_0007.pdb"

