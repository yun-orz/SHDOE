"""仅mock优化器与微型几何的合同测试，不运行额外物理定位实验。"""
import ast
import inspect
import numpy as np


def checks(runner, cases, model):
    result = []
    def check(name, passed, **details):
        result.append(dict(name=name,passed=bool(passed),**details))
    check('48观测唯一且只读',len(cases)==48 and len({c['id'] for c in cases})==48 and all(not c['y'].flags.writeable for c in cases))
    check('24clean24Q40单seed',sum(c['source']['protocol']=='noiseless' for c in cases)==24 and
          sum(c['source']['protocol']=='Q40' for c in cases)==24 and {int(c['source']['seed']) for c in cases}=={0,20261021})
    check('Joint无真值入参',list(inspect.signature(runner.joint_solve).parameters)==['y','model','frozen_params'])
    a,b=runner.algorithm_ast(55),runner.algorithm_ast(150)
    for node in ast.walk(b):
        if isinstance(node,ast.keyword) and node.arg=='maxfev': node.value.value=55
    check('原函数AST两路仅maxfev不同',ast.dump(a)==ast.dump(b))
    old=runner.ast.parse(runner.HISTORICAL_SOLVER.read_text(encoding='utf-8-sig'))
    oldfn=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name=='joint_solve')
    check('A函数AST与canonical逐节点相同',ast.dump(a.body[0])==ast.dump(oldfn))
    check('几何单位与RGB布局',model.pitch==2.7397868561278864 and model.matrix((0,0))[0].shape==(103788,9))
    tiny=np.zeros((3,3));tiny[1,1]=1
    edges=np.arange(4,dtype=float)-1.5
    from frozen_pilot import sampling
    w=sampling.overlap_matrix(edges,edges)
    plus=sampling.rebin(tiny,w,sampling.overlap_matrix(edges+.25,edges))
    minus=sampling.rebin(tiny,w,sampling.overlap_matrix(edges-.25,edges))
    check('正负位移方向与连续面积积分',plus[1,2]>0 and minus[1,0]>0 and np.isclose(plus.sum(),1) and np.isclose(minus.sum(),1))
    check('Q40原SNR与噪声指纹',all(c['snr'] is None or abs(c['snr']-40)<1e-8 for c in cases))
    original=runner.scipy_minimize
    seen=[]
    class GuardModel:
        __slots__=()
        def matrix(self,p):
            return np.array([[1.,0.],[0.,1.],[float(p[0]),float(p[1])]]),np.ones(2)
        def __getattr__(self,name):
            raise AssertionError('禁止访问真值或其他接口：'+name)
    def fake(fun,start,method,bounds,options):
        seen.append(options.copy())
        p=np.array(start);value=fun(p)
        return runner.SimpleNamespace(x=p,fun=value,success=False,status=1,message='Maximum number of function evaluations has been exceeded.',nfev=options['maxfev'],nit=1)
    try:
        runner.scipy_minimize=fake
        y=np.array([.5,.5,0.]);y.setflags(write=False)
        outputs=[runner.joint_solve(y,GuardModel(),{'maxfev_per_start':budget}) for budget in [55,150]]
    finally:
        runner.scipy_minimize=original
    check('mock验证maxfev确实传入SciPy',[x['maxfev'] for x in seen]==[55,55,150,150])
    check('Powell失败不得误标SUCCESS',all(o['joint_optimizer_status']!='SUCCESS' and not o['joint_numerically_accepted'] for o in outputs))
    check('NNLS非负KKT与直接残差',all(o['estimate'].min()>=0 and o['kkt']<=1e-7 and
          np.isclose(o['loss'],np.linalg.norm(GuardModel().matrix(o['position'])[0]@o['estimate']-y)**2/np.linalg.norm(y)**2) for o in outputs))
    check('mock真值隔离',all(o['joint_has_candidate'] for o in outputs))
    from validate_results import gates, percentile
    prototype=[]
    for group in ['A','B']:
        for i in range(48):
            for method in ['O','F','J']:
                prototype.append(dict(budget_group=group,observation=str(i),method=method,
                                      protocol='noiseless' if i<24 else 'Q40',position_error_pixel=.005 if i<24 else .02,
                                      NRMSE=.01,selected_candidate_converged=True,joint_numerically_accepted=True,
                                      position_boundary_hit=False))
    controls=[dict(passed=True,same_y=True) for _ in range(96)]
    gate=gates(prototype,True,True,True,controls)
    check('hard gate逐例≤等号通过',all(gate[k]['passed'] for k in ['H2','H3','H4','H5','H6']))
    clean=next(r for r in prototype if r['budget_group']=='B' and r['method']=='J')
    clean['position_error_pixel']=.005+1e-10
    check('hard gate单例超限不能由mean掩盖',not gates(prototype,True,True,True,controls)['H2']['passed'])
    clean['position_error_pixel']=.005
    noisy=[r for r in prototype if r['budget_group']=='B' and r['method']=='J' and r['protocol']=='Q40']
    noisy[0]['position_error_pixel']=.02+1e-10
    check('Q40门实际检查位置',not gates(prototype,True,True,True,controls)['H3']['passed'])
    noisy[0]['position_error_pixel']=.02
    for r in noisy[:5]: r['NRMSE']=.0100001
    check('光谱80%比例门不能被残差代替',not gates(prototype,True,True,True,controls)['H4']['passed'])
    clean['joint_numerically_accepted']=False
    check('选中未收敛解触发H5失败',not gates(prototype,True,True,True,controls)['H5']['passed'])
    check('独立P90与NumPy一致',abs(percentile(list(range(24)))-np.quantile(np.arange(24),.9))<1e-14)
    return result
