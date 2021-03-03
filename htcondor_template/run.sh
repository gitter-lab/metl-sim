#!/usr/bin/env bash

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

# get the rosettafy repository from github at the specific tag
# prefer wget rather than git clone for portability
# todo: when the repo is public, switch to this public github link
# wget https://github.com/samgelman/rosettafy/archive/{github_tag}.zip
# for private repo, use OAuth token that is passed in as an environment variable from the submit node each time
wget --header="Authorization: token $TOKEN"  https://github.com/samgelman/rosettafy/archive/{github_tag}.tar.gz

# git clone --depth 1 --branch <tag_name> <repo_url>

# download the rosetta distribution from SQUID
# wget --recursive --no-parent http://proxy.chtc.wisc.edu/SQUID/sgelman2/squid_rosetta/
wget http://proxy.chtc.wisc.edu/SQUID/sgelman2/squid_rosetta/rosetta_minimal.tar.gz.aa
wget http://proxy.chtc.wisc.edu/SQUID/sgelman2/squid_rosetta/rosetta_minimal.tar.gz.ab
wget http://proxy.chtc.wisc.edu/SQUID/sgelman2/squid_rosetta/rosetta_minimal.tar.gz.ac
wget http://proxy.chtc.wisc.edu/SQUID/sgelman2/squid_rosetta/rosetta_minimal.tar.gz.ad

# combine the split database tar files into a single database
cat rosetta_minimal.tar.gz.* > rosetta_minimal.tar.gz
tar -xf rosetta_minimal.tar.gz

# set up miniconda and add it to path
wget -q https://repo.anaconda.com/miniconda/Miniconda3-py38_4.9.2-Linux-x86_64.sh
bash Miniconda3-py38_4.9.2-Linux-x86_64.sh -b -p ~/miniconda3
export PATH=$HOME/miniconda3/bin:$PATH

# set up conda environment from env.yml
source "$HOME/miniconda3/etc/profile.d/conda.sh"
hash -r
conda config --set always_yes yes --set changeps1 no
conda env create -f setup/rosettafy_env.yml

# activate environment and list out packages
conda activate rosettafy
conda list

# launch our python run script with argument file number
python code/energize.py args_gb1/"$1".txt --job_id="$1" --cluster="$CLUSTER" --process="$PROCESS"
# python code/energize.py args_gb1/random-10.txt --job_id=$1 --pdb_fn="raw_pdb_files/gb1_clean_0007.pdb"

