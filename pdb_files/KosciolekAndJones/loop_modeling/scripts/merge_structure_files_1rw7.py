""" Special merging for 1rw7 as it has been removed from the pdb
    and doesn't have a mmtf file"""

import pandas as pd

import Bio.Data.SCOPData

import merge_structure_files

code = '1rw7' # has no mmtf file as 1rw7 is removed from PDB and replaced by 4QYX.


if __name__ == "__main__":
    import argparse
    import logging
    parser = argparse.ArgumentParser()
    parser.add_argument("code", default="1rw7",
                    help="pdb code")
    parser.add_argument("-d", "--data_dir",
                    help="location of data directory",
                    default="") # default is data_dir global variable
    parser.add_argument("-o", "--output_tsv", required=True)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.data_dir:
        data_dir = args.data_dir

    assert(args.code == code)
    logging.info("code : %s", code)

    seqres = merge_structure_files.get_seqres_pdb_raw(code)
    construct_seq = str(seqres.seq)
    logging.info("code : %s, construct_seq : %s", code, construct_seq)

    # add the construct sequence and a counter for the pdb indexing (1-based)$
    cons_df = pd.DataFrame(list(construct_seq))
    cons_df.columns = ["construct"]
    cons_df["pdb_idx"] = range(1, len(construct_seq) + 1)

    cons_df["resolved"] = False
    cons_df["sec_struct"] = -1

    cons_df["clean_pdb_idx"] = -1 # default values for missing
    cons_df["clean_pdb_aa"] = "" # default values for missing

    y = merge_structure_files.get_struct_pdb_clean(code)

    for i, res in enumerate(y.get_residues()):
        clean_pdb_idx = i + 1 # pdb indexing always starts from 1$
        min_dist_idx = i + 1 # special handling for 1rw7

        res_code = Bio.Data.SCOPData.protein_letters_3to1[res.resname]
        assert(cons_df.loc[min_dist_idx, "construct"] == res_code)

        cons_df.loc[min_dist_idx, "clean_pdb_idx"] = clean_pdb_idx
        cons_df.loc[min_dist_idx, "clean_pdb_aa"] = res_code

    cons_df_save = cons_df
    cons_df_save.to_csv(args.output_tsv, index=False, sep="\t")
    logging.info("code : %s, merged files saved to %s", code, args.output_tsv)
