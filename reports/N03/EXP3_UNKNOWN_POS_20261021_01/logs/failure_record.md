# 首次运行工程故障记录

48幅pilot计算已完成，写入pilot_gate.json时NumPy int64统计量无法由标准JSON序列化，进程退出；该JSON是未写完的故障证据，不能用作验收。

修复仅将NumPy标量转换为Python标量，不修改模型、优化预算、样本、噪声或阈值。旧目录保留；在EXP3_UNKNOWN_POS_20261021_02以完全相同参数重跑。
