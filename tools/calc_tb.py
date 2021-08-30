#!/bin/python3

"""
Reads DMFT_ouput observables such as real-frequency Sigma and a Wannier90
TB Hamiltonian to compute spectral properties. It runs in two modes,
either calculating the bandstructure or Fermi slice.

Written by Sophie Beck, 2021
"""

from numpy import dtype
from matplotlib.ticker import MaxNLocator, AutoMinorLocator
from matplotlib.colors import LogNorm
from matplotlib import cm, colors
from scipy.optimize import brentq
from scipy.interpolate import interp1d
import itertools
import matplotlib.pyplot as plt

# triqs
from triqs.sumk import SumkDiscreteFromLattice
from tools.TB_functions import *
from h5 import HDFArchive
from triqs.gf import BlockGf
from triqs.gf import GfReFreq, MeshReFreq
from triqs.utility.dichotomy import dichotomy

def get_tb_bands(e_mat):
    """
    Compute band eigenvalues and eigenvectors from matrix per k-point
    """

    e_val = np.zeros((e_mat.shape[0], e_mat.shape[2]), dtype=complex)
    e_vec = np.zeros(np.shape(e_mat), dtype=complex)
    for ik in range(np.shape(e_mat)[2]):
        e_val[:,ik], e_vec[:,:,ik] = np.linalg.eigh(e_mat[:,:,ik])

    return e_val.real, e_vec

def get_tb_kslice(tb, dft_mu):
    """
    Compute band eigenvalues and eigenvectors...
    """

    prim_to_cart = [[0,1,1],
                    [1,0,1],
                    [1,1,0]]
    cart_to_prim = np.linalg.inv(prim_to_cart)
    w90_paths = list(map(lambda section: (np.array(specs[section[0]]), np.array(specs[section[1]])), specs['bands_path']))
    final_x, final_y = w90_paths[1]
    Z = np.array(specs['Z'])

    e_val, e_vec = get_kx_ky_FS(final_x, final_y, Z, tb, k_trans_back=cart_to_prim, N_kxy=specs['n_k'], kz=specs['kz'], fermi=dft_mu)

    return e_val, e_vec

def _get_TBL(hopping, units, n_wf, extend_to_spin=False, add_local=None, add_field=None, renormalize=None):
    """
    get triqs tight-binding object from hoppings + units
    """

    if extend_to_spin:
    	hopping, n_wf = extend_wannier90_to_spin(hopping, n_wf)
    if add_local is not None:
        hopping[(0,0,0)] += add_local
    if renormalize is not None:
        assert len(np.shape(renormalize)) == 1, 'Give Z as a vector'
        assert len(renormalize) == n_wf, 'Give Z as a vector of size n_orb (times two if SOC)'
        
        Z_mat = np.diag(np.sqrt(renormalize))
        for R in hopping:
            hopping[R] = np.dot(np.dot(Z_mat, hopping[R]), Z_mat)

    if add_field is not None:
        hopping[(0,0,0)] += add_field

    TBL = TBLattice(units = units, hopping = hopping, orbital_positions = [(0,0,0)]*n_wf,
                    orbital_names = [str(i) for i in range(n_wf)])
    return TBL

def calc_tb_bands(data, add_spin, mu, add_local, k_mesh, fermi_slice, band_basis = False):
    """
    calculate tight-binding bands based on a W90 Hamiltonian 
    """

    # set up Wannier Hamiltonian
    n_orb_rescale = 2 * data['n_wf'] if add_spin else data['n_wf']
    H_add_loc = np.zeros((n_orb_rescale, n_orb_rescale), dtype=complex)
    H_add_loc += np.diag([-mu]*n_orb_rescale)
    if add_spin: H_add_loc += tools.lambda_matrix_w90_t2g(add_local)

    hopping = {eval(key): np.array(value, dtype=complex) for key, value in data['hopping'].items()}
    tb = _get_TBL(hopping, data['units'], data['n_wf'], extend_to_spin=add_spin, add_local=H_add_loc)
    # print local H(R)
    h_of_r = tb.hopping_dict()[(0,0,0)][2:5,2:5] if add_spin else tb.hopping_dict()[(0,0,0)]
    tools.print_matrix(h_of_r, data['n_wf'], 'H(R=0)')

    # bands info
    k_path = k_mesh['k_path']
    k_path = [list(map(lambda item: (k[item]), k.keys())) for k in k_path] # turn dict into list
    k_point_labels = [k.pop(0) for k in k_path] # remove first time, which is label
    # make sure all kpts are floats
    k_path = [list(map(float,k)) for k in k_path]
    k_path = [(np.array(k), np.array(k_path[ct+1])) for ct, k in enumerate(k_path) if ct+1 < len(k_path)] # turn into tuples


    # calculate tight-binding eigenvalues
    if not fermi_slice:
        k_disc, k_points, e_mat = energy_matrix_on_bz_paths(k_path, tb, n_pts=k_mesh['n_k'])
        if add_spin: e_mat = e_mat[2:5,2:5]

        if band_basis:
            e_vecs = np.zeros(e_mat.shape, dtype=complex)
            for ik in range(np.shape(e_mat)[2]):
                evals, e_vecs[:,:,ik] = np.linalg.eigh(e_mat[:,:,ik])
                e_mat[:,:,ik] = np.zeros(e_mat[:,:,ik].shape)
                np.fill_diagonal(e_mat[:,:,ik],evals)
        else:
            e_vecs = np.array([None])

    else:
        e_mat = np.zeros((n_orb_rescale, n_orb_rescale, k_mesh['n_k'], k_mesh['n_k']), dtype=complex)
        e_vecs = np.array([None])
        final_x, final_y = k_path[1]
        Z = np.array(k_mesh['Z'])
        for ik_y in range(k_mesh['n_k']):
            path_along_x = [(final_y / (k_mesh['n_k'] - 1) * ik_y + k_mesh['kz'] * Z, final_x + final_y / (k_mesh['n_k'] - 1) * ik_y + k_mesh['kz'] * Z)]
            _, _, e_mat[:,:,:,ik_y] = energy_matrix_on_bz_paths(path_along_x, tb, n_pts=k_mesh['n_k'])
        k_array = k_points = [0,1]
        if add_spin: e_mat = e_mat[2:5,2:5]

    k_mesh = {'k_disc': k_disc.tolist(), 'k_points': k_points.tolist(), 'k_point_labels': k_point_labels, 'k_points_dash': k_mesh['k_path']}

    return k_mesh, e_mat, e_vecs, tb
