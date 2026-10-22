
import argparse
import time
from pathlib import Path

import torch
import yaml
from torchvision.utils import save_image

from hsi_dataset import CaveDataset
from src.hsi_camera import HSICamera
from src.network import NAFNet


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--output", type=Path, help="尚不存在的新输出目录")
    parser.add_argument("--swap-rb", action=argparse.BooleanOptionalAction, default=None,
                        help="覆盖配置中的网络输入红蓝交换开关")
    args = parser.parse_args()

    assert torch.cuda.is_available(), "未检测到 CUDA GPU"
    device = torch.device("cuda")

    # 1. 加载原仓库配置
    with open("configs/1_deeplens_hsi.yml", "r",
              encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # 只适配网络输入，不改传感器响应、GT或预训练权重。
    swap_rb = cfg["network"].get("swap_rgb_channels", False) if args.swap_rb is None else args.swap_rb
    out_root = args.output or Path("results/R06_2_validation" if swap_rb else "results/R05_validation")
    if out_root.exists():
        raise FileExistsError(f"输出目录已存在，请指定新的 --output：{out_root}")
    if args.limit < 1:
        raise ValueError("--limit必须为正整数")
    torch.manual_seed(cfg.get("seed", 42))
    print("网络输入通道:", "BGR（R06-2）" if swap_rb else "RGB（R05对照）")

    # 2. 验证集：保持原仓库的 512×512 配置
    dataset = CaveDataset(
        file_path=cfg["eval_set"]["dataset"],
        crop_size=cfg["eval_set"]["crop_size"],
        is_train=False
    )

    print("验证集场景总数:", len(dataset))
    print("本次测试场景数:", min(args.limit, len(dataset)))
    print("GPU:", torch.cuda.get_device_name(0))

    # 3. 初始化 DOE 相机
    camera = HSICamera(
        lens_file=cfg["camera"]["lens_file"],
        sensor_file=cfg["camera"]["sensor_file"],
        device=device
    )

    # 4. 初始化 NAFNet
    nc = cfg["network"]
    model = NAFNet(
        in_chan=nc["in_chan"],
        out_chan=nc["out_chan"],
        width=nc["width"],
        middle_blk_num=nc["middle_blk_num"],
        enc_blk_nums=nc["enc_blk_nums"],
        dec_blk_nums=nc["dec_blk_nums"]
    ).to(device)

    ckpt = torch.load(
        nc["ckpt_path"],
        map_location=device,
        weights_only=True
    )

    if isinstance(ckpt, dict) and "model" in ckpt:
        ckpt = ckpt["model"]

    model.load_state_dict(ckpt, strict=True)
    model.eval()

    print("预训练模型加载成功")

    # 5. 创建输出目录
    out_root.mkdir(parents=True, exist_ok=False)

    # 6. 逐场景前向编码与重建
    for i in range(min(args.limit, len(dataset))):
        start = time.perf_counter()
        scene_name = Path(dataset.image_folders[i]).name
        out_dir = out_root / scene_name
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n===== 场景 {i + 1}: {scene_name} =====",
              flush=True)

        sample = dataset[i]

        data = {
            "wvln": sample["wvln"].unsqueeze(0),
            "img": sample["img"].unsqueeze(0)
        }

        with torch.no_grad():
            # 完整原仓库 DOE 前向模型
            encoded_rgb, gt = camera.render(data)

            # 网络重建 31 波段
            model_input = encoded_rgb[:, [2, 1, 0], :, :] if swap_rb else encoded_rgb
            pred = model(model_input).clamp(0, 1)

            # RGB 可视化
            reference_rgb = camera.spectral2rgb(gt)
            reconstructed_rgb = camera.spectral2rgb(pred)

            # 计算当前场景的总体 PSNR
            mse = torch.mean((pred - gt) ** 2)
            psnr = -10 * torch.log10(
                mse.clamp_min(1e-12)
            )

        # 7. 保存结果
        comparison = torch.cat(
            [reference_rgb, encoded_rgb, reconstructed_rgb],
            dim=3
        )

        save_image(
            comparison.clamp(0, 1),
            out_dir / "comparison.png"
        )

        # 保存光谱真值和预测，用于后续指标评价
        torch.save(
            {
                "gt": gt.detach().cpu(),
                "pred": pred.detach().cpu()
            },
            out_dir / "spectra.pt"
        )

        print("GT shape:", tuple(gt.shape))
        print("Pred shape:", tuple(pred.shape))
        print("PSNR:", round(psnr.item(), 4), "dB")
        print("耗时:", round(time.perf_counter() - start, 1), "秒")
        print("保存路径:", out_dir.resolve(), flush=True)

    print("\n预训练推理完成，通道适配:", swap_rb)


if __name__ == "__main__":
    main()
