""" generate variants from pdb files """
import argparse
import hashlib
import itertools
import math
import sqlite3
import time
import os
from os.path import join, basename, isfile
from collections import Counter
import random
import zlib

from Bio.SeqIO.PdbIO import AtomIterator
from Bio.PDB import PDBParser
import numpy as np


# silence warnings when reading PDB files generated from Rosetta (which have comments which aren't parsed by my
# approach for getting sequences from PDB files w/ Bio.SeqIO...
import warnings

import utils

warnings.filterwarnings("ignore", message="Ignoring unrecognized record ")


def gen_all_variants(base_seq, num_subs, chars, seq_idxs):
    """ generates all possible variants of base_seq with the given number of substitutions
        using the given available chars and valid sequence idxs for substitution"""
    # positions is a tuple of (pos(1), pos(2), ... pos(num_subs))
    for positions in itertools.combinations(seq_idxs, num_subs):
        # new_aas is a tuple of (aa(1), aa(2), ... aa(num_subs))
        for new_aas in itertools.product(chars, repeat=num_subs):
            if np.all([base_seq[pos] != new_aa for pos, new_aa in zip(positions, new_aas)]):
                # note the pos+1 for 1-based indexing
                variant = ",".join(["{}{}{}".format(base_seq[pos], pos+1, new_aa) for pos, new_aa in zip(positions, new_aas)])
                # should be in sorted order already, but just in case, sort it here again
                variant = utils.sort_variant_mutations(variant)
                yield variant


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

    # this variant list should already be in sorted order (we sort the positions above)
    # but just in case, sort it again here. we need variants in sorted order to avoid accidental dupes.
    mutant_list = utils.sort_variant_mutations(mutant_list)

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


def get_seq_from_pdb(pdb_fn):
    # do it the hacky way that avoids parsing the PDB file header which may not be present
    structure = PDBParser().get_structure(None, pdb_fn)
    records = [record for record in AtomIterator(None, structure)]

    if len(records) > 1:
        # all our FASTAs should have single records only
        raise ValueError("pdb file has more than one record: {}".format(pdb_fn))

    # the base sequence
    seq = str(records[0].seq)

    return seq


def single_pdb_local_variants(seq, target_num, num_subs_list, chars, seq_idxs, rng):
    """ generate local variants for a single PDB file.
        given the target number of variants, and the max number of substitutions,
        this function tries to generate an equal number of variants for each possible number of substitutions """

    # print out some info
    print("aa sequence: {}".format(seq))
    print("aa seq len: {}".format(len(seq)))

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


def get_subvariants(variant, num_subs):
    # num_subs must be less than number of substitutions in the given variant
    if num_subs >= len(variant.split(",")):
        raise ValueError("num_subs must be less than the number of substitutions in the given variant ({})".format(
            len(variant.split(","))))

    sv = [",".join(muts) for muts in list(itertools.combinations(variant.split(","), num_subs))]
    # should be in sorted order if the given main variant is in sorted order, but sort here just in case
    sv = utils.sort_variant_mutations(sv)
    return sv


