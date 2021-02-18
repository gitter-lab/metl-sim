""" Adds chain ID to PDB files that don't have a named chain...
    the reason we do this is just because rosetta expects a chain ID in some places and it's easier to add it
    than have to workaround it in rosetta

    the only file that doesn't have a chain ID is the bgl3 pdb file. """


def main():

    pdb_fn = "rosetta/rosetta_energy/pdb_files/bgl3_clean_0008.pdb"
    output_fn = "rosetta/rosetta_energy/pdb_files/bgl3_clean_0008_with_chain_id.pdb"

    # load the data
    with open(pdb_fn, "r") as f:
        lines = f.readlines()

    updated_lines = []
    for line in lines:
        # only add chain IDs to lines that are ATOM records
        if line.startswith("ATOM"):
            # for bgl3, add it
            updated_line = line[0:21] + "A" + line[22:]
        else:
            updated_line = line

        updated_lines.append(updated_line)

    with open(output_fn, "w") as f:
        f.writelines(updated_lines)


if __name__ == "__main__":
    main()
