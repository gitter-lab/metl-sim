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


def create_directory_and_copy_items(new_dir, items_to_copy):
    # Create the new directory if it doesn't exist
    os.makedirs(new_dir, exist_ok=True)
    # print(f"✅ Directory '{new_dir}' created")

    # Copy each item (file or directory) into the new directory
    for item in items_to_copy:
        destination = os.path.join(new_dir, os.path.basename(item))
        
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
        if not check_directory_exists(job_name):
            return  
        elif job_type=='helloworld': 
            ## now construct the directory 
            print(f"\033[92m✅ Setting up job type `helloworld`\033[0m")

            # must specify file paths and submit jobs
            submit_file_path = "submit.sub"
            working_directory = f"condor/{job_name}"
            
            create_directory_and_copy_items(working_directory,['condor/practice/'])
            
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
            cwd=working_directory  # Specify the working directory here
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
    if 'Job terminated' in job_output:
        match = re.search(r'Job terminated.*exit-code (\d+)', job_output, re.DOTALL)
        # print('match code:',match)
        if match is None: 
            f+=1
        else:
            exit_code = match.group(1)
            assert exit_code=='0'
            c+=1 
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



def untar_file_with_progress(file_path, extract_dir,filetype='gz'):
    try:
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




def download_file(url, output_path):
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
    
    except Exception as e:
        # Handle any other exceptions and output failure message in red
        print(f"\033[91m❌ Failure: {str(e)}\033[0m")


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
    