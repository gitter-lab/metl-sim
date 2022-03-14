
## Taking a deeper look at the 6 stragglers


### `1gz2`
Residues 64-68 are zero occupancy in the original pdb file. The PDB coordinates
are in a loop on the surface at the protein. 

*Recommend*: Use the pdb coordinates inspite of zero occupancy.

### `1hdo`
Residue  120 is zero occupancy in the original pdb file. The PDB coordinates for this residue join a loop on the outside of the protein.

*Recommend*: Use the pdb coordinates inspite of zero occupancy.

### `1i1n`
`clean_pdb.py` put a `CYS` residue for position 266 (last position). It did not
respect a `TER` statement and should have left that position blank.

*Recommend*: Drop the last `CYS` residue for position 266 and have Rosetta
remodel it.

### `1j3a`
Residues 54-66 are mising from the original pdb file. This connects a loop to a
helix. The 3D structure at rcsb.org shows this join as a dotted line. 

*Recommend*: ignore this pdb entry

### `1jbe`
Both residues 74 and 75 are modified residues. There is a `SEQADV` record for
both residues but there is a `MODRES`entry only for one of these residues.
[SEQADV just notes a discrepency and MODRES tells us what it
is](https://www.wwpdb.org/documentation/file-format-content/format33/sect3.html#SEQADV)
Would consider this a bug in the orignal pdb and that causes programs like
Biopython to give us the wrong sequence for this pdb file. Even the mmtf format
of this file tells us that we have a sequence with an unknown residue at one of
these position 75. 

*Recommend*: ignore this pdb entry.

### `1lm4`
There is a giant break in the positions of the reisudes (5-6). This is in the
midde of the HIS-TAG at the start of the protein and so it is not an important
location. Rosetta Remodel cannot close this break. 

*Recommend*: Clean out all these residues 1-6 at the start of the protein and
then remodel. 


## Remodel scripts

```shell
mkdir -p pdbs_raw

# 1gz2. set occupancy of residues 64-68 to 1
awk '
BEGIN { FPAT = "([[:space:]]*[[:alnum:][:punct:][:digit:]]+)"; OFS = ""; } 
/^ATOM/{if (($6 >= 64)&&($6 <= 68)) {$10 = "  1.00"}} 
1' ../data/pdbs_raw/1gz2.pdb  > pdbs_raw/1gz2.pdb

# 1hdo. set the occupancy of residue 120 to 1
awk '
BEGIN { FPAT = "([[:space:]]*[[:alnum:][:punct:][:digit:]]+)"; OFS = ""; } 
/^ATOM/{if ($6 == 120) {$10 = "  1.00"}} 
1' ../data/pdbs_raw/1hdo.pdb  > pdbs_raw/1hdo.pdb

# 1i1n. remove HETATM at end which is being confused with residue 266 
awk '
BEGIN { FPAT = "([[:space:]]*[[:alnum:][:punct:][:digit:]]+)"; OFS = ""; } 
! (($1 == "HETATM") && ($2 >= 1707)) {print} 
' ../data/pdbs_raw/1i1n.pdb > pdbs_raw/1i1n.pdb

# 1lm4. removing first few ATOM records from HIS-TAG
awk '
BEGIN { FPAT = "([[:space:]]*[[:alnum:][:punct:][:digit:]]+)"; OFS = ""; } 
! (($1 == "ATOM") && ($6 < 0)) {print} 
' ../data/pdbs_raw/1lm4.pdb > pdbs_raw/1lm4.pdb

```

```shell
# run the rest of the pipeline
clean_pdb=/mnt/scratch/software/rosetta/rosetta.binary.linux.release-296/main/tools/protein_tools/scripts/clean_pdb.py
mkdir -p pdbs_clean
(cd pdbs_clean; 
 for fn in ../pdbs_raw/*.pdb; 
   do 
     "${clean_pdb}" "${fn}" A 
   done
)

mkdir -p pdbs_bp
remodel_dir=/mnt/scratch/software/rosetta/rosetta.binary.linux.release-296/main/tools/remodel 
for fn in pdbs_clean/*.pdb; 
  do 
    code=`basename $fn .pdb`
    ${remodel_dir}/getBluePrintFromCoords.pl \
          -pdbfile "${fn}" \
          -chain A > pdbs_bp/${code}.bp  
  done

for fn in pdbs_raw/*.pdb; 
  do 
    code=`basename $fn .pdb`
    wget -P pdbs_mmtf https://mmtf.rcsb.org/v1.0/full/$code.mmtf.gz 
  done   

mkdir -p pdbs_merge
rm -f merge_logs.txt
for fn in pdbs_raw/*.pdb;                                            
  do                                                                 
    code=`basename $fn .pdb`                                         
    python3 ../scripts/merge_structure_files.py ${code} \
      -d . -o pdbs_merge/${code}_merge.tsv 2>&1 | tee -a merge_logs.txt
  done  

mkdir -p pdbs_remodel_bp
rm -f remodel_bp_logs.txt
for fn in pdbs_raw/*.pdb;                                            
  do                                                                 
    code=`basename $fn .pdb`                                         
    python3 ../scripts/remodel_blueprint.py ${code} \
      -d . -o pdbs_remodel_bp/${code}_remodel.bp 2>&1 | tee -a remodel_bp_logs.txt
  done  

mkdir -p pdbs_remodel
RR_BIN=/mnt/scratch/software/rosetta/bin/remodel.static.linuxgccrelease  
for fn in pdbs_remodel_bp/*.bp;
  do
    code=`basename $fn _remodel.bp`
    ${RR_BIN} -in:file:s pdbs_clean/${code}_A.pdb \
         -remodel:blueprint pdbs_remodel_bp/${code}_remodel.bp \
         -run:chain A \
         -remodel:num_trajectory 1 \
         -remodel:quick_and_dirty \
         -out:path:all pdbs_remodel \
         -out:file:scorefile ${code}_remodel.sc
    rm -f 1.pdb
  done

 echo "code, remodel_check_passed" > remodel_checks.csv
 for fn in pdbs_remodel_bp/*.bp;
   do
     code=`basename $fn _remodel.bp`
     python ../scripts/check_remodeled_structure.py ${code}  \
              -d . >> remodel_checks.csv
   done
  

```
