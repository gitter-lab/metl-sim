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
# wget https://github.com/samgelman/rosettafy/archive/{github_tag}.zip
# for private repo, use OAuth token that is passed in as an environment variable from the submit node each time
# wget --header="Authorization: token ${TOKEN}" "https://github.com/samgelman/rosettafy/archive/${GITHUB_TAG}.tar.gz"

# untar the code repo (transferred from submit node), removing the enclosing folder with strip-components
# tar -xf "${GITHUB_TAG}.tar.gz" --strip-components=1
# switched to a static filename so there's less need to have github tag everywhere
tar -xf code.tar.gz --strip-components=1

# untar the args
tar -xf args.tar.gz

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

# set up miniconda and add it to path
#wget -q https://repo.anaconda.com/miniconda/Miniconda3-py38_4.9.2-Linux-x86_64.sh
wget -q http://proxy.chtc.wisc.edu/SQUID/sgelman2/Miniconda3-py38_4.9.2-Linux-x86_64.sh
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
python code/energize.py @energize_args.txt --variants_fn="args/${PROCESS}.txt" --cluster="$CLUSTER" --process="$PROCESS" --commit_id="$GITHUB_TAG"

