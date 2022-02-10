# PDB files for global dataset

The list of PDB files for the global dataset was acquired from _De novo structure prediction of globular proteins aided by sequence variation-derived contacts_.

>Kosciolek, T., & Jones, D. T. (2014). De novo structure prediction of globular proteins aided by sequence variation-derived contacts. PloS one, 9(3), e92197. https://doi.org/10.1371/journal.pone.0092197

The raw list is stored as a .doc file and comes from Supplementary Table 1 (https://doi.org/10.1371/journal.pone.0092197.s002). 
We copied the list to a simple text file ([pdb_list.txt](pdb_list.txt)). 

There are multiple processing steps to download and prepare these files. See below for the full pipeline.
Final processed are placed in [prepared_pdb_files](../prepared_pdb_files).


[//]: # (The code for fetching and processing the PDB files from [RCSB Protein Data Bank]&#40;https://www.rcsb.org&#41; is contained in [fetch_pdbs.sh]&#40;fetch_pdbs.sh&#41;.)

[//]: # (Running the script will create intermediate directories for the raw PDB files and other processing steps. )

### Pipeline for preparing these 150 PDB files 
There was some trial and error. We may simplify this pipeline in the future. 
1. Run [fetch_pdbs.sh](fetch_pdbs.sh) to download the raw PDB files
2. Run the [parse_KosciolekAndJones.ipynb](../../notebooks/parse_KosciolekAndJones.ipynb) notebook up to section 6 
   1. This creates ready_set_1.txt, which is a list of PDB files that do not have missing or modified residues
   2. Two PDBs actually do end up having missing residues after clean_pdb.py (1c52 and 1fx2). These can be removed from the list manually or just ignored in downstream analysis.
5. Run [parse_KosciolekAndJones.ipynb](../../notebooks/parse_KosciolekAndJones.ipynb) section 7 to create ready_set_2.txt, which contains PDB files that have modified residues but are still able to processed by Rosetta's clean_pdb.py. Also includes some PDB files that were though to have missing residues, but don't.  

Now, we must deal with the PDB files that have missing or modified residues.
5. Run the loop modeling pipeline in [loop_modeling](loop_modeling)
6. Copy and rename remodeled PDB files from `loop_modeling/pdbs_remodel` to `pdbs_remodel` (replace A_0001 in filenames with "remod")
7. Run [parse_KosciolekAndJones.ipynb](../../notebooks/parse_KosciolekAndJones.ipynb) section 8 to create ready_set_3.txt, containing remodeled PDBs

Once we have the three sets, they need to be run through the [prepare.py](../../code/prepare.py) pipeline. 

### Future pipeline
To make the above more easily reproducible. 
1. Download raw PDB files by running fetch_pdbs.sh
2. Run a single script that will filter PDBs and perform loop modeling where appropriate
3. Run the final PDB files through the prepare pipeline