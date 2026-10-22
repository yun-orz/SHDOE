
from pathlib import Path
import torch
from torchvision.utils import save_image

from hsi_dataset import CaveDataset
from src.hsi_camera import HSICamera

# 1. 设置 GPU
device = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)
print("计算设备:", device, flush=True)

# 2. 检查测试数据
dataset_list = Path("datasets/cave_val.txt")
scene_path = Path(
    dataset_list.read_text(encoding="utf-8").splitlines()[0]
)
png_files = sorted(scene_path.glob("*.png"))

assert scene_path.is_dir(), f"场景目录不存在: {scene_path}"
assert len(png_files) == 31, (
    f"期望 31 个波段，实际 {len(png_files)} 个"
)
print("测试场景:", scene_path)

# 3. 加载 CAVE 高光谱图像
dataset = CaveDataset(
    file_path=str(dataset_list),
    crop_size=(256, 256),
    is_train=False
)

sample = dataset[0]

# 增加 batch 维度
data_dict = {
    "wvln": sample["wvln"].unsqueeze(0),
    "img": sample["img"].unsqueeze(0),
}

print("高光谱图像:", data_dict["img"].shape)
print("波长数量:", data_dict["wvln"].shape[1])

# 4. 初始化高光谱相机
camera = HSICamera(
    lens_file="./lenses/paraxiallens/doelens_hsi.json",
    sensor_file="./sensors/flir/BFS-U3-200S7C-C.json",
    device=device,
)

# 5. DOE 前向成像
# 31 个波长都需要计算 PSF，可能耗时数分钟
print("开始计算 31 波段 DOE 前向成像...", flush=True)

with torch.no_grad():
    encoded_rgb, spectral_gt = camera.render(data_dict)

    # 没有 DOE 模糊的参考 RGB 图像
    reference_rgb = camera.spectral2rgb(spectral_gt)

print("编码图像:", encoded_rgb.shape)
print("真实光谱:", spectral_gt.shape)

for name, img in [
    ("Ground Truth HSI", spectral_gt),
    ("Reference RGB", reference_rgb),
    ("Encoded RGB", encoded_rgb),
]:
    print(f"\n{name}")
    print("Shape:", img.shape)
    print("Min:", img.min().item())
    print("Max:", img.max().item())
    print("Mean:", img.mean().item())
    print("Finite:", torch.isfinite(img).all().item())

# 6. 生成结果
output_dir = Path("results/R03_forward")
output_dir.mkdir(parents=True, exist_ok=True)

save_image(
    reference_rgb,
    output_dir / "reference_rgb.png"
)
save_image(
    encoded_rgb,
    output_dir / "encoded_rgb.png"
)
save_image(
    torch.cat([reference_rgb, encoded_rgb], dim=-1),
    output_dir / "comparison.png"
)

difference = (
    reference_rgb - encoded_rgb
).abs().mean().item()

print("RGB 平均绝对差异:", difference)
print("结果保存到:", output_dir.resolve())
print("R03 前向成像完成！")
