"""先列负例与反例；不运行额外物理优化。"""
import copy
import math


def fixtures():
    def endpoint(sid, success, position, loss):
        return dict(start_id=sid,start=[0,0],position=position,loss=loss,success=success,
                    status=0 if success else 1,message='ok' if success else 'budget',
                    nfev=10 if success else 150,maxfev=150,nit=1,budget_exhausted=not success)
    def trace(kind):
        ends=[endpoint(0,kind!='failure',[.1,.2],.01),endpoint(1,False,[.3,.2],.03)]
        best=[.1,.2] if kind=='endpoint' else [.1+1e-13,.2]
        return dict(best_position=best,best_loss=.01,selected_start_id=0,
                    terminations=ends,candidates=[dict(position=best,relative_squared_residual=.01)],
                    local_requests=[dict(start_id=0,position=best)],
                    evaluation_records=[dict(position=best,nnls_success=True,nnls_KKT=1e-16,nnls_nonnegative=True)])
    return trace


def checks(core, writer):
    tests=[]
    def check(name,value): tests.append(dict(name=name,passed=bool(value)))
    make=fixtures()
    check('成功返回终点严格认证',core.classify(make('endpoint'))['provenance']=='SUCCESSFUL_RETURN_ENDPOINT')
    intermediate=core.classify(make('intermediate'))
    check('成功起点中间点不冒充严格终点',intermediate['provenance']=='SUCCESSFUL_START_INTERMEDIATE' and not intermediate['strict'])
    check('浮点接近不改写原H5',0<intermediate['nearest_successful_endpoint_distance']<1e-8)
    check('只有失败轨迹来源正确',core.classify(make('failure'))['provenance']=='UNSUCCESSFUL_START_ONLY')
    check('没有成功终点不回退缓存点',core.select_endpoint(make('failure')['terminations']) is None)
    broken=make('endpoint');del broken['local_requests']
    check('缺失关键轨迹明确UNVERIFIED',core.classify(broken)['status']=='UNVERIFIED')
    class Trap(dict):
        def __getitem__(self,key):
            if key in ('truth','dx_true','dy_true','NRMSE','SAM_deg'): raise AssertionError('GT leak')
            return super().__getitem__(key)
    endpoints=[Trap(start_id=0,success=True,position=[.1,.2],loss=.02),
               Trap(start_id=1,success=True,position=[.3,.4],loss=.01)]
    check('C1仅按目标选择且不访问真值',core.select_endpoint(endpoints)['start_id']==1)
    tie=[Trap(start_id=0,success=True,position=[.1,.2],loss=.01),
         Trap(start_id=1,success=True,position=[.3,.4],loss=.01)]
    check('目标相同保持原终点顺序',core.select_endpoint(tie)['start_id']==0)
    budget=core.MicroBudget()
    for _ in range(8): budget.start()
    try: budget.start();rejected=False
    except RuntimeError: rejected=True
    check('第9个精修起点被拒绝',rejected)
    for _ in range(80): budget.evaluate()
    try: budget.evaluate();rejected=False
    except RuntimeError: rejected=True
    check('单例第81次评价被拒绝',rejected)
    try: writer.path(writer.root.parent/'EXP3R_BUDGET_AB_20261021_01/pilot_gate.json');rejected=False
    except PermissionError: rejected=True
    check('旧报告路径写入被拒绝',rejected)
    values=[.3,.1,.2,.4]
    check('独立统计P90线性插值',math.isclose(core.stats(values)['p90'],.37))
    return tests
