""" Fills the template files for energize pipeline """
import os
from os.path import join
import shutil


def gen_res_selector_str(variant, index_type="1-based"):
    """ generates the ResidueIndexSelector string Rosetta scripts """
    resnums = []
    for mutation in variant.split(","):
        if index_type == "1-based":
            resnum_1_index = int(mutation[1:-1])
        elif index_type == "0-based":
            resnum_0_idx = int(mutation[1:-1])
            resnum_1_index = resnum_0_idx + 1
        else:
            raise ValueError("unrecognized index_type {}".format(index_type))
        resnums.append("{}A".format(resnum_1_index))
    resnum_str = ",".join(resnums)
    return resnum_str


def gen_relax_xml_str(template_dir, variant, relax_distance, relax_repeats):
    resnum_str = gen_res_selector_str(variant)
    template_fn = "relax_template.xml"

    # load the template
    template_fn = join(template_dir, template_fn)
    with open(template_fn, "r") as f:
        template_str = f.read()

    # fill in the template
    formatted = template_str.format(resnums=resnum_str, relax_distance=relax_distance, relax_repeats=relax_repeats)
    return formatted


def gen_resfile_str(template_dir, chain, variant, index_type="1-based"):
    """residue_number chain PIKAA replacement_AA"""

    mutation_strs = []
    for mutation in variant.split(","):
        if index_type == "1-based":
            resnum_1_index = int(mutation[1:-1])
        elif index_type == "0-based":
            resnum_0_idx = int(mutation[1:-1])
            resnum_1_index = resnum_0_idx + 1
        else:
            raise ValueError("unrecognized index_type {}".format(index_type))
        new_aa = mutation[-1]

        mutation_strs.append("{} {} PIKAA {}".format(resnum_1_index, chain, new_aa))

    # add new lines between mutation strs
    mutation_strs = "\n".join(mutation_strs)

    # load the templates
    template_fn = join(template_dir, "mutation_template.resfile")
    with open(template_fn, "r") as f:
        template_str = f.read()

    formatted_template = template_str.format(mutation_strs)

    return formatted_template


def fill_templates(template_dir, chain, variant, relax_distance, relax_repeats, out_dir):

    # the mutate xml no longer has any argument that need to be filled in, so just copy the template
    # todo: this could be done in prep_working_dir in energize.py instead, that's where other files
    #   that are unchanged are copied from the template dir to the working dir
    shutil.copy(join(template_dir, "mutate_template.xml"), join(out_dir, "mutate.xml"))

    relax_xml_str = gen_relax_xml_str(template_dir, variant, relax_distance, relax_repeats)
    with open(join(out_dir, "relax.xml"), "w") as f:
        f.write(relax_xml_str)

    resfile_str = gen_resfile_str(template_dir, chain, variant)
    with open(join(out_dir, "mutation.resfile"), "w") as f:
        f.write(resfile_str)

