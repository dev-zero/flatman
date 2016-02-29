
from peewee import *
from playhouse.postgres_ext import BinaryJSONField
from flask.ext.security import UserMixin, RoleMixin

from fatman import db

class BaseModel(Model):
    class Meta:
        database = db

class Role(BaseModel, RoleMixin):
    name = CharField(unique=True)
    description = TextField(null=True)

    def __str__(self):
        return self.name

class User(BaseModel, UserMixin):
    email = CharField(unique=True)
    password = TextField()
    active = BooleanField(default=False, null=False)
    confirmed_at = DateTimeField(null=True)

    def __str__(self):
        return self.email

class UserRole(BaseModel):
    user = ForeignKeyField(User, related_name='roles')
    role = ForeignKeyField(Role, related_name='users')
    name = property(lambda self: self.role.name)
    description = property(lambda self: self.role.description)

class Structure(BaseModel):
    name = CharField(unique=True, null=False)
    ase_structure = TextField(null=False)
    class Meta:
        order_by = ('name',)

    def __str__(self):
        return self.name

class BasissetFamily(BaseModel):
    name = CharField(unique=True, null=False)

    class Meta:
        order_by = ('name',)

    def __str__(self):
        return self.name

class PseudopotentialFamily(BaseModel):
    name = CharField(unique=True, null=False)

    class Meta:
        order_by = ('name',)

    def __str__(self):
        return self.name


class BasisSet(BaseModel):
    family = ForeignKeyField(BasissetFamily, related_name='basisset')
    element = CharField(null=False)
    basis = TextField(null=False)

    class Meta:
        order_by = ('family',)

    def __str__(self):
        return self.family.name

class Pseudopotential(BaseModel):
    family = ForeignKeyField(PseudopotentialFamily, related_name='pseudopotential')
    element = CharField(null=False)
    pseudo = TextField(null=False)

    class Meta:
        order_by = ('family',)

    def __str__(self):
        return self.family.name

class Method(BaseModel):
    # proper database design would demand introduction of
    # separate entities for the following fields, but let's make it easy
    code = CharField()
    pseudopotential = ForeignKeyField(PseudopotentialFamily, related_name = 'method_pp')
    basis_set = ForeignKeyField(BasissetFamily, related_name = 'method_bs')
    settings = BinaryJSONField(null=True)

    class Meta:
        order_by = ('code',)

    def __str__(self):
        if "cutoff_rho" in self.settings.keys():
            settings_info = ", cutoff: {:.1f}".format(self.settings['cutoff_rho']/13.605692)
        else:
            settings_info = ""

        return "code: {}, pseudopotential: {}, basis set: {} {}".format(
                self.code,
                self.pseudopotential,
                self.basis_set,
                settings_info
                )

class Test(BaseModel):
    name = CharField(unique=True, null=False)
    description = TextField(null=True)

    class Meta:
        order_by = ('name',)

    def __str__(self):
        return self.name

class TestStructure(BaseModel):
    structure = ForeignKeyField(Structure, related_name='tests')
    test = ForeignKeyField(Test, related_name='structures')

class TaskStatus(BaseModel):
    name = CharField(unique=True, null=False)

    class Meta:
        order_by = ('name',)

    def __str__(self):
        return self.name

class Task(BaseModel):
    structure = ForeignKeyField(Structure, related_name='tasks')
    method = ForeignKeyField(Method, related_name='tasks')
    status = ForeignKeyField(TaskStatus)
    test = ForeignKeyField(Test, related_name='tasks')
    ctime = DateTimeField()
    mtime = DateTimeField()
    machine = CharField()

    def __str__(self):
        return "id: {}, structure: {}, status: {}".format(
                self.id,
                self.structure,
                self.status)

class Result(BaseModel):
    energy = DoubleField()
    task = ForeignKeyField(Task, related_name='results')
    filename = CharField(null=True)

class TestResult(BaseModel):
    ctime = DateTimeField()
    test = ForeignKeyField(Test, related_name='testresult')
    method = ForeignKeyField(Method, related_name='testresult')
    result_data = BinaryJSONField(null=True)

