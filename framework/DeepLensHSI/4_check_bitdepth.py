
import cv2
import numpy as np
from pathlib import Path

# 选择一个实际波段
folder = Path(
    "datasets/cave/photo_and_face_ms/photo_and_face_ms"
)
path = folder / "photo_and_face_ms_01.png"

# 原始 16 位读取
img16 = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)

# 原仓库 8 位读取
img8 = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)

# 两种归一化方式
x16 = img16.astype(np.float64) / 65535.0
x8 = img8.astype(np.float64) / 255.0

error = np.abs(x16 - x8)

print("原始类型:", img16.dtype)
print("仓库读取类型:", img8.dtype)

print("\n===== 归一化强度 =====")
print("16位均值:", x16.mean())
print("8位均值:", x8.mean())

print("\n===== 量化误差 =====")
print("平均绝对误差:", error.mean())
print("最大绝对误差:", error.max())

print("\n===== 灰度等级数量 =====")
print("原始16位:", len(np.unique(img16)))
print("转换8位:", len(np.unique(img8)))
