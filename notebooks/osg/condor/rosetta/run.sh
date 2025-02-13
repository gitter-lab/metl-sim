#!/usr/bin/env bash

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

echo "Launching Rosetta download"

curl https://downloads.rosettacommons.org/downloads/academic/3.14/rosetta_bin_linux_3.14_bundle.tar.bz2 -o rosetta_bin_linux_3.14_bundle.tar.bz2 

# curl --range 0-10485759 https://downloads.rosettacommons.org/downloads/academic/3.14/rosetta_bin_linux_3.14_bundle.tar.bz2 -o rosetta_bin_linux_3.14_bundle_partial.tar.bz2

tar -xvjf rosetta_bin_linux_3.14_bundle.tar.bz2

rm rosetta_bin_linux_3.14_bundle.tar.bz2

chmod 777 encrypt.sh

echo "Generating a minimal Rosetta distribution and compressing it"
python rosetta_minimal.py --gen_distribution --rosetta_main_dir=rosetta.binary.linux.release-371/main --out_dir=rosetta_minimal

echo "Encrypting the minimal Rosetta distribution"
python rosetta_minimal.py --prep_for_squid --out_dir=rosetta_minimal --squid_dir=output/squid_rosetta --encryption_password=R0S3774123

echo "Tarring final outputs"
tar -czf output.tar.gz output/squid_rosetta/


