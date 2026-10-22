"""SVD正交压缩保留NNLS目标的全部与解有关部分，避免反复求解巨大瘦矩阵。"""
import numpy as np
from scipy.optimize import nnls


def factorize(matrix):
    u, singular, vt = np.linalg.svd(matrix, full_matrices=False)
    tolerance = np.finfo(float).eps * max(matrix.shape) * singular[0]
    rank = int(np.sum(singular > tolerance))
    return u[:, :rank], singular[:rank, None] * vt[:rank], singular, rank, tolerance


def solve_nnls(reduced, projected, scale):
    # A和y同时乘同一常数，不逐列归一化、不改变优化问题。
    estimate, residual = nnls(reduced/scale, projected/scale, maxiter=1000)
    return estimate, dict(status='SUCCESS', reduced_scaled_residual=float(residual), maxiter=1000)


def spectral_metrics(truth, estimate, waves):
    nt, ne = np.linalg.norm(truth), np.linalg.norm(estimate)
    angle = float(np.degrees(np.arccos(np.clip(truth @ estimate / (nt*ne), -1, 1)))) if ne > 0 else None
    return dict(spectral_NRMSE=float(np.linalg.norm(estimate-truth)/nt), SAM_deg=angle,
                amplitude_bias=float(estimate.sum()-truth.sum()),
                relative_amplitude_bias=float(estimate.sum()/truth.sum()-1),
                vector_amplitude_relative_bias=float(ne/nt-1),
                peak_error_nm=float(abs(waves[np.argmax(estimate)]-waves[np.argmax(truth)])))
