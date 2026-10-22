import json
import os

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import scipy.io as sio
import torch

from src.camera import Renderer
from src.deeplens.diffraclens import DiffractiveLens
from src.deeplens.render_psf import render_psf
from src.sensor import RGBSensor


class HSICamera(Renderer):
    def __init__(self, lens_file, sensor_file, device=None):
        super().__init__(device=device)

        # RGB sensor
        sensor_config = json.load(open(sensor_file))
        sensor = RGBSensor.from_config(sensor_config)
        self.sensor = sensor.to(self.device)

        # Single DOE lens
        self.lens = DiffractiveLens(
            filename=lens_file,
            sensor_res=sensor.res,
            sensor_size=sensor.size,
            device=self.device,
        )
        # self.lens.surfaces[0].phase_map = self.read_mat()
        # lens_config = json.load(open(lens_file))
        # self.lens.surfaces[0].phase_map = self.load_phase_map(lens_config["surfaces"][0]["doe_path"])

    # def read_mat(self, height_map_path="./lenses/paraxiallens/planar_doe.mat"):
    #     """Read phase map from a .mat file. This function only works for the example DOE."""
    #     # Load the .mat file
    #     mat_data = sio.loadmat(height_map_path)
    #     data_keys = [k for k in mat_data.keys() if not k.startswith("__")]
    #     doe_data = None
    #     for key in data_keys:
    #         if isinstance(mat_data[key], np.ndarray) and mat_data[key].size > 1:
    #             doe_data = mat_data[key]
    #             break
    #     height_map = doe_data[0, :, :, 0]  # shape (1024, 1024), data range [0, 2000]

    #     # Calculate relative height map ([um]) for non-zero values
    #     non_zero_mask = height_map > 0
    #     if np.any(non_zero_mask):
    #         min_non_zero = np.min(height_map[non_zero_mask])
    #         height_map[non_zero_mask] -= min_non_zero

    #     # Convert height map to phase map
    #     doe = self.lens.surfaces[0]
    #     phase_map0 = height_map * (doe.n0 - 1) * 2 * torch.pi / doe.wvln0
    #     phase_map0 = torch.from_numpy(phase_map0).to(self.device)

    #     return phase_map0
    
    # def save_phase_map(self, file_path="./phase_map.npy"):
    #     """Save the current DOE phase map to a NumPy array file.
        
    #     Args:
    #         file_path (str): Path to save the NumPy array file.
    #     """
    #     phase_map = self.lens.surfaces[0].phase_map.cpu().numpy()
    #     np.save(file_path, phase_map)
        
    # def load_phase_map(self, file_path="./phase_map.npy"):
    #     """Load a DOE phase map from a NumPy array file.
        
    #     Args:
    #         file_path (str): Path to the NumPy array file.
        
    #     Returns:
    #         torch.Tensor: The loaded phase map.
    #     """
    #     phase_map = np.load(file_path)
    #     phase_map = torch.from_numpy(phase_map).to(self.device)
    #     self.lens.surfaces[0].phase_map = phase_map
    #     return phase_map
    
    def vis_doe(self, save_dir="./results/vis"):
        """可视化并保存 DOE 2D 与 3D 相位图。"""
        os.makedirs(save_dir, exist_ok=True)
        self.lens.surfaces[0].draw_phase_map(os.path.join(save_dir, "DOE_phase_map.png"))
        self.lens.surfaces[0].draw_phase_map3d(os.path.join(save_dir, "DOE_phase_map3d.png"))
        
    def vis_psf(
        self,
        wvln_spectral,
        psf_ks=201,
        depth=float("inf"),
        save_dir="./results/vis",
        save_name=None,
    ):
        """可视化每个光谱通道的 PSF。支持单行与多行多列网格自适应展示，波长范围覆盖 400nm 至 700nm。"""
        num_wvln = len(wvln_spectral)
        # 计算每个光谱通道的 PSF
        psf_spectral = torch.zeros((num_wvln, psf_ks, psf_ks)).to(self.device)
        for i, wvln in enumerate(wvln_spectral):
            psf_chan = self.lens.psf(
                depth=depth, wvln=wvln, ks=psf_ks, upsample_factor=2
            )
            psf_spectral[i, :, :] = psf_chan

        # 自适应布局：通道较多时采用多行网格（如 31 个波段采用 4 行 8 列）
        if num_wvln <= 6:
            ncols = num_wvln
            nrows = 1
            figsize = (3.5 * ncols, 3.5)
        else:
            ncols = 8
            nrows = int(np.ceil(num_wvln / ncols))
            figsize = (2.6 * ncols, 2.6 * nrows)

        norm = mcolors.Normalize(vmin=0.4, vmax=0.7)
        cmap_name = "jet"
        fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
        if nrows == 1 and ncols == 1:
            axes = np.array([[axes]])
        elif nrows == 1 or ncols == 1:
            axes = np.array(axes).reshape(nrows, ncols)

        # 绘制各个波长通道的 PSF
        for i in range(nrows * ncols):
            r = i // ncols
            c = i % ncols
            ax = axes[r, c]

            if i < num_wvln:
                wvln = wvln_spectral[i]
                color = plt.cm.get_cmap(cmap_name)(norm(wvln))
                colors = [(0, 0, 0, 1), color]
                custom_cmap = mcolors.LinearSegmentedColormap.from_list(
                    f"custom_{i}", colors
                )
                ax.imshow(psf_spectral[i, :, :].cpu().numpy(), cmap=custom_cmap)
                wvln_nm = wvln * 1000 if wvln < 10 else wvln
                ax.set_title(f"{wvln_nm:.0f} nm", fontsize=10, pad=3)
            ax.set_xticks([])
            ax.set_yticks([])
            if i >= num_wvln:
                ax.axis("off")  # 隐藏网格多余的空白子图

        plt.tight_layout()
        os.makedirs(save_dir, exist_ok=True)
        if save_name is None:
            if num_wvln > 6:
                save_name = f"psf_spectral_{num_wvln}ch_{-depth}mm.png"
            else:
                save_name = f"psf_spectral_{-depth}mm.png"
        fig.savefig(os.path.join(save_dir, save_name), dpi=300, bbox_inches="tight")

        plt.close("all")

    def spectral2rgb(self, img_spectral):
        """Convert reconstrcuted spectral image to rgb image for visualization."""
        img_rgb_raw = self.sensor.response_curve(img_spectral)
        return img_rgb_raw

    def render_lens(self, img_spectral, wvln_spectral, depth=float("inf"), psf_ks=201):
        """Render lens blur for each spectral channel.

        Args:
            img_spectral (torch.Tensor): Input image. Shape: (B, C, H, W)
            wvln_spectral (torch.Tensor): Wavelength. Shape: (C,)
            psf_ks (int, optional): PSF kernel size. Defaults to 51.

        Returns:
            img_render (torch.Tensor): Rendered image. Shape: (B, C, H, W)

        Note:
            [1] When creating a diffractive lens, we change the default dtype to double. Here we need to convert it back.
        """
        # Calculate PSF for all spectral channels
        num_spectral = len(wvln_spectral)
        psf_spectral = (
            torch.zeros((num_spectral, psf_ks, psf_ks))
            .to(img_spectral.device)
            .to(img_spectral.dtype)
        )
        for i, wvln in enumerate(wvln_spectral):
            psf_chan = self.lens.psf(
                depth=depth, wvln=wvln, ks=psf_ks, upsample_factor=2
            )
            psf_spectral[i, :, :] = psf_chan

        # PSF convolution by each spectral channel
        img_render = render_psf(img_spectral, psf_spectral)
        return img_render

    def render(self, data_dict):
        """Render a blurry and noisy RGB image batch from spectral data.

        Args:
            data_dict (dict): Dictionary containing essential information for image simulation, for example:
                {
                    "wvln": wvln (torch.Tensor), (B, C)
                    "img": rgb image (torch.Tensor), (B, C, H, W), [0, 1]
                }

        Returns:
            img_spectral (torch.Tensor): Rendered spectral image. Shape: (B, C, H, W)
            img_rgb_raw (torch.Tensor): Rendered RGB image. Shape: (B, 3, H, W)
        """
        data_dict = self.move_to_device(data_dict)
        wvln_spectral = data_dict["wvln"][0].tolist()  # (C,)
        img_spectral = data_dict["img"]  # (B, C, H, W)

        # Render lens blur for all spectral channels
        img_spectral_render = self.render_lens(img_spectral, wvln_spectral)

        # Simulate sensor response (raw space)
        img_rgb_raw = self.sensor.response_curve(img_spectral_render)

        # Simulate sensor noise
        # img_rgb_noise = sensor.simu_noise(img_rgb_raw, iso)

        return img_rgb_raw, img_spectral