def gen_subvariants_vlist(seq, target_num, min_num_subs, max_num_subs, chars, seq_idxs, rng, db_fn=None):
    # max_num_subs determines the maximum number of substitutions for the main variants
    # min_num_subs determines the minimum number of substitutions for subvariants
    #  so for example, if min_num_subs is 2, then this function won't generate subvariants with 1 substitution
    # target_num is the number of variants to generate (approximate)

    # If db_fn is specified, this function will check to see if the generated variants exists in the DB already,
    # and if so, it won't return them from this function. note it only some of the subvariants are in the db,
    # then this will still return the ones that aren't in the DB.
    if db_fn is not None:
        # load DB into memory
        source = sqlite3.connect(db_fn)
        con = sqlite3.connect(':memory:')
        source.backup(con)
        source.close()
        cur = con.cursor()

        # con = sqlite3.connect(db_fn)
        # cur = con.cursor()

    # using a set and a list to maintain the order
    # this is slower and uses 2x the memory, but the final variant list will be ordered
    variants_set = set()
    variants_list = []

    while len(variants_list) < target_num:
        # generate a variant with max_num_subs substitutions
        main_v = gen_sample(seq, num_mutants=1, num_subs=max_num_subs, chars=chars, seq_idxs=seq_idxs, rng=rng)[0]

        # if the variant has already been generated, continue to next one
        if main_v in variants_set:
            continue

        # now generate all subvariants for this variant
        # generating subvariants for all number of substitutions down to single variants
        av = [main_v]
        for i in reversed(range(min_num_subs, max_num_subs)):
            av += get_subvariants(main_v, i)

        # now add this variant and all subvariants to the main list (as long as they are not already there)
        for v in av:
            # check if the variant is already in the set or already in the DB
            variant_in_set = v in variants_set
            if variant_in_set:
                print("Generated variant already in set: {}".format(v))

            variant_in_db = False
            if db_fn is not None:
                query = "SELECT * FROM `variant` WHERE `mutations`==\"{}\"".format(v)
                result = cur.execute(query).fetchall()
                if len(result) >= 1:
                    variant_in_db = True
                    print("Generated variant already in database: {}".format(v))

            if not variant_in_set and not variant_in_db:
                # only add variant to master list if it's not already in the set and it's not in the db
                variants_set.add(v)
                variants_list.append(v)

    # close sqlite handles
    cur.close()
    con.close()

    return variants_list


def human_format(num):
    """https://stackoverflow.com/questions/579310/formatting-long-numbers-as-strings-in-python"""
    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])


def get_seq_idxs(seq):
    """ which sequence indices to mutate """
    return np.arange(len(seq))
    # todo: figure out whether to ignore starting methionine (for now, include it)
    if seq[0] == "M":
        # valid mutation range excludes the starting methionine
        seq_idxs = np.arange(1, len(seq))
    else:
        seq_idxs = np.arange(len(seq))
    return seq_idxs


def gen_random_main(pdb_fn, seq, seq_idxs, chars, target_num, num_subs_list, num_replicates, seed, out_dir):

    out_fn = "{}_random_TN-{}_NR-{}_NS-{}_RS-{}.txt".format(basename(pdb_fn)[:-4],
                                                            human_format(target_num), num_replicates,
                                                            ",".join(map(str, num_subs_list)), seed)
    out_fn = join(out_dir, out_fn)
    if isfile(out_fn):
        raise FileExistsError("Output file already exists: {}".format(out_fn))
    print("Output file will be {}".format(out_fn))

    # create a random number generator for this call
    rng = np.random.default_rng(seed=seed)

    # generate the variants
    variants = single_pdb_local_variants(seq, target_num, num_subs_list, chars, seq_idxs, rng)
    # multiply number of variants for variance testing
    variants *= num_replicates
    print_variant_info(variants)

    with open(out_fn, "w") as f:
        for v in variants:
            f.write("{} {}\n".format(basename(pdb_fn), v))


def gen_all_main(pdb_fn, seq, seq_idxs, chars, num_subs_list, out_dir):

    out_fn = "{}_all_NS-{}.txt".format(basename(pdb_fn)[:-4], ",".join(map(str, num_subs_list)))
    out_fn = join(out_dir, out_fn)
    if isfile(out_fn):
        raise FileExistsError("Output file already exists: {}".format(out_fn))
    print("Output file will be {}".format(out_fn))

    for i in num_subs_list:
        mp = max_possible_variants(len(seq_idxs), i, len(chars))
        print("Generating {} {}-mutation variants".format(mp, i))

    variants = []
    for i in num_subs_list:
        variants += list(gen_all_variants(seq, i, chars, seq_idxs))
    print_variant_info(variants)

    with open(out_fn, "w") as f:
        for v in variants:
            f.write("{} {}\n".format(basename(pdb_fn), v))


