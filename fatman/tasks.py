
import bz2
from collections import OrderedDict
from urllib.parse import urlsplit
import datetime as dt

from ase.units import kcal, mol

from celery.utils.log import get_task_logger
from celery import group

from sqlalchemy import and_
from sqlalchemy.orm import joinedload, contains_eager, aliased

from . import capp, resultfiles, tools, db, cache
from .models import (
    Result,
    Task,
    Method,
    Test,
    TestResult,
    Task2,
    Calculation,
    TaskStatus,
    TestResult2,
    TestResult2Collection,
    TestResult2Calculation,
    BasisSet,
    Pseudopotential,
    )

from .tools import (
    json2atoms,
    parsers,
    checks,
    nodehours_from_job_data,
    )
from .tools.deltatest import deltatest_ev_curve
from .tools.gmtkn import GMTKN_COEFFICIENTS


logger = get_task_logger(__name__)


@capp.task
def postprocess_result_files(update=False):
    """Postprocess all results files.
    Returns a tuple of rids and a group task."""

    query = (db.session.query(Result.id)
             .filter(Result.filename != None)
             .all())

    rids = [r.id for r in query]

    return (rids, group(postprocess_result_file.s(r, update)
                        for r in rids)())


@capp.task
def postprocess_result_file(rid, update=False):
    """Parse the file uploaded for a result.
    Set update to True to re-parse the file and update already present data"""

    result = (Result.query
              .options(joinedload("task")
                       .joinedload("method"))
              .get(rid))

    if result.data and not update:
        logger.warning(("Parsed data available and update=False"
                        ", skipping file parsing for result id %s"),
                       rid)
        return False

    if not result.filename:
        logger.error("Missing filename for result id %s", rid)
        return False

    filepath = resultfiles.path(result.filename)
    code = result.task.method.code

    with bz2.open(filepath, mode='rt') as infile:
        try:
            data = parsers.get_data_from_output(infile, code)
        except tools.OutputParseError as exc:
            logger.error("Parsing %s for result id %s failed: %s",
                         filepath, rid, exc)
            return False

    logger.info("Parsing %s for result id %s succeeded", filepath, rid)

    if result.data is None:
        result.data = data
    else:
        # merging works only for the top-level dict,
        # nested dicts/lists get overwritten
        result.data.update(data)

    db.session.commit()

    return True


@capp.task(bind=True)
def calculate_deltatest(self, tid, rid, trid=None):
    """Calculate the Δ-value for a given test ID `tid`,
    including the result with ID `rid`.
    If `trid` is given, update the respective TestResult instead of
    creating a new entry"""

    test = Test.query.get(tid)
    method = (Method.query
              .join(Task)
              .join(Result)
              .filter(Result.id == rid)
              .one())

    # select all results which share the same method
    # and are from the same test (deltatest_<El>_<Vol>)
    results = (Result.query
               .join(Task)
               .join(Method)
               .join(Test)
               .options(contains_eager(Result.task))
               .filter(Method.id == method.id, Test.id == test.id))

    if results.count() < 5:
        logger.info(("Not enough datapoints to calculate %s value"
                     " for Method %s using result %s, skipping"),
                    test.name, method.id, rid)
        return False

    if results.count() > 5:
        logger.critical(("More than 5 elements found to calculate %s value"
                         " for Method %s using result %s"),
                        test.name, method.id, rid)
        return False

    for result in results:
        if 'total_energy' not in result.data.keys():
            logger.info(("total_energy missing for %s to calculate %s value"
                         " for Method %s from result %s, skipping"),
                        result.id, test.name, method.id, rid)
            return False

    lock_id = '{}-lock-{}-method-{}'.format(self.name, test.name, method.id)
    if not cache.cache.add(lock_id, True, 60*60):
        # another task is already calculating the deltavalue for this result
        logger.info(("Skipping deltatest calculation for %s using Method %s"
                     ", another calculation task is already running"),
                    test.name, method.id)
        return False

    try:
        energies = []
        volumes = []
        natom = 0

        for result in results:
            struct = json2atoms(result.task.structure.ase_structure)
            natom = len(struct.get_atomic_numbers())

            energies.append(result.data['total_energy']/natom)
            volumes.append(struct.get_volume()/natom)

        v, e, B0, B1, R = deltatest_ev_curve(volumes, energies)

        if isinstance(v, complex) or (v == "fail"):
            result_data = {"_status": "unfittable"}
        else:
            result_data = {"_status": "fitted",
                           "V": v, "E0": e, "B0": B0, "B1": B1, "R": R}

        if trid:
            testresult = TestResult.query.get(trid)
            testresult.result_data = result_data
        else:
            testresult = TestResult(test=test,
                                    method=method,
                                    result_data=result_data)
        db.session.commit()

        logger.info("Calculated deltatest value for %s using Method %s",
                    test.name, method.id)

    finally:
        cache.cache.delete(lock_id)

    # only if no exception was thrown somewhere above
    return True


