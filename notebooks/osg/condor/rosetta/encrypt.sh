#!/usr/bin/env bash

# exit if any command fails...
set -e



# we need to activate the conda environment prior to encrypting 
. rosettafy_env/bin/activate

tar_fn=$1
tar_fn_encrypted=$2
pass=$3


openssl enc -e -aes256 -pbkdf2 -in "$tar_fn" -out "$tar_fn_encrypted" -pass "$pass"