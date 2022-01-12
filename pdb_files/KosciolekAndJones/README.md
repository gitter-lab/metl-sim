# PDB files for global dataset

The list of PDB files for the global dataset was acquired from _De novo structure prediction of globular proteins aided by sequence variation-derived contacts_.

>Kosciolek, T., & Jones, D. T. (2014). De novo structure prediction of globular proteins aided by sequence variation-derived contacts. PloS one, 9(3), e92197. https://doi.org/10.1371/journal.pone.0092197

The raw list is stored as a .doc file and comes from Supplementary Table 1 (https://doi.org/10.1371/journal.pone.0092197.s002). 
We copied the list to a simple text file ([pdb_list.txt](pdb_list.txt)). 

The code for fetching and processing the PDB files from [RCSB Protein Data Bank](https://www.rcsb.org) is contained in [fetch_pdbs.sh](fetch_pdbs.sh).
Running the script will create intermediate directories for the raw PDB files and other processing steps. 
Final processed PDB files that are ready to use with Rosetta are placed in [prepared_pdb_files](../prepared_pdb_files) along with PDB files for local datasets. 