""" generate job argument files for rosetta energy
- Each job will have an args_gb1 file (0.txt … n.txt) that gets transferred to condor
- The args file contains a list of variants (each with a global variant identifier) that should be processed in this job"""

import os
import numpy as np
import utils


def main():

    # load dataset (need variants to generate args files)
    # ds_fn = "data/gb1/sc_e2_wt/gb1_e2_wt.tsv"
    # ds_fn = "data/ube4b/sc_nscor_log2/ube4b_nscor_log2.tsv"
    # ds_fn = "data/bgl3/sc_e2_ph_nr_ar/bgl3_e2_ph_nr_ar.tsv"
    # ds_fn = "data/avgfp/sc_med_brightness/avgfp_med_brightness.tsv"
    # ds_fn = "data/pab1/sc_log2/pab1_log2.tsv"
    # ds_fn = "data/bgl3/bgl3_filtered_5/bgl3_filtered_5.tsv"
    ds_fn = "data/gb1/gb1_filtered_5/gb1_filtered_5.tsv"

    # output directory
    out_dir = "rosetta/rosetta_energy/args_gb1"
    utils.ensure_dir_exists(out_dir)

    # load variants
    ds, _, _ = utils.load_dataset_new(ds_fn)
    variants = ds["variant"].values

    # # save a random-10 file which contains 10 completely random variants (for testing purposes)
    # seed = 10
    # num_variants = 10
    # np.random.seed(seed)
    # inds = np.random.choice(np.arange(len(variants)), size=num_variants, replace=False)
    # with open(os.path.join(out_dir, "random-10.txt"), "w") as f:
    #     for idx in inds:
    #         f.write("{} {}\n".format(idx, variants[idx]))

    # split into num_jobs args files
    num_jobs = 4000

    split_variants = np.array_split(variants, num_jobs)
    split_indices = np.array_split(np.arange(len(variants)), num_jobs)

    for i, (svariants, sindices) in enumerate(zip(split_variants, split_indices)):
        with open(os.path.join(out_dir, "{}.txt".format(i)), "w") as f:
            for svariant, sindex in zip(svariants, sindices):
                f.write("{} {}\n".format(sindex, svariant))


if __name__ == "__main__":
    main()
