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

# combine the split database tar files into a single database
echo "Combining Rosetta split files"
cat rosetta_min_enc.tar.gz.* > rosetta_min_enc.tar.gz
rm rosetta_min_enc.tar.gz.*

# decrypt
echo "Decrypting Rosetta"
openssl version # echo the version for my knowledge
# this was encrypted w/ openssl v > 1.1.0, which uses default digest sha256
# include "-md sha256" for decrypt compatibility with older versions that used md5
openssl enc -d -aes256 -md sha256 -in rosetta_min_enc.tar.gz -out rosetta_min.tar.gz -pass file:pass.txt

rm rosetta_min_enc.tar.gz

# extract
echo "Extracting Rosetta"
tar -xf rosetta_min.tar.gz
rm rosetta_min.tar.gz

# set up the python environment (from packaged version)
# https://chtc.cs.wisc.edu/conda-installation.shtml

# this is the version of the rosettafy environment in repo version 0.4
# simply a convenient way to keep track of versioning for this package which was created by hand
# these lines handle setting up the environment
echo "Setting up Python environment"
export PATH
mkdir rosettafy_env
tar -xzf rosettafy_env_v0.4.tar.gz -C rosettafy_env
. rosettafy_env/bin/activate

# launch our python run script with argument file number
echo "Launching energize.py"
python3 code/energize.py @energize_args.txt --variants_fn="${PROCESS}.txt" --cluster="$CLUSTER" --process="$PROCESS" --commit_id="$GITHUB_TAG"

