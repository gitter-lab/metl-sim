# Variant lists


These files contain lists of protein variants and can be provided as the `variants_fn` argument in [energize.py](../code/energize.py).
They can also be split into smaller files to be distributed across many jobs in [condor.py](../code/condor.py).

To specify a variant, you must list the PDB file it is based on (the PDB file defines the base amino acid sequence).
The variant itself follows the format <old_AA><seq_pos><new_AA>.

For example:
```
2qmt_p.pdb A23F
2qmt_p.pdb G37V,L6E
```

Variant lists for the RosettaTL dataset can be generated using [variants.py](../code/variants.py).