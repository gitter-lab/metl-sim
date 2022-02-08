import warnings

import Bio
import Bio.SeqIO
import Bio.PDB

from merge_structure_files import get_seqres_pdb_raw, data_dir, chain

def get_pdb_remodeled_fn(code):
    return f"{data_dir}/pdbs_remodel/{code}_{chain}_0001.pdb"

def get_struct_pdb_remodeled(code):
    pdb_parser = Bio.PDB.PDBParser()
    with warnings.catch_warnings():
        warnings.filterwarnings(action='ignore',  
                  message="Ignoring unrecognized record 'TER'")
        return pdb_parser.get_structure(
                file=get_pdb_remodeled_fn(code), id=code)[0][chain]

def get_seq_pdb_remodeled(code):
    with warnings.catch_warnings():
        warnings.filterwarnings(action='ignore',  
                  message=".*")
        return Bio.SeqIO.read(get_pdb_remodeled_fn(code), "pdb-atom")



if __name__ == "__main__":
    import argparse
    import logging
    parser = argparse.ArgumentParser()
    parser.add_argument("code",
                    help="pdb code")
    parser.add_argument("-d", "--data_dir",
                    help="location of data directory",
                    default="") # default is data_dir global variable
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.data_dir:
        data_dir = args.data_dir

    code = args.code

    seqres = get_seqres_pdb_raw(code)
    construct_seq = str(seqres.seq)
    logging.info("code : %s, construct_seq : %s", code, construct_seq)

    seqatom = get_seq_pdb_remodeled(code)
    print(f"{code}, {seqres.seq == seqatom.seq}")


