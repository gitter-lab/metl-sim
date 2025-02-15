#!/usr/bin/env bash

CODE_FN=code.tar.gz
ENV_FN=metl-sim_2025-02-13.tar.gz

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

# combine any split tar files into a single file (this will probably just be the rosetta distribution)
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

# the environment files need to be un-tarred into the "env" directory
# un-tar the environment files
if [ -f "$ENV_FN" ]; then
  echo "Extracting $ENV_FN"
  mkdir env
  tar -xzf $ENV_FN -C env
  rm $ENV_FN
fi

echo "Activating Python environment"
export PATH
. env/bin/activate

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

# launch our python run script with argument file number
echo "Launching ${PYSCRIPT}"
python3 code/${PYSCRIPT} @energize_args.txt --variants_fn="${PROCESS}.txt" --cluster="$CLUSTER" --process="$PROCESS" --commit_id="$GITHUB_TAG"
