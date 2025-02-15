import os
import tarfile
import shutil
from tqdm import tqdm
import requests

import subprocess
import time
import json
import pandas as pd
import numpy as np
import re

from os.path import basename, join

def remove_all_condor_jobs():
    try:
        count=get_jobs_on_OSG()
        if len(count)==0: 
            print(f"\033[92m No jobs active on Open Science Grid.\033[0m")
            return
            
        # Run the condor_rm command to remove all jobs
        result = subprocess.run(["condor_rm", "-all"], check=True, capture_output=True, text=True)

        # Success message in green
        print(f"\033[92m✅ Successfully removed {len(count)} jobs.\033[0m")

    except subprocess.CalledProcessError as e:
        # Error message in red
        print(f"\033[91m❌ Failed to remove jobs:\n{e.stderr}\033[0m")



def check_directory_exists(folder_name,base_dir='condor'):
    # Construct the full path
    full_path = os.path.join(base_dir, folder_name)
    
    # Check if the directory exists
    if folder_name=='practice' or folder_name=='rosetta':
        print(f"\033[91m❌ Cannot name job '{folder_name}' it is a special name used for the demo.\nPlease specify a new job name.\033[0m")
        return False 
    
    if os.path.exists(full_path) and os.path.isdir(full_path):
        # Red highlighting
        print(f"\033[91m❌ A job named '{folder_name}' already exists. Please specify a new job name.\033[0m")
        return False
    else:
        # Green highlighting
        print(f"\033[92m✅ No job named '{folder_name}' exists'. You can use this job name.\033[0m")
        return True


def create_directory_and_copy_items(
    new_dir, 
    items_to_copy,
    basename=True,
    condor_logs_dir="output/condor_logs"
):
    
    # Create the new directory if it doesn't exist
    os.makedirs(new_dir, exist_ok=True)

    # create the condor logs directory, which needs to exist for condor to save the .log files
    os.makedirs(join(new_dir, condor_logs_dir), exist_ok=True)

    # print(f"✅ Directory '{new_dir}' created")

    # Copy each item (file or directory) into the new directory
    for item in items_to_copy:

        if basename: 
            destination = os.path.join(new_dir, os.path.basename(item))
        else:
            destination=new_dir
        
        if os.path.isdir(item):
            if os.path.exists(destination):
                # Merge the contents of the directory if it already exists
                for root, dirs, files in os.walk(item):
                    relative_path = os.path.relpath(root, item)
                    dest_path = os.path.join(destination, relative_path)

                    os.makedirs(dest_path, exist_ok=True)
                    for file in files:
                        shutil.copy(os.path.join(root, file), dest_path)
                # print(f"✅ Directory '{item}' copied to '{destination}'.")
            else:
                shutil.copytree(item, destination)
                # print(f"✅ Directory '{item}' copied to '{new_dir}'.")
        else:
            shutil.copy(item, destination)
            # print(f"✅ File '{item}' copied to '{new_dir}'.")    


def get_log_files(directory):
    if not os.path.exists(directory):
        print(f'\033[33m💡 Notice: No log files found for job: {directory.split(os.sep)[1]}, skipping job \033[0m')
        return []

    # List all files in the directory
    files = os.listdir(directory)
    
    # Filter files that end with .log
    log_files = [f for f in files if f.endswith('.log')]
    
    return log_files


