#!/bin/bash

# todo: call this from python instead of running via a shell script?

# this script might be called from the root or code directory
# but it does all its work in the rosetta working directory
cd ~/rosetta_working_dir

./rosetta_scripts.static.linuxgccrelease @flags_mutate > mutate.log
./rosetta_scripts.static.linuxgccrelease @flags_relax > relax.log

