"""Merge the three structure files `pdb_raw`, `pdb_clean` and `pdb_mmtf`. 
We need to merge them to figure out the following
1. What residues are missing and need to be remodeled by rosetta (loop modeling)
2. What the secondary structure is so that we can make informed guesses about
   the missing residues

The output of the merged files is a tsv file that aligns all the three structure
files. This tsv file is in a format where it will be easy to create a remodel
blueprint file.  
"""
import warnings

import numpy as np
import pandas as pd

import Bio
import Bio.Seq
import Bio.SeqIO
import Bio.PDB
import Bio.Data.SCOPData

import mmtf # usually automatically pre-installed along with Biopython
import Bio.PDB.mmtf

data_dir = "../data"
chain = 'A'


# force clean_pdb index to merge to this value 
# key = (code, clean_pdb_idx), value = (pdb_idx)
hand_edits = {}
hand_edits[('1i1n', 225)] = 226 # missing coordinates in mmft file
hand_edits[('1xff', 239)] = 239 # missing coordinates in mmtf file

# force editing of seqres that is extract from raw pdb file
hand_edits_seqres = {}
hand_edits_seqres['1jbe'] = [(75, 'X', 'N')] # residue 'X' in pdb and mmtf file

def get_raw_fn(code):
    return f"{data_dir}/pdbs_raw/{code}.pdb"

def get_seqres_pdb_raw(code, do_hand_edits=True):
    seqres = None
    for record in Bio.SeqIO.parse(get_raw_fn(code), "pdb-seqres"):
        if record.annotations["chain"] == "A":
            seqres = record
            break
    if do_hand_edits and (code in hand_edits_seqres): # make hand edits
        edits_list = hand_edits_seqres[code]
        ms = Bio.Seq.MutableSeq(seqres.seq)
        for pdb_idx, orig_res, new_res in edits_list:
            assert(ms[pdb_idx - 1] == orig_res)
            ms[pdb_idx - 1] = new_res
        seqres.seq = Bio.Seq.Seq(ms)
    return seqres

def get_struct_pdb_raw(code):
    pdb_parser = Bio.PDB.PDBParser()
    return pdb_parser.get_structure(
            file=get_raw_fn(code), id=code)[0][chain]

def get_clean_fn(code):
    return f"{data_dir}/pdbs_clean/{code}_{chain}.pdb"

def get_struct_pdb_clean(code):
    pdb_parser = Bio.PDB.PDBParser()
    with warnings.catch_warnings():
        warnings.filterwarnings(action='ignore',  
                  message="Ignoring unrecognized record 'TER'")
        return pdb_parser.get_structure(
                file=get_clean_fn(code), id=code)[0][chain]

def get_bp_fn(code):
    return f"{data_dir}/pdbs_bp/{code}_{chain}.bp"

def get_mmtf_fn(code):
    return f"{data_dir}/pdbs_mmtf/{code}.mmtf.gz"

def get_struct_pdb_mmtf(code):
    with warnings.catch_warnings():
        warnings.filterwarnings(action='ignore',  
                  message=".*is discontinuous at line.*")
        return Bio.PDB.mmtf.get_from_decoded(get_struct_mmtf(code))

def get_struct_mmtf(code):
    return mmtf.parse_gzip(get_mmtf_fn(code))

