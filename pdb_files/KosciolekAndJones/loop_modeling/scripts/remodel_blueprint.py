import itertools

import numpy as np
import pandas as pd


data_dir = "../data"
chain = 'A'


def get_bp_fn(code):
    return f"{data_dir}/pdbs_bp/{code}_{chain}.bp"

def get_merge_fn(code):
    return f"{data_dir}/pdbs_merge/{code}_merge.tsv"

def get_bp_pd(code):
    ret = pd.read_table(get_bp_fn(code), sep=" ", header=None )
    ret.columns = ["clean_pdb_idx", "clean_pdb_aa", "dot"]
    return ret

def get_merge_pd(code):
    return pd.read_csv(get_merge_fn(code), sep="\t")

# ** rosetta remodel codes **
# "E", "L", "H", "I" or "D", Remodel will build residues with secondary
# structure of extended strand, loop, helix, inserted, or random, respectively.
# https://www.rosettacommons.org/docs/latest/application_documentation/design/rosettaremodel#algorithm_basic-remodelling-tasks_fixed-backbone-design

# ** mmtf secondary structure code **
# Code  Name
#   0   pi helix
#   1   bend
#   2   alpha helix
#   3   extended
#   4   3-10 helix
#   5   bridge
#   6   turn
#   7   coil
#   -1  undefined
# https://github.com/rcsb/mmtf/blob/master/spec.md#secstructlist
sec_struct_to_remodel_code = {}
sec_struct_to_remodel_code[0] = "H"
sec_struct_to_remodel_code[2] = "H"
sec_struct_to_remodel_code[4] = "H"

