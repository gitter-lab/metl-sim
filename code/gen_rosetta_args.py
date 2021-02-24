""" Generates arguments for Rosetta run """

import argparse
import os
from os.path import join


def gen_res_selector_str(variant, wt_offset):
    """ generates the ResidueIndexSelector string Rosetta scripts """
    resnums = []
    for mutation in variant.split(","):
        resnum_0_idx_raw = int(mutation[1:-1])
        resnum_0_idx_offset = resnum_0_idx_raw - wt_offset
        resnum_1_index = resnum_0_idx_offset + 1
        resnums.append("{}A".format(resnum_1_index))
    resnum_str = ",".join(resnums)
    return resnum_str


def gen_mutate_xml_str(template_dir, variant, wt_offset):
    # TODO: the mutant.xml template from Jerry doesn't use the chain (A) in the residue selector...
    #  verify I can use it to keep consistency with relax template (I think I can)
    resnum_str = gen_res_selector_str(variant, wt_offset)

    template_fn = "mutate_template.xml"

    # load the template
    template_fn = join(template_dir, template_fn)
    with open(template_fn, "r") as f:
        template_str = f.read()

    # fill in the template
    formatted_template = template_str.format(resnum_str)
    return formatted_template


def gen_relax_xml_str(template_dir, variant, wt_offset):
    resnum_str = gen_res_selector_str(variant, wt_offset)
    template_fn = "relax_template.xml"

    # load the template
    template_fn = join(template_dir, template_fn)
    with open(template_fn, "r") as f:
        template_str = f.read()

    # fill in the template
    formatted_template = template_str.format(resnum_str)
    return formatted_template


def gen_resfile_str(template_dir, variant, wt_offset):
    """residue_number chain PIKAA replacement_AA"""

    mutation_strs = []
    for mutation in variant.split(","):
        resnum_0_idx_raw = int(mutation[1:-1])
        resnum_0_idx_offset = resnum_0_idx_raw - wt_offset
        resnum_1_index = resnum_0_idx_offset + 1
        new_aa = mutation[-1]

        mutation_strs.append("{} A PIKAA {}".format(resnum_1_index, new_aa))

    # add new lines between mutation strs
    mutation_strs = "\n".join(mutation_strs)

    # load the templates
    template_fn = join(template_dir, "mutation_template.resfile")
    with open(template_fn, "r") as f:
        template_str = f.read()

    formatted_template = template_str.format(mutation_strs)

    return formatted_template


def gen_rosetta_args(template_dir, variant, wt_offset, out_dir):

    mutate_xml_str = gen_mutate_xml_str(template_dir, variant, wt_offset)
    relax_xml_str = gen_relax_xml_str(template_dir, variant, wt_offset)
    resfile_str = gen_resfile_str(template_dir, variant, wt_offset)

    with open(join(out_dir, "mutate.xml"), "w") as f:
        f.write(mutate_xml_str)

    with open(join(out_dir, "relax.xml"), "w") as f:
        f.write(relax_xml_str)

    with open(join(out_dir, "mutation.resfile"), "w") as f:
        f.write(resfile_str)


def main(args):
    gen_rosetta_args(args.template_dir, args.variant, args.wt_offset, args.out_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--template_dir",
                        help="the directory containing the template files",
                        type=str,
                        default="energize_wd_template")
    parser.add_argument("--variant",
                        help="the variant for which to generate rosetta args_gb1",
                        type=str)
    parser.add_argument("--wt_offset",
                        help="the offset for variant indexing",
                        type=int,
                        default=0)
    parser.add_argument("--out_dir",
                        help="the directory in which to save mutation.resfile and mutate.xml",
                        type=str)

    main(parser.parse_args())
