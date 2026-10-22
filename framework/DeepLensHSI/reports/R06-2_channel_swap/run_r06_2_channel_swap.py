"""
R06-2 受控对照实验脚本：RGB 通道交换 (A/B 测试)
严格保持单次光学渲染、相同模型、相同权重、相同评价口径，
对比原始编码 RGB 输入与通道翻转输入 [B, G, R] 的重建性能。
"""
import sys
import os
import time
import json
import csv
import random
from pathlib import Path

import numpy as np
import torch
import yaml
from torchvision.utils import save_image

# 保证从项目根目录导入 src
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.hsi_camera import HSICamera
from src.network import NAFNet
from src.utils import batch_ssim
from hsi_dataset import CaveDataset


def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def compute_metrics_for_pred(pred, gt):
    """
    计算 PSNR、SSIM、SAM (历史口径与固定 GT 掩膜口径)。
    pred, gt 形状均为 [1, 31, H, W]
    """
    # 1. PSNR (复现 R05 / 脚本 6)
    mse = ((pred - gt) ** 2).mean()
    psnr_db = (-10 * torch.log10(mse.clamp_min(1e-12))).item()

    # 2. SSIM (原仓库 8 位量化口径)
    ssim_val = float(batch_ssim(pred, gt))

    # 3. 基础向量内积与模长
    dot = (pred * gt).sum(dim=1)  # [1, H, W]
    gt_norm = torch.linalg.vector_norm(gt, dim=1)  # [1, H, W]
    pred_norm = torch.linalg.vector_norm(pred, dim=1)  # [1, H, W]

    # 3.1 历史口径 SAM (双有效掩膜)
    valid_hist = (gt_norm > 1e-8) & (pred_norm > 1e-8)
    assert valid_hist.any(), "无有效光谱像素 (历史口径)"
    cos_hist = (dot[valid_hist] / (gt_norm[valid_hist] * pred_norm[valid_hist])).clamp(-1.0, 1.0)
    sam_hist_deg = torch.rad2deg(torch.acos(cos_hist)).mean().item()
    sam_hist_valid_pct = (valid_hist.float().mean() * 100).item()

    # 3.2 固定 GT 掩膜 SAM (主对比口径: 有效像素仅取决于 GT)
    valid_gt = (gt_norm > 1e-8)
    assert valid_gt.any(), "无有效光谱像素 (GT 掩膜)"
    
    dot_val = dot[valid_gt]
    gt_n_val = gt_norm[valid_gt]
    pred_n_val = pred_norm[valid_gt]

    # 针对预测为零向量的点赋 90 度，非零点计算真实夹角
    non_zero_pred = pred_n_val > 1e-8
    angles_deg = torch.full_like(dot_val, 90.0)
    if non_zero_pred.any():
        cos_fixed = (dot_val[non_zero_pred] / (gt_n_val[non_zero_pred] * pred_n_val[non_zero_pred])).clamp(-1.0, 1.0)
        angles_deg[non_zero_pred] = torch.rad2deg(torch.acos(cos_fixed))
    
    sam_fixed_deg = angles_deg.mean().item()
    sam_fixed_valid_pct = (valid_gt.float().mean() * 100).item()

    return {
        "mse": float(mse.item()),
        "psnr_db": psnr_db,
        "ssim": ssim_val,
        "sam_hist_deg": sam_hist_deg,
        "sam_hist_valid_pct": sam_hist_valid_pct,
        "sam_fixed_deg": sam_fixed_deg,
        "sam_fixed_valid_pct": sam_fixed_valid_pct,
    }


