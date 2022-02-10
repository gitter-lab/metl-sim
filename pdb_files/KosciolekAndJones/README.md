# PDB files for global dataset

The list of PDB files for the global dataset was acquired from _De novo structure prediction of globular proteins aided by sequence variation-derived contacts_.

>Kosciolek, T., & Jones, D. T. (2014). De novo structure prediction of globular proteins aided by sequence variation-derived contacts. PloS one, 9(3), e92197. https://doi.org/10.1371/journal.pone.0092197

The raw list is stored as a .doc file and comes from Supplementary Table 1 (https://doi.org/10.1371/journal.pone.0092197.s002). 
We copied the list to a simple text file ([pdb_list.txt](pdb_list.txt)). 

The code for fetching and processing the PDB files from [RCSB Protein Data Bank](https://www.rcsb.org) is contained in [fetch_pdbs.sh](fetch_pdbs.sh).
Running the script will create intermediate directories for the raw PDB files and other processing steps. 
Final processed PDB files that are ready to use with Rosetta are placed in [prepared_pdb_files](../prepared_pdb_files) along with PDB files for local datasets.

### Pipeline for preparing these 150 PDB files 
Note this pipeline involves multiple files and steps. 
In the future, we may potentially simplify this to make it easier to run.
1. Run [fetch_pdbs.sh](fetch_pdbs.sh) to download the raw PDB files
2. Run the [parse_KosciolekAndJones.ipynb](../../notebooks/parse_KosciolekAndJones.ipynb) notebook up to section 6 to create ready_set_1.txt, which is a list of PDB files that do not have missing or modified residues
3. Run [prepare.sh](prepare.sh) to run the PDBs in ready_set_1.txt through the Rosettafy prepare pipeline
4. Run [parse_KosciolekAndJones.ipynb](../../notebooks/parse_KosciolekAndJones.ipynb) section 6.1 to copy the prepared PDB files to the main directory 

Now, we must deal with the PDB files that have missing or modified residues.
5. Run the loop modeling pipeline in [loop_modeling](loop_modeling)
6. 