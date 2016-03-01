#!/usr/bin/env python

import requests, os
from fatman.tools import Json2Atoms
from codehandling import HandlerFactory
import os

SERVER = 'https://172.23.64.223'
TASKS_URL = SERVER + '/fatman/tasks'
RESULTS_URL = SERVER + '/fatman/results'
BASISSET_URL = SERVER + '/fatman/basis'
PSEUDOPOTENTIAL_URL   = SERVER + '/fatman/pseudo'

def main():
    """The fatman client queries the DB for new tasks and runs them until none are left"""

    while 1:
        #request a task
        req = requests.get(TASKS_URL, params={'limit': 1, 'status': 'new'}, verify=False)
        req.raise_for_status()

        #perhaps this could be replaced by daemon-like behavior: sleep, and check for new tasks after a few minutes
        tasks = req.json()
        if len(tasks) == 0:
            print('No task to run, exiting')
            return 0

        #set the task's status to pending
        req = requests.patch(SERVER + tasks[0]['_links']['self'], data={'status': 'pending', 'machine':os.uname()[1]}, verify=False)
        req.raise_for_status()
        task = req.json()

        try:
            #get structure and convert to ASE object
            struct_json = task['structure']['ase_structure']
            struct = Json2Atoms(struct_json)

            #which code to use with which settings?
            mymethod = task['method']
            if "kpoints" in struct.info["key_value_pairs"].keys():
                mymethod["kpoints"] = struct.info["key_value_pairs"]["kpoints"]
                #kindof a hack: kpoints are specified with each structure, but are in fact code parameters

            #REMOTE: get dicts containing the Pseudos and Basissets for all required chemical elements
            basis = requests.get(BASISSET_URL, data={'family':mymethod['basis_set'], 'element':set(struct.get_chemical_symbols())}, verify=False).json()
            pseudo = requests.get(PSEUDOPOTENTIAL_URL, data={'family':mymethod['pseudopotential'], 'element':set(struct.get_chemical_symbols())}, verify=False).json()

            if not "kind_settings" in mymethod.keys():
                mymethod["kind_settings"] = {}

            for x in set(basis.keys()) & set(pseudo.keys()):
                mymethod["kind_settings"][x] =  {"basis_set":basis[x], "potential":pseudo[x]}


            #create our code-running object with the relevant settings.
            codehandler = HandlerFactory(struct, mymethod)

            #REMOTE: update the task's status to "running"
            req = requests.patch(SERVER + task['_links']['self'], data={'status': 'running'}, verify=False)
            req.raise_for_status()
            task = req.json()

            #run the code
            e,output_file_path = codehandler.runOne()

            #REMOTE: throw the energy into the DB, get the id of the stored result
            req = requests.post(RESULTS_URL, data={'energy': e, 'task_id': task['id']}, verify=False)
            req.raise_for_status()
            done_task = req.json()
            
            #REMOTE: upload the output file
            os.system ("bzip2 {}".format(output_file_path))
            with open(output_file_path + ".bz2") as f:
                req = requests.post(SERVER + done_task["_links"]["self"]+'/file', files={'file':f}, verify=False)
                req.raise_for_status()


            #REMOTE: update the task's status to "done"
            req = requests.patch(SERVER + task['_links']['self'], data={'status': 'done'}, verify=False)
            req.raise_for_status()
            task = req.json()

        except :
            req = requests.patch(SERVER + task['_links']['self'], data={'status': 'error'}, verify=False)
            req.raise_for_status()


if __name__=="__main__":
    main()
