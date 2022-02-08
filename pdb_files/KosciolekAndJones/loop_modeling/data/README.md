
## Overview

We start with the raw pdb file and then use the rosetta `clean_pdb.py`
script to prepare to allow the pdb file to be read by rosetta. Then we create a
blueprint file for each pdb by running the `getBluePrintFromCoords.pl` script.

In order to remodel the missing residues we need to guess what the secondary
structure is. We get the secondary structure from the `mmtf` files as this
format is easier to read than the raw pdb files. Then we merge the `mmtf`
files, the cleaned pdb files and the blueprint files to figure out what
residues we need to remodel. 

It was not possible to predict when the missing residues in the middle of a
protein should be helices instead of loops and so even though the secondary
structure is used in the scripts, they end up requesting loops for missing
residues in the middle and never helices. Since the secondary structure isn't
used we could skip downloading the `mmtf` files but it is kept in there incase
we need the secondary structure later. 

After the merged files are created, we create remodel files which tell the
`remodel` Rosetta application how to remodel the protein for proteins that are
missing residues. In the last step, we actually run Rosetta `remodel` in a
quick and dirty mode and get a pdb with the same sequence as the seqres entry
in the pdb and Rosetta can read every residue. 

**Exceptions:** The file [remodel_checks.csv](./remodel_checks.csv) has a list
of pdb codes where the remodeling worked. 

**Final files:** For every raw pdb file, we should either pick the pdb file from
the  `pdbs_remodel` directory and if it doesn't exist in that directory then we
should pick it from the `pdbs_clean` directory. This will ensure that we have a
pdb file that Rosetta can read and matches up with the seqres entry in the pdb
file. The exceptions are the pdb entries set to False in the [remodel_checks.csv](./remodel_checks.csv) csv file.

**Post Processing:** All files will need to be relaxed further before the next steps

## Directories

* `pdbs_raw`: raw pdb files (input)

* `pdbs_clean`: cleaned pdb files with rosetta script
  [Documentation on Rosetta clean pdb script](https://www.rosettacommons.org/docs/latest/rosetta_basics/preparation/preparing-structures#cleaning-pdbs-for-rosetta) 
  ```shell
  clean_pdb=/mnt/scratch/software/rosetta/rosetta.binary.linux.release-296/main/tools/protein_tools/scripts/clean_pdb.py
  mkdir -p pdbs_clean
  (cd pdbs_clean; 
   for fn in ../pdbs_raw/*.pdb; 
     do 
       "${clean_pdb}" "${fn}" A 
     done
  )
  ```

* `pdbs_bp`: Rosetta blueprint files for chain A of each pdb file
  Create the blueprint files from the cleaned pdb files
  ```shell
  mkdir -p pdbs_bp
  remodel_dir=/mnt/scratch/software/rosetta/rosetta.binary.linux.release-296/main/tools/remodel 
  for fn in pdbs_clean/*.pdb; 
    do 
      code=`basename $fn .pdb`
      ${remodel_dir}/getBluePrintFromCoords.pl \
            -pdbfile "${fn}" \
            -chain A > pdbs_bp/${code}.bp  
    done
  ``` 
  
* `pdbs_mmtf`: pdb files in mmtf format (for secondary structure)
  mmtf format is a cleaned up and tiny version of the original pdb files. It
  is easier to programmatically extract secondary structure information from
  mmtf files than pdb.  Rosetta Remodel requires us to specify the secondary
  structure of the missing residues/loop. Use the available secondary structure
  in the mtmtf file to make an informed guess.
  ```shell
  for fn in pdbs_raw/*.pdb; 
    do 
      code=`basename $fn .pdb`
      wget -P pdbs_mmtf https://mmtf.rcsb.org/v1.0/full/$code.mmtf.gz 
    done   
  ```

* `pdbs_merge`: tsv files that merge the `pdbs_mmtf`, `pdbs_raw` and 
                `pdbs_clean` files. Main script is at [merge_structure_files.py](../scripts/merge_structure_files.py).
  ```shell
  mkdir -p pdbs_merge
  rm -f merge_logs.txt
  for fn in pdbs_raw/*.pdb;                                            
    do                                                                 
      code=`basename $fn .pdb`                                         
      if [[ ${code}  == "1rw7" ]]; then
        continue
      fi
      python3 ../scripts/merge_structure_files.py ${code} \
        -d . -o pdbs_merge/${code}_merge.tsv 2>&1 | tee -a merge_logs.txt
    done  
  python3 ../scripts/merge_structure_files_1rw7.py 1rw7 \
        -d . -o pdbs_merge/1rw7_merge.tsv 2>&1 | tee -a merge_logs.txt
  ```

* `pdbs_remodel_bp` : remodel blueprint files. Main script is at [remodel_blueprint.py](../scripts/remodel_blueprint.py).
  ```shell
  mkdir -p pdbs_remodel_bp
  rm -f remodel_bp_logs.txt
  for fn in pdbs_raw/*.pdb;                                            
    do                                                                 
      code=`basename $fn .pdb`                                         
      python3 ../scripts/remodel_blueprint.py ${code} \
        -d . -o pdbs_remodel_bp/${code}_remodel.bp 2>&1 | tee -a remodel_bp_logs.txt
    done  
  ``` 

* `pdbs_remodel` : Rosetta remodel
   ```shell
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
   ```

* check remodeled structures
  ```shell
   echo "code, remodel_check_passed" > remodel_checks.csv
   for fn in pdbs_remodel_bp/*.bp;
     do
       code=`basename $fn _remodel.bp`
       python ../scripts/check_remodeled_structure.py ${code}  \
                -d . >> remodel_checks.csv
     done
    

  ```



