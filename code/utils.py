from Bio import SeqIO

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
    seq_records = list(SeqIO.parse(pdb_fn, "pdb-atom"))

    # found more than one chain
    if len(seq_records) > 1:
        raise ValueError("pdb contains more than one chain: {}".format(pdb_fn))

    return str(seq_records[0].seq)