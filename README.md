# Molecular simulations for METL
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.10819523.svg)](https://zenodo.org/doi/10.5281/zenodo.10819523)

This repository facilitates high-throughput Rosetta runs to compute energy terms for protein variants.
For more information, please see the [metl](https://github.com/gitter-lab/metl) repository and our manuscript:

[Biophysics-based protein language models for protein engineering](https://doi.org/10.1101/2024.03.15.585128).  
Sam Gelman, Bryce Johnson, Chase Freschlin, Arnav Sharma, Sameer D'Costa, John Peters, Anthony Gitter<sup>+</sup>, Philip A Romero<sup>+</sup>.  
*bioRxiv*, 2024. doi:10.1101/2024.03.15.585128  
<sup>+</sup> denotes equal contribution.

Users of this workflow should [cite Rosetta](https://github.com/RosettaCommons/rosetta/blob/main/CITING_ROSETTA.md) in addition to METL.

## Table of Contents
  * [Setup](#setup)
  * [Preparing PDB files for Rosetta](#preparing-pdb-files-for-rosetta)
  * [Computing Rosetta energy terms for protein variants](#computing-rosetta-energy-terms-for-protein-variants)
  * [Running with HTCondor](#running-with-htcondor)
    + [Packaging a minimal distribution of Rosetta](#packaging-a-minimal-distribution-of-rosetta)
    + [Packaging the Python environment](#packaging-the-python-environment)
    + [Prepare a PDB file for use with Rosetta](#prepare-a-pdb-file-for-use-with-rosetta)
    + [Generating variant lists](#generating-variant-lists)
      - [Generating all possible variants](#generating-all-possible-variants)
      - [Generating variants using the subvariants algorithm](#generating-variants-using-the-subvariants-algorithm)
    + [Prepare an HTCondor run](#prepare-an-htcondor-run)
    + [Processing results](#processing-results)
        - [Parse the results files](#parse-the-results-files)
        - [Add results to a database](#add-results-to-a-database)


## Setup

Install Rosetta v3.13 from [rosettacommons.org](https://www.rosettacommons.org). 
See the website for instructions on acquiring a license and installing the software.

There are two Python environments in the [setup](setup) directory. Install them with [Anaconda](https://www.anaconda.com).
```
conda env create -f setup/clean_pdb_env.yml
conda env create -f setup/metl-sim_env.yml
```

Installation typically takes approximately 5 minutes. 

The main environment is named `metl-sim`.
```
conda activate metl-sim
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

The main script for this pipeline is [prepare.py](code/prepare.py), and it will run the above steps for you (no need to do it manually).

### Example

Let's prepare [2qmt.pdb](pdb_files/raw_pdb_files/2qmt.pdb) for use with Rosetta. 
This PDB file was downloaded from [Protein Data Bank](https://www.rcsb.org/structure/2QMT) and is located at `pdb_files/raw_pdb_files/2qmt.pdb`.

Make sure the `metl-sim` conda environment is active. 
Then, call the following command from the root directory of this repository.

```commandline
python code/prepare.py --rosetta_main_dir=<path_to_rosetta_main_dir> --pdb_fn=pdb_files/raw_pdb_files/2qmt.pdb --relax_nstruct=10 --out_dir_base=output/prepare_outputs 
```

>**Note**  
> You need to specify the path to your Rosetta installation's `main` folder. It may look similar to:  
`/Users/<username>/rosetta_bin_mac_2021.16.61629_bundle/main` 

Additional arguments specified in this example: 

| Parameter       | Description                      | Value                              |
|-----------------|----------------------------------|------------------------------------|
| `pdb_fn`        | Path to the raw PDB file         | `pdb_files/raw_pdb_files/2qmt.pdb` |
| `relax_nstruct` | Number of structures to generate | `10`                               |
| `out_dir_base`  | Base directory for outputs       | `output/prepare_outputs`           |

For a full list of parameters, call `python code/prepare.py -h`. 

Running this example can take approximately 5-10 minutes depending on CPU speed.

When you call this command, the [prepare.py](code/prepare.py) script will:
- Create an output directory named `2qmt` under `output/prepare_outputs`
- Call Rosetta `relax` to generate `10` potential structures
- Automatically select the lowest energy structure and copy it to `2qmt_p.pdb`
- Place the remaining structures and other outputs in the `working_dir` directory.


## Computing Rosetta energy terms for protein variants

The [energize.py](code/energize.py) script can be used to compute Rosetta energy terms for protein variants.

This script runs our full Rosetta pipeline, consisting of multiple steps to:
1. Introduce the variant's mutations to the base structure using a resfile \[[1](templates/energize_wd_template/mutate_template.xml)\] \[[2](templates/energize_wd_template/mutation_template.resfile)\]
2. Relax the updated structure to compute the main energy terms \[[1](templates/energize_wd_template/relax_template.xml)\] \[[2](templates/energize_wd_template/flags_relax)\] \[[3](templates/energize_wd_template/flags_relax_all)\]
3. Compute custom filter-based energy terms \[[1](templates/energize_wd_template/filter_3rd.xml)\] \[[2](templates/energize_wd_template/flags_filter)\]
4. Compute centroid energy terms \[[1](templates/energize_wd_template/flags_centroid)\]

This script calls Rosetta binaries using the `subprocess` library. 
Some hyperparameters for Rosetta can be specified as arguments to this script.
This script will either pass those hyperparameters along to Rosetta as command line arguments, or it will modify the templates in the [templates](templates) directory to account for the hyperparameters.
Other hyperparameters are hardcoded in various files in the [templates](templates) directory.
For ease of use and reproducibility, arguments to this script can be stored in text files in the [energize_args](energize_args) directory.
The arguments used to generate Rosetta data for our manuscript are in [condor_set_2.txt](energize_args/condor_set_2.txt) 

This script processes the results from all of these steps into a single dataframe.


### Example

Let's compute Rosetta energy terms for a variant of the PDB file we prepared in the previous step, [2qmt_p.pdb](pdb_files/prepared_pdb_files/2qmt_p.pdb).
The [energize.py](code/energize.py) script accepts variants in a text file.
I explain how to generate variant lists in the next section.
For now, I created a sample text file with two variants, [2qmt_p_example.txt](variant_lists/2qmt_p_example.txt).

Make sure the `metl-sim` conda environment is active. 
Then, call the following command from the root directory of this repository.

```commandline
python code/energize.py @energize_args/example.txt --rosetta_main_dir=<path_to_rosetta_main_dir>  --variants_fn=variant_lists/2qmt_p_example.txt --save_wd
```

Note we are using the `@energize_args/example.txt` argument to insert arguments from that file.
Additionally, we are specifying the path to the Rosetta installation, the file containing the variants to run, and an additional flag `--save_wd` to save the working directory for each variant.
For condor runs, there is no need to specify the `--save_wd` flag, as it will generate too much output.

Running this example takes approximately 2-3 minutes depending on CPU speed.

By default, the output will be placed in the `output/energize_outputs` directory.
The output consists of multiple files:
- **args.txt** which contains the arguments used to run the script
- **energies.csv** which contains the computed energy terms for each variant
- **hparams.csv** which contains the hyperparameters used to compute the energy terms
- **job.csv** which contains information about the run
- If the `--save_wd` flag is specified, the output will also contain working directories for each variant, which contain a number of additional log files and structure files output by Rosetta. 


## Running with HTCondor

The main steps for setting up a metl-sim HTCondor run are:
1. Package a minimal distribution of Rosetta and upload it to SQUID or OSDF ([rosetta_minimal.py](code/rosetta_minimal.py))
2. Package the Python environment and upload it to SQUID or OSDF
3. Prepare a PDB file for use with Rosetta ([prepare.py](code/prepare.py))
4. Generate a list of variants for which you want to compute energies ([variants.py](code/variants.py))
5. Prepare an HTCondor run ([condor.py](code/condor.py))

### Packaging a minimal distribution of Rosetta
The [rosetta_minimal.py](code/rosetta_minimal.py) script can be used to:
- Create a minimal distribution of Rosetta
- Compress it into a single `.tar.gz` file
- Encrypt the `.tar.gz` file with a password using the `openssl` library
- Split the encrypted `.tar.gz` file into multiple ~700mb files

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
The minimal distribution will be created in the `rosetta_minimal` directory.

To package the Rosetta distribution for SQUID or OSDF:

```commandline
python code/rosetta_minimal.py --prep_for_squid --out_dir=rosetta_minimal --squid_dir=output/squid_rosetta --encryption_password=password
```
The packaged distribution will be created in the `output/squid_rosetta` directory.

> **Note**  
> You must specify an encryption password to prevent unauthorized access to the Rosetta distribution. Make sure to update [pass.txt](htcondor/templates/pass.txt) with the password you choose. The password contained in [pass.txt](htcondor/templates/pass.txt) is what will be used to decrypt Rosetta later on and must match the encryption password.   

Once you have the packaged Rosetta distribution, upload it to OSDF.
**Then, modify [osdf_rosetta_distribution.txt](htcondor/templates/osdf_rosetta_distribution.txt) to list the OSDF paths to the Rosetta distribution files you uploaded.** 
The file currently contains the following example paths:
```
osdf:///chtc/staging/sgelman2/squid_rosetta_2023-10-30_21-53-58/rosetta_min_enc.tar.gz.aa
osdf:///chtc/staging/sgelman2/squid_rosetta_2023-10-30_21-53-58/rosetta_min_enc.tar.gz.ab
osdf:///chtc/staging/sgelman2/squid_rosetta_2023-10-30_21-53-58/rosetta_min_enc.tar.gz.ac
```


### Packaging the Python environment

You must package the Python environment and upload it to SQUID or OSDF.
CHTC has instructions on how to do this [here](https://chtc.cs.wisc.edu/uw-research-computing/conda-installation.html).
To make this process easier, I created a helper script, [package_env.sh](htcondor/package_env.sh). 

To package the Python environment, perform the following steps:
1. Create a working directory on the submit node named `environment`
2. Upload [htcondor/package_env.sh](htcondor/package_env.sh) and [setup/metl-sim_env.yml](setup/metl-sim_env.yml) to the `environment` directory
3. CD into the `environment` directory on the submit node
4. Rename metl-sim.yml to environment.yml (this is what package_env.sh expects)
5. Run `package_env.sh` and wait for it to finish
6. Transfer the resulting `metl-sim_env.tar.gz` file to OSDF
7. **Modify [osdf_python_distribution.txt](htcondor/templates/osdf_python_distribution.txt) to list the OSDF path to the Python environment file you uploaded. See the current file contents for an example.**


### Prepare a PDB file for use with Rosetta
See the above section on [Preparing PDB files for Rosetta](#preparing-pdb-files-for-rosetta).

If preparing your PDB file(s) locally is too slow, you can create an HTCondor run to do it.

_Todo: add instructions for this_

### Generating variant lists
The [variants.py](code/variants.py) script can be used to generate variant lists.
It has three modes of operation: `all`, `random`, `subvariants`.

#### Generating all possible variants
For small proteins with a small number of mutations, it may be feasible to generate all possible variants.
Here is how to generate all possible single amino acid substitution variants for the PDB file [2qmt_p.pdb](pdb_files/prepared_pdb_files/2qmt_p.pdb) we prepared in the previous section.

```commandline
python code/variants.py all --pdb_fn=pdb_files/prepared_pdb_files/2qmt_p.pdb --num_subs_list 1
```

You can generate all double amino acid substitution variants by specifying `--num_subs_list 2`.
By default, the output will be written to `variant_lists/2qmt_p_all_NS-1.txt`. 
You can specify a different output directory using the `--out_dir` argument.

#### Generating variants using the subvariants algorithm

We implemented a subvariants sampling algorithm to ensure that all possible subvariants are included in the variant list.

Given:
- The maximum and minimum number of substitutions
- The desired number of variants 

The algorithm initializes an empty list of variants and performs the following until the desired number of variants is reached:
1. Generate a random variant with the maximum number of substitutions.
2. Check if the new variant is already in the list of variants. If it is, go back to step 1.
3. Add the new variant to the list of variants.
4. Generate all possible subvariants of the new variant, starting with the max number of substitutions minus one and down to the minimum number of substitutions.
5. For each subvariant, check if it is in the list, and if it is not, add it to the list.

In the previous step, we generated all possible single amino acid substitution variants for the PDB file [2qmt_p.pdb](pdb_files/prepared_pdb_files/2qmt_p.pdb).
Now, let's use the subvariants algorithm to generate 100,000 variants with a maximum of 5 substitutions and a minimum of 2 substitutions.

```commandline
python code/variants.py subvariants --pdb_fn=pdb_files/prepared_pdb_files/2qmt_p.pdb --target_num 100000 --max_num_subs 5 --min_num_subs 2
```

By default, the output will be written to the `variant_lists` directory.

### Prepare an HTCondor run

The [condor.py](code/condor.py) script can be used to prepare an HTCondor run.
You can specify arguments to this script directly on the command line, or you can specify them in arguments files stored in the [run_defs](htcondor/run_defs) directory.
I prefer to create an argument file for every condor run for record-keeping and reproducibility.

Here is how you would create an argument file for a condor run to compute energy terms for the single substitution variants we generated in the previous section.
Note each command line argument is specified on a separate line.

Contents of `htcondor/run_defs/gb1_example_run.txt`
```text
--run_type
energize
--run_name
gb1_example_run
--energize_args_fn
energize_args/condor_set_2.txt
--master_variant_fn
variant_lists/2qmt_p_all_NS-1.txt
--variants_per_job
-1
--osdf_python_distribution
htcondor/templates/osdf_python_distribution.txt
--osdf_rosetta_distribution
htcondor/templates/osdf_rosetta_distribution.txt
--github_tag
v1.0
```

You can then generate the HTCondor run using the following command:
```commandline
python code/condor.py @htcondor/run_defs/gb1_example_run.txt
```

The script will generate a run directory and place it in `output/htcondor_runs`.
From there, you can upload the run directory to your HTCondor submit node. 
You can then submit the run using `submit.sh`, which should be located in the run directory.

### Processing results

The HTCondor run will produce a log directory for each job. 
The log directory contains 4 files: `args.txt`, `job.csv`, `hparams.csv`, and `energies.csv`.

| File Name     | Description                                                                                                          |
|---------------|----------------------------------------------------------------------------------------------------------------------|
| `args.txt`    | Contains the arguments fed into the `energize.py` script to produce the output.                                      |
| `job.csv`     | Contains information about the HTCondor job that produced the output, such as the cluster, hostname, and start time. |
| `hparams.csv` | Contains the Rosetta hyperparameters used to compute the energies.                                                   |
| `energies.csv`| Contains the computed energies for each variant in the job.                                                          |

After the HTCondor run, transfer these log directories to your local machine for processing. 
I recommend compressing them before the file transfer:
```commandline
tar -czf output.tar.gz output
```
Then untar the file on your local machine:
```commandline
tar -xf output.tar.gz
```

Make sure to extract the output into the same condor run directory that you produced with `condor.py` in the [Prepare an HTCondor run](#prepare-an-htcondor-run) section.

#### Parse the results files

The [process_run.py](code/process_run.py) script can be used to parse the results files and combine them into a single dataframe.

Run it with the following command, specifying the mode `stats` and the main run directory of the HTCondor run:
```commandline
python code/process_run.py stats --main_run_dirs output/htcondor_runs/my_condor_run
```

This will produce a directory named `processed_run` inside in the main run directory.
The `processed_run` directory contains a number of plots and dataframes which should be self-explanatory.
The main dataframe is `processed_run/energies_df.csv` and contains the computed energies for each variant in the run.

You can specify multiple run directories to process at a time by separating them with a space when calling [process_run.py](code/process_run.py).

#### Add results to a database

You can add the results of one or more HTCondor runs to an SQLite database using the [process_run.py](code/process_run.py) script.

First, create the blank database using [database.py](code/database.py).
```commandline
python code/database.py create --db_fn variant_database/my_database.db
```

Then, add the results of one or more HTCondor runs to the database using the `database` mode of [process_run.py](code/process_run.py).
```commandline
python code/process_run.py database --main_run_dirs output/htcondor_runs/my_condor_run --db_fn variant_database/my_database.db
```

This database can now be used with the [metl](https://github.com/gitter-lab/metl) repository to create a processed Rosetta dataset and pretrain METL models.
