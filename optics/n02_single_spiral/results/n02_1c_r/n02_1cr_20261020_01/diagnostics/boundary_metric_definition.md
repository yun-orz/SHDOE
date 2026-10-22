# 全域16um边界份额定义

冻结源码：experiments/n02/optics.py propagate，b=round(16/dx)。
分子：I[:b,:]+I[-b:,:]+I[b:-b,:b]+I[b:-b,-b:]之和乘dx²；四角只计一次。
分母：整个填充传播数组ΣI dx²。原字段edge_fraction，本轮并列boundary_share_16um。
坐标原点在几何中心，像素(i-(N-1)/2)dx。标准输入2048um，pad2输出4096um、pad4输出8192um、pad5输出10240um；ROI始终512um。
dx0.5的旧输入4096像素仍2048um，pad2输出8192像素=4096um，条带32像素。它增加采样，不增加物理域。
条带面积=4Db-4b²，其中D为全域物理宽度，b=16um；不同D的面积与测量位置都不同，条带份额下降不是环绕误差的直接测量。
ROI外能量=有限域总能量-512um ROI能量；光学主瓣效率=主盘能量/入瞳能量，均不是上述边界指标。
原checks.edge=max(candidate_edge,frozen_baseline_edge)<0.001；基线超门时，候选达标也不能改变组合FAIL。本轮逐列保留candidate_edge、frozen_baseline_edge、combined_gate。
原0.001门永久保留；0.0005/0.001/0.002仅作敏感性图，不改变验收。
