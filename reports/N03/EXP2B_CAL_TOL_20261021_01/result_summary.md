# A：9带位置标定容差

EXP2B EXPLORATORY, archived PSFs; N03 G0 FAIL; N02 G2/G3_Numerics FAIL.

**工程PASS；1224例全部完成。原N03 G0和N02 G2/G3失败状态不变。**

完全复用EXP2正式连续源像元→detector积分、pitch=2.73978685612789um、186² detector、shape_only及物理RGB。A_nominal冻结，仅A_true平移，沿用零延拓及detector裁切后逐带归一。因此本实验不保留截取通量差，不是DOE加工纳米公差。
17个位置含唯一零基准，18条原谱、无噪声和原3seed Q40；Q40逐模型true signal匹配实际40dB，同谱/同seed标准高斯方向在全部δ间配对。没有P_in混合，没有oracle、未知位置搜索或重新标定。
A0零位72例逐例复现EXP2，最大估计绝对差0。非零位矩阵差及归一化前capture见shift_manifest；KKT/残差/非负性/实际SNR见metrics。
1 pixel=2.739786856128um=2739.786856128nm；0.005/0.01/0.02/0.05 pixel分别为[13.698934, 27.397869, 54.795737, 136.989343]nm。

## 预注册1%参考容差：首次离散超限区间

|协议|轴|方向|统计量|首次超限绝对pixel区间|对应绝对nm区间|说明|
|---|---|---|---|---|---|---|
|noiseless|x|negative|mean|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|noiseless|x|negative|median|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|noiseless|x|negative|p90|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|noiseless|x|negative|max|(0.02,0.05)|(54.7957,136.98934280639432)|FIRST_DISCRETE_CROSSING|
|noiseless|x|positive|mean|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|noiseless|x|positive|median|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|noiseless|x|positive|p90|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|noiseless|x|positive|max|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|noiseless|y|negative|mean|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|noiseless|y|negative|median|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|noiseless|y|negative|p90|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|noiseless|y|negative|max|(0.02,0.05)|(54.7957,136.98934280639432)|FIRST_DISCRETE_CROSSING|
|noiseless|y|positive|mean|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|noiseless|y|positive|median|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|noiseless|y|positive|p90|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|noiseless|y|positive|max|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|Q40|x|negative|mean|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|Q40|x|negative|median|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|Q40|x|negative|p90|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|Q40|x|negative|max|(0.02,0.05)|(54.7957,136.98934280639432)|FIRST_DISCRETE_CROSSING|
|Q40|x|positive|mean|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|Q40|x|positive|median|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|Q40|x|positive|p90|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|Q40|x|positive|max|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|Q40|y|negative|mean|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|Q40|y|negative|median|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|Q40|y|negative|p90|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|Q40|y|negative|max|(0.02,0.05)|(54.7957,136.98934280639432)|FIRST_DISCRETE_CROSSING|
|Q40|y|positive|mean|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|Q40|y|positive|median|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|Q40|y|positive|p90|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|
|Q40|y|positive|max|(0.05,None)|(136.989,None)|NO_CROSSING_IN_TESTED_GRID|

None表示在已扫描最大0.05pixel仍未发现超限，不是可外推的物理上限；区间只给相邻离散位置。未强制误差单调，完整序列及monotonic标记见tolerance_intervals.csv。0.5%/2%敏感性同表保留，未事后选择通过阈值。

## 全谱统计与最坏谱