def submit_condor_job(job_name,job_type):
    """
    Submits a Condor job using the provided submit file name and directory.
    
    Args:
    - submit_file (str): The name of the submit file.
    - job_name (str): name of job.
    
    Returns:
    - str: A message indicating whether the job was submitted successfully or not.
    """
    try:
        # Check if the current submit directory is already in the Iwd values

        env_vars = os.environ.copy()
        
        if not check_directory_exists(job_name):
            return  
        elif job_type=='helloworld': 
            ## now construct the directory 
            print(f"\033[92m✅ Setting up job type `helloworld`\033[0m")

            # must specify file paths and submit jobs
            submit_file_path = "submit.sub"
            working_directory = f"condor/{job_name}"
            
            create_directory_and_copy_items(working_directory, ['condor/practice/'])
        elif job_type=='rosetta_download': 
            ## now construct the directory 
            print(f"\033[92m✅ Setting up job type `rosetta_download`\033[0m")

            # must specify file paths and submit jobs
            submit_file_path = "rosetta_download.sub"
            working_directory = f"condor/{job_name}"
            
            create_directory_and_copy_items(working_directory, ['condor/rosetta/', 'downloads/metl-sim_2025-02-13.tar.gz'])
        elif job_type=='relax':
            print(f"\033[92m✅ Setting up job type `relax`\033[0m")
            
            submit_file_path = "energize.sub"
            working_directory = f"condor/{job_name}"
            
             # 0) make the directory
            os.makedirs(working_directory, exist_ok=True)
           
            # 0.5) get the name of the previous directory based on the endswith function.
            htcondor_output_dir='../../output/htcondor_runs'

            dir_metl_sim =[x for x in os.listdir(htcondor_output_dir) if x.endswith(job_name)]
            if len(dir_metl_sim)>1: 
                print(f"\033[91m❌ Error found multiple prepared runs for job name: {job_name}, please prepare a run (using prepare_rosetta_run() for OSG with a unique job name \033[91m\n")
                return 
            elif len(dir_metl_sim)==0:
                print(f"\033[91m❌ Error no found job name: {job_name}, please prepare a run using prepare_rosetta_run() for OSG with this job name or select from already prepared job names \033[91m\n")
                return
            
            # print(filename_metl_sim)
            dir_metl_sim = dir_metl_sim[0]

            # 1) untar the args file into the directory in notebooks
            untar_file_with_progress(f'{htcondor_output_dir}/{dir_metl_sim}/args.tar.gz',working_directory)

            # 2) copy over the contents from metl-sim dir into notebooks condor dir
            create_directory_and_copy_items(working_directory,[f'{htcondor_output_dir}/{dir_metl_sim}'],basename=False)

            # 3) export local environment parameters env_vars = os.environ.copy()  # Copy the current environment variables
                # env_vars["MY_VAR"] = "my_value"  # Add or modify environment variables
                # env_vars["ANOTHER_VAR"] = "another_value"

            file_path_env_vars=f'{working_directory}/env_vars.txt'
            with open(file_path_env_vars, 'r') as file:
                for line in file:
                    # Strip leading/trailing whitespace and ignore empty lines or comments
                    line = line.strip()
                    if line.startswith("export"):
                        # Remove 'export' keyword and split into key-value pairs
                        key, value = line.replace("export ", "").split("=", 1)
                        
                        env_vars[key.strip()] = value.strip()

        else:
            print(f"\033[91m❌ Error invalid job type, select from:\033[91m\n"\
            "\033[91m--->'helloworld'\n--->'rosetta_download'\n--->'relax'\033[91m")
            return False 

        # Run the command with a specified working directory
        result = subprocess.run(
            ["condor_submit", submit_file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            cwd=working_directory,            # Specify the working directory here
            env=env_vars

        )

        # give it time to create the log files
        time.sleep(5)

        print(f"\033[92m✅ Job name: '{job_name}' submitted \033[92m")  

    except subprocess.CalledProcessError as e:
        print(f"\033[91m❌ Error submitting job: {e}\033[91m")


def remove_jobs_with_constraints():
    # Define the constraint to select jobs with status other than 1 or 2
    constraint = "JobStatus =!= 2 && JobStatus =!= 1"
    
    try:
        # Construct the condor_rm command with the constraint
        result = subprocess.run(
            ['condor_rm', '-constraint', constraint],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        print("\033[32mSuccess:\033[0m Jobs removed that were failed.")
        # print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"\033[31mError:\033[0m Failed to remove jobs.")
        print(e.stderr)

def extract_exit_code(job_output):
    # Regular expression to match the exit code part
    c,r,f=0,0,0
    # match = re.search(r'Job terminated.*exit-code (\d+)', job_output, re.DOTALL)
    # exit_code = match.group(1)
    
    if 'exit-code 0' in job_output:
        c+=1 
    elif 'Nonzero exit-code' in job_output or 'Job was aborted' in job_output: 
        f+=1
    else: 
        r+=1
    return r,c,f


def get_single_job_status(job_name):
    log_dir=f'condor/{job_name}/output/condor_logs'
    log_files=get_log_files(log_dir)
    completed,failed,running=0,0,0
    for log_file in log_files:
        with open(f"{log_dir}/{log_file}",'r') as f: 
            r,c,f=extract_exit_code(f.read())   
        completed+=c
        failed+=f
        running+=r
    
    return running,completed,failed
       
def get_jobs_on_OSG():
    try:
        result = subprocess.run(
            ["condor_q", "-json", "-attributes", "Iwd"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        
        json_output = result.stdout
        if len(json_output)==0: 
            return []
        data = json.loads(json_output)
        
        iwd_values = [entry['Iwd'].split(os.sep)[-1] for entry in data if 'Iwd' in entry]


        counts = pd.Series(iwd_values).value_counts()

        for val in counts.keys():
            print(f'\033[33m💡 Notice: Jobs currently running on OSG, job name: {val}, number jobs:{counts[val]}\033[0m')

            # print(f"\033[0mJob name: {val}, number jobs:{counts[val]}\033[0m")         
        return counts
    
    except subprocess.CalledProcessError as e:
        print(f"Error checking for running jobs: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return []


    # condor_rm -constraint 'JobStatus == 1'

def job_status():
    # go through each folder that is valid in condor/ 
    # look to each logs file and see what is currently their 

    jobs=os.listdir('condor')

    C,F,R,J=[],[],[],[]
    for job in jobs: 
        if job!='practice' and job!='rosetta' and job[0]!='.':
            running,completed,failed=get_single_job_status(job)
            C.append(completed)
            F.append(failed)
            R.append(running)
            J.append(job)
    df=pd.DataFrame(index=J)
    df['Running⌛']=R
    df['Completed✅']=C
    df['Failed❌']=F

    if sum(F)!=0: 
        print('\033[33m💡 Notice: Found failed jobs in log files, checking OSG if jobs exist\033[0m')
        count =get_jobs_on_OSG()
        # print(count)
        run_condor_rm= False 
        if len(count)!=0: 
            for c in count.keys(): 
                if df.loc[c]['Failed❌']>0: 
                    run_condor_rm=True

        if run_condor_rm: 
            print('\033[33m💡 Notice: Found failed jobs on OSG, removing failed jobs now\033[0m')

            remove_jobs_with_constraints()
        else: 
            print('\033[33m💡 Notice: No failed jobs currently on OSG\033[0m')

    print(f"\033[92m Status of all submitted jobs \033[0m")
                    
    print(df)


def untar_file_with_progress(file_path, extract_dir='.', filetype='gz'):
    try:
        # Use current directory if no extract_dir is specified
        if extract_dir == '.':
            extract_dir = os.getcwd()
        
        # Check if the directory already exists
        if os.path.exists(extract_dir):
            # Check if the directory is not empty
            if os.listdir(extract_dir):
                print(f"\033[93m🔔 Notice: Directory '{extract_dir}' already exists and is not empty. Skipping extraction.\033[0m")
                return
        
        # Create the directory if it does not exist
        os.makedirs(extract_dir, exist_ok=True)
        
        # Open the tar file
        with tarfile.open(file_path, f"r:{filetype}") as tar:
            # Get the list of files in the tar archive
            members = tar.getmembers()
            total_files = len(members)
            
            # Create a progress bar
            with tqdm(total=total_files, unit='file', desc='Extracting') as pbar:
                # Extract each member and update the progress bar
                for member in members:
                    tar.extract(member, path=extract_dir)
                    pbar.update(1)
            
            print(f"\033[92m✅ Success: File untarred to '{extract_dir}'.\033[0m")
    
    except Exception as e:
        # Handle extraction errors
        if os.path.exists(extract_dir):
            # Clean up the directory if extraction fails
            shutil.rmtree(extract_dir)
            print(f"\033[91m❌ Failure: Extraction failed. Directory '{extract_dir}' has been removed.\033[0m")
        
        print(f"\033[91m❌ Failure: {str(e)}\033[0m")

# def untar_file_with_progress(file_path, extract_dir,filetype='gz'):
#     try:
#         # Check if the directory already exists
#         if os.path.exists(extract_dir):
#             # Check if the directory is not empty
#             if os.listdir(extract_dir):
#                 print(f"\033[93m🔔 Notice: Directory '{extract_dir}' already exists and is not empty. Skipping extraction.\033[0m")
#                 return
        
#         # Create the directory if it does not exist
#         os.makedirs(extract_dir, exist_ok=True)
        
#         # Open the tar file
#         with tarfile.open(file_path, f"r:{filetype}") as tar:
#             # Get the list of files in the tar archive
#             members = tar.getmembers()
#             total_files = len(members)
            
#             # Create a progress bar
#             with tqdm(total=total_files, unit='file', desc='Extracting') as pbar:
#                 # Extract each member and update the progress bar
#                 for member in members:
#                     tar.extract(member, path=extract_dir)
#                     pbar.update(1)
            
#             print(f"\033[92m✅ Success: File untarred to '{extract_dir}'.\033[0m")
    
#     except Exception as e:
#         # Handle extraction errors
#         if os.path.exists(extract_dir):
#             # Clean up the directory if extraction fails
#             shutil.rmtree(extract_dir)
#             print(f"\033[91m❌ Failure: Extraction failed. Directory '{extract_dir}' has been removed.\033[0m")
        
#         print(f"\033[91m❌ Failure: {str(e)}\033[0m")


def download_file(url, output_path, method='curl'):
    try:
        # Check if the downloads directory exists
        dir_path = os.path.dirname(output_path)
        if not os.path.exists(dir_path):
            # Create the directory
            os.makedirs(dir_path)
            print(f"\033[93m🔔 Notice: Directory '{dir_path}' did not exist and has been created.\033[0m")

        # Check if the file has already been downloaded
        if os.path.isfile(output_path):
            print(f"\033[93m🔔 Notice: File '{output_path}' already exists. No download needed.\033[0m")
            return
        
        if method == 'curl':
            # Send a GET request to the URL
            response = requests.get(url, stream=True)

            # Check if the request was successful
            if response.status_code == 200:
                # Get the total file size from the response headers
                total_size = int(response.headers.get('content-length', 0))

                # Write the content to the output file with progress bar
                with open(output_path, 'wb') as file:
                    # Wrap the iter_content with tqdm to show progress
                    for chunk in tqdm(response.iter_content(chunk_size=8192), 
                                      total=total_size // 8192, 
                                      unit='KB', 
                                      desc='Downloading'):
                        file.write(chunk)

                # Output success message in green
                print(f"\033[92m✅ Success: File downloaded to '{output_path}'.\033[0m")
            else:
                # Output failure message in red if the request was unsuccessful
                print(f"\033[91m❌ Failure: HTTP {response.status_code} - Could not download the file.\033[0m")

        elif method == 'scp':
            # Assume url is of the form 'user@host:/path/to/file'
            try:
                scp_command = f"scp {url} {output_path}"
                subprocess.check_call(scp_command, shell=True)
                print(f"\033[92m✅ Success: File copied to '{output_path}' using SCP.\033[0m")
            except subprocess.CalledProcessError as e:
                print(f"\033[91m❌ Failure: SCP command failed with error: {str(e)}\033[0m")

        else:
            print(f"\033[91m❌ Failure: Invalid method '{method}'. Use 'curl' or 'scp'.\033[0m")
    
    except Exception as e:
        # Handle any other exceptions and output failure message in red
        print(f"\033[91m❌ Failure: {str(e)}\033[0m")

# def download_file(url, output_path):
#     try:
#         # Check if the downloads directory exists
#         dir_path = os.path.dirname(output_path)
#         if not os.path.exists(dir_path):
#             # Create the directory
#             os.makedirs(dir_path)
#             print(f"\033[93m🔔 Notice: Directory '{dir_path}' did not exist and has been created.\033[0m")

#         # Check if the file has already been downloaded
#         if os.path.isfile(output_path):
#             print(f"\033[93m🔔 Notice: File '{output_path}' already exists. No download needed.\033[0m")
#             return

#         # Send a GET request to the URL
#         response = requests.get(url, stream=True)
        
#         # Check if the request was successful
#         if response.status_code == 200:
#             # Get the total file size from the response headers
#             total_size = int(response.headers.get('content-length', 0))

#             # Write the content to the output file with progress bar
#             with open(output_path, 'wb') as file:
#                 # Wrap the iter_content with tqdm to show progress
#                 for chunk in tqdm(response.iter_content(chunk_size=8192), 
#                                   total=total_size // 8192, 
#                                   unit='KB', 
#                                   desc='Downloading'):
#                     file.write(chunk)
            
#             # Output success message in green
#             print(f"\033[92m✅ Success: File downloaded to '{output_path}'.\033[0m")
#         else:
#             # Output failure message in red if the request was unsuccessful
#             print(f"\033[91m❌ Failure: HTTP {response.status_code} - Could not download the file.\033[0m")
    
#     except Exception as e:
#         # Handle any other exceptions and output failure message in red
#         print(f"\033[91m❌ Failure: {str(e)}\033[0m")


def check_last_two_folders(expected_folder1, expected_folder2):
    # Get the current working directory
    cwd = os.getcwd()
    
    # Split the path into components
    path_components = os.path.normpath(cwd).split(os.sep)
    
    # Check if there are at least two components in the path
    if len(path_components) < 2:
        print("\033[91m❌ Failure: The current working directory does not have enough components.\033[0m")
    
    # Get the last two components
    last_folder = path_components[-1]
    second_last_folder = path_components[-2]
    
    # Compare with the expected folder names
    if last_folder == expected_folder2 and second_last_folder == expected_folder1:
        print(f"\033[92m✅ Success: You are in '{second_last_folder}/{last_folder}'.\033[0m")
    else:
        print(f"\033[91m❌ Failure: Your current working directory is '{second_last_folder}/{last_folder}', not '{expected_folder1}/{expected_folder2}'.\033[0m")

def set_permissions(path, permissions):
    """
    Change the permissions of a file or all files in a directory using chmod.

    Parameters:
    path (str): Path to the file or directory.
    permissions (str): Permissions to set, e.g., '755'.

    Returns:
    None
    """
    # Helper function to change permissions for a file
    def change_permissions(file_path):
        command = ['chmod', permissions, file_path]
        try:
            subprocess.run(command, check=True)
            # print(f"\033[92m✅ Successfully changed permissions for {file_path} to {permissions}.\033[0m")
        except subprocess.CalledProcessError as e:
            print(f"\033[91m❌ Error occurred while changing permissions for {file_path}: {e}\033[0m")
    
    # If path is a directory, change permissions for all files inside it
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            for name in files:
                file_path = os.path.join(root, name)
                change_permissions(file_path)
    else:
        # Change permissions for the single file
        change_permissions(path)

def decode_rosetta():
    """
    Set permissions for the bash_scripts directory and then run the rosetta_download.sh script.

    Returns:
    None
    """
    # Set permissions for the bash_scripts directory
    set_permissions('bash_scripts', '777')

    # Run the shell script
    script_path = 'bash_scripts/rosetta_download.sh'
    command = ['bash', script_path]
    
    try:
        subprocess.run(command, check=True)
        print("\033[92m✅ Successfully decoded rosetta.\033[0m")
    except subprocess.CalledProcessError as e:
        print(f"\033[91m❌ Error occurred while executing the script: {e}\033[0m")



# def print_colored(message, color_code):
#     """Prints the message in the specified color."""
#     print(f"\033[{color_code}m{message}\033[0m")

# def run_prepare_script(rosetta_main_dir, pdb_fn, relax_nstruct=10, out_dir_base='output/prepare_outputs'):
#     # Construct the command to run the shell script with parameters
#     command = [
#         './bash_scripts/run_prepare.sh',
#         rosetta_main_dir,
#         pdb_fn,
#         str(relax_nstruct),
#         out_dir_base
#     ]
    
#     # Run the shell script
#     try:
#         result = subprocess.run(command, check=True, text=True, capture_output=True)
#         print_colored("✅ Prepare.py executed successfully!", '32')  # Green color
#         print(result.stdout)
#     except subprocess.CalledProcessError as e:
#         print_colored("❌ Prepare.py execution failed!", '31')  # Red color
#         print(f"Error details:\n{e.stderr}")

def print_colored(message, color_code):
    """Prints the message in the specified color."""
    print(f"\033[{color_code}m{message}\033[0m")

def extract_output_directory(output):
    """Extracts the output directory from the given output text."""
    match = re.search(r'output directory is: (.+)', output)
    if match:
        return match.group(1)
    return None

def transfer_file(src_file, dest_dir, cwd):
    """Transfers a file from source to destination directory."""
    original_cwd = os.getcwd()
    try:
        # Change to the specified directory
        os.chdir(cwd)
        
        # Ensure destination directory exists
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        
        # Copy the file to the destination directory
        shutil.copy(src_file, dest_dir)
        print_colored(f"✅ File transferred to {dest_dir}!", '32')  # Green color
    
    except Exception as e:
        print_colored(f"❌ Failed to transfer file: {e}", '31')  # Red color
    
    finally:
        # Change back to the original directory
        os.chdir(original_cwd)

def run_prepare_script(rosetta_main_dir, pdb_fn, relax_nstruct, out_dir_base, conda_pack_env):
    # Construct the command to run the shell script with parameters
    command = [
        './bash_scripts/run_prepare.sh',
        rosetta_main_dir,
        pdb_fn,
        str(relax_nstruct),
        out_dir_base,
        conda_pack_env
    ]
    
    # Run the shell script
    try:
        result = subprocess.run(command, check=True, text=True, capture_output=True)
        output_directory = extract_output_directory(result.stdout)
        # print('found output dir:',output_directory)
        # output_directory='output/prepare_outputs/2qmt_2024-08-27_21-52-35'
        if output_directory:
            print_colored("✅ Prepare.py executed successfully!", '32')  # Green color
            # print(f"Output directory: {output_directory}")
            pdb = pdb_fn.split(os.sep)[-1].split('.')[0]
            # print(pdb)
            file_to_transfer = f"{output_directory}/{pdb}_p.pdb"
            # Define the file to transfer (assuming you have a specific file to look for, e.g., 'prepared.pdb')
            # file_to_transfer = Path(output_directory) / 'prepared.pdb'
            target_directory = 'pdb_files/prepared_pdb_files'

            # print(os.getcwd())
            # Check if the file exists and transfer it
            
            transfer_file(file_to_transfer, target_directory, '../..')
        else:
            print_colored("✅ Script executed successfully, but output directory not found!", '33')  # Yellow color
            print(result.stdout)
    
    except subprocess.CalledProcessError as e:
        print_colored("❌ Script execution failed!", '31')  # Red color
        print(f"Error details:\n{e.stderr}")




def human_format(num):
    """https://stackoverflow.com/questions/579310/formatting-long-numbers-as-strings-in-python"""
    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])



def get_variants_fn(pdb_fn,variants_to_generate,max_subs,min_subs,seed):
    out_fn_template = "{}_subvariants_TN-{}_MAXS-{}_MINS-{}_{}-DB-{}-{}_RS-{}.txt"
    
    out_fn_template_args = [
        basename(pdb_fn).rsplit('.', 1)[0],
        human_format(variants_to_generate),
        max_subs,
        min_subs,
        "filtered",
        0, # currently the db hash will always be zero 458 of variants.py
        basename(pdb_fn).rsplit('.', 1)[0],
        seed
    ]
    
    out_fn = out_fn_template.format(*out_fn_template_args)
    return out_fn

def run_variant_script(
    pdb_fn,
    variants_to_generate,
    max_subs,
    min_subs,
    seed=0
):

    out_fn = get_variants_fn(pdb_fn, variants_to_generate, max_subs, min_subs, seed)
    params = f"\t variants to generate: {variants_to_generate}\n\t maximum substitutions: {max_subs} \n\t minimum substitutions: {min_subs} \n\t random seed: {seed} \n\t filename: {out_fn}"

    if os.path.isfile(f"../../variant_lists/{out_fn}"):
        print_colored(f"❌ A variant file with these parameters already exist: \n {params} \n -->Either run this function again with new parameters or move onto next step.", '31')  # red color
        return 
    else:
        print_colored(f"✅ A variant file with these parameters doesn't exist: \n {params} \n--> Generating variants now ⌛", '32')  # Green color
        
    command = [
        './bash_scripts/run_variants.sh',
        pdb_fn,
        str(variants_to_generate),
        str(max_subs),
        str(min_subs),
        str(seed)
    ]

    # Run the shell script
    try:
        result = subprocess.run(command, check=True, text=True, capture_output=True)
        print_colored("✅ Successfully generate variants!", '32')  # Green color
        
    except subprocess.CalledProcessError as e:
        print_colored("❌ Script execution failed!", '31')  # Red color
        print(f"Error details:\n{e.stderr}")


def post_process_rosetta_download(job_name): 
    untar_file_with_progress(f'condor/{job_name}/output.tar.gz',f'condor/{job_name}/output/rosetta_download')
    
    for suffix in ['aa','ab','ac']:
        file_path=f'condor/{job_name}/output/rosetta_download/output/squid_rosetta/rosetta_min_enc.tar.gz.{suffix}'
        dest_dir=f'downloads'
        if not os.path.isfile(file_path):
            print_colored(f"❌ Could not find all rosetta file:{file_path} for {job_name}", '31')
            print_colored(f"❌ Please redo the Downloading Rosetta section above and wait until the download of rosetta job has completed", '31')
            print_colored(f"💡 Notice: This function could lead to errors if using a different version of Rosetta than the default version", '33')
            print_colored(f"💡 Notice: Feel free to post an issue on github if any problems with downloading rosetta", '33')
            return 
        else:
            print_colored(f"✅ Found Rosetta File: {file_path}", '32') 
            transfer_file(file_path, dest_dir, cwd='.')

    # move the files over ...
    
    # for osdf in ['rosetta','python']:
    #     osdf_fn=f'htcondor/templates/osdf_{osdf}_distribution.txt'
    #     with open(osdf_fn,'r') as f: 
    #         out=f.read()
        
    #     out=out.replace('full_path',os.getcwd())
    
    #     with open(f'../htcondor/templates/osdf_{osdf}_distribution.txt','w') as f:
    #         f.write(out)

     
    # we also need to decode rosetta 
    decode_rosetta()

    # then untar the binaries ...
    file_path = "downloads/rosetta_min.tar.gz"
    extract_dir = "rosetta"
    untar_file_with_progress(file_path, extract_dir)

# variant file 
# pdb file 
# osdf files  - probably should be changed earlier 
# usual tarring process. 

def load_lines(fn: str):
    """ loads each line from given file """
    lines = []
    with open(fn, "r") as f_handle:
        for line in f_handle:
            lines.append(line.strip())
    return lines

def prepare_rosetta_run(
    job_name,
    pdb_file_name,
    variant_fns,
    verbose=False
):
    # the relative path to the repo root
    rel_path_to_root = "../../"

    # paths to various directories (from the repo root)
    vl_dir = "variant_lists"
    prepared_pdb_dir = "pdb_files/prepared_pdb_files"
    run_defs_dir = "htcondor/run_defs"

    # full relative paths to the directories
    rel_path_to_run_defs = f"{rel_path_to_root}{run_defs_dir}"
    rel_path_to_vls = f"{rel_path_to_root}{vl_dir}"

    # check if the job name is already taken
    # if it is, print an error message and return
    # otherwise, create the job directory
    runs = os.listdir(rel_path_to_run_defs)
    if job_name in runs:
        print_colored(f"❌ Job name {job_name} not is available, please specify a new job name", '31')
        # return 
    else:
        print_colored(f"✅ Job name {job_name} is available, preparing rosetta job", '32')
    os.makedirs(f"{rel_path_to_run_defs}/{job_name}", exist_ok=True)
    
    pdb_fn = f'{pdb_file_name.split(".")[0]}_p.pdb'
    pdb_fp = f'{prepared_pdb_dir}/{pdb_fn}'

    # make sure the variant files exist
    total_variants = 0
    for variant_fn in variant_fns:
        variant_fp = f"{rel_path_to_vls}/{variant_fn}"
        if not os.path.isfile(variant_fp):
            print_colored(f"❌ Variant file does not exist: {variant_fn}\nPlease run the previous section to generate variants.", '31')   
            return
        else:
            num_variants = len(load_lines(variant_fp))
            print_colored(f"✅ Variant file exists: {variant_fn}", '32') 
            total_variants += num_variants
    print_colored(f"✅ Total number of variants: {total_variants}", '32')

    # open the template run def file and replace the placeholders
    # then save it to the run defs directory
    run_def_template_fn = "templates/energize_run_template.txt"
    with open(run_def_template_fn, 'r') as f:
        contents = f.read()

    contents = contents.replace('{job_name}', job_name)
    # generate the full paths from the repository root dir to the variant files
    variant_fns_full = [f"{vl_dir}/{variant_fn}" for variant_fn in variant_fns]
    contents = contents.replace('{variant_file}', "\n".join(variant_fns_full))

    # fill in additional data files (python environment and rosetta binaries)
    addtl_files = [
        "notebooks/osg/downloads/rosetta_min_enc.tar.gz.aa",
        "notebooks/osg/downloads/rosetta_min_enc.tar.gz.ab",
        "notebooks/osg/downloads/rosetta_min_enc.tar.gz.ac",
        "notebooks/osg/downloads/metl-sim_2025-02-13.tar.gz"
    ]
    contents = contents.replace(
        '{additional_data_files}',
        "\n".join(addtl_files)
    )

    param_fn = f"{rel_path_to_run_defs}/{job_name}/htcondor.txt"
    with open(param_fn,'w') as f:
        f.write(contents)

    # run the main condor prep script using the run def we created
    command = [
        './bash_scripts/run_condor.sh',
        f"{run_defs_dir}/{job_name}/htcondor.txt"
    ]

    try:
        result = subprocess.run(command, check=True, text=True, capture_output=True)
         # Print stdout and stderr from the bash script
        if verbose: 
            print("Standard Output:\n", result.stdout)
            print("Standard Error:\n", result.stderr)
        print_colored("✅ Successfully prepared OSG run!", '32')  # Green color

    except subprocess.CalledProcessError as e:
        print_colored("❌ Script execution failed to prepare OSG run!", '31')  # Red color
        print(f"Error details:\n{e.stderr}")

    # export things here maybe 

    # untar the arguments file here as well. 

    # edit condor.py such that if the github tag is "notebooks" then 
    # it automatically just tar's up everything instead. 
    # then no need to worry about pdb file either, because it just works. 
    # just need to figure out how to rename the title folder metl-sim-notebooks

def run_post_process_script(job_name,verbose=False):
    
    command = ['./bash_scripts/run_post_process.sh',job_name]
    final_file=f'condor/{job_name}/processed_run/energies_df.csv'
    if os.path.exists(final_file):
        print_colored(f"💡 Notice:{job_name} all ready post processed, loading pandas dataframe", '33')  # yellow color

    else:
        try:
            result = subprocess.run(command, check=True, text=True, capture_output=True)
             # Print stdout and stderr from the bash script
            if verbose: 
                print("Standard Output:\n", result.stdout)
                print("Standard Error:\n", result.stderr)
            print_colored(f"✅ Successfully post process job name {job_name}", '32')  # Green color
        
        
        except subprocess.CalledProcessError as e:
            print_colored(f"❌ Script execution failed to post process {job_name}!", '31')  # Red color
            print(f"Error details:\n{e.stderr}")


    df=pd.read_csv(final_file)

    return df

    




