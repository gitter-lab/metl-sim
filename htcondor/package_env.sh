#!/usr/bin/env bash

# conda needs to be installed for us to proceed
if ! command -v conda &> /dev/null;
then
  echo "Conda not found. Install miniconda to continue."
  exit 1
fi

conda config --set always_yes yes

# make sure we are in the base environment
if [ "$CONDA_DEFAULT_ENV" != "base" ];
then
  conda deactivate
  conda activate base
fi

# make sure conda-pack is installed (needed to package environment)
if ! conda list | grep -q "^conda-pack\s";
then
  echo "Installing dependency conda-pack"
  conda install -c conda-forge conda-pack
fi

# parse the environment name from environment.yml
env_name=$(head -n 1 environment.yml | cut -d ":" -f 2 | xargs)

# if the environment already exists... let the user handle it
if conda env list | grep -q "^$env_name\s";
then
  # echo "Using existing environment. Delete with 'conda env remove --name $env_name' to reinstall from environment.yml."
  # todo: add an option to delete and reinstall the environment from this script
  echo "Environment already exists. Deleting it..."
  conda env remove --name $env_name
fi

# create the environment from environment.yml
if ! conda env list | grep -q "^$env_name\s";
then
  echo "Installing environment named $env_name"
  conda env create -f environment.yml
fi

# create an output directory for this packaged environment
out_dir="${env_name}_$(date +%Y-%m-%d_%H-%M-%S)"
mkdir "$out_dir"

# pack up the environment
echo "Packing up environment"
conda pack -n "$env_name" -o "$out_dir/$env_name.tar.gz"
# set correct permission
chmod 644 "$out_dir/$env_name.tar.gz"

# if resulting environment is larger than 1GB
# it needs to be split into smaller that can go on SQUID
if [ -n "$(find "$out_dir/$env_name.tar.gz" -prune -size +1000000000c)" ]; then
  echo "Splitting packaged environment into smaller files"
  split -b 950m "$out_dir/$env_name.tar.gz" "$out_dir/$env_name.tar.gz."
fi

conda config --set always_yes no

echo "Output directory is $out_dir"
