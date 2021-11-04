# Template working directory for energize pipeline

This is the template working directory for the energize pipeline. 

This directory contains files needed to run Rosetta, including RosettaScripts XML files and simple text files with command line arguments. 
Files from this directory are copied over to the actual working directory at runtime. 
Some files in this directory need to be dynamically updated depending on the specific variant and hyperparameters.
For example, [mutation_template.resfile](mutation_template.resfile) is renamed to mutation.resfile and filled in with the amino acid substitutions for the variant that is being processed.

Not all Rosetta hyperparameters are defined via these files. 
Some are passed directly into the python script [energize.py](../../code/energize.py) and forwarded to Rosetta via command line arguments when the script invokes the Rosetta binaries with `subprocess.call()`.