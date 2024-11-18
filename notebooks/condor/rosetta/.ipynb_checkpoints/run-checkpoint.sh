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

echo "Launching Download environment"
# start the downloading for the environment first.
curl http://proxy.chtc.wisc.edu/SQUID/bcjohnson7/rosettafy_env_v0.7.11.tar.gz -o rosettafy_env_v0.7.11.tar.gz


echo "Setting up Python environment"
export PATH
mkdir rosettafy_env
tar -xzf rosettafy_env_v0.7.11.tar.gz -C rosettafy_env
. rosettafy_env/bin/activate
rm rosettafy_env_v0.7.11.tar.gz

echo "Launching Download Rosetta"

curl https://downloads.rosettacommons.org/downloads/academic/3.14/rosetta_bin_linux_3.14_bundle.tar.bz2 -o rosetta_bin_linux_3.14_bundle.tar.bz2 


# curl --range 0-10485759 https://downloads.rosettacommons.org/downloads/academic/3.14/rosetta_bin_linux_3.14_bundle.tar.bz2 -o rosetta_bin_linux_3.14_bundle_partial.tar.bz2


tar -xvjf rosetta_bin_linux_3.14_bundle.tar.bz2

rm rosetta_bin_linux_3.14_bundle.tar.bz2


chmod 777 encrypt.sh

echo "Sucessfully Downloaded Rosetta and deleted tar file"



echo "Starting the compression of rosetta "
python rosetta_minimal.py --gen_distribution --rosetta_main_dir=rosetta.binary.linux.release-371/main --out_dir=rosetta_minimal
echo "completed the compression of rosetta "


echo "Starting the encryption "


python rosetta_minimal.py --prep_for_squid --out_dir=rosetta_minimal --squid_dir=output/squid_rosetta --encryption_password=R0S3774123
echo "finished the encryption "


echo "starting the tar output "
tar -czf output.tar.gz output/squid_rosetta/


