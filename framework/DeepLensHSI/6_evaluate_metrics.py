
import argparse
import csv
from pathlib import Path

import torch

from src.utils import batch_ssim


parser = argparse.ArgumentParser()
parser.add_argument("--input", type=Path, default=Path("results/R06_2_validation"))
parser.add_argument("--output", type=Path, help="指标CSV路径，必须尚不存在")
args = parser.parse_args()
root = args.input
output = args.output or root / "metrics.csv"
if output.exists():
    raise FileExistsError(f"指标文件已存在，请指定新的 --output：{output}")
files = sorted(root.glob("*/spectra.pt"))

assert len(files) == 8, (
    f"预期8个场景，实际找到{len(files)}个"
)


def compute_metrics(pred, gt):
    assert pred.shape == gt.shape
    assert pred.ndim == 4 and pred.shape[1] == 31
    assert torch.isfinite(pred).all()
    assert torch.isfinite(gt).all()

    # 1. PSNR: 与此前实验保持一致
    mse = ((pred - gt) ** 2).mean()
    psnr = -10 * torch.log10(
        mse.clamp_min(1e-12)
    )

    # 2. SSIM: 采用原仓库实现
    # 内部转换为8位图像后计算
    ssim = batch_ssim(pred, gt)

    # 3. SAM: 每个像素沿31个光谱通道计算夹角
    dot = (pred * gt).sum(dim=1)
    gt_norm = torch.linalg.vector_norm(gt, dim=1)
    pred_norm = torch.linalg.vector_norm(pred, dim=1)

    # 零向量的光谱角无定义，将其排除
    valid = (gt_norm > 1e-8) & (pred_norm > 1e-8)

    assert valid.any(), "无有效光谱像素"

    cosine = dot[valid] / (
        gt_norm[valid] * pred_norm[valid]
    )
    cosine = cosine.clamp(-1.0, 1.0)

    angles_deg = torch.rad2deg(
        torch.acos(cosine)
    )
    sam = angles_deg.mean()
    valid_pct = valid.float().mean() * 100

    # 固定GT掩膜作为R06-2的公平比较口径；预测零向量按90度计。
    valid_gt = gt_norm > 1e-8
    fixed_angles = torch.full_like(gt_norm[valid_gt], 90.0)
    nonzero = pred_norm[valid_gt] > 1e-8
    fixed_cos = dot[valid_gt][nonzero] / (gt_norm[valid_gt][nonzero] * pred_norm[valid_gt][nonzero])
    fixed_angles[nonzero] = torch.rad2deg(torch.acos(fixed_cos.clamp(-1.0, 1.0)))
    sam_fixed = fixed_angles.mean()

    return {
        "psnr_db": float(psnr),
        "ssim": float(ssim),
        "sam_deg": float(sam),
        "sam_valid_pct": float(valid_pct),
        "sam_fixed_deg": float(sam_fixed),
        "sam_fixed_valid_pct": float(valid_gt.float().mean() * 100),
    }


rows = []

for path in files:
    data = torch.load(
        path, map_location="cpu", weights_only=True
    )
    gt = data["gt"].float()
    pred = data["pred"].float()

    result = compute_metrics(pred, gt)
    result["scene"] = path.parent.name
    rows.append(result)

    print(
        f'{result["scene"]:30s} | '
        f'PSNR={result["psnr_db"]:.2f} dB | '
        f'SSIM={result["ssim"]:.4f} | '
        f'SAM={result["sam_deg"]:.2f} deg'
    )

# 逐场景算术平均
print("\n===== 验证集平均指标 =====")

print("sam_deg沿用历史双有效掩膜；sam_fixed_deg为固定GT掩膜")
for key in ["psnr_db", "ssim", "sam_deg", "sam_fixed_deg"]:
    avg = sum(r[key] for r in rows) / len(rows)
    print(f"{key}: {avg:.4f}")

print(
    "SAM有效像素比例范围:",
    f'{min(r["sam_valid_pct"] for r in rows):.2f}%',
    "至",
    f'{max(r["sam_valid_pct"] for r in rows):.2f}%'
)

# 保存评价表格
output.parent.mkdir(parents=True, exist_ok=True)

with open(output, "x", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "scene", "psnr_db", "ssim",
            "sam_deg", "sam_valid_pct",
            "sam_fixed_deg", "sam_fixed_valid_pct"
        ]
    )
    writer.writeheader()
    writer.writerows(rows)

print("\n评价结果已保存:", output.resolve())
print("指标评价完成")
