import argparse
import numpy as np
import pandas as pd


def parse_score(score_sc_fn, output_base):
    """ parses the score.sc file to get overall energy for variant """

    # load the score sc
    df = pd.read_csv(score_sc_fn, delim_whitespace=True, skiprows=1)

    total_scores = df["total_score"].values.astype(np.float32)
    avg_score = np.mean(total_scores)
    std_dev = np.std(total_scores)
    print("standard deviation for variant scores: {}".format(std_dev))

    np.save("{}variant_score.npy".format(output_base), avg_score)


def main():

    sample_score_sc = "output/1621_score.sc"
    parse_score(sample_score_sc)


if __name__ == "__main__":
    main()