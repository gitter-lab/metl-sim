""" generate variants from pdb files """
import itertools
import math
import time
import os
from os.path import join, basename

from Bio.SeqIO.PdbIO import AtomIterator
from Bio.PDB import PDBParser
import numpy as np


def gen_all_variants(base_seq, num_subs, chars, seq_idxs):
    """ generates all possible variants of base_seq with the given number of substitutions
        using the given available chars and valid sequence idxs for substitution"""

    # positions is a tuple of (pos(1), pos(2), ... pos(num_subs))
    for positions in itertools.combinations(seq_idxs, num_subs):
        # new_aas is a tuple of (aa(1), aa(2), ... aa(num_subs))
        for new_aas in itertools.product(chars, repeat=num_subs):
            if np.all([base_seq[pos] != new_aa for pos, new_aa in zip(positions, new_aas)]):
                # note the pos+1 for 1-based indexing
                yield ",".join(["{}{}{}".format(base_seq[pos], pos+1, new_aa) for pos, new_aa in zip(positions, new_aas)])


def gen_sample(base_seq, num_mutants, num_subs, chars, seq_idxs, rng):
    """ generates a random sample of variants with the given number of substitutions """

    # using a set and a list to maintain the order
    # this is slower and uses 2x the memory, but the final variant list will be orderd
    mutants = set()
    mutant_list = []

    for mut_num in range(num_mutants):

        found_valid_mutant = False
        while not found_valid_mutant:

            # choose the positions to mutate and sort them in ascending order
            positions = rng.choice(seq_idxs, num_subs, replace=False)
            positions.sort()

            # choose new amino acids for each of the selected positions
            subs = []
            for pos in positions:
                base_aa = base_seq[pos]
                new_aa = rng.choice([c for c in chars if c != base_aa])
                # note the pos+1 for 1-based indexing
                sub = "{}{}{}".format(base_aa, pos+1, new_aa)
                subs.append(sub)

            # generate the mutant string
            mutant = ",".join(subs)

            if mutant not in mutants:
                found_valid_mutant = True
                mutants.add(mutant)
                mutant_list.append(mutant)

    # sort by avg position across all mutations
    return mutant_list


def max_possible_variants(seq_len, num_subs, num_chars):
    return math.comb(seq_len, num_subs) * ((num_chars - 1) ** num_subs)


def distribute_into_buckets(n, num_buckets, bucket_sizes):
    """ distributes n items evenly into num_buckets with sizes bucket_sizes
        i'm sure there's a better way to do this, but this works and was quick to figure out """

    # first check if the buckets have enough capacity to store all n items
    if n > sum(bucket_sizes):
        raise ValueError("buckets do not have enough capacity to store all n items")

    # all buckets start with zero items
    buckets = [0] * num_buckets

    # keep track of which buckets have free space
    free_bucket_idxs = list(range(num_buckets))

    while True:
        # remaining items left to distribute
        remaining = n - sum(buckets)

        # if we evenly split remaining number of items, how much goes into each bucket?
        amount_per_bucket = remaining // len(free_bucket_idxs)
        if amount_per_bucket == 0:
            # no more to distribute (either distributed all of them, or an odd number left)
            break

        # can the free buckets accommodate extra items?
        has_capacity = [(buckets[bi] + amount_per_bucket) <= bucket_sizes[bi] for bi in free_bucket_idxs]
        if all(has_capacity):
            # there is capacity, so distribute those items
            for bi in free_bucket_idxs:
                buckets[bi] += amount_per_bucket
        else:
            # one of the buckets doesn't have the capacity
            fbi = has_capacity.index(False)  # index into free_bucket_idxs (not buckets)
            bi = free_bucket_idxs[fbi]  # index into buckets
            buckets[bi] = bucket_sizes[bi]
            free_bucket_idxs.remove(bi)

    # distribute any stragglers
    num_stragglers = n - sum(buckets)
    free_bucket_idxs = [i for i in range(num_buckets) if buckets[i] < bucket_sizes[i]]
    # at most there will be 1 extra item to place in each free bucket so no need to loop this
    for bi in free_bucket_idxs:
        if num_stragglers > 0:
            buckets[bi] += 1
            num_stragglers -= 1

    # final sanity check
    over_capacity = [buckets[bi] > bucket_sizes[bi] for bi in range(num_buckets)]
    if any(over_capacity):
        raise AssertionError("There are buckets over capacity but that should be impossible. This function"
                             " needs to be fixed")

    return buckets


