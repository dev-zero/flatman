
from io import StringIO, BytesIO
from collections import OrderedDict

import numpy as np
from ase import io as ase_io

from .cp2k import mergedicts, dict2cp2k

def generate_CP2K_inputs(settings, basis_sets, pseudos, struct, tagline, overrides=None):
    """
    Generate the inputs for CP2K based on the given data for CP2K

    Args:
        settings: CP2K-specific input settings dictionary
        basis_sets: List of tuples (type, id, element, family, basis)
        pseudos: List of tuples (id, element, family, ncore_el, pseudo)
        struct: A Python ASE atoms structure
        tagline: Comment line to add to generated files
        overrides: Input settings to be merged after autogenerating, just before generating the actual file

    Returns:
        a dictionary of (filename, bytebuf) objects
    """

    inputs = {}

    generated_input = {
        'global': {
            'project': "fatman.calc",
            },
        'force_eval': {
            'dft': {
                'basis_set_file_name': "./BASIS_SETS",
                'potential_file_name': "./POTENTIALS",
                'poisson': {
                    'periodic': None,
                    },
                },
            'subsys': {
                'cell': {  # filled out below
                    'a': None,  # filled out below
                    'b': None,
                    'c': None,
                    'periodic': None,
                    },
                'topology': {
                    'coord_file': "./struct.xyz",
                    'coord_file_format': 'XYZ',
                    },
                'kind': [],  # filled out below
                },
            },
        }

    periodic = "".join(axis*bool(enabled) for axis, enabled in zip("XYZ", struct.get_pbc()))
    if periodic == "":
        periodic = "NONE"

    generated_input['force_eval']['dft']['poisson']['periodic'] = periodic

    cell = {
        'a': (('[angstrom]',) + tuple(struct.get_cell()[0, :])),
        'b': (('[angstrom]',) + tuple(struct.get_cell()[1, :])),
        'c': (('[angstrom]',) + tuple(struct.get_cell()[2, :])),
        'periodic': periodic,
        }
    generated_input['force_eval']['subsys']['cell'] = cell

    if 'key_value_pairs' in struct.info:
        # it seems Python ASE is unable to handle nested dicts in
        # the Atoms.info attribute when writing XYZ, even though it
        # creates it in the first place
        # see https://gitlab.com/ase/ase/issues/60
        struct.info = dict(mergedicts(
            {k: v for k, v in struct.info.items() if k != 'key_value_pairs'},
            struct.info['key_value_pairs']))

    inputs['BASIS_SETS'] = BytesIO()
    inputs['BASIS_SETS'].write("# BASIS_SETS: {}\n".format(tagline).encode('utf-8'))

    # for the basis sets we have to be able to
    # lookup the entry by element
    kind = {s: {'_': s, 'element': s, 'basis_set': [], 'potential': None} for s in struct.get_chemical_symbols()}

    for btype, _, element, family, _ in basis_sets:
        kind[element]['basis_set'].append(('ORB' if btype == 'default' else btype.upper(), family))

    # to write the basis set we can drop the type and therefore avoid
    # writing a basis twice in case we use the same basis for different types
    for basis_set in set(b[1:] for b in basis_sets):
        inputs['BASIS_SETS'].write(("# Basis Set ID {0}\n"
                                    "{1} {2}\n"
                                    "{3}\n")
                                   .format(*basis_set)
                                   .encode('utf-8'))

    inputs['BASIS_SETS'].seek(0)

    inputs['POTENTIALS'] = BytesIO()
    inputs['POTENTIALS'].write("# POTENTIALS: {}\n".format(tagline).encode('utf-8'))
    for pseudo in pseudos:
        kind[pseudo[1]]['potential'] = ("{2}-q{3}".format(*pseudo))
        # the format is checked when creating the Calculation
        inputs['POTENTIALS'].write(("# Pseudopotential ID {0}\n"
                                    "{1} {2}-q{3} {2}\n"
                                    "{4}\n")
                                   .format(*pseudo)
                                   .encode('utf-8'))
        inputs['POTENTIALS'].seek(0)

    # if we have any initial magnetic moment defined in the structure,
    # we need unrestricted KS + setting the magnetic moment and calculate the multiplicity
    if struct.get_initial_magnetic_moments().any():
        generated_input['force_eval']['dft']['uks'] = True
        # calculate the total magnetic moment,
        # the total magnetization gives the difference in # of electrons between α and β spin, so 0.5*2*tmom=tmom
        generated_input['force_eval']['dft']['multiplicity'] = int(sum(struct.get_initial_magnetic_moments())) + 1

        # enumerate the different element+magmoms
        symmagmom = list(zip(struct.get_chemical_symbols(), struct.get_initial_magnetic_moments()))
        # and create a mapper (can not use set() here since it doesn't preserve the order)
        symmagmom2key = {(sym, magmom): '{}{}'.format(sym, num)
                         for num, (sym, magmom) in enumerate(OrderedDict.fromkeys(symmagmom), 1)}

        # replace the generated kind list by one containing the MAGNETIZATION
        mkind = {}
        for (sym, magmom), key in symmagmom2key.items():
            mkind[key] = kind[sym].copy()
            mkind[key]['_'] = key
            mkind[key]['magnetization'] = magmom
        kind = mkind

        # and add a new column to the atoms struct containing those labels
        struct.new_array('cp2k_labels', np.array([symmagmom2key[sm] for sm in symmagmom]))
    else:
        # if no magnetic moments are required, simply copy the chemical symbols
        struct.new_array('cp2k_labels', struct.get_chemical_symbols())

    # we can't use TextIOWrapper here since this will close the underlying BytesIO
    # on destruction, resulting in a close BytesIO when leaving the scope
    stringbuf = StringIO()
    ase_io.write(stringbuf, struct, format='xyz', columns=['cp2k_labels', 'positions'])
    inputs['struct.xyz'] = BytesIO(stringbuf.getvalue().encode("utf-8"))
    inputs['struct.xyz'].seek(0)

    # if charges are defined, set the charges keyword to be the total charge
    if struct.get_initial_charges().any():
        generated_input['force_eval']['dft']['charge'] = int(sum(struct.get_initial_charges()))

    # in the CP2K Python dict struct the kinds are stored as list
    generated_input['force_eval']['subsys']['kind'] = list(kind.values())

    # merge the generated input over the basic settings
    combined_input = dict(mergedicts(settings, generated_input))

    # make some last adjustments which depend on a merged input structure

    try:
        # if scf is itself a dict we get a reference here
        scf = combined_input['force_eval']['dft']['scf']
        if 'smear' in scf.keys() and 'added_mos' not in scf.keys():
            # when calculating the number of MOs on the other hand, we only want the default (for CP2K the "ORB")
            # type of basis sets since we don't want to count the AUX/RI/.. sets as well
            n_mos = 0
            for basis in [b[-1] for b in basis_sets if b[0] == 'default']:
                # the number of MOs depends on the basis set
                econfig_string = basis.split('\n')[1]
                econfig = [int(n) for n in econfig_string.split()]
                # sum over (the number of m's per l quantum number times
                # the number of functions per m):
                n_mos += np.dot([2*l+1 for l in range(econfig[1], econfig[2]+1)], econfig[4:])

            scf['added_mos'] = int(0.3*n_mos)
    except KeyError:
        pass

    # enforce same periodicity for CELL_REF (if specified) as for the cell itself
    try:
        combined_input['force_eval']['subsys']['cell']['cell_ref']['periodic'] = \
                combined_input['force_eval']['subsys']['cell']['periodic']
    except KeyError:
        pass

    # merge any override settings on top if not None or empty
    if overrides:
        combined_input = dict(mergedicts(combined_input, overrides))

    inputs['calc.inp'] = BytesIO()
    inputs['calc.inp'].write("# calc.inp: {}\n".format(tagline).encode('utf-8'))
    dict2cp2k(combined_input, inputs['calc.inp'], parameters=struct.info)
    inputs['calc.inp'].seek(0)

    return inputs


