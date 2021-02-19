#!/bin/bash

# todo: rename this script to mutate.sh to differentiate from potential script to prep pdb (which will also relax)

# this script might be called from the root or code directory
# but it does all its work in the rosetta working directory
cd ~/rosetta_working_dir

./rosetta_scripts.static.linuxgccrelease @flags_mutate > mutate.log
./rosetta_scripts.static.linuxgccrelease @flags_relax > relax.log

