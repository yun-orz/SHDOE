# G3 数值收敛

SIMULATED G3-Numerics: **FAIL**。
关键判定采用padding4、相同物理视场dx0.5、独立SciPy ASM；complex64和Fresnel近似另列，不能覆盖精确模型失败。
预注册容差见protocol_frozen.json；逐工况原始PSF及能量见convergence/cases与gate3_convergence.csv。
形态L1、峰位/角度、主盘外峰比、主瓣入瞳效率、边缘与Parseval门全部报告。ROI99另列而不当作Parseval守恒。
