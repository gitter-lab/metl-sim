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
tar -xf code.tar.gz --strip-components=1

# download the rosetta distribution from SQUID
# wget --recursive --no-parent http://proxy.chtc.wisc.edu/SQUID/sgelman2/squid_rosetta/
SQUID_DIR="squid_rosetta_2021-05-11_14-57-25"
wget -q http://proxy.chtc.wisc.edu/SQUID/sgelman2/$SQUID_DIR/rosetta_min_enc.tar.gz.aa
wget -q http://proxy.chtc.wisc.edu/SQUID/sgelman2/$SQUID_DIR/rosetta_min_enc.tar.gz.ab
wget -q http://proxy.chtc.wisc.edu/SQUID/sgelman2/$SQUID_DIR/rosetta_min_enc.tar.gz.ac

# combine the split database tar files into a single database
cat rosetta_min_enc.tar.gz.* > rosetta_min_enc.tar.gz
rm rosetta_min_enc.tar.gz.*
# decrypt
openssl version # echo the version for my knowledge
# this was encrypted w/ openssl v > 1.1.0, which uses default digest sha256
# include "-md sha256" for decrypt compatibility with older versions that used md5
openssl enc -d -aes256 -md sha256 -in rosetta_min_enc.tar.gz -out rosetta_min.tar.gz -pass pass:R0S3774123
rm rosetta_min_enc.tar.gz
# extract
tar -xf rosetta_min.tar.gz
rm rosetta_min.tar.gz

# set up the python environment (from packaged version)
# https://chtc.cs.wisc.edu/conda-installation.shtml

# this is the version of the rosettafy environment in repo version 0.4
# simply a convenient way to keep track of versioning for this package which was created by hand
wget -q http://proxy.chtc.wisc.edu/SQUID/sgelman2/rosettafy_env_v0.4.tar.gz
# these lines handle setting up the environment
export PATH
mkdir rosettafy_env
tar -xzf rosettafy_env_v0.4.tar.gz -C rosettafy_env
. rosettafy_env/bin/activate

# launch our python run script with argument file number
python3 code/energize.py @energize_args.txt --variants_fn="${PROCESS}.txt" --cluster="$CLUSTER" --process="$PROCESS" --commit_id="$GITHUB_TAG"

