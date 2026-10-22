# G3 工艺/材料敏感性

SIMULATED G3-Fabrication-Robustness: PASS（限已列假设扰动影响已定量，不代表所有扰动通过硬门）。
实测加工验收：NOT_TESTED。共17组×25通道，连续/Q10-floor基线见B1/B2。各组形态/链接/能量/相关性见gate3_fabrication.csv及候选原始cases。
材料Cauchy、常数及±0.005均为ASSUMED。局部噪声、圆角、横向采样、孔径偏心、倾斜参数见fabrication_assumptions.json，不能外推加工良率。像元积分见gate3_pixel_integration.csv。
须确认：IP-Dip2实测色散、10级高度标定/误差分布、最小横向线宽/侧壁角、固化收缩、有效填充与传感器MTF。
