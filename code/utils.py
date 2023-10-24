from io import StringIO
from typing import Optional

from Bio import SeqIO, PDB
from Bio.PDB.PDBParser import PDBParser


def save_argparse_args(args_dict, out_fn):
    """ save argparse arguments out to a file """
    with open(out_fn, "w") as f:
        for k, v in args_dict.items():
            # if a flag is set to false, dont include it in the argument file
            if (not isinstance(v, bool)) or (isinstance(v, bool) and v):
                f.write("--{}\n".format(k))
                # if a flag is true, no need to specify the "true" value
                if not isinstance(v, bool):
                    # list args should be saved one per line
                    if isinstance(v, list):
                        for item in v:
                            f.write("{}\n".format(item))
                    else:
                        f.write("{}\n".format(v))


def sort_variant_mutations(variants):
    """ put variant mutations in sorted order by position """
    # this function is also duplicated in RosettaTL utils
    converted_to_list = False
    if not isinstance(variants, list) and not isinstance(variants, tuple):
        variants = [variants]
        converted_to_list = True

    sorted_variants = []
    for variant in variants:
        muts = variant.split(",")
        positions = [int(mut[1:-1]) for mut in muts]
        # now sort muts by positions index, then join on "," to recreate variant
        sorted_muts = [x for x, _ in sorted(zip(muts, positions), key=lambda pair: pair[1])]
        sorted_variants.append(",".join(sorted_muts))

    if converted_to_list:
        sorted_variants = sorted_variants[0]

    return sorted_variants


def get_seq_from_pdb(pdb_fn):
    """ uses atom iterator method """

    # load the text of the PDB
    with open(pdb_fn, "r") as f:
        pdb_lines = f.readlines()

    # remove everything after the /last/ "TER" line (supports w/ multiple chains)
    # find the index of the last "TER" line
    ter_index = None
    for i, line in reversed(list(enumerate(pdb_lines))):
        if line.startswith("TER"):
            ter_index = i
            break

    # if no "TER" line is found, this will raise an error as it would be an invalid PDB
    if ter_index is None:
        raise ValueError("Invalid PDB file: No 'TER' line found.")

    # keep only the lines up to and including the last "TER" line
    filtered_pdb_lines = pdb_lines[:ter_index + 1]

    filtered_pdb_text = "".join(filtered_pdb_lines)

    # load the seq records from pdb_text
    # seq_records = list(SeqIO.parse(pdb_fn, "pdb-atom"))
    seq_records = list(SeqIO.parse(StringIO(filtered_pdb_text), "pdb-atom"))

    # found more than one chain
    if len(seq_records) > 1:
        raise ValueError("pdb contains more than one chain: {}".format(pdb_fn))

    return str(seq_records[0].seq)


def clean_pdb_data(pdb_fn):
    """ only keep ATOM and HETATM lines """
    with open(pdb_fn, 'r') as fin:
        lines = [line for line in fin if line.startswith(('ATOM', 'HETATM'))]
    return ''.join(lines)


def extract_seq_from_pdb(pdb_fn: str,
                         chain_id: Optional[str] = None,
                         error_on_missing_residue: bool = True,
                         error_on_multiple_chains: bool = True):

    """
    Extract the sequence from a PDB file
    :param pdb_fn: path to PDB file
    :param chain_id: If None, return sequences for every chain in PDB. Otherwise, extract sequence only for given chain
    :param error_on_missing_residue: if True, raise an error if a residue is missing, based on sequential numbering
    :param error_on_multiple_chains: if True and chain_id is None, raise error if the PDB contains more than one chain
    :return: the seq as a str (if returning 1 chain) or a dict mapping chain id to seq (if returning more than 1 chain)
    """

    # only keep ATOM and HETATM lines
    pdb_data = clean_pdb_data(pdb_fn)
    pdb_handle = StringIO(pdb_data)

    # create a structure object for this PDB
    pdb_parser = PDBParser()
    structure = pdb_parser.get_structure("structure", pdb_handle)

    # this function only handles PDBs with 1 model
    if len(list(structure.get_models())) > 1:
        raise ValueError("PDB contains more than one model")

    # retrieve the chains in this PDB
    chains = list(structure.get_chains())
    valid_chain_ids = [chain.id for chain in chains]
    if chain_id is not None:
        if chain_id not in valid_chain_ids:
            raise ValueError(
                "Invalid chain_id '{}' for PDB file which contains chains {}".format(chain_id, valid_chain_ids))
        else:
            chains = [chain for chain in chains if chain.id == chain_id]

    if len(chains) > 1 and error_on_multiple_chains:
        raise ValueError("PDB contains more than one chain: {}".format(pdb_fn))

    sequences = []
    for chain in chains:
        # find missing residues (looking for non-sequential residue numberings)
        residue_numbers = [res.id[1] for res in chain if PDB.is_aa(res)]
        missing_residues = []
        if len(residue_numbers) > 1:
            for i in range(1, len(residue_numbers)):
                if residue_numbers[i] - residue_numbers[i - 1] != 1:
                    missing_residues.extend(range(residue_numbers[i - 1] + 1, residue_numbers[i]))

        # error out on a missing residue if requested
        if len(missing_residues) > 0 and error_on_missing_residue:
            raise ValueError("Missing residues {} in chain {}".format(missing_residues, chain.id))

        # build up the sequence
        seq = []
        last_residue_number = None
        for res in [r for r in chain if PDB.is_aa(r)]:
            # fill in missing residues with 'X'
            if last_residue_number is not None:
                while res.id[1] > last_residue_number + 1:
                    seq.append("X")
                    last_residue_number += 1

            seq.append(PDB.Polypeptide.three_to_one(res.get_resname()))
            last_residue_number = res.id[1]

        sequences.append("".join(seq))

    if len(chains) > 1:
        # for multiple chains, return a dictionary mapping chain id to the sequence
        return {ch.id: seq for ch, seq in zip(chains, sequences)}
    else:
        return sequences[0]
