import os
import numpy as np


def verify_ids(fns):
    """ Verifies that there is a complete sample of IDs and returns the IDs in original order. """

    print("Verifying IDs")

    variant_ids = [int(x.split("_")[0]) for x in fns]

    # min and max id
    min_id = min(variant_ids)
    print("Min ID: {}".format(min_id))
    max_id = max(variant_ids)
    print("Max ID: {}".format(max_id))

    # complete sample
    complete_sample_match = set(range(min_id, max_id+1)) - set(variant_ids)
    if len(complete_sample_match) == 0:
        print("There is a complete sample of IDs starting with min ID and ending with max ID.")
    else:
        print("There is NOT a complete sample of IDs.")
        print("Missing the following IDs: ", complete_sample_match)

    return variant_ids


def order_variant_fns(fns, ids):
    """ Sorts the fns in order of increasing ids """

    return [fn for fn, _ in sorted(zip(fns, ids), key=lambda x: x[1])]


def stack_data(data_dir, sorted_fns):

    # variant scores
    stacked_data = []

    for fn in sorted_fns:
        # print(fn)
        stacked_data.append(np.load(os.path.join(data_dir, fn)))

    stacked_data = np.stack(stacked_data)

    return stacked_data


def verify(combined_fn):
    """ simply loads and prints out the shape of the combined fn """

    data = np.load(combined_fn)
    print(data.shape)


def combine():

    # data_dir = "/Volumes/TurtleSSD/radioactive-mutants/rosetta/bgl3/output_bgl3"
    # output_dir = "/Volumes/TurtleSSD/radioactive-mutants/rosetta_output/bgl3_rosetta_combined"

    # data_dir = "/Users/sg/Desktop/new_htcondor_results/bgl3 rosetta output/output_all"
    # output_dir = "/Users/sg/Desktop/new_htcondor_results/bgl3 rosetta output/combined"

    data_dir = "/Users/sg/Desktop/new_htcondor_results/gb1 rosetta output/output"
    output_dir = "/Users/sg/Desktop/new_htcondor_results/gb1_rosetta_output_combined"

    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    all_fns = os.listdir(data_dir)
    variant_score_fns = [x for x in all_fns if x.endswith("variant_score.npy")]
    per_residue_energy_fns = [x for x in all_fns if x.endswith("per_residue_energies.npy")]
    pairwise_energies_fns = [x for x in all_fns if x.endswith("pairwise_energies.npy")]

    # variant scores
    variant_score_ids = verify_ids(variant_score_fns)
    sorted_variant_score_fns = order_variant_fns(variant_score_fns, variant_score_ids)
    variant_scores = stack_data(data_dir, sorted_variant_score_fns)
    print(variant_scores.shape)
    np.save(os.path.join(output_dir, "variant_scores.npy"), variant_scores)

    # per residue energies
    per_residue_energy_ids = verify_ids(per_residue_energy_fns)
    sorted_per_residue_energy_fns = order_variant_fns(per_residue_energy_fns, per_residue_energy_ids)
    per_residue_energies = stack_data(data_dir, sorted_per_residue_energy_fns)
    print(per_residue_energies.shape)
    np.save(os.path.join(output_dir, "per_residue_energies.npy"), per_residue_energies)

    # pairwise energies - requires more work since there is a different number of pairwise interactions in each variant
    # verify_ids(pairwise_energies_fns)
    # for fn in pairwise_energies_fns:
    #     print(np.load(os.path.join(output_dir, fn)).shape)


def main():

    combine()
    # verify("rosetta/rosetta_energy/variant_scores.npy")
    # verify("rosetta/rosetta_energy/per_residue_energies.npy")

if __name__ == "__main__":
    main()