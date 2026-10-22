# N02-0 仓库审计

真实根目录：`E:\SpiralDOE_HSI\n00_run_20261009`；Git HEAD：`b9bf90c94bda664502d309be147949262fa71309`；起始dirty清单见git_status_before.txt。
默认系统Python只有CPU版本torch，选用现有`D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe`，未安装依赖。
设备：NVIDIA GeForce RTX 4060 Laptop GPU；可用磁盘：78.11 GiB。
N00/N01历史不改写；仅新建configs/n02、experiments/n02、results/n02、reports/n02。
保护快照记录全部历史文件size/mtime，文本额外SHA；不声称历史全部二进制内容哈希。

## 真实入口与冻结依据
- `E:\SpiralDOE_HSI\n00_run_20261009\src\spiral_hsi\optics\propagation.py`
- `E:\SpiralDOE_HSI\n00_run_20261009\src\spiral_hsi\optics\phase_from_height.py`
- `E:\SpiralDOE_HSI\n00_run_20261009\experiments\N01_1\model.py`
- `E:\SpiralDOE_HSI\n00_run_20261009\experiments\N01_2A\model.py`
- `E:\SpiralDOE_HSI\n00_run_20261009\experiments\N01_2E_multiorder_pilot\run.py`
- `E:\SpiralDOE_HSI\n00_run_20261009\experiments\N01_3A_G2_f2_q6_13wave\support.py`
- `E:\SpiralDOE_HSI\n00_run_20261009\experiments\N01_2E_m12_branch_diagnostic\analyze.py`
- `E:\SpiralDOE_HSI\n00_run_20261009\results\N01_3A_G2_f2_q6_13wave\g2_20261016_01\acquisition_plan.json`
- `E:\SpiralDOE_HSI\n00_run_20261009\results\N01_3A_G3_f2_q6_blue_dense\g3_20261016_01\hypothesis_and_endpoints.json`
- `E:\SpiralDOE_HSI\n00_run_20261009\results\N01_3A_G5_f2_q6_candidate_sensitivity\g5_20261017_01\summary.md`
- `E:\SpiralDOE_HSI\n00_run_20261009\reports\N01_2A\N01_2A_固定高度DOE波长旋转可行性研究报告.md`
- `E:\SpiralDOE_HSI\N02_单孔径低浮雕波长旋转单螺旋DOE设计方案_MF_SH_DOE.md`
- `C:\Users\李咏晨\Downloads\N02_MF_SH_DOE_Codex_%E5%AE%8C%E6%95%B4%E6%89%A7%E8%A1%8C%E8%A7%84%E5%88%92.md`

N01-2A：W/C同为R=1000um,f=20mm,550nm设计,400–700nm,熔融石英,18cm物距,22.495mm探测面。
W=14/31有效；C=31/31有效及-82.2099°，数值来自冻结报告，不重新实验。高度以原metadata及height文件为准，历史方案文档的55.488um与报告55.505um不一致，保留差异。
F2-q6：等面积L8、q6/G3；13点12/13有效，蓝端410/415nm双峰，G5证实候选截断敏感。
全部历史为NON-FAIR REFERENCE，材料、几何、波段不同，不作严格优越性证明。
