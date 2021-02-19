# Rosettafy: compute Rosetta energy terms for protein variants

This repository facilitates large-scale runs of Rosetta on HTCondor for the purpose of generating Rosetta datasets for RosettaTL.
There are two main pipelines: prepare and energize. 

## Prepare
This pipeline prepares raw PDB files for use with Rosetta. 
It is based on the [recommendation in the Rosetta documentation](https://www.rosettacommons.org/docs/latest/rosetta_basics/preparation/preparing-structures). 

1. Run Rosetta's `clean_pdb_keep_ligand.py`
2. Relax with all-heavy-atom constraints

Note: There may need to be an additional step at the beginning to handle inconsistencies when downloading from RCSB PDB.
Also, I think at some point we need to make sure there is only a single chain in the PDB file.

## Energize
This pipeline computes Rosetta energies for specified variants.

1. Mutate
2. Relax