@capp.task(bind=True)
def calculate_GMTKN(self, tid, rid, trid=None):
    """Calculate the GMTKN-value for a given test ID `tid`,
    including the result with ID `rid`.
    If `trid` is given, update the respective TestResult instead of
    creating a new entry"""

    test = Test.query.get(tid)
    method = (Method.query
              .join(Task)
              .join(Result)
              .filter(Result.id == rid)
              .one())

    # select all results which share the same method
    # and are from the same test (GMTKN_<sub-set>)
    results = (Result.query
               .join(Task)
               .join(Method)
               .join(Test)
               .options(contains_eager(Result.task))
               .filter(Method.id == method.id, Test.id == test.id))

    sub_db = test.name[6:]
    all_structures = set([item[0]
                          for sublist in GMTKN_COEFFICIENTS[sub_db]
                          for item in sublist])

    results_count = results.count()
    required_count = len(all_structures)
    if results_count < required_count:
        logger.info(("Only %d of %d required results to calculate %s available"
                     ", skipping"), results_count, required_count, test.name)
        return False

    for result in results:
        if 'total_energy' not in result.data.keys():
            logger.info(("total_energy missing for %s to calculate %s value"
                         " for Method %s from result %s, skipping"),
                        result.id, test.name, method.id, rid)
            return False

    lock_id = '{}-lock-{}-method-{}'.format(self.name, test.name, method.id)
    if not cache.cache.add(lock_id, True, 60*60):
        # another task is already calculating the deltavalue for this result
        logger.info(("Skipping GMTKN calculation for %s using Method %s"
                     ", another calculation task is already running"),
                    test.name, method.id)
        return False

    try:
        result_data = {"_status": "incomplete", "energies": []}

        prefix = "gmtkn30_{}_".format(sub_db)
        struct2energies = OrderedDict([(x.task.structure.name,
                                        x.data['total_energy'])
                                       for x in results])
        for rxn in GMTKN_COEFFICIENTS[sub_db]:
            etot = 0.
            for struct, coeff in rxn:
                try:
                    etot += coeff*struct2energies[prefix+struct]
                except KeyError:
                    logger.warning(("Result for structure %s%s missing"
                                    ", ignored to calculate %s"),
                                   prefix, struct, test.name)

            logger.debug("%s: %f/%f", rxn, etot/kcal*mol, etot)
            result_data["energies"].append(etot)

        result_data["_status"] = "done"

        if trid:
            testresult = TestResult.query.get(trid)
            testresult.result_data = result_data
        else:
            testresult = TestResult(test=test,
                                    method=method,
                                    result_data=result_data)
        db.session.commit()

        logger.info("Calculated GMTKN values for %s using Method %s",
                    test.name, method.id)

    finally:
        cache.cache.delete(lock_id)

    return True


