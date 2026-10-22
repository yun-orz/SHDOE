
from pathlib import Path

import torch
import yaml
from torchvision.utils import save_image

from hsi_dataset import CaveDataset
from src.hsi_camera import HSICamera
from src.network import NAFNet

device = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

# 1. 加载原仓库配置
with open("configs/1_deeplens_hsi.yml", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

# 2. 加载一个 CAVE 验证场景
dataset = CaveDataset(
    file_path=cfg["eval_set"]["dataset"],
    crop_size=(256, 256),
    is_train=False
)
sample = dataset[0]

data = {
    "wvln": sample["wvln"].unsqueeze(0),
    "img": sample["img"].unsqueeze(0),
}

# 3. 初始化光学相机
camera = HSICamera(
    lens_file=cfg["camera"]["lens_file"],
    sensor_file=cfg["camera"]["sensor_file"],
    device=device
)

print("开始生成 DOE 编码图像...", flush=True)

with torch.no_grad():
    encoded_rgb, gt = camera.render(data)

# 4. 初始化 NAFNet
net_cfg = cfg["network"]

model = NAFNet(
    in_chan=net_cfg["in_chan"],
    out_chan=net_cfg["out_chan"],
    width=net_cfg["width"],
    middle_blk_num=net_cfg["middle_blk_num"],
    enc_blk_nums=net_cfg["enc_blk_nums"],
    dec_blk_nums=net_cfg["dec_blk_nums"],
).to(device)

# 5. 加载预训练权重
ckpt_path = Path(net_cfg["ckpt_path"])
assert ckpt_path.is_file(), f"权重不存在: {ckpt_path}"

weights = torch.load(
    ckpt_path,
    map_location=device,
    weights_only=True
)

if isinstance(weights, dict) and "model" in weights:
    weights = weights["model"]

model.load_state_dict(weights, strict=True)
model.eval()

print("预训练权重加载成功")

# 6. 网络重建
with torch.no_grad():
    reconstructed = model(encoded_rgb).clamp(0, 1)

    reference_rgb = camera.spectral2rgb(gt)
    reconstructed_rgb = camera.spectral2rgb(reconstructed)

# 7. 计算光谱重建 PSNR
mse = torch.mean((reconstructed - gt) ** 2)
psnr = -10 * torch.log10(mse.clamp_min(1e-12))

print("编码图像:", encoded_rgb.shape)
print("重建光谱:", reconstructed.shape)
print("光谱重建 MSE:", mse.item())
print("光谱重建 PSNR:", psnr.item(), "dB")

# 各波段 MSE
band_mse = ((reconstructed - gt) ** 2).mean(
    dim=(0, 2, 3)
)

# 各波段 PSNR
band_psnr = -10 * torch.log10(
    band_mse.clamp_min(1e-12)
)

print("\n===== 各波段重建 PSNR =====")

for i in range(31):
    wavelength = 400 + i * 10
    print(
        f"{wavelength} nm: "
        f"{band_psnr[i].item():.2f} dB"
    )

# 检查重建 RGB 的颜色偏差
print("\n===== RGB 通道平均值 =====")

for name, image in [
    ("Reference", reference_rgb),
    ("Reconstructed", reconstructed_rgb)
]:
    means = image.mean(dim=(0, 2, 3))
    print(name, means.cpu().tolist())

# 8. 保存可视化结果
out = Path("results/R04_pretrained")
out.mkdir(parents=True, exist_ok=True)

comparison = torch.cat(
    [reference_rgb, encoded_rgb, reconstructed_rgb],
    dim=3
)

save_image(
    comparison.clamp(0, 1),
    out / "comparison.png"
)

torch.save(
    reconstructed.cpu(),
    out / "reconstructed_hsi.pt"
)

print("R04 推理完成！")
print("结果路径:", out.resolve())

print("\n===== 波段重建能力诊断 =====")

# 真实光谱各波段平均强度
band_mean = gt.mean(dim=(0, 2, 3))

# 各波段重建 MSE
model_mse = ((reconstructed - gt) ** 2).mean(
    dim=(0, 2, 3)
)

# 零图像基准：始终预测零
zero_mse = (gt ** 2).mean(dim=(0, 2, 3))

model_psnr = -10 * torch.log10(
    model_mse.clamp_min(1e-12)
)

zero_psnr = -10 * torch.log10(
    zero_mse.clamp_min(1e-12)
)

for i in [0, 5, 10, 15, 20, 25, 30]:
    print(
        f"{400 + i * 10} nm | "
        f"GT均值={band_mean[i].item():.5f} | "
        f"模型PSNR={model_psnr[i].item():.2f} | "
        f"零图基准={zero_psnr[i].item():.2f} | "
        f"提升={(model_psnr[i]-zero_psnr[i]).item():.2f} dB"
    )

print("\n===== RGB通道平均值 =====")

for name, img in [
    ("Reference", reference_rgb),
    ("Reconstructed", reconstructed_rgb)
]:
    means = img.mean(dim=(0, 2, 3))
    print(name, means.cpu().tolist())