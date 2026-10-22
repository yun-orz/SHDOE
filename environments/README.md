# 运行环境与移植说明

本次实测环境为D:/MiniAnaconda/envs/deeplens_hsi_4060/python.exe：Python 3.10.22、PyTorch 2.5.1+cu121、torchvision 0.20.1+cu121、NumPy 2.2.6、SciPy 1.15.3、CUDA运行时12.1，GPU为NVIDIA GeForce RTX 4060 Laptop GPU。与历史R05和N02环境一致。N00也在该环境通过T01–T06，与旧PSF完全一致。

系统默认python为3.10.4，未将其当成验收环境。doe_research实查为Python 3.12.15 / torch 2.10.0+cu128，未用于本次验收。原DeepLens environment.yml保留原文，其CUDA12.8规格不代表历史R05或本次环境。

`runtime_versions.json`记录完整实测包版本；`requirements_runtime.txt`依据已安装distribution的实际版本生成，包含PyTorch cu121索引。该清单不含`file:///home/conda`依赖。原N00 requirements.txt保留来源原文；其中不可移植的packaging路径，在新清单中由实际安装的packaging版本替代，没有删除依赖或盲装新版。

可移植环境安装示例（本次未新建或重装环境，不能宣称异机安装已验证）：

```powershell
conda create -n sh_hsi python=3.10.22
conda run -n sh_hsi python -m pip install -r E:\SH\environments\requirements_runtime.txt
```

驱动、CUDA兼容性与包索引可用性需在新主机重新核验。完整科研依赖未包含在Python wheel清单中的系统库，不应与二进制环境镜像等同。

验收通过`provenance/tools/record_run.py`记录命令、工作目录、退出码和耗时，并设置PYTHONDONTWRITEBYTECODE、MPLCONFIGDIR、TORCH_HOME、TEMP/TMP指向SH子目录。`provenance/guard/sitecustomize.py`拒绝访问两个源工程及个人Downloads；N00的测试子进程也通过PYTHONPATH继承该屏蔽。`source_N02_parity`只读源侧比较特意不启用屏蔽。

少量Matplotlib字体缓存和运行临时目录保留在provenance/runtime_cache；这是本次验收生成的小型缓存，不是迁入的旧缓存。不执行未经许可的删除操作。
