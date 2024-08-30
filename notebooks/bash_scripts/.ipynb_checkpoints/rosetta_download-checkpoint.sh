#!/bin/bash


set -e


cd downloads

# Check if there are any split tar files in the current directory
if [ "$(ls 2>/dev/null -Ubad1 -- *.tar.gz.* | wc -l)" -gt 0 ]; then
  # Declare an associative array to store unique tar file prefixes
  declare -A tar_prefixes
  
  # Populate the array with unique prefixes from the split tar files
  for f in *.tar.gz.*; do
      tar_prefixes[${f%%.*}]=
  done
  
  # Combine split tar files for each unique prefix
  for f in "${!tar_prefixes[@]}"; do
    echo "Combining split files for $f.tar.gz"
    cat "$f".tar.gz.* > "$f".tar.gz
    
    # Remove the split tar files after combining
    # rm "$f".tar.gz.*
  done
fi


. ../rosetta_env/bin/activate

echo "Decrypting Rosetta"
openssl version # echo the version for my knowledge
openssl enc -d -aes256 -pbkdf2 -in rosetta_min_enc_v2.tar.gz -out rosetta_min.tar.gz -pass file:pass.txt
# rm rosetta_min_enc_v2.tar.gz


tar -xf downloads/rosetta_min.tar.gz