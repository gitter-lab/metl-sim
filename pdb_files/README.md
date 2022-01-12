# PDB files

### Local datasets
Local datasets are based on proteins from deep mutational scanning datasets. 
We found structures for these proteins by manually searching [RCSB Protein Data Bank](https://www.rcsb.org) for matching sequences.
The raw PDB files are located in [raw_pdb_files](raw_pdb_files) and ready-to-use pdb files are located in [prepared_pdb_files](prepared_pdb_files).

| Protein | DMS Reference | PDB Reference | Notes                                                                                                                                                                                          |
|---------|-------------|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| GB1     |             | 2QMT          |                                                                                                                                                                                                |
| avGFP   |             | 1GFL          | To match the reference sequence of the DMS dataset, we ultiamtely used a homology model based on 1GFL. The homology model `1gfl_cm.pdb` is stored in [prepared_pdb_files](prepared_pdb_files). |



### Global dataset

For the global dataset, we are using a list of 150 protein structures from _De novo structure prediction of globular proteins aided by sequence variation-derived contacts_.
The relevant code for fetching and processing PDB files for these proteins is located in [KosciolekAndJones](KosciolekAndJones).  

>Kosciolek, T., & Jones, D. T. (2014). De novo structure prediction of globular proteins aided by sequence variation-derived contacts. PloS one, 9(3), e92197. https://doi.org/10.1371/journal.pone.0092197