def main():
    set_seed(42)
    start_all = time.perf_counter()

    out_dir = Path("reports/R06-2_channel_swap")
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    print("================================================================================")
    print("R06-2 受控对照实验：RGB 输入红蓝通道交换 (A/B 测试)")
    print("================================================================================")

    # 1. 环境与设备
    assert torch.cuda.is_available(), "未检测到 CUDA GPU"
    device = torch.device("cuda")
    gpu_name = torch.cuda.get_device_name(0)
    print(f"计算设备: {device} ({gpu_name})")
    torch.cuda.reset_peak_memory_stats(device)

    # 2. 读取配置
    cfg_path = Path("configs/1_deeplens_hsi.yml")
    assert cfg_path.exists(), f"配置文件不存在: {cfg_path}"
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # 3. 数据集与场景检查
    val_dataset_path = cfg["eval_set"]["dataset"]
    crop_size = tuple(cfg["eval_set"]["crop_size"])
    dataset = CaveDataset(file_path=val_dataset_path, crop_size=crop_size, is_train=False)
    num_scenes = len(dataset)
    print(f"验证集路径: {val_dataset_path}")
    print(f"裁剪尺寸: {crop_size}")
    print(f"验证场景数量: {num_scenes}")
    assert num_scenes == 8, f"预期 8 个场景，实际 {num_scenes} 个"

    # 4. 初始化光学相机
    print("正在初始化光学相机 (单次实例化)...")
    camera = HSICamera(
        lens_file=cfg["camera"]["lens_file"],
        sensor_file=cfg["camera"]["sensor_file"],
        device=device,
    )

    # 5. 初始化 NAFNet 并加载权重
    print("正在初始化 NAFNet 并加载预训练权重...")
    net_cfg = cfg["network"]
    model = NAFNet(
        in_chan=net_cfg["in_chan"],
        out_chan=net_cfg["out_chan"],
        width=net_cfg["width"],
        middle_blk_num=net_cfg["middle_blk_num"],
        enc_blk_nums=net_cfg["enc_blk_nums"],
        dec_blk_nums=net_cfg["dec_blk_nums"],
    ).to(device)

    ckpt_path = Path(net_cfg["ckpt_path"])
    assert ckpt_path.exists(), f"权重文件不存在: {ckpt_path}"
    weights = torch.load(ckpt_path, map_location=device, weights_only=False)
    if isinstance(weights, dict) and "model" in weights:
        weights = weights["model"]
    model.load_state_dict(weights, strict=True)
    model.eval()
    print("预训练权重严格匹配并加载成功 (model.eval() 就绪).\n")

    # 6. 读取 R05 历史基准指标用于门槛比对
    r05_csv = Path("results/R05_validation/metrics.csv")
    assert r05_csv.exists(), f"历史 R05 指标文件不存在: {r05_csv}"
    r05_historical = {}
    with open(r05_csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            r05_historical[row["scene"]] = {
                "psnr_db": float(row["psnr_db"]),
                "ssim": float(row["ssim"]),
                "sam_deg": float(row["sam_deg"]),
            }

    # 7. 逐场景 A/B 实验循环
    scene_records = []
    
    for i in range(num_scenes):
        scene_name = Path(dataset.image_folders[i]).name
        print(f"----- [{i+1}/8] 场景: {scene_name} -----")
        t0 = time.perf_counter()

        sample = dataset[i]
        data_dict = {
            "wvln": sample["wvln"].unsqueeze(0),
            "img": sample["img"].unsqueeze(0),
        }

        with torch.inference_mode():
            # 7.1 单次前向物理渲染，获取完全相同的一份 encoded_rgb 与 gt
            encoded_rgb, gt = camera.render(data_dict)

            # 7.2 形状与有限性检查
            assert encoded_rgb.shape == (1, 3, 512, 512), f"encoded_rgb 形状异常: {encoded_rgb.shape}"
            assert gt.shape == (1, 31, 512, 512), f"gt 形状异常: {gt.shape}"
            assert torch.isfinite(encoded_rgb).all(), "encoded_rgb 包含非有限值"
            assert torch.isfinite(gt).all(), "gt 包含非有限值"

            # 7.3 A 组：标准输入 [R, G, B]
            pred_A = model(encoded_rgb).clamp(0, 1)

            # 7.4 B 组：红蓝通道交换输入 [B, G, R]
            encoded_rgb_swapped = encoded_rgb[:, [2, 1, 0], :, :]
            pred_B = model(encoded_rgb_swapped).clamp(0, 1)

            # 7.5 预测张量检验
            assert pred_A.shape == (1, 31, 512, 512), f"pred_A 形状异常: {pred_A.shape}"
            assert pred_B.shape == (1, 31, 512, 512), f"pred_B 形状异常: {pred_B.shape}"
            assert torch.isfinite(pred_A).all(), "pred_A 包含非有限值"
            assert torch.isfinite(pred_B).all(), "pred_B 包含非有限值"
            assert (0.0 <= pred_A).all() and (pred_A <= 1.0).all(), "pred_A 超出 [0, 1]"
            assert (0.0 <= pred_B).all() and (pred_B <= 1.0).all(), "pred_B 超出 [0, 1]"

            # 7.6 计算各组指标
            mA = compute_metrics_for_pred(pred_A, gt)
            mB = compute_metrics_for_pred(pred_B, gt)

            # 7.7 计算交集掩膜 SAM
            gt_n = torch.linalg.vector_norm(gt, dim=1)
            pA_n = torch.linalg.vector_norm(pred_A, dim=1)
            pB_n = torch.linalg.vector_norm(pred_B, dim=1)
            valid_inter = (gt_n > 1e-8) & (pA_n > 1e-8) & (pB_n > 1e-8)
            dot_A = (pred_A * gt).sum(dim=1)
            dot_B = (pred_B * gt).sum(dim=1)
            cos_inter_A = (dot_A[valid_inter] / (gt_n[valid_inter] * pA_n[valid_inter])).clamp(-1.0, 1.0)
            cos_inter_B = (dot_B[valid_inter] / (gt_n[valid_inter] * pB_n[valid_inter])).clamp(-1.0, 1.0)
            sam_inter_A = torch.rad2deg(torch.acos(cos_inter_A)).mean().item()
            sam_inter_B = torch.rad2deg(torch.acos(cos_inter_B)).mean().item()

            # 7.8 生成四图对比可视化并保存
            # 无论 A 或 B，都使用相同的 camera.spectral2rgb 真实响应函数生成可视化
            ref_rgb = camera.spectral2rgb(gt)
            rec_rgb_A = camera.spectral2rgb(pred_A)
            rec_rgb_B = camera.spectral2rgb(pred_B)

            comparison = torch.cat([ref_rgb, encoded_rgb, rec_rgb_A, rec_rgb_B], dim=3)
            save_image(comparison.clamp(0, 1), fig_dir / f"{scene_name}.png")

        elapsed = time.perf_counter() - t0
        peak_vram_mb = torch.cuda.max_memory_allocated(device) / 1024 / 1024

        delta_psnr = mB["psnr_db"] - mA["psnr_db"]
        delta_ssim = mB["ssim"] - mA["ssim"]
        delta_sam_fixed = mB["sam_fixed_deg"] - mA["sam_fixed_deg"]
        delta_sam_hist = mB["sam_hist_deg"] - mA["sam_hist_deg"]

        record = {
            "scene": scene_name,
            # A 组
            "psnr_A": mA["psnr_db"],
            "ssim_A": mA["ssim"],
            "sam_fixed_A": mA["sam_fixed_deg"],
            "sam_hist_A": mA["sam_hist_deg"],
            "sam_inter_A": sam_inter_A,
            "mse_A": mA["mse"],
            # B 组
            "psnr_B": mB["psnr_db"],
            "ssim_B": mB["ssim"],
            "sam_fixed_B": mB["sam_fixed_deg"],
            "sam_hist_B": mB["sam_hist_deg"],
            "sam_inter_B": sam_inter_B,
            "mse_B": mB["mse"],
            # 差值 (B - A)
            "delta_psnr": delta_psnr,
            "delta_ssim": delta_ssim,
            "delta_sam_fixed": delta_sam_fixed,
            "delta_sam_hist": delta_sam_hist,
            "delta_sam_inter": sam_inter_B - sam_inter_A,
            # 历史对比
            "r05_psnr": r05_historical[scene_name]["psnr_db"],
            "diff_A_vs_r05_psnr": abs(mA["psnr_db"] - r05_historical[scene_name]["psnr_db"]),
            "elapsed_sec": round(elapsed, 2),
            "peak_vram_mb": round(peak_vram_mb, 1),
        }
        scene_records.append(record)

        print(f"  [A组 基准] PSNR: {mA['psnr_db']:.4f} dB | SSIM: {mA['ssim']:.4f} | SAM(固定): {mA['sam_fixed_deg']:.4f}° | SAM(历史): {mA['sam_hist_deg']:.4f}°")
        print(f"  [B组 交换] PSNR: {mB['psnr_db']:.4f} dB | SSIM: {mB['ssim']:.4f} | SAM(固定): {mB['sam_fixed_deg']:.4f}° | SAM(历史): {mB['sam_hist_deg']:.4f}°")
        print(f"  [差异 B-A] ΔPSNR: {delta_psnr:+.4f} dB | ΔSSIM: {delta_ssim:+.4f} | ΔSAM(固定): {delta_sam_fixed:+.4f}° | 耗时: {elapsed:.1f}s")

    # 8. 汇总统计与门槛校验
    print("\n================================================================================")
    print("A 组基线复现性门槛检验 (vs R05 历史)")
    print("================================================================================")
    avg_psnr_A = sum(r["psnr_A"] for r in scene_records) / num_scenes
    avg_ssim_A = sum(r["ssim_A"] for r in scene_records) / num_scenes
    avg_sam_hist_A = sum(r["sam_hist_A"] for r in scene_records) / num_scenes
    avg_sam_fixed_A = sum(r["sam_fixed_A"] for r in scene_records) / num_scenes

    avg_psnr_B = sum(r["psnr_B"] for r in scene_records) / num_scenes
    avg_ssim_B = sum(r["ssim_B"] for r in scene_records) / num_scenes
    avg_sam_hist_B = sum(r["sam_hist_B"] for r in scene_records) / num_scenes
    avg_sam_fixed_B = sum(r["sam_fixed_B"] for r in scene_records) / num_scenes

    diff_mean_psnr = abs(avg_psnr_A - 18.1866)
    diff_mean_ssim = abs(avg_ssim_A - 0.6621)
    diff_mean_sam = abs(avg_sam_hist_A - 39.2232)
    max_scene_psnr_diff = max(r["diff_A_vs_r05_psnr"] for r in scene_records)

    pass_psnr_mean = diff_mean_psnr <= 0.05
    pass_ssim_mean = diff_mean_ssim <= 0.005
    pass_sam_mean = diff_mean_sam <= 0.2
    pass_scene_psnr = max_scene_psnr_diff <= 0.1

    baseline_pass = pass_psnr_mean and pass_ssim_mean and pass_sam_mean and pass_scene_psnr

    print(f"8场景平均 PSNR(A): {avg_psnr_A:.4f} dB (历史: 18.1866, 绝对差: {diff_mean_psnr:.6f} dB, 门槛<=0.05) -> {'PASS' if pass_psnr_mean else 'FAIL'}")
    print(f"8场景平均 SSIM(A): {avg_ssim_A:.4f} (历史: 0.6621, 绝对差: {diff_mean_ssim:.6f}, 门槛<=0.005) -> {'PASS' if pass_ssim_mean else 'FAIL'}")
    print(f"8场景平均 SAM(A历史): {avg_sam_hist_A:.4f}° (历史: 39.2232°, 绝对差: {diff_mean_sam:.6f}°, 门槛<=0.2°) -> {'PASS' if pass_sam_mean else 'FAIL'}")
    print(f"最大逐场景 PSNR 差异: {max_scene_psnr_diff:.6f} dB (门槛<=0.1 dB) -> {'PASS' if pass_scene_psnr else 'FAIL'}")
    print(f"综合基线复现门槛判定: {'PASS (基线完美复现)' if baseline_pass else 'BLOCKED (基线复现失败)'}")

    # 9. 组间对比统计
    num_psnr_improved = sum(1 for r in scene_records if r["delta_psnr"] > 0)
    num_ssim_improved = sum(1 for r in scene_records if r["delta_ssim"] > 0)
    num_sam_fixed_improved = sum(1 for r in scene_records if r["delta_sam_fixed"] < 0)  # 角度下降为改善

    avg_delta_psnr = avg_psnr_B - avg_psnr_A
    avg_delta_ssim = avg_ssim_B - avg_ssim_A
    avg_delta_sam_fixed = avg_sam_fixed_B - avg_sam_fixed_A
    avg_delta_sam_hist = avg_sam_hist_B - avg_sam_hist_A

    # 全局聚合 MSE 换算 PSNR
    global_mse_A = sum(r["mse_A"] for r in scene_records) / num_scenes
    global_mse_B = sum(r["mse_B"] for r in scene_records) / num_scenes
    global_psnr_A = -10 * np.log10(global_mse_A)
    global_psnr_B = -10 * np.log10(global_mse_B)

    print("\n================================================================================")
    print("A/B 对照实验汇总结果")
    print("================================================================================")
    print(f"8 场景平均 PSNR: A组 = {avg_psnr_A:.4f} dB | B组 = {avg_psnr_B:.4f} dB | Δ = {avg_delta_psnr:+.4f} dB")
    print(f"全局聚合 PSNR:   A组 = {global_psnr_A:.4f} dB | B组 = {global_psnr_B:.4f} dB | Δ = {global_psnr_B - global_psnr_A:+.4f} dB")
    print(f"8 场景平均 SSIM: A组 = {avg_ssim_A:.4f} | B组 = {avg_ssim_B:.4f} | Δ = {avg_delta_ssim:+.4f}")
    print(f"固定掩膜 SAM:    A组 = {avg_sam_fixed_A:.4f}° | B组 = {avg_sam_fixed_B:.4f}° | Δ = {avg_delta_sam_fixed:+.4f}°")
    print(f"历史口径 SAM:    A组 = {avg_sam_hist_A:.4f}° | B组 = {avg_sam_hist_B:.4f}° | Δ = {avg_delta_sam_hist:+.4f}°")
    print(f"\n场景改善统计 (共8场景):")
    print(f"  PSNR 改善场景数: {num_psnr_improved} / 8")
    print(f"  SSIM 改善场景数: {num_ssim_improved} / 8")
    print(f"  SAM(固定) 改善场景数: {num_sam_fixed_improved} / 8")

    # 10. 保存 CSV
    csv_file = out_dir / "metrics_per_scene.csv"
    csv_fields = [
        "scene",
        "psnr_A", "psnr_B", "delta_psnr",
        "ssim_A", "ssim_B", "delta_ssim",
        "sam_fixed_A", "sam_fixed_B", "delta_sam_fixed",
        "sam_hist_A", "sam_hist_B", "delta_sam_hist",
        "sam_inter_A", "sam_inter_B", "delta_sam_inter",
        "r05_psnr", "diff_A_vs_r05_psnr",
        "elapsed_sec", "peak_vram_mb"
    ]
    with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for r in scene_records:
            writer.writerow({k: r[k] for k in csv_fields})
    print(f"\n逐场景指标 CSV 已写入: {csv_file.resolve()}")

    # 11. 保存 JSON
    summary_data = {
        "experiment_name": "R06-2_RGB_Channel_Swap",
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "hardware": {
            "gpu": gpu_name,
            "peak_vram_mb": round(torch.cuda.max_memory_allocated(device) / 1024 / 1024, 1),
            "device": str(device)
        },
        "config": {
            "crop_size": crop_size,
            "seed": 42,
            "lens_file": cfg["camera"]["lens_file"],
            "sensor_file": cfg["camera"]["sensor_file"],
            "ckpt_path": cfg["network"]["ckpt_path"],
            "dataset_path": val_dataset_path
        },
        "baseline_reproducibility": {
            "pass": baseline_pass,
            "avg_psnr_A": avg_psnr_A,
            "r05_ref_psnr": 18.1866,
            "diff_psnr": diff_mean_psnr,
            "avg_ssim_A": avg_ssim_A,
            "r05_ref_ssim": 0.6621,
            "diff_ssim": diff_mean_ssim,
            "avg_sam_hist_A": avg_sam_hist_A,
            "r05_ref_sam": 39.2232,
            "diff_sam": diff_mean_sam,
            "max_scene_psnr_diff": max_scene_psnr_diff
        },
        "group_summary": {
            "avg_psnr_A": avg_psnr_A,
            "avg_psnr_B": avg_psnr_B,
            "avg_delta_psnr": avg_delta_psnr,
            "global_psnr_A": global_psnr_A,
            "global_psnr_B": global_psnr_B,
            "global_delta_psnr": global_psnr_B - global_psnr_A,
            "avg_ssim_A": avg_ssim_A,
            "avg_ssim_B": avg_ssim_B,
            "avg_delta_ssim": avg_delta_ssim,
            "avg_sam_fixed_A": avg_sam_fixed_A,
            "avg_sam_fixed_B": avg_sam_fixed_B,
            "avg_delta_sam_fixed": avg_delta_sam_fixed,
            "avg_sam_hist_A": avg_sam_hist_A,
            "avg_sam_hist_B": avg_sam_hist_B,
            "avg_delta_sam_hist": avg_delta_sam_hist,
            "scenes_improved_psnr": f"{num_psnr_improved}/8",
            "scenes_improved_ssim": f"{num_ssim_improved}/8",
            "scenes_improved_sam_fixed": f"{num_sam_fixed_improved}/8"
        },
        "per_scene": scene_records
    }

    json_file = out_dir / "metrics_summary.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)
    print(f"汇总 JSON 已写入: {json_file.resolve()}")
    print(f"总耗时: {time.perf_counter() - start_all:.2f} 秒")
    print("================================================================================")


if __name__ == "__main__":
    main()