def test():
    from . import Json2Atoms

    settings = {
        "force_eval": {
            "method": "Quickstep",
            "dft": {
                "scf": {
                    "eps_scf": 1e-08,
                    "smear": {
                        "method": "FERMI_DIRAC",
                        "_": True,
                        "electronic_temperature": "[K] 300"
                        },
                    "mixing": {
                        "method": "BROYDEN_MIXING",
                        "alpha": 0.4
                        }
                    },
                "xc": {"xc_functional": {"_": "PBE"}},
                "print": {"overlap_condition": {"1-norm": True, "_": "ON", "diagonalization": True}},
                "qs": {"method": "GPW", "extrapolation": "USE_GUESS"},
                "mgrid": {"cutoff": 1000, "rel_cutoff": 100},
                "kpoints": {
                    "full_grid": True,
                    "symmetry": False,
                    "parallel_group_size": -1,
                    "scheme": "MONKHORST-PACK {kpoints[0]} {kpoints[1]} {kpoints[2]}"
                    }
                }
            },
        "global": {"run_type": "ENERGY", "print_level": "MEDIUM"}
        }
    basis_sets = [('default', 1, 'O', 'SZV-GTH', ''' 1
     2  0  1  4  1  1
       8.3043855492   0.1510165999  -0.0995679273
       2.4579484191  -0.0393195364  -0.3011422449
       0.7597373434  -0.6971724029  -0.4750857083
       0.2136388632  -0.3841133622  -0.3798777957
''')]
    pseudos = [(1, 'O', 'GTH-PBE', 6, ''' 2    4
     0.24455430    2   -16.66721480     2.48731132
    2
     0.22095592    1    18.33745811
     0.21133247    0
''')]
    struct = Json2Atoms('''
        {
            "numbers": [8, 8, 8, 8],
            "positions": [[4.27100416, 2.48306235e-17, 0.615915813], [1.80729466, 1.44465234e-16, 3.58341475], [2.13518916, 2.13841, 0.615915813], [3.94310966, 2.13841, 3.58341475]],
            "initial_magmoms": [1.5, 1.5, -1.5, -1.5],
            "cell": [[4.27163, 0.0, 0.0], [2.61879696e-16, 4.27682, 0.0], [1.80666882, 1.69295858e-16, 4.19933056]],
            "pbc": [true, true, true],
            "key_value_pairs": {"dataset": "deltatest", "identifier": "deltatest_O_1.00", "kpoints": [26, 24, 24]},
            "unique_id": "d54e984f10fd34539f0a8d1d4f89a7f4"
        }
        ''')
    tagline = "Generated by generator test"

    inputs = generate_CP2K_inputs(settings, basis_sets, pseudos, struct, tagline, overrides=None)

    for filename, content in inputs.items():
        print("=== BEGIN: {}".format(filename))
        print(content.read().decode("utf-8"))
        print("=== END: {}\n".format(filename))

if __name__ == '__main__':
    test()