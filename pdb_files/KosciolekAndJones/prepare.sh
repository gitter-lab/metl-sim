# cd to the main rosettafy directory (using a absolute path here...)
# alternatively, make sure this script is run from the main directory
cd /Users/sg/PycharmProjects/rosettafy

for i in $(cat "pdb_files/KosciolekAndJones/ready_set_1.txt");
do
  echo "$i"
  conda run -n rosettafy python code/prepare.py --rosetta_main_dir=/Users/sg/rosetta_bin_mac_2021.16.61629_bundle/main --pdb_fn="$i"
done