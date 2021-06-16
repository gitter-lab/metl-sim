from subprocess import call

# import yaml
import requests
import json


def clean_pdb(pdb_fn, chain, out_dir="data/clean_pdb_files"):
    script_fn = "code/clean_pdb/clean_pdb.py"
    conda_env = "clean_pdb"
    call(['conda', 'run', '-n', conda_env, 'python', script_fn, "--outdir", out_dir, pdb_fn, chain])


def pretty_print_POST(req):
    """
    At this point it is completely built and ready
    to be fired; it is "prepared".

    However pay attention at the formatting used in
    this function because it is programmed to be pretty
    printed and may differ from the actual request.
    """
    print('{}\n{}\r\n{}\r\n\r\n{}'.format(
        '-----------START-----------',
        req.method + ' ' + req.url,
        '\r\n'.join('{}: {}'.format(k, v) for k, v in req.headers.items()),
        req.body,
    ))


def main():

    clean_pdb("source_data/pdb_files/2qmt.pdb", "A")
    quit()

    pdb_url = "https://search.rcsb.org/rcsbsearch/v1/query"

    sq = {"query": {
            "type": "terminal",
            "service": "sequence",
            "parameters": {
                "evalue_cutoff": 1,
                "identity_cutoff": 0,
                "target": "pdb_protein_sequence",
                "value": "MQYKLILNGKTLKGETTTEAVDAATAEKVFKQYANDNGVDGEWTYDDATKTFTVTE"
            }
        },
        "request_options": {
            "scoring_strategy": "sequence",
            "return_all_hits": True,
            "sort": [
                {
                    "sort_by": "score",
                    "direction": "desc"
                }
            ],
        },
        "return_type": "polymer_entity"
    }

    r = requests.get(pdb_url, params={"json": json.dumps(sq)})
    # print(r.url)
    # print(r)
    # print(r.json())

    # with open("../output/pdb/results.yaml", "w") as f:
    #     yaml.dump(r.json(), f, allow_unicode=True)


if __name__ == "__main__":
    main()
