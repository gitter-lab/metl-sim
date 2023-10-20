#!/bin/bash

# this script is meant to be called from the working directory (will be handled by python caller)

if [[ $# -le 3 ]] ; then
    echo 'Usage: ./$0 PROCESS_NUM START_STRUCT VARIANT NUM_STRUCTS'
    exit 1
fi

PROCESS_NUM=$1
START_STRUCT=$2
VARIANT=$3
NUM_STRUCTS=$4

echo "PROCESS_NUM :" $PROCESS_NUM
echo "START_STRUCT :" $START_STRUCT
echo "VARIANT :" $VARIANT
echo "NUM_STRUCTS :" $NUM_STRUCTS

# todo: this should be an input parameter, could vary for different PDBs
CHAIN="C" # chain that gets mutated

# https://stackoverflow.com/questions/2664740/extract-file-basename-without-path-and-extension-in-bash/
# this is the PDB file name without the path
START_STRUCT_NO_PATH="${START_STRUCT##*/}"
# this is the PDB file name without the path or the extension
START_STRUCT_BASE="${START_STRUCT_NO_PATH%.pdb}"

ROSETTA_SCRIPTS_EXEC=rosetta_scripts.static.linuxgccrelease
ROSETTA_RELAX_EXEC=relax.static.linuxgccrelease
ROSETTA_PATH=`pwd`
DATABASE_PATH="${ROSETTA_PATH}/database"
WORKING_DIR="docking_wd"

ROSETTA_SCRIPTS_BIN="${ROSETTA_PATH}/${ROSETTA_SCRIPTS_EXEC}"



# this is not necessary because my parsing script will add this info to final dataframe
# todo: delete
OUTPUT_YAML=output/info.yaml
echo "starting_struct: " ${START_STRUCT_BASE}  > ${OUTPUT_YAML}
echo "variant: " "$VARIANT" >> ${OUTPUT_YAML}

if [ -z "$NUM_STRUCTS" ]; then
    echo "Error: Number of structs $NUM_STRUCTS not specified"
    exit 1
fi

# normally I would have a separate python function for this call
echo "Making the mutations"
# Make the mutations 
# this also does some sort of relax
ROSETTA3_DB="${DATABASE_PATH}" \
	"${ROSETTA_SCRIPTS_BIN}" \
    -in:file:s "${START_STRUCT}" \
    @options_mutate.txt  \
	-nstruct 1 >> rosetta_output.txt

cp mutated_structures/${START_STRUCT_BASE}_0001.pdb \
	output/variant_relaxed.pdb
mv mutated_structures/score.sc output/variant_relaxed_score.sc


# normally I would have a separate python function for this call
echo "Docking relaxed structure"
# dock
ROSETTA3_DB="${DATABASE_PATH}" \
	"${ROSETTA_SCRIPTS_BIN}" \
    -in:file:s mutated_structures/${START_STRUCT_BASE}_0001.pdb \
   	-docking:partners A_C	\
    -use_input_sc \
    -ex1 \
    -ex2 \
    -out:path:all docked_structures \
    -out:file:scorefile docked_score.sc \
    -out:overwrite \
    -score:weights ref2015.wts			 \
    -parser:protocol docking_minimize_fast.xml     \
    -nstruct ${NUM_STRUCTS}  >> rosetta_output.txt


# normally I would do this parsing in Python / Pandas
best_struct_info=`sort -nk 3 docked_structures/docked_score.sc | awk '{print $2, $6, $NF}' | head -1`
IFS=" " read -r best_struct_total_energy \
        best_struct_dG_separated \
        best_struct <<< ${best_struct_info}
# copy best structure and all scores to output directory
cp docked_structures/"${best_struct}.pdb" output/
cp docked_structures/docked_score.sc output/docked_score.sc

echo "results:" >> ${OUTPUT_YAML}
echo "  best_struct: " ${best_struct} >> ${OUTPUT_YAML}
echo "  dG_separated: " ${best_struct_dG_separated} >> ${OUTPUT_YAML}
echo "  best_struct_total_energy: " ${best_struct_total_energy} >> ${OUTPUT_YAML}


exit 0