|位置|协议|均值|中位数|P90|最坏|超过1%比例|seed均值SD|最坏谱|
|---|---|---:|---:|---:|---:|---:|---:|---|
|origin|noiseless|3.34957e-15|3.06276e-15|5.26806e-15|6.65918e-15|0|0|onehot_660|
|origin|Q40|0.000106375|8.07388e-05|0.00022607|0.000277595|0|6.99e-06|random_0|
|x_-0.05|noiseless|0.0049168|0.00514322|0.00784334|0.010218|0.0555556|0|onehot_540|
|x_-0.05|Q40|0.00492178|0.00514818|0.00872469|0.0101866|0.0555556|1.18e-05|onehot_540|
|x_-0.02|noiseless|0.00194645|0.00205595|0.00312411|0.00406618|0|0|onehot_540|
|x_-0.02|Q40|0.00195492|0.00207406|0.00348761|0.00403519|0|1.01e-05|onehot_540|
|x_-0.01|noiseless|0.000971465|0.00102799|0.00156061|0.00202955|0|0|onehot_540|
|x_-0.01|Q40|0.000983999|0.00106303|0.00174776|0.00199908|0|8.64e-06|onehot_540|
|x_-0.005|noiseless|0.000485531|0.000514251|0.000780189|0.00101471|0|0|onehot_540|
|x_-0.005|Q40|0.000504815|0.000533957|0.000895616|0.000985232|0|7.22e-06|onehot_540|
|x_+0.005|noiseless|0.000444192|0.000494864|0.000678446|0.000736458|0|0|near_equal|
|x_+0.005|Q40|0.000454883|0.000491497|0.000705883|0.00081516|0|7.09e-06|broad_585|
|x_+0.01|noiseless|0.000888635|0.00098967|0.00135687|0.00147274|0|0|near_equal|
|x_+0.01|Q40|0.000892375|0.00099163|0.00143771|0.00153996|0|5.95e-06|near_equal|
|x_+0.02|noiseless|0.00178034|0.00198223|0.00271133|0.0029515|0|0|near_equal|
|x_+0.02|Q40|0.0017797|0.00200396|0.00281803|0.00301726|0|5.11e-06|near_equal|
|x_+0.05|noiseless|0.00447733|0.00497225|0.00680575|0.0073958|0|0|near_equal|
|x_+0.05|Q40|0.00447224|0.00499349|0.00710909|0.00746062|0|3.26e-06|near_equal|
|y_-0.05|noiseless|0.00447284|0.00478337|0.00702459|0.0114157|0.0555556|0|onehot_630|
|y_-0.05|Q40|0.00445945|0.00475506|0.00726268|0.0113849|0.0555556|1.76e-05|onehot_630|
|y_-0.02|noiseless|0.00177886|0.00189842|0.00280136|0.00454281|0|0|onehot_630|
|y_-0.02|Q40|0.00176716|0.00187344|0.00289222|0.00451249|0|1.71e-05|onehot_630|
|y_-0.01|noiseless|0.00088824|0.00094731|0.00140014|0.00226777|0|0|onehot_630|
|y_-0.01|Q40|0.000881054|0.000927391|0.00145053|0.00223793|0|1.61e-05|onehot_630|
|y_-0.005|noiseless|0.000444122|0.000473642|0.000699976|0.00113382|0|0|onehot_630|
|y_-0.005|Q40|0.000445072|0.000451668|0.000735891|0.00110464|0|1.41e-05|onehot_630|
|y_+0.005|noiseless|0.000407908|0.00045987|0.000606381|0.000832742|0|0|onehot_660|
|y_+0.005|Q40|0.000434543|0.000477075|0.000721458|0.000873023|0|1.13e-05|onehot_660|
|y_+0.01|noiseless|0.000815365|0.000919576|0.0012125|0.00166553|0|0|onehot_660|
|y_+0.01|Q40|0.00083592|0.000957189|0.00130075|0.0017064|0|1.11e-05|onehot_660|
|y_+0.02|noiseless|0.00163188|0.0018401|0.00242816|0.00333744|0|0|onehot_660|
|y_+0.02|Q40|0.00164926|0.00189939|0.00250321|0.00337827|0|1.1e-05|onehot_660|
|y_+0.05|noiseless|0.00408709|0.00459711|0.00606809|0.00838682|0|0|onehot_660|
|y_+0.05|Q40|0.00410059|0.00465293|0.00609422|0.00842761|0|9.04e-06|onehot_660|

按onehot/double/broad/random分组的同口径表，以及SAM、相对总能量偏差、传感器相对残差，见tolerance_summary.csv；每个位置无噪声18例、Q40为54例。跨样本SD与3个seed均值之间的样本SD分别保存，3seed不解释为精确置信区间。
NRMSE=||estimate-truth||₂/||truth||₂；SAM为向量夹角度。传感器残差不能替代谱误差。旧B0/B1只读配对参考见archived_control_comparison.csv，分别报告均值、中位数与B2零位逐谱胜率，不把秩3控制的低中位数当可恢复性门槛。

测试24项通过、失败0；全部求解KKT≤1.68686e-16，失败率0。真谱仅在合成/评价出现；真实恢复接口只有A_nominal和y。
图：figures/nrmse_signed_shift.png、fraction_exceeding_threshold.png、worst_spectra.png。估计曲线按metrics.solution_index索引spectral_solutions.npz，真谱指向旧EXP2配置并保存18×9的小数组，不复制大型图像。
结论仅限归档PSF的点源位置标定敏感性；方向/正负号差异按实测表保留。达到扫描上界未超限不等于任何更大位移可用，也不等于DOE器件纳米级加工合格。B支路独立验收，不与本支路合并宣称物理认证。