@capp.task
def postprocess_result(rid, update=False):
    # check whether there is already testresult using this result
    # and the same method
    trid = (db.session.query(TestResult.id)
            .join(Test)
            .join(Task)
            .join(Result)
            .filter(Task.method_id == TestResult.method_id,
                    Result.id == rid)
            .scalar())

    if trid:
        if update:
            logger.info("Updating TestResult %s for result %s",
                        trid, rid)
        else:
            logger.warning(("Found TestResult %s for result %s"
                            ", skipping postprocessing"),
                           trid, rid)
            return False

    test = (Test.query
            .join(Task)
            .join(Result)
            .filter(Result.id == rid)
            .one())

    if test.name.startswith('deltatest'):
        return calculate_deltatest(test.id, rid, trid)
    elif test.name.startswith('GMTKN'):
        return calculate_GMTKN(test.id, rid, trid)
    else:
        logger.error("No TestResult process function found for Test %s",
                     test.name)
        return False


@capp.task
def generate_calculation_results(calc_id, update=False):
    """
    Parse the outputs attached to the first succeeded task for the given calculation,
    if the calculation does not have any results yet.

    Args:
        update: update the results if they already exist, careful: test results
                based on this calculation are not automatically updated!
    """
    calc = (Calculation.query
            .with_for_update(of=Calculation)
            .options(joinedload('code'))
            .get(calc_id))

    if calc is None:
        logger.error("calculation %s: not found")
        return False

    if calc.results_available and not update:
        logger.info("calculation %s: has already a result and update=False, skipping", calc.id)
        return False

    task = (calc.tasks_query
            .join(Task2.status)
            .filter(TaskStatus.name == 'done')
            .order_by(Task2.mtime.desc())
            .first())

    if task is None:
        logger.info("calculation %s: no successfully finished task found, skipping", calc.id)
        return False

    logger.info("calculation %s: taking results from task %s", calc.id, task.id)

    if calc.code.name == 'CP2K':
        resultfile_name = 'calc.out'
    else:
        logger.error("calculation %s: no parser available (yet) for code %s",
                     calc.id, task.calculation.code.name)
        return False

    try:
        # the artifacts are already loaded via lazy='joined', can't use task.outfiles for querying
        artifact = [a for a in task.outfiles if a.name == resultfile_name][0]
    except IndexError:
        logger.info("calculation %s: no artifact with name '%s' linked to task %s",
                    calc.id, resultfile_name, task.id)
        return False

    scheme, nwloc, path, _, _ = urlsplit(artifact.path)

    results = None

    if scheme == 'fkup' and nwloc == 'results':
        filepath = resultfiles.path(path[1:])

        # Artifact.name contains a full path, including possible subdirs
        compressed = artifact.mdata.get('compressed', None)

        if compressed is None:
            with open(filepath, 'r') as fhandle:
                results = parsers.get_data_from_output(fhandle, calc.code.name)
        elif compressed == 'bz2':
            with bz2.open(filepath, mode='rt') as fhandle:
                results = parsers.get_data_from_output(fhandle, calc.code.name)
        else:
            logger.error("unsupported compression scheme found: %s", compressed)
            return False

        try:
            results['checks'] = checks.generate_checks_dict(results, calc.code.name, calc.test.name)
        except NotImplementedError:
            logger.error("no data checking implemented for code: %s", calc.code.name)

    else:
        logger.error("unsupported storage scheme found: %s", scheme)
        return False

    if not results:
        logger.error("calculation %s: no parseable data found in artifact %s",
                     calc.id, artifact.id)
        return False

    calc.results = results
    db.session.commit()

    return True


@capp.task(bind=True)
def generate_all_calculation_results(self, update=False):
    """
    Parse all calculation task outputs and generate the results
    if not already present.

    Args:
        update: rewrite the results even if they already exist

    Returns:
        A tuple of a list of calculation ids and a group task
    """

    # select only calculations where the latest task is done
    t2 = aliased(Task2)
    calcs = (db.session.query(Calculation.id)
             .join(Task2)
             .outerjoin(t2, and_(Calculation.id == t2.calculation_id, Task2.ctime < t2.ctime))
             .filter(t2.id == None)
             .join(Task2.status)
             .filter(TaskStatus.name == 'done')
             .order_by(Task2.mtime.desc()))

    if not update:
        calcs = calcs.filter(Calculation.results_available == False)

    # execute the query to check whether we have anything to do
    calcs = calcs.all()

    if not calcs:
        # Celery does not like empty groups, end it here
        logger.info("no calculations found which require processing")
        return

    # replace the task with a group task for the single calculations
    raise self.replace(group(generate_calculation_results.s(c.id, update) for c in calcs))