if __name__ == '__main__':
    import argparse
    import logging
    parser = argparse.ArgumentParser()
    parser.add_argument("code",
                    help="pdb code")
    parser.add_argument("-d", "--data_dir",
                    help="location of data directory",
                    default="") # default is data_dir global variable
    parser.add_argument("-o", "--output_tsv", required=True)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.data_dir:
        data_dir = args.data_dir

    code = args.code

    logging.info("code : %s", code)

    seqres = get_seqres_pdb_raw(code)
    construct_seq = str(seqres.seq)
    logging.info("code : %s, construct_seq : %s", code, construct_seq)

    # read mmtf and check that it matches up with raw_pdb
    m = get_struct_mmtf(code)

    m0 = m.entity_list[0]
    assert(m0['type'] == 'polymer') # check that chain 0 is a polymer
    assert(m0['chainIndexList'][0] == 0) # we are looking at chain 0
    assert(m.chain_id_list[0] == 'A') # also called chain A
    if code not in hand_edits_seqres:
        assert(m0['sequence'] == construct_seq) # seq matches up with raw_pdb

    num_res_resolved = m.groups_per_chain[0]

    # number of atoms in each group (residue/molecule etc)
    group_num_atoms = np.array([len(x['atomNameList']) for x in m.group_list])

    group_num_atoms_list = group_num_atoms[m.group_type_list] 
    # should be total number of atoms
    assert(group_num_atoms_list.sum() == len(m.x_coord_list)) 

    # where each group's/residues's atomic coordinates start
    coord_offset = np.roll(group_num_atoms_list, 1) # shift by one
    coord_offset[0] = 0 # set to 0 as this is offset for the first atom now
    coord_offset = coord_offset.cumsum() # offset for every group/residue


    ca_offset = [] # offset of the CA atom
    for x in m.group_list:
        ca_idx = -1
        try:
            ca_idx = x['atomNameList'].index('CA')
        except ValueError: # append -1 instead
            pass
        ca_offset.append(ca_idx)
    # this array should usually be all 1's as whenever there is 
    # CA atom as it is the second atom in the residue list
    ca_offset = np.array(ca_offset) 

    # first find out where the residue's atomic coordinates start
    # then add the number of atom's to skip till we get to the CA atom
    ca_idx = coord_offset[:num_res_resolved] + \
                ca_offset[m.group_type_list[:num_res_resolved]]

    # find the x,y,z coordinates for the CA atom
    ca_xcor = m.x_coord_list[ca_idx]
    ca_ycor = m.y_coord_list[ca_idx]
    ca_zcor = m.z_coord_list[ca_idx]

    # index into the sequence of all residues that are resolved
    idx_resolved = m.sequence_index_list[:num_res_resolved]

    # secondary structure codes for all resolved residues
    sec_struct_resolved = m.sec_struct_list[:num_res_resolved]

    # construct dataframe

    # add the construct sequence and a counter for the pdb indexing (1-based)
    cons_df = pd.DataFrame(list(construct_seq))
    cons_df.columns = ["construct"]
    cons_df["pdb_idx"] = range(1, len(construct_seq) + 1)

    # mark resolved residues
    cons_df["resolved"] = False
    # idx_resolved is zero based indexing so we can use the dataframe index
    cons_df.loc[idx_resolved, "resolved"] = True

    # add the secondard structure
    cons_df["sec_struct"] = -1
    cons_df.loc[idx_resolved, "sec_struct"] = sec_struct_resolved

    # add CA columns
    cons_df["ca_x"] = np.NaN
    cons_df["ca_y"] = np.NaN
    cons_df["ca_z"] = np.NaN

    cons_df.loc[idx_resolved, "ca_x"] = ca_xcor
    cons_df.loc[idx_resolved, "ca_y"] = ca_ycor
    cons_df.loc[idx_resolved, "ca_z"] = ca_zcor

    # now prepare for merging in cleaned_pdb file
    # the blueprints are based on the cleaned_pdb file
    ca_coords_np = cons_df[["ca_x", "ca_y", "ca_z"]].to_numpy()
    cons_df["clean_pdb_idx"] = -1 # default values for missing
    cons_df["clean_pdb_dist"] = -1.0 # default values for missing
    cons_df["clean_pdb_aa"] = "" # default values for missing

    y = get_struct_pdb_clean(code)
    # loop over the cleaned_pdb residues and merge them to 
    # the construct residues by matching the CA atom coordinates
    for i, res in enumerate(y.get_residues()):
        dist = ((ca_coords_np - res['CA'].get_coord()) ** 2).sum(axis=1)
        # match on minimum distance
        min_dist_idx = np.nanargmin(dist)
        min_dist = dist[min_dist_idx]
        clean_pdb_idx = i + 1 # pdb indexing always starts from 1
        
        # see if we should make the matched by hand
        if (code, clean_pdb_idx) in hand_edits:
            construct_pdb_idx = hand_edits[(code, clean_pdb_idx)]
            min_dist_idx = construct_pdb_idx - 1
            min_dist = 0
        
        res_code = Bio.Data.SCOPData.protein_letters_3to1[res.resname]
        if (cons_df.loc[min_dist_idx, "construct"] != res_code):
            logging.info("code : %s, construct conflict at clean_pdb_idx %d, ", 
                    code, clean_pdb_idx)

        cons_df.loc[min_dist_idx, "clean_pdb_idx"] = clean_pdb_idx
        cons_df.loc[min_dist_idx, "clean_pdb_dist"] = min_dist
        cons_df.loc[min_dist_idx, "clean_pdb_aa"] = res_code

    # check that all distances that matched are small
    assert((cons_df.clean_pdb_dist < 1e-3).all())

    # check that all matched indices are consecutive
    all_matched_indices = cons_df.clean_pdb_idx[cons_df.clean_pdb_idx >= 1]

    assert((all_matched_indices.diff()[1:] > 0).all())

    cons_df_save = cons_df.drop(columns=['ca_x', 'ca_y', 'ca_z', 
                                                'clean_pdb_dist'])

    cons_df_save.to_csv(args.output_tsv, index=False, sep="\t")
    logging.info("code : %s, merged files saved to %s", code, args.output_tsv)
