# Rosettafy: compute Rosetta energy terms for protein variants

This repository facilitates large-scale runs of Rosetta on HTCondor for the purpose of generating Rosetta datasets for RosettaTL.
There are two main pipelines: prepare and energize. 

## Setup

Install Rosetta v3.13 from [rosettacommons.org](https://www.rosettacommons.org). 
See the website for instructions on acquiring a license and installing the software.

There are two Python environments in the [setup](setup) directory. Install them with [Anaconda](https://www.anaconda.com).
```
conda env create -f setup/clean_pdb_env.yml
conda env create -f setup/rosettafy_env.yml
```

The main environment is named `rosettafy`.
```
conda activate rosettafy
```
The other environment, named `clean_pdb`, is exclusively for running Rosetta's `clean_pdb.py` and `clean_pdb_keep_ligand.py`, which require Python 2. 
There is no need to manually activate this environment. It will be automatically activated when preparing PDB files for use with Rosetta.

## Prepare
This pipeline prepares raw PDB files for use with Rosetta. 
It is based on the [recommendation in the Rosetta documentation](https://www.rosettacommons.org/docs/latest/rosetta_basics/preparation/preparing-structures). 

1. Run Rosetta's `clean_pdb.py` or `clean_pdb_keep_ligand.py`.
2. Relax with all-heavy-atom constraints.
    ```
    -relax:constrain_relax_to_start_coords
    -relax:coord_constrain_sidechains
    -relax:ramp_constraints false
    -ex1
    -ex2
    -use_input_sc
    -flip_HNQ
    -no_optH false
    ```
3. Select the lowest energy structure generated in the previous step.

### Example

Let's prepare [2qmt.pdb](pdb_files/raw_pdb_files/2qmt.pdb) for use with Rosetta. 
Call the following from the root directory. 
Note you will need to specify the path to your Rosetta installation's `main` folder. It may look similar to:  
`/Users/<username>/rosetta_bin_mac_2021.16.61629_bundle/main`.

```commandline
python code/prepare.py --rosetta_main_dir=<path_to_rosetta_main_dir> --pdb_fn=pdb_files/raw_pdb_files/2qmt.pdb --relax_nstruct=10 --out_dir_base=output/prepare_outputs 
```

Here, we specify the raw PDB file [2qmt.pdb](pdb_files/raw_pdb_files/2qmt.pdb) located in the [raw_pdb_files](pdb_files/raw_pdb_files) directory. 
Rosetta will generate 10 potential structures because we set `relax_nstruct` to 10. 
The outputs will be placed in the `output/prepare_outputs` directory. 
The lowest energy structure will be automatically selected and copied over as `2qmt_p.pdb`. 
The remaining structures and other outputs will be available under the `working_dir` directory.

For a full list of parameters, call `python code/prepare.py -h`. 


## Energize
This pipeline computes Rosetta energies for specified variants and consists of two steps: mutate and relax.

1. Mutate performs the amino acid substitutions and optimizes rotamers at the mutated residues
2. Relax optimizes the structure at and around the mutated residues and computes the energies for the final structure
