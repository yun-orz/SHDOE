"""严格复用已验收的几何积分与光谱求解接口。"""
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'integration/single_spiral_to_hsi/n03_exp2'))
import forward as f
import sampling as sampling
import perturbations as perturbations
import noise as noise


class ForwardAdapter:
    def __init__(self):
        kernels, self.weights, self.assets, self.records, self.indices, self.pitch = f.load(ROOT)
        self.fine = kernels[f.MODELS[2]]
        self.edges, self.det_edges, self.overlap = sampling.centered_grid(512, self.pitch)

    def cube(self, position, blur=0.):
        dx, dy = np.asarray(position, dtype=float)*self.pitch
        if blur:
            # 已验收连续高斯双面积积分，在源边界上叠加固定平移。
            wx = sampling.gaussian_overlap_matrix(self.edges+dx, self.det_edges, blur*self.pitch)
            wy = sampling.gaussian_overlap_matrix(self.edges+dy, self.det_edges, blur*self.pitch)
        else:
            wx = sampling.overlap_matrix(self.edges+dx, self.det_edges)
            wy = sampling.overlap_matrix(self.edges+dy, self.det_edges)
        cube = np.stack([sampling.rebin(h, wy, wx) for h in self.fine])
        capture = cube.sum(axis=(1, 2))
        # 与EXP2/EXP2B相同的逐带shape_only定义；并非RGB整图再归一化。
        return cube/capture[:, None, None], capture

    def matrix(self, position, blur=0.):
        cube, capture = self.cube(position, blur)
        return f.matrix(cube, self.weights), capture
