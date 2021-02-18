""" handle stragglers on condor """

import os
import os.path
from os.path import join
import shutil

def parse_stragglers_job_ids(stragglers_fn):
    job_ids = []
    with open(stragglers_fn, "r") as f:
        for line in f:
            job_id = line.split()[0].split(".")[1]
            job_ids.append(job_id)
    return job_ids


def parse_stragglers_bgl3_bzip(stragglers_fn):
    job_ids = []
    with open(stragglers_fn, "r") as f:
        for line in f:
            job_id = line.split("_")[1]
            job_ids.append(job_id)
    return job_ids


def final_bl3_stragglers():
    variant_ids = [25856, 25857, 25858, 25859, 25860, 21766, 21767, 21768, 21769, 21770, 21771, 21772,
     21773, 21774, 25882, 25883, 25884, 25885, 25886, 25887, 19491, 19492, 19493, 19494,
     19495, 19496, 19497, 26537, 26538, 26539, 26540, 26541, 26542, 26543, 26544, 25404,
     25405, 25406, 25407, 25408, 25409, 25410, 25667, 25668, 25669, 25670, 25671, 25854, 25855]

    # find the args files these variant ids are in so we can copy the variant id and the variant itself
    original_args_dir = "rosetta/rosetta_energy/args_bgl3"
    original_args_dict = {}
    for args_fn in os.listdir(original_args_dir):
        with open(join(original_args_dir, args_fn), "r") as f:
            data = f.readlines()
            for line in data:
                original_args_dict[int(line.split()[0])] = line.split()[1].strip()

    args_new_dir = "rosetta/rosetta_energy/args_bgl3_stragglers2"
    for i, variant_id in enumerate(variant_ids):
        with open(join(args_new_dir, "{}.txt".format(i)), "w") as f:
            f.writelines(["{} {}".format(variant_id, original_args_dict[variant_id])])


def main():

    final_bl3_stragglers()

    # stragglers_fn = "rosetta/rosetta_energy/stragglers_avgfp/stragglers.txt"
    # condor_logs_dir = "rosetta/rosetta_energy/stragglers_avgfp/condor_logs"
    # out_dir = "rosetta/rosetta_energy/stragglers_avgfp/stragglers_logs"
    # job_ids = parse_stragglers_job_ids(stragglers_fn)

    # stragglers_fn = "rosetta/rosetta_energy/bgl3_stragglers.txt"
    # args_old_dir = "rosetta/rosetta_energy/args_bgl3"
    # args_new_dir = "rosetta/rosetta_energy/args_bgl3_stragglers"
    #
    # job_ids = parse_stragglers_bgl3_bzip(stragglers_fn)
    # print(job_ids)
    #
    # # copy the args files from the failed jobs to the new args dir, also rename them
    # # to be sequential so they can be run in a single condor batch easily
    # for i, job_id in enumerate(job_ids):
    #     print("Copying {}.txt, new name: {}.txt".format(job_id, i))
    #     shutil.copyfile(os.path.join(args_old_dir, "{}.txt".format(job_id)),
    #                     os.path.join(args_new_dir, "{}.txt".format(i)))





if __name__ == "__main__":
    main()