@capp.task(bind=True)
def generate_test_result_deltatest(self, calc_id, update=False):
    """
    Calculate the Δ-test value using a given calculation id.
    Creates a new Test Result in a Test Result Collection named
    after the Calculation Collection of the given calculation.

    Args:
        calc_id: the UUID of the calculation to be included in the generated test result
    """

    updated = False

    # first get the specified calculation from the DB
    calc = (Calculation.query
            .options(joinedload('test'))
            .options(joinedload('collection'))
            .get(calc_id))

    # get the element from the first (and only) pseudo
    element = calc.pseudos[0].element
    # get the basis set family ID for the first (and only) default basis set
    basis_set_family_id = next(
        b.basis_set.family_id for b in calc.basis_set_associations
        if b.btype == 'default' and b.basis_set.element == element)

    # from the same calculation collection as the given calculation,
    # get the calculations for the same elements (selected via pseudos)
    calcs = (Calculation.query
             # AND lock all calculations being part of this test result:
             # This will prevent any changes to the calculation objects while we read them
             # but will also make parallel executions of this function run serialized from here on
             # for calculations going to be used in the same test result
             # IMPORTANT: this has to come before checking for available results to ensure proper locking
             .with_for_update(of=Calculation)
             .filter_by(collection=calc.collection)
             .filter(Calculation.results_available)  # ignore calculations with no test results
             .options(joinedload('structure'))
             .options(joinedload('code'))
             .join(Calculation.pseudos)
             .filter(Pseudopotential.element == element)
             .join(Calculation.basis_sets)
             .filter(BasisSet.family_id == basis_set_family_id)  # only match calcs with the same ORB basis set
             .limit(6)  # limit to one more than we can actually use, to catch errors
             .all())

    # exit early again in case we do not have enough or too many datapoints

    if len(calcs) < 5:
        logger.info("Not enough datapoints to calculate deltatest value using calculation %s", calc.id)
        return False

    if len(calcs) > 5:
        logger.critical("More than 5 elements found to calculate deltatest value using calculation %s", calc.id)
        return False

    # now fetch the only testresult if already available
    tr = (calc.testresults_query
          # Limit the Test Results to the test the calculation was meant for (which should be the ∆-test)
          .filter(TestResult2.test == calc.test)
          .one_or_none())

    if tr is None or update:

        result_data = {'element': element}

        for calc in calcs:
            if not calc.results or 'total_energy' not in calc.results.keys():
                logger.error("total_energy missing for calculation %s to calculate deltatest value", calc.id)
                return False

        energies = []
        volumes = []
        nodehours = {
            'no_current_tasks': 0,
            'no_current_tasks_accounted': 0,
            'current_total': dt.timedelta(),
            }

        for calc in calcs:
            struct = json2atoms(calc.structure.ase_structure)

            natoms_struct = len(struct.get_atomic_numbers())
            volumes.append(struct.get_volume()/natoms_struct)  # the per-atom volume is independant of a MULTIPLE_UNIT_CELL

            # When normalizing the energy, we have to take the effect of a MULTIPLE_UNIT_CELL into account:
            # the parser extracts the final number of atoms per Kind from the ATOMIC KIND INFORMATION (AKI) section,
            # since the deltatest has only one real kind, but may contain multiple pseudo-kinds to define
            # broken symmetries, we sum here over all natoms in the atomic_kind_information entries
            if 'atomic_kind_information' in calc.results:
                natoms_sim = sum(e['natoms'] for e in calc.results['atomic_kind_information'])
            else:
                # as a fallback we use the natoms from the structure (for results generated prior to the AKI parsing)
                natoms_sim = natoms_struct

            energies.append(calc.results['total_energy']/natoms_sim)

            nodehours['no_current_tasks'] += 1
            try:
                jobname = 'fatman.%s' % calc.current_task.id
                nodehours['current_total'] += nodehours_from_job_data(calc.current_task.data['runner']['commands'][jobname])
                nodehours['no_current_tasks_accounted'] += 1
            except (KeyError, AttributeError):
                pass

            if calc.structure.name.endswith('1.00') and 'overlap_matrix_condition_number' in calc.results:
                result_data['overlap_matrix_condition_number@V0'] = calc.results['overlap_matrix_condition_number']

        # convert timedelta to a fraction of hours
        nodehours['current_total'] = nodehours['current_total'].total_seconds() / 3600

        result_data['nodehours'] = nodehours

        # If the energy was calculated using CP2K, we have to convert from a.u. to eV,
        # since the reference results are in eV
        if calc.code.name == "CP2K":
            energies = [e*27.2113860217 for e in energies]
        else:
            raise RuntimeError("Unknown unit of energy for code {}, unsave to continue generating results", calc.code.name)

        # sort the values by increasing volume
        volumes, energies = (list(t) for t in zip(*sorted(zip(volumes, energies))))

        result_data.update({
            'energies': energies,
            'volumes': volumes,
            })

        coeffs = deltatest_ev_curve(volumes, energies)

        if isinstance(coeffs[0], complex) or (coeffs[0] == "fail"):
            result_data['status'] = "unfittable"
        else:
            result_data.update({
                'status': "fitted",
                'coefficients': dict(zip(('V', 'E0', 'B0', 'B1', 'R'), coeffs)),
                })

        # make some additional checks to tag bad values
        result_data['checks'] = {
            'min_at_V0': all(e > energies[2] for e in energies[:2] + energies[3:]),
            'min_inside': any(e < energies[0] and e < energies[-1] for e in  energies[1:-2]),
            'all_converged': all(c.results.get('checks', {}).get('converged', False) for c in calcs),
            }

        logger.info("calculation %s: calculated deltatest value for element %s in collection %s",
                    calc.id, element, calc.collection.id)

        if tr:
            logger.info("calculation %s: update=True specified, updating the existing test result %s",
                        calc.id, tr.id)
            tr.data = result_data
            tr.calculations.clear()
            tr.calculations.extend(calcs)
        else:
            logger.info("calculation %s: creating new test result", calc.id)
            tr = TestResult2(test=calc.test, data=result_data, calculations=calcs)
            db.session.add(tr)

        updated = True

    # get or create a new test result collection with the same name as the calc collection
    trc = (TestResult2Collection.query
           .filter_by(name=calc.collection.name)
           .first())

    if not trc:
        trc = TestResult2Collection(name=calc.collection.name,
                                    desc="{} (autogenerated)".format(calc.collection.desc))
        db.session.add(trc)
        updated = True

    if tr not in trc.testresults:
        trc.testresults.append(tr)
        updated = True

    db.session.commit()
    return updated


