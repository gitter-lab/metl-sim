#!/usr/bin/env bash

CODE_FN=code.tar.gz

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

# combine all split tar files in the home directory
# this will probably just be the rosetta distribution
if [ "$(ls 2>/dev/null -Ubad1 -- *.tar.gz.* | wc -l)" -gt 0 ];
then
  # first get all the unique split tar file prefixes
  declare -A tar_prefixes
  for f in *.tar.gz.*; do
      tar_prefixes[${f%%.*}]=
  done

  # now combine the split tar files for each prefix
  for f in "${!tar_prefixes[@]}"; do
    echo "Combining split files for $f.tar.gz"
    cat "$f".tar.gz.* > "$f".tar.gz
    rm "$f".tar.gz.*
  done
fi

# the code tar file needs a special flag to un-tar properly
# remove the enclosing folder with strip-components
if [ -f "$CODE_FN" ]; then
  echo "Extracting $CODE_FN"
  tar -xf $CODE_FN --strip-components=1
  rm $CODE_FN
fi

# set up the python environment (from packaged version)
# https://chtc.cs.wisc.edu/conda-installation.shtml

# this is the version of the rosettafy environment in repo version 0.7.11 (pinned openssl)
# simply a convenient way to keep track of versioning for this package which was created by hand
# these lines handle setting up the environment
echo "Setting up Python environment"
export PATH
mkdir rosettafy_env
tar -xzf rosettafy_env_v0.7.11.tar.gz -C rosettafy_env
. rosettafy_env/bin/activate
rm rosettafy_env_v0.7.11.tar.gz

# decrypt
# note this is done AFTER setting up the Python environment because it requires
# the openssl version inside the environment
echo "Decrypting Rosetta"
openssl version # echo the version for my knowledge
openssl enc -d -aes256 -pbkdf2 -in rosetta_min_enc.tar.gz -out rosetta_min.tar.gz -pass file:pass.txt
rm rosetta_min_enc.tar.gz

# extract rosetta and any additional tar files that might contain additional data
if [ "$(ls 2>/dev/null -Ubad1 -- *.tar.gz | wc -l)" -gt 0 ];
then
  for f in *.tar.gz;
  do
    echo "Extracting $f"
    tar -xf "$f";
    rm "$f"
  done
fi

# install miniconda
echo "Installing miniconda"
bash Miniconda3-py38_4.9.2-Linux-x86_64.sh -b -p ~/miniconda3
# important to add to END of path otherwise interferes with the unpackaged environment above
export PATH=$PATH:$HOME/miniconda3/bin

# activate the miniconda environment
source "$HOME/miniconda3/etc/profile.d/conda.sh"
hash -r
conda config --set always_yes yes --set changeps1 no

# install the environment packages
echo "Creating conda environments"
conda env create -f setup/clean_pdb_env.yml -q

# launch our python run script with argument file number
echo "Launching prepare.py"
python3 code/prepare.py --pdb_fn="$PDB" --relax_nstruct=10 --chain=A
