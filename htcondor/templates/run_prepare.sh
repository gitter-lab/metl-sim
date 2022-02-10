#!/usr/bin/env bash

# exit if any command fails...
set -e

# create output directory for condor logs early
# not sure exactly when/if this needs to be done
mkdir -p output/condor_logs

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

# untar the code repo (transferred from submit node), removing the enclosing folder with strip-components
# switched to a static filename so there's less need to have github tag everywhere
echo "Extracting code.tar.gz"
tar -xf code.tar.gz --strip-components=1

echo "Extracting raw PDB files from kj.tar.gz"
tar -xf kj.tar.gz
rm kj.tar.gz

# combine the split database tar files into a single database
echo "Combining Rosetta split files"
cat rosetta_min_enc.tar.gz.* > rosetta_min_enc.tar.gz
rm rosetta_min_enc.tar.gz.*

# decrypt
echo "Decrypting Rosetta"
openssl version # echo the version for my knowledge
# this was encrypted w/ openssl v > 1.1.0, which uses default digest sha256
# include "-md sha256" for decrypt compatibility with older versions that used md5
openssl enc -d -aes256 -md sha256 -in rosetta_min_enc.tar.gz -out rosetta_min.tar.gz -pass pass:R0S3774123
rm rosetta_min_enc.tar.gz

# extract
echo "Extracting Rosetta"
tar -xf rosetta_min.tar.gz
rm rosetta_min.tar.gz

# install miniconda
echo "Installing miniconda"
bash Miniconda3-py38_4.9.2-Linux-x86_64.sh -b -p ~/miniconda3
export PATH=$HOME/miniconda3/bin:$PATH

# activate the miniconda environment
source "$HOME/miniconda3/etc/profile.d/conda.sh"
hash -r
conda config --set always_yes yes --set changeps1 no

# install the environment packages
echo "Creating conda environments"
conda env create -f setup/rosettafy_env.yml -q
conda env create -f setup/clean_pdb_env.yml -q

# activate environment and list out packages
conda activate rosettafy

# launch our python run script with argument file number
echo "Launching prepare.py"
python code/prepare.py --pdb_fn="$PDB" --relax_nstruct=10 --chain=A
