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