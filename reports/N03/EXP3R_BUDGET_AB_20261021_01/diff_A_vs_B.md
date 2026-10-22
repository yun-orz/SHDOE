EXPLORATORY / N03 G0 FAIL / N02 G2+G3_Numerics FAIL

直接编译canonical旧joint_solve函数AST，只修改唯一maxfev常量；断言上限随预算派生，不参与数值优化。记录通过代理包装matrix/NNLS/minimize，不改变返回值和候选顺序。

```diff
--- A55
+++ B150
@@ -22,7 +22,7 @@
     ranked = sorted(((evaluate(p), p) for p in coarse))
     endings = []
     for (_, p) in ranked[:ALGORITHM['starts']]:
-        opt = minimize(evaluate, p, method='Powell', bounds=[(-0.5, 0.5)] * 2, options=dict(maxfev=55, xtol=1e-05, ftol=1e-10))
+        opt = minimize(evaluate, p, method='Powell', bounds=[(-0.5, 0.5)] * 2, options=dict(maxfev=150, xtol=1e-05, ftol=1e-10))
         endings.append(dict(start=list(p), position=opt.x.tolist(), loss=float(opt.fun), success=bool(opt.success), message=str(opt.message), nfev=int(opt.nfev)))
     ordered = sorted(cache, key=lambda p: cache[p][0])
     best = ordered[0]

```
