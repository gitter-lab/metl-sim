# HTCondor Run Arguments

This directory contains argument files for [condor.py](../../code/condor.py).
These files define the condor run by specifying the run name, variant list, etc.
Then, [condor.py](../../code/condor.py) generates a folder that can be uploaded directly the submit node containing everything needed to run the job.
The folder contains the HTCondor submit file, the main executable, the variant lists for each job, and any additional files needed for the HTCondor run.