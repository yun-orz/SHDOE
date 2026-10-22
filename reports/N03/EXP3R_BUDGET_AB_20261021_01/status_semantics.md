EXPLORATORY / N03 G0 FAIL / N02 G2+G3_Numerics FAIL

H5按实验前frozen_contract中的严格定义判定：选中缓存点必须与成功Powell返回终点逐位相同。只属于成功起点的中间评价点不自动取得终点收敛认证。该定义从未在结果出来后放宽，也未更改原最低缓存残差选点规则。

selected_start_id=-1表示第一次评价来自粗网格。局部起点成功数、预算耗尽数、选中缓存点的来源与终点认证是不同统计。H5未认证的40个B候选，不等同40个候选全部来自预算耗尽起点。逐例见selection_provenance.csv。

后验来源分类：{
  "A": {
    "seen_in_converged_start_not_returned_endpoint": 11,
    "seen_only_in_nonconverged_starts": 37
  },
  "B": {
    "seen_in_converged_start_not_returned_endpoint": 28,
    "seen_only_in_nonconverged_starts": 12,
    "certified_returned_endpoint": 8
  }
}

最终决定仍为EXP3R_PILOT_FAIL，原因FAIL_OPTIMIZER_CONVERGENCE。没有追加优化、改变候选选择或运行full。