def single_pdb_local_variants(pdb_fn, target_num, num_subs_list, chars, rng):
    """ generate local variants for a single PDB file.
        given the target number of variants, and the max number of substitutions,
        this function tries to generate an equal number of variants for each possible number of substitutions """

    # for multiple pdb files, there are multiple ways to determine the number of variants per pdb file
    # we can specify a fixed value for number of variants per PDB or we can specify a target total number of
    # variants and divide the total equally among the PDB files
    # records = list(SeqIO.parse(pdb_fn, "pdb-atom"))
    # do it the hacky way that avoids parsing the PDB file header which may not be present
    structure = PDBParser().get_structure(None, pdb_fn)
    records = [record for record in AtomIterator(None, structure)]

    # all our FASTAs should have single records only
    if len(records) > 1:
        print("err: pdb file has more than one record: {}".format(pdb_fn))
        return

    # the base sequence
    seq = records[0].seq

    # print out some info
    print("parsing {}".format(pdb_fn))
    print("aa sequence: {}".format(seq))
    print("aa seq len: {}".format(len(seq)))

    # does the base sequence start with methionine?
    if seq[0] == "M":
        # valid mutation range excludes the starting methionine
        seq_idxs = np.arange(1, len(seq))
    else:
        seq_idxs = np.arange(len(seq))

    # want to distribute number of target seqs evenly across range(max_subs)
    # single mutants probably not have enough possible variants
    max_variants = [max_possible_variants(len(seq_idxs), num_subs, len(chars)) for num_subs in num_subs_list]
    # print("max variants: {}".format(max_variants))

    # distribute the target_num variants to the range of substitutions
    variants_per_num_subs = distribute_into_buckets(target_num, len(num_subs_list), max_variants)

    # now generate the actual variants
    variants = []
    for num_subs, num_v, max_v in zip(num_subs_list, variants_per_num_subs, max_variants):
        # print("getting sample: {} subs, {} variants".format(num_subs, num_v))
        if num_v == max_v:
            print("num_subs: {} num_v: {} max_v: {} approach: gen all".format(num_subs, num_v, max_v))
            variants += list(gen_all_variants(seq, num_subs, chars, seq_idxs))
        elif num_v / max_v > 0.4:
            print("num_subs: {} num_v: {} max_v: {} approach: gen all, then sample".format(num_subs, num_v, max_v))
            # gen_sample could be slow if we are generating a sample approaching the max number of variants
            # in that case it would be much faster to just generate all and select a sample from the pre-generated ones
            all_variants = list(gen_all_variants(seq, num_subs, chars, seq_idxs))
            # variants += random.sample(all_variants, num_v)
            variants += rng.choice(all_variants, num_v, replace=False).tolist()
        else:
            print("num_subs: {} num_v: {} max_v: {} approach: sample".format(num_subs, num_v, max_v))
            variants += gen_sample(seq, num_v, num_subs, chars, seq_idxs, rng)

    return variants


def human_format(num):
    """https://stackoverflow.com/questions/579310/formatting-long-numbers-as-strings-in-python"""
    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])


def main():

    # todo: convert this to an argparse script so it can be called from the command line easily
    # todo: figure out what is going on with that distribute_into_buckets function
    # todo: generally figure out if this is coded optimally

    # the possible amino acid characters
    # not using stop codon
    chars = ["A", "C", "D", "E", "F", "G", "H", "I", "K", "L", "M", "N", "P", "Q", "R", "S", "T", "V", "W", "Y"]

    target_num = 13000
    num_subs_list = [1,3,4,5,6]
    # pdb_fn = "pdb_files/prepared_pdb_files/1gfl_cm.pdb"
    pdb_fn = "pdb_files/prepared_pdb_files/2qmt_p.pdb"
    seed = 15

    # create a random number generator for this call
    rng = np.random.default_rng(seed=seed)

    variants = single_pdb_local_variants(pdb_fn, target_num, num_subs_list, chars, rng)

    # multiply number of variants for variance testing
    num_replicates = 50
    variants *= num_replicates

    out_dir = "variant_lists"

    if num_replicates == 1:
        out_fn = "{}_{}_NV-{}_NS-{}_RS-{}.txt".format(basename(pdb_fn)[:-4], time.strftime("%Y-%m-%d_%H-%M-%S"),
                                                      human_format(target_num), ",".join(map(str, num_subs_list)), seed)
    else:
        out_fn = "{}_{}_NV-{}_NR-{}_NS-{}_RS-{}.txt".format(basename(pdb_fn)[:-4], time.strftime("%Y-%m-%d_%H-%M-%S"),
                                                      human_format(target_num), num_replicates,
                                                            ",".join(map(str, num_subs_list)), seed)

    with open(join(out_dir, out_fn), "w") as f:
        for v in variants:
            f.write("{} {}\n".format(basename(pdb_fn), v))


if __name__ == "__main__":
    main()
