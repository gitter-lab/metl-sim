RAW_DIR="pdbs_raw"
CHAINS_DIR="pdbs_chains"
MISSING_AA_DIR="missing_aa"

# Step 1: Obtaining a list of proteins that satisfy our criteria.
## We obtained the list of proteins from the work by Kosciolek & Jones, PLOS One, 2014(https://doi.org/10.1371/journal.pone.0092197). 
## 150 diverse globular proteins, with each protein having a different Pfam domain family, <1.9 A, all monomeric, all between 50-270 residues. 
## Link for the table, it Supplementary Table 1: https://doi.org/10.1371/journal.pone.0092197.s002. 
## Copied the list of PDBs to pdb_list.txt

# Step 2: Downloading the PDB files from RCSB website.
## The following command is reading the pdb_list file and separating the PDB & chain id, and then downloading the PDB files in the directory.
mkdir -p $RAW_DIR
for i in $(cat "pdb_list.txt");
do
  j=$(echo "$i" | cut -c1-4);
  wget "https://files.rcsb.org/download/$j.pdb" --directory-prefix $RAW_DIR;
done

#Step 3: Extracting the chains of interest from the PDB files.
##Just grepping the ATOM lines from the .pdb files that have the chain_id of our interest. Column 22 represents the chain_id.
## todo: the default grep on macOS doesn't support full regex and has a problem with this regex string, so the solution
##    is to either install GNU grep (brew install grep) or change the regex to support macOS
mkdir -p $CHAINS_DIR
for i in $(cat "pdb_list.txt");
do
  pdb=$(echo "$i" | cut -c1-4);
  chain=$(echo "$i" | cut -c5);
  grep "^ATOM.\{16\}* ${chain} .*" "$RAW_DIR/${pdb}.pdb" > "$CHAINS_DIR/${pdb}_${chain}.pdb";
done


# Step 4: Getting a list of Missing AAs for these PDBs.
## The .pdb files have REMARK lines stating the missing AAs and Atoms, REMARK 465 for Missing AA & REMARK 470 for Missing Atoms.
## In the following command, I'm just extracting these REMARK lines for each of the pdb files and the chain of interest and writing them in a separate .txt file. (Make the Missing_AA directory here using command: 'mkdir Missing_AA', if the directory isn't made earlier on)
mkdir -p $MISSING_AA_DIR
for i in $(cat pdb_list.txt);
do
  pdb=$(echo "$i" | cut -c1-4);
  chain=$(echo $i | cut -c5);
  grep "^REMARK 465 .* $chain " "$RAW_DIR/$pdb.pdb" > "$MISSING_AA_DIR/${pdb}_${chain}".txt;
done
## Not all PDBs have missing AAs, so we will only keep .txt files that have them i.e., the ones that are not empty, using the following command:
for i in $(ls ${MISSING_AA_DIR}/*.txt);
do
  [ -s "$i" ] || rm "$i";
done

##Step 5: Making the .remodel files for the missing AAs PDBs
### Going to the directory
#cd /home/amritkar@ad.wisc.edu/Jones_PDBs/Missing_AA/
### Out of the 150, 95 have missing Amino Acids. One of the steps in Rosetta loop modelling/fixing missing AAs is to make a .remodel file, the following command is used to make the .remodel files for all the PDBs that have Missing AAs, out of the 150, 95 have missing Amino Acids.
#for i in `ls *.txt`; do pdb=`echo $i | cut -d'_' -f1`; chain=`echo $i | cut -d'_' -f2 | cut -d'.' -f1`; /mnt/scratch/software/rosetta/rosetta.binary.linux.release-296/main/tools/remodel/getBluePrintFromCoords.pl -pdbfile /home/amritkar@ad.wisc.edu/Jones_PDBs/"$pdb".pdb -chain $chain > /home/amritkar@ad.wisc.edu/Jones_PDBs/Missing_AA/"$pdb"_"$chain"_missing_loops.remodel; done
#
### There are multiple other steps after making the .remodel files in the Rosetta loop modeling protocol, and the automation for that is not finished yet. The script for that is in: '/home/amritkar@ad.wisc.edu/Jones_PDBs/Missing_AA/bin', and I'll work on that in the break.
#
## Step 6: Getting a list of Missing Atomss for these PDBs.
### The .pdb files have REMARK lines stating the missing AAs and Atoms, REMARK 465 for Missing AA & REMARK 470 for Missing Atoms. In the following command, I'm just extracting these REMARK lines for each of the pdb files and the chain of interest and writing them in a separate .txt file. (Make the Missing_AA directory here using command: 'mkdir Missing_Atoms', if the directory isn't made earlier on).
#for i in `cat /home/amritkar@ad.wisc.edu/Jones_PDBs/Jones_pdb_list.txt`; do pdb=`echo $i | cut -c1-4`; chain=`echo $i | cut -c5`; grep "^REMARK 470 .* $chain " /home/amritkar@ad.wisc.edu/Jones_PDBs/"$pdb".pdb > /home/amritkar@ad.wisc.edu/Jones_PDBs/Missing_Atoms/"$pdb"_"$chain".txt; done
### Not all PDBs have missing Atoms, so we will only keep .txt files that have them i.e., the ones that are not empty, using the following command:
#for i in `ls /home/amritkar@ad.wisc.edu/Jones_PDBs/Missing_Atoms/*.txt`; do [ -s $i ] || rmtrash $i; done