def gen_subvariants_main(pdb_fn, seq, seq_idxs, chars, target_num, max_num_subs, min_num_subs, seed, db_fn, out_dir):

    # check if the output file already exists
    # if db_fn is specified, we need to have a hash of the database in the filename
    if db_fn is None:
        db_hash = 0
    else:
        hash_obj = hashlib.shake_128()
        with open(db_fn, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                hash_obj.update(byte_block)
        db_hash = hash_obj.hexdigest(4)

    out_fn = "{}_subvariants_TN-{}_MAXS-{}_MINS-{}_DB-{}_RS-{}.txt".format(basename(pdb_fn)[:-4],
                                                                     human_format(target_num),
                                                                     max_num_subs,
                                                                     min_num_subs,
                                                                     db_hash,
                                                                     seed)
    out_fn = join(out_dir, out_fn)
    if isfile(out_fn):
        raise FileExistsError("Output file already exists: {}".format(out_fn))
    print("Output file will be {}".format(out_fn))

    # create a random number generator for this call
    rng = np.random.default_rng(seed=seed)

    # generate the variants
    variants = gen_subvariants_vlist(seq, target_num, min_num_subs, max_num_subs, chars, seq_idxs, rng, db_fn)
    print_variant_info(variants)

    # save output to file
    with open(out_fn, "w") as f:
        for v in variants:
            f.write("{} {}\n".format(basename(pdb_fn), v))


def print_variant_info(variants):
    # print out info about the generated variants
    print("Generated {} variants".format(len(variants)))
    count = Counter([len(v.split(",")) for v in variants])
    for k, v in count.items():
        print("{}-mutants: {}".format(k, v))


def main(args):

    chars = ["A", "C", "D", "E", "F", "G", "H", "I", "K", "L", "M", "N", "P", "Q", "R", "S", "T", "V", "W", "Y"]

    seq = get_seq_from_pdb(args.pdb_fn)
    seq_idxs = get_seq_idxs(seq)

    # grab a random, random seed
    seed = args.seed
    if seed is None:
        seed = random.randint(100000000, 999999999)

    if args.method == "subvariants":
        gen_subvariants_main(args.pdb_fn, seq, seq_idxs, chars,
                             args.target_num, args.max_num_subs, args.min_num_subs, seed, args.db_fn, args.out_dir)

    elif args.method == "random":
        gen_random_main(args.pdb_fn, seq, seq_idxs, chars,
                        args.target_num, args.num_subs_list, args.num_replicates, seed, args.out_dir)

    elif args.method == "all":
        gen_all_main(args.pdb_fn, seq, seq_idxs, chars, args.num_subs_list, args.out_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        fromfile_prefix_chars="@")

    parser.add_argument("method",
                        help="what method to use to generate variants",
                        type=str,
                        choices=["all", "random", "subvariants"])

    # common args
    parser.add_argument("--pdb_fn",
                        help="the PDB file from which to generate variants",
                        type=str)
    parser.add_argument("--target_num",
                        type=int,
                        help="target number of variants")
    parser.add_argument("--seed",
                        type=int,
                        help="random seed, None for a random random seed",
                        default=None)
    parser.add_argument("--out_dir",
                        type=str,
                        help="output directory for variant lists",
                        default="variant_lists")
    parser.add_argument("--db_fn",
                        type=str,
                        help="database filename, if specified, will not generate variants already in database",
                        default=None)
    # random args
    parser.add_argument("--num_subs_list",
                        type=int,
                        help="for random and 'all' method, numbers of substitutions for variants",
                        nargs="+",
                        default=[1, 2])
    parser.add_argument("--num_replicates",
                        type=int,
                        help="for random method, the maximum number of replicates of each variant",
                        default=1)

    # subvariants args
    parser.add_argument("--max_num_subs",
                        type=int,
                        help="for subvariants method, the maximum number of substitutions for a variant",
                        default=5)
    parser.add_argument("--min_num_subs",
                        type=int,
                        help="for subvariants method, the minimum number of substitutions for a variant",
                        default=1)




    main(parser.parse_args())
