# Rosettafy

This repository facilitates high-throughput Rosetta runs to compute energy terms for protein variants.

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

## Preparing PDB files for Rosetta
Raw PDB files like those acquired from [Protein Data Bank](https://www.rcsb.org/) need to be prepared for use with Rosetta. 
Our approach is based on the [recommendation in the Rosetta documentation](https://www.rosettacommons.org/docs/latest/rosetta_basics/preparation/preparing-structures). 

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

The main script for this pipeline is [prepare.py](code/prepare.py).

### Example

Let's prepare [2qmt.pdb](pdb_files/raw_pdb_files/2qmt.pdb) for use with Rosetta. 
This PDB file was downloaded from [Protein Data Bank](https://www.rcsb.org/structure/2QMT) and is located at `pdb_files/raw_pdb_files/2qmt.pdb`.

Make sure the `rosettafy` conda environment is active. 
Then, call the following command from the root directory of this repository.

```commandline
python code/prepare.py --rosetta_main_dir=<path_to_rosetta_main_dir> --pdb_fn=pdb_files/raw_pdb_files/2qmt.pdb --relax_nstruct=10 --out_dir_base=output/prepare_outputs 
```

_Note: you will need to specify the path to your Rosetta installation's `main` folder. On macOS, it may look similar to:  
`/Users/<username>/rosetta_bin_mac_2021.16.61629_bundle/main`._ 

Additional arguments specified in this example: 

| Parameter       | Description                      | Value                              |
|-----------------|----------------------------------|------------------------------------|
| `pdb_fn`        | Path to the raw PDB file         | `pdb_files/raw_pdb_files/2qmt.pdb` |
| `relax_nstruct` | Number of structures to generate | `10`                               |
| `out_dir_base`  | Base directory for outputs       | `output/prepare_outputs`           |

For a full list of parameters, call `python code/prepare.py -h`. 


When you call this command, the [prepare.py](code/prepare.py) script will:
- Create an output directory named `2qmt` under `output/prepare_outputs`
- Call Rosetta `relax` to generate `10` potential structures
- Automatically select the lowest energy structure and copy it to `2qmt_p.pdb`
- Place the remaining structures and other outputs in the `working_dir` directory.


## Computing Rosetta energy terms for protein variants
This pipeline computes Rosetta energies for specified variants and consists of two steps: mutate and relax.

1. Mutate performs the amino acid substitutions and optimizes rotamers at the mutated residues
2. Relax optimizes the structure at and around the mutated residues and computes the energies for the final structure


## Running with HTCondor

The main steps for setting up a Rosettafy HTCondor run are:
1. Package a minimal distribution of Rosetta and upload it to SQUID 
2. Prepare a PDB file for use with Rosetta
3. Generate a list of variants for which you want to compute energies

### Packaging a minimal distribution of Rosetta
The [rosetta_minimal.py](code/rosetta_minimal.py) script can be used to:
- Create a minimal distribution of Rosetta
- Compress it into a single `.tar.gz` file
- Encrypt the `.tar.gz` file with a password using the `openssl` library
- Split the encrypted `.tar.gz` file into multiple ~700mb files to adhere to SQUID guidelines for file size

> **Note**
> You need to package the Linux version of Rosetta for running on Linux servers like those available from CHTC and OSG

> **Note**
> If you add custom Rosetta code to compute new energy terms, you will need to modify the [rosetta_minimal.py](code/rosetta_minimal.py) script to include your code dependencies in the minimal distribution 

To create the minimal distribution of Rosetta, call the following command from the root directory of this repository.

```commandline
python code/rosetta_minimal.py --gen_distribution --rosetta_main_dir=<path_to_rosetta_main_dir> --out_dir=rosetta_minimal
```
where `<path_to_rosetta_main_dir>` is the path to full Rosetta distribution.
It may look similar to: `/Users/<username>/rosetta_bin_linux_2021.16.61629_bundle/main`.

### Generating variant lists
The [variants.py](code/variants.py) script can be used to generate variant lists.
It has three modes of operation: `all`, `random`, `subvariants`.

#### Generating all possible variants
For small proteins with a small number of mutations, it may be feasible to generate all possible variants.
Here is how to generate all possible single amino acid substitution variants for the protein [2qmt.pdb](pdb_files/raw_pdb_files/2qmt.pdb).

```commandline
python code/variants.py all --pdb_fn=pdb_files/prepared_pdb_files/2qmt_p.pdb --num_subs_list 1
```

By default, the output will be written to `variant_lists/2qmt_p_all_NS-1.txt`.
You can generate all double amino acid substitution variants by specifying `2` for the `--num_subs_list` parameter.

#### Generating variants using the sub-variants algorithm

The algorithm...



