#!/usr/bin/env python

from fatman.models import *
from datetime import datetime
from fatman.tools import Json2Atoms
from ase.test.tasks import dcdft
from ase.units import kJ, Ry


def compute_results():
    """retrieve all the datapoints for the various tests that have been done and compute the deltatest scores"""
    created_count = 0
    attempt_count = 0

    q = Test.select().join(Task).join(ResultWithoutTestResult).group_by(Test)
    available_tests = list(q)

    q = Method.select().join(Task).join(ResultWithoutTestResult).group_by(Method)
    available_methods = list(q)
    
    for t in available_tests:
        #print "TEST: ", t.name
        for m in available_methods:
            #print "  METHOD: ", m

            q = ResultWithoutTestResult.select().join(Task).where((Task.test == t)&(Task.method==m))

            if len(q)>0:   #it can happen that no data is available for a particular method 
                created = store_test_result(list(q))
            else:
                created = False

            if created:
                created_count+=1
            attempt_count +=1
            #print "created:", created 

    return created_count, attempt_count


def store_test_result(testset):
    """Take a list of 'result' rows and process them according to the type of test that was performed.
       Store a Row object in the TestResults table"""

    testname = testset[0].task.test.name
    method = testset[0].task.method
    test = testset[0].task.test

    ctime = datetime.now()

    if "deltatest" in testname:

        if len(testset) < 5: return None
        #for a deltatest we have to have (at least) 5 structure/volume pairs, to which we fit a curve

        energies = []
        volumes = []
        natom = 0


        for x in range(len(testset)):
            struct = Json2Atoms(testset[x].task.structure.ase_structure)
            natom = len(struct.get_atomic_numbers())

            energies.append(testset[x].energy/natom)
            volumes.append(struct.get_volume()/natom)
        
        v,e,B0,B1,R = ev_curve(volumes, energies)
        if isinstance(v,complex) or (v=="fail"):
            result_data = {"_status" : "unfittable"}
        else:
            result_data = {"_status" : "fitted", 
                           "V"       : v,
                           "E0"      : e,
                           "B0"      : B0,
                           "B1"      : B1,
                           "R"       : R }
        

    elif "GMTKN" in testname:
        from fatman.tools import gmtkn_coefficients as gc
        from ase.units import kcal, mol

        sub_db = testname[6:]
        all_structures = set([item[0] for sublist in gc[sub_db] for item in sublist] )

        if len(testset)<len(all_structures): return None
        #if we don't have all needed data points, we do nothing.

        result_data = {"_status" : "incomplete", 
                       "energies": []}
                       
        prefix = "gmtkn30_" + testname[6:] + "_"
        all_energies = dict([(x.task.structure.name, x.energy) for x in testset])
        for rxn in gc[sub_db]:
            etot=0.
            for struct, c in rxn:
                try:
                    etot += c*all_energies[prefix+struct]
                except KeyError:
                    pass

            #print rxn, etot/kcal*mol, etot
            result_data["energies"].append(etot)

    else:
        raise RuntimeError("Can't generate a Result entry for test %s" % testname)

    res, created = TestResult.get_or_create(test=test, 
                             method=method,
                             defaults={'ctime': ctime,
                                       'result_data': result_data })

    if not created:
        assert res.result_data == result_data

    return created 

def ev_curve(volumes,energies):                                                                                                                                                                   
    structuredata = dcdft.DeltaCodesDFTCollection()                                                                                                                                                     
    eos = dcdft.FullEquationOfState(volumes, energies)                                                                                                                                                  
                                                                                                                                                                                                        
    try:                                                                                                                                                                                                     
        v,e,B0, B1, R = eos.fit()                                                                                                                                                                            
    except ValueError:
        print "failure"
        return "fail", "fail", "fail", "fail", "fail"
    else:
        return v,e,B0/kJ * 1.0e24, B1, R[0] 




if __name__=="__main__":
    created_count, attempt_count = compute_results()
    print "CREATED {} NEW ENTRIES FROM {} RESULTS.".format(created_count, attempt_count)            