if __name__ == "__main__":
    import sys
    import argparse
    import logging
    parser = argparse.ArgumentParser()
    parser.add_argument("code", help="pdb code")
    parser.add_argument("-d", "--data_dir",
                    help="location of data directory",
                    default="") # default is data_dir global variable
    parser.add_argument("-o", "--output_remodel", required=True)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.data_dir:
        data_dir = args.data_dir

    code = args.code
    logging.info("code : %s", code)

    bp = get_bp_pd(code)  # blueprint file from Rosetta
    merge_df = get_merge_pd(code) # merge tsv file with structural info

    # remove the -1 places (where we have to fill in and)
    # check that everything else matched up with the blueprint file
    merge_df_valid = merge_df[merge_df.clean_pdb_idx != -1]
    assert((merge_df_valid.clean_pdb_idx.values == 
                                            bp.clean_pdb_idx.values).all())

    conflict_idxs = np.where(merge_df_valid.construct.values 
                                        != bp.clean_pdb_aa.values)[0]
    if len(conflict_idxs):
        logging.info("code : %s, found %d conflict indices", 
                                            code, len(conflict_idxs))

    # see how many positions we need to remodel
    num_pos_to_remodel = (merge_df.clean_pdb_idx == -1).sum()
    if num_pos_to_remodel == 0:
        logging.info("code : %s, nothing to remodel", code)
        sys.exit(0)

    rle_res_to_remodel = []

    # run length encode the sections that need to be filled in 
    # and the sections that do not need to be filled in
    for remodel_flag, remodel_flag_iter in \
                itertools.groupby(merge_df.clean_pdb_idx == -1):
        rle_res_to_remodel.append(
                (remodel_flag, sum(1 for _ in remodel_flag_iter)))
    num_chunks_to_remodel = len(rle_res_to_remodel)

    # fix everything first
    merge_df["remodel_type"] = "FIXED" # our own codes for remodel_type
    # extended strand, loop, helix, inserted, or random
    merge_df["remodel_code"] = "-" # "E", "L", "H", "I" or "D"
    merge_df["remodel_str"] = "-" # string that will go into remodel file   

    # decide what we are going to remodel and what the flanking positions are
    merge_idx = 0
    for i, (remodel_flag, remodel_length) in enumerate(rle_res_to_remodel):
        if remodel_flag is True:
            if i == 0: # N terminal expansion
                merge_df.loc[:remodel_length, "remodel_type"] = "NTE"
                merge_df.loc[:remodel_length, "remodel_code"] = "L"
                merge_df.loc[remodel_length, "remodel_type"] = "FLANK"
                merge_df.loc[remodel_length, "remodel_code"] = "L"
            elif i > 0 and (i < (num_chunks_to_remodel - 1)): # MIDDLE
                merge_idx_right = merge_idx + remodel_length
                merge_df.loc[merge_idx:merge_idx_right, 
                        "remodel_type"] = "MIDDLE" # Middle section
                rc = "L" # remodel code by default is loop
                sec_struct_left = merge_df.loc[merge_idx-1, "sec_struct"]
                sec_struct_right = merge_df.loc[merge_idx-1, "sec_struct"]
                if sec_struct_left == sec_struct_right: # both sides equal
                    if sec_struct_left != -1: # and known 
                        logging.info("code : %s, both sides equal at %d"
                                     " and known.", code, merge_idx)
                        if sec_struct_left in sec_struct_to_remodel_code:
                            rc = sec_struct_to_remodel_code[sec_struct_left]
                            logging.info("code : %s, changing remodel_code "
                                         "at %d to %s", code, merge_idx, rc)

                merge_df.loc[merge_idx - 1, "remodel_type"] = "FLANK"
                merge_df.loc[merge_idx_right, "remodel_type"] = "FLANK"

                merge_df.loc[merge_idx:merge_idx_right, "remodel_code"] = rc
                merge_df.loc[merge_idx - 1, "remodel_code"] = rc
                merge_df.loc[merge_idx_right, "remodel_code"] = rc
            else: # i == (num_chunks_to_remodel - 1) # C terminal expansion
                merge_df.loc[merge_idx:, "remodel_type"] = "CTE"
                merge_df.loc[merge_idx:, "remodel_code"] = "L"
                merge_df.loc[(merge_idx-1), "remodel_type"] = "FLANK"
                merge_df.loc[(merge_idx-1), "remodel_code"] = "L"
            
        merge_idx += remodel_length


    # Convert all our own remodel_type codes to remodel_str 
    # NTE: N Terminal expansion. For some reason they want this index to start
    #    : with 1 instead of zero.
    #    : 1 X L PIKAA G
    select_idx = (merge_df.remodel_type == "NTE")
    merge_df.loc[select_idx, "remodel_str"] = "1 X " + \
                merge_df.loc[select_idx, "remodel_code"].astype(str) + \
                " PIKAA " + merge_df.loc[select_idx, "construct"].astype(str)

    # FLANK: flanking section
    #      : 123 V L PIKAA V
    select_idx = (merge_df.remodel_type == "FLANK")
    merge_df.loc[select_idx, "remodel_str"] = \
                merge_df.loc[select_idx, "clean_pdb_idx"].astype(str) + " " + \
                merge_df.loc[select_idx, "clean_pdb_aa"] + " " + \
                merge_df.loc[select_idx, "remodel_code"].astype(str) + \
                " PIKAA " + merge_df.loc[select_idx, "construct"].astype(str)

    # MIDDLE: gap in the middle
    #       : 0 X L PIKAA G
    select_idx = (merge_df.remodel_type == "MIDDLE")
    merge_df.loc[select_idx, "remodel_str"] = "0 X " + \
                merge_df.loc[select_idx, "remodel_code"].astype(str) + \
                " PIKAA " + merge_df.loc[select_idx, "construct"] 

    # CTE: C-term expansion
    #    : 0 X L PIKAA G
    select_idx = (merge_df.remodel_type == "CTE")
    merge_df.loc[select_idx, "remodel_str"] = "0 X " + \
                merge_df.loc[select_idx, "remodel_code"].astype(str) + \
                " PIKAA " + merge_df.loc[select_idx, "construct"]

    # Fixed: Section to stay unchanged
    #      : 118 W .
    select_idx = (merge_df.remodel_type == "FIXED")
    merge_df.loc[select_idx, "remodel_str"] =  \
                merge_df.loc[select_idx, "clean_pdb_idx"].astype(str) + \
                " " + merge_df.loc[select_idx, "construct"] + " ."

    # where construct doesn't match up with clean_pdb
    # should be very few conflicts. Only 2 found so far and both
    # are in merge_structure_files.hand_edits
    for conflict_idx in conflict_idxs: 
        # Note: we only have to edit this residue if it is FIXED
        #       if it is FLANK then it is already changed above
        if merge_df.loc[conflict_idx, "remodel_type"] == "FIXED":
            merge_df.loc[conflict_idx, "remodel_str"] =  \
                merge_df.loc[conflict_idx, "clean_pdb_idx"].astype(str) + \
                " " + merge_df.loc[conflict_idx, "clean_pdb_aa"] + \
                " . PIKAA " + merge_df.loc[conflict_idx, "construct"]


    # write out all the remodel strings to the remodel file
    remodel_blueprint = "\n".join(merge_df.remodel_str.values)
    with open(args.output_remodel, "w") as fh:
        # must not have a new line at the end of the blueprint file
        # otherwise rosetta crashes
        print(remodel_blueprint, file=fh, end="")

