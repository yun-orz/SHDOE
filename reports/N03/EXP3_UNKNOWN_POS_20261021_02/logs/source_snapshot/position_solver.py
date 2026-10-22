"""估计器仅接收观测和固定前向接口，不接收位置或光谱真值。"""
import itertools
import numpy as np
from scipy.optimize import minimize
from forward_adapter import f

ALGORITHM = dict(grid=[-.5, 0., .5], starts=2, local='Powell',
                 maxfev_per_start=55, max_evaluations=119, xtol=1e-5, ftol=1e-10)


def joint_solve(y, model):
    cache = {}; calls = 0; hits = 0; trace = []
    def evaluate(p):
        nonlocal calls, hits
        calls += 1
        key = tuple(float(v) for v in p)
        if key in cache:
            hits += 1
            return cache[key][0]
        a, capture = model.matrix(p)
        op = f.Operator(a)
        s, residual, kkt = op.solve(y)
        loss = residual**2
        cache[key] = (loss, s, kkt, capture)
        trace.append(dict(position=list(key),relative_squared_residual=loss))
        return loss
    coarse = list(itertools.product(ALGORITHM['grid'], repeat=2))
    ranked = sorted((evaluate(p), p) for p in coarse)
    endings = []
    for _, p in ranked[:ALGORITHM['starts']]:
        opt = minimize(evaluate, p, method='Powell', bounds=[(-.5,.5)]*2,
                       options=dict(maxfev=55, xtol=1e-5, ftol=1e-10))
        endings.append(dict(start=list(p),position=opt.x.tolist(),loss=float(opt.fun),
                            success=bool(opt.success),message=str(opt.message),nfev=int(opt.nfev)))
    ordered = sorted(cache, key=lambda p:cache[p][0]); best=ordered[0]
    loss,s,kkt,capture = cache[best]
    assert len(cache) <= ALGORITHM['max_evaluations']
    alternatives = [p for p in ordered if np.linalg.norm(np.array(p)-best)>.01]
    second = alternatives[0] if alternatives else ordered[min(1,len(ordered)-1)]
    return dict(position=list(best),estimate=s,loss=loss,kkt=kkt,capture=capture,
                trace=dict(evaluations=len(cache),nnls_calls=len(cache),cache_hits=hits,
                           requests=calls,terminations=endings,best_position=list(best),
                           best_loss=loss,second_position=list(second),second_loss=cache[second][0],
                           boundary=bool(max(abs(np.array(best)))>=.5-1e-5),candidates=trace))