@capp.task
def generate_test_result_GW100(calc_id, update=False):
    """
    Creates or updates a GW100 test result (which is currently a copy of a part of the calculation results)
    for the given calculation id.

    Args:
        calc_id: the UUID for which to generate a test result
    """

    updated = False

    calc = (Calculation.query
            .with_for_update(of=Calculation)  # lock this calculation object to enforce synchronization here
            .options(joinedload('test'))
            .options(joinedload('collection'))
            .filter(Calculation.results_available, Calculation.id == calc_id)
            .one_or_none())

    if not calc:
        logger.error("calculation %s: no results available", calc_id)
        return False

    # figure out whether there is already a testresult for the GW100 test for this calculation
    # we assume here there is at most one or then None GW100 testresult for this calculation
    tr = (calc.testresults_query
          # Limit the Test Results to the test the calculation was meant for (we can't handle other tests here, obviously):
          .filter(TestResult2.test == calc.test)
          # ignore Test Results only present in non-autogenerated Test Result Collections
          # now we want only the ID of the first one
          .one_or_none())

    if tr is None or update:
        try:
            result_data = {
                'checks': calc.results['checks'],
                'total_energy': calc.results['total_energy'],
                'GW_quasiparticle_energies': {},
                }

            try:
                jobname = 'fatman.%s' % calc.current_task.id
                nodehours = nodehours_from_job_data(calc.current_task.data['runner']['commands'][jobname])
                result_data['nodehours'] = nodehours.total_seconds() / 3600
            except (KeyError, AttributeError):
                pass

            gw_data = calc.results['GW_quasiparticle_energies']

            result_data['GW_quasiparticle_energies']['HOMO'] = max(
                filter(lambda e: e['MO_type'] == 'occ', gw_data),
                key=lambda e: e['MO_nr'])
            result_data['GW_quasiparticle_energies']['LUMO'] = min(
                filter(lambda e: e['MO_type'] == 'vir', gw_data),
                key=lambda e: e['MO_nr'])

        except KeyError:
            logger.warning("calculation %s: no GW quasiparticle energy entries in data found", calc.id)
            return False

        if tr:
            logger.info("calculation %s: update=True specified, updating the existing test result %s",
                        calc.id, tr.id)
            tr.data = result_data
            updated = True
        else:
            logger.info("calculation %s: creating new test result", calc.id)
            tr = TestResult2(test=calc.test, data=result_data, calculations=[calc])
            db.session.add(tr)
            updated = True

    trc = TestResult2Collection.query.filter_by(name=calc.collection.name).one_or_none()

    # the following we are doing unconditionally of the update flag by intention
    if not trc:
        trc = TestResult2Collection(name=calc.collection.name, desc="{} (autogenerated)".format(calc.collection.desc))
        db.session.add(trc)
        updated = True

    if tr not in trc.testresults:
        trc.testresults.append(tr)
        updated = True

    db.session.commit()
    return updated


