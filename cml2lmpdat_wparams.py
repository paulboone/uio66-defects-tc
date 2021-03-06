from collections import Counter
from pathlib import Path

import click
import networkx as nx
import numpy as np

from mofun import Atoms
from mofun.uff4mof import UFF4MOF
from mofun.atoms import find_unchanged_atom_pairs
import mofun.rough_uff as ruff

def angle2lammpsdat(params):
    if params[0] == "fourier":
        return '%s %10.6f %10.6f %10.6f %10.6f # %s' % params
    elif params[0] == "cosine/periodic":
        return '%s %10.6f %d %d # %s' % params
    else:
        raise Exception("Unhandled angle style '%s'" % params[0])

def order_types(tup):
    rev = list(tup)
    rev.reverse()
    if tuple(rev) <= tuple(tup):
        return tuple(rev)
    return tuple(tup)


def cml2lmpdat_typed_parameterized_for_new_atoms(fnlinker_path, linker_path=None, outpath="-"):
    uff_rules = {
        "H": [
            ("H_b", dict(n=2)),
            ("H_", {})
        ],
        "N": [
            ("N_R", dict(n=3, aromatic=True)),
            ("N_1", dict(neighbors=("N","N")))
        ],
        "O": [("O_1", dict(n=1))],
        "C": [("C_R", dict(n=3, aromatic=True))]
    }
    bond_order_rules = [({'N_1'}, 2), ({'N_1', 'N_2'}, 2)]

    fnlinker = Atoms.from_cml(fnlinker_path)

    # assign uff atom types using mofun.rough_uff
    g = nx.Graph()
    g.add_edges_from(fnlinker.bonds)
    uff_types = ruff.assign_uff_atom_types(g, fnlinker.elements, override_rules=uff_rules)
    fnlinker.retype_atoms_from_uff_types(uff_types)

    # calculate all possible many-body terms
    fnlinker.calc_angles()
    fnlinker.calc_dihedrals()

    # calculate potential parameters and assign type #s to linker
    fnlinker.pair_params = ['%10.6f %10.6f # %s' % (*ruff.pair_params(a1), a1) for a1 in fnlinker.atom_type_labels]

    bond_types = [order_types([uff_types[b1], uff_types[b2]]) for b1, b2 in fnlinker.bonds]
    unique_bond_types = list(dict.fromkeys(bond_types).keys())
    fnlinker.bond_types = [unique_bond_types.index(bt) for bt in bond_types]
    bond_params = [(*ruff.bond_params(a1, a2, bond_order_rules=bond_order_rules), "%s %s" % (a1, a2)) for (a1, a2) in unique_bond_types]
    fnlinker.bond_type_params = ['%10.6f %10.6f # %s' % params for params in bond_params]

    angle_types = [order_types([uff_types[a] for a in atoms]) for atoms in fnlinker.angles]
    unique_angle_types = list(dict.fromkeys(angle_types).keys())
    fnlinker.angle_types = [unique_angle_types.index(a) for a in angle_types]
    angle_params = [(*ruff.angle_params(*a_ids, bond_order_rules=bond_order_rules), "%s %s %s" % a_ids) for a_ids in unique_angle_types]
    fnlinker.angle_type_params = [angle2lammpsdat(a) for a in angle_params]

    num_dihedrals_per_bond = Counter([order_types([a2, a3]) for _, a2, a3, _ in fnlinker.dihedrals])

    dihedral_types = [(*order_types([uff_types[a] for a in atoms]),
                            num_dihedrals_per_bond[order_types([atoms[1], atoms[2]])])
                        for atoms in fnlinker.dihedrals]
    unique_dihedral_types = list(dict.fromkeys(dihedral_types).keys())
    dihedral_params = [ruff.dihedral_params(*a_ids, bond_order_rules=bond_order_rules) for a_ids in unique_dihedral_types]

    # delete any dihedrals when the params come back None (i.e. for *_1)
    for i in reversed(range(len(dihedral_params))):
        if dihedral_params[i] is None:
            none_dihedral = unique_dihedral_types[i]
            print(len(fnlinker.dihedrals), len(dihedral_types), len(unique_dihedral_types), len(dihedral_params))

            fnlinker.dihedrals = [d for j, d in enumerate(fnlinker.dihedrals) if dihedral_types[j] != none_dihedral]
            dihedral_types = [d for d in dihedral_types if d != none_dihedral]

            del(unique_dihedral_types[i])
            del(dihedral_params[i])
            print(len(fnlinker.dihedrals), len(dihedral_types), len(unique_dihedral_types), len(dihedral_params))

    # assign dihedral types
    fnlinker.dihedral_types = [unique_dihedral_types.index(a) for a in dihedral_types]
    dihedral_params = [(*ruff.dihedral_params(*a_ids, bond_order_rules=bond_order_rules), "%s %s %s %s M=%d" % a_ids) for a_ids in unique_dihedral_types]
    fnlinker.dihedral_type_params = ['%s %10.6f %d %d # %s' % params for params in dihedral_params]

    print("Num dihedrals, angles, bonds: %d, %d, %d" % (len(fnlinker.dihedrals), len(fnlinker.angles), len(fnlinker.bonds)))

    # output lammps-data file
    with open(outpath, "w") as f:
        fnlinker.to_lammps_data(f)

@click.command()
@click.argument('fnlinkers', nargs=-1, type=click.Path())
@click.option('--linker-path', type=click.Path())
@click.option('--outpath', '-o', type=click.Path())
def cml2lmpdat_wparams(fnlinkers, linker_path=None, outpath=Path()):
    outpath = Path(outpath)
    print(outpath)
    for fnlinker_path in fnlinkers:
        fnlinker_path = Path(fnlinker_path)
        print("\nreading %s" % fnlinker_path)
        try:
            print(linker_path, fnlinker_path)
            cml2lmpdat_typed_parameterized_for_new_atoms(fnlinker_path, linker_path, outpath.joinpath(fnlinker_path.stem + ".lmpdat"))
        except Exception as e:
            print("ERROR! ", e.args)


if __name__ == '__main__':
    cml2lmpdat_wparams()
