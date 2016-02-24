#!/usr/bin/env python

from flask.ext.script import Manager

from fatman import app

manager = Manager(app)

@manager.command
def initdb():
    """Initialize the database (structure and initial data)"""

    from fatman import db
    from fatman.models import Structure, Method, Test, TestStructure, TaskStatus, Task, Result, BasissetFamily, PseudopotentialFamily, BasisSet, Pseudopotential
    db.create_tables([Structure, Method, Test, TestStructure, TaskStatus, Task, Result, BasissetFamily, PseudopotentialFamily, BasisSet, Pseudopotential], safe=True)

    for name in ['new', 'pending', 'running', 'done', 'error']:
        TaskStatus.create_or_get(name=name)

    for name in ['SZV-GTH', 'DZV-GTH', 'DZVP-GTH', 'TZVP-GTH', 'TZV2P-GTH', 'QZV2P-GTH', 'QZV3P-GTH', 'aug-DZVP-GTH', 'aug-TZVP-GTH', 'aug-TZV2P-GTH', 'aug-QZV2P-GTH', 'aug-QZV3P-GTH', 'aug-QZV3P-GTH-i01', 'SADLEJ', 'DZ-ANO', '6-31G*', '6-311ppG3f2d', '6-31ppG3f2d', 'TZVP-pob']:
        BasissetFamily.create_or_get(name=name)

    for name in ['GTH-PBE', 'GTH-PBE-NLCC', 'GTH-PBE-NLCC2015', 'ALL']:
        PseudopotentialFamily.create_or_get(name=name)


@manager.command
def cleardb():
    """Delete all the data in the Structure, Test, TestStructure, and Task databases. 
       The Result and Method tables remain intact."""

    from fatman import db
    from fatman.models import Structure, Test, TestStructure, Task
    for table in [Structure, TestStructure, Test, Task]:
        q = table.delete()
        q.execute()


@manager.command
def createconfig():
    """Create initial configuration file"""

    from os import urandom

    with open('fatman.cfg', 'w') as cfg:
        cfg.write("SECRET_KEY = {}\n".format(urandom(24)))

@manager.shell
def make_shell_context():
    from fatman import db
    import fatman.models
    return dict(app=app, db=db, models=fatman.models)

if __name__ == '__main__':
    manager.run()