@capp.task
def generate_test_result(calc_id, update=False):
    """
    Generate test result using the given calculation id
    """

    calc = (Calculation.query
            .options(joinedload('test'))
            .get(calc_id))

    if calc.test.name == 'deltatest':
        return generate_test_result_deltatest(calc.id, update)

    if calc.test.name == 'GW100':
        return generate_test_result_GW100(calc.id, update)

    logger.error("No test result process function found for test %s", calc.test.name)
    return False


@capp.task(bind=True)
def generate_all_test_results(self, update=False):
    """
    Generate all possible test results based on the available calculation results,
    if there is no calculation result yet for a calculation.

    Args:
        update: updates the test results if they already exist

    Returns:
        A tuple of a list of test result ids and a group task
    """

    # basic filter is on whether a result is available or not
    calcs = (db.session.query(Calculation.id)
             .filter(Calculation.results_available))

    if not update:
        # find all calculations where there is no test result with the same test
        # as the calculation was initially created for.
        calcs = (calcs
                 # We have to manually join the m:n relationship between Calculations and TestResults:
                 .outerjoin(TestResult2Calculation)
                 .outerjoin(TestResult2,
                            and_(Calculation.id == TestResult2Calculation.c.calculation_id,
                                 # to be able to specify an additional join condition:
                                 Calculation.test_id == TestResult2.test_id))
                 # now filter out all results which have an associated test result available
                 .filter(TestResult2.id == None))

    # execute the query to check whether we have anything to do
    calcs = calcs.all()

    if not calcs:
        # Celery does not like empty groups, end it here
        logger.info("no calculations/testresults found which require processing")
        return

    # replace the task with a group task for the single calculations
    raise self.replace(group(generate_test_result.s(c.id, update) for c in calcs))

#  vim: set ts=4 sw=4 tw=0 :
