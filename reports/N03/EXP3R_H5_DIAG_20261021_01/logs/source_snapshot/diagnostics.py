"""不读取真值的来源判定、候选选择与预算限制。"""
import math
import statistics


REQUIRED=['best_position','best_loss','selected_start_id','terminations','candidates','local_requests','evaluation_records']
END_FIELDS=['start_id','start','position','loss','success','status','message','nfev','nit','maxfev','budget_exhausted']


def distance(a,b):
    return math.hypot(a[0]-b[0],a[1]-b[1])


def classify(trace):
    missing=[k for k in REQUIRED if k not in trace]
    if not missing:
        missing=[f'termination.{i}.{k}' for i,e in enumerate(trace['terminations']) for k in END_FIELDS if k not in e]
    if missing:
        return dict(status='UNVERIFIED',provenance='UNKNOWN',missing=missing)
    best=tuple(trace['best_position'])
    ends=trace['terminations']
    good={e['start_id'] for e in ends if e['success']}
    requested={r['start_id'] for r in trace['local_requests'] if tuple(r['position'])==best}
    certified=any(e['success'] and tuple(e['position'])==best for e in ends)
    label=('SUCCESSFUL_RETURN_ENDPOINT' if certified else 'SUCCESSFUL_START_INTERMEDIATE'
           if requested & good else 'UNSUCCESSFUL_START_ONLY' if requested else 'UNKNOWN')
    distances=[distance(e['position'],best) for e in ends if e['success']]
    corresponding=[distance(e['position'],best) for e in ends if e['success'] and e['start_id'] in requested]
    return dict(status='VERIFIED' if label!='UNKNOWN' else 'UNVERIFIED',provenance=label,
                strict=certified,selected_start_id=trace['selected_start_id'],
                requested_start_ids=sorted(requested),successful_start_ids=sorted(good),
                has_successful_endpoint=bool(good),
                nearest_successful_endpoint_distance=min(distances) if distances else None,
                corresponding_successful_endpoint_distance=min(corresponding) if corresponding else None)


def select_endpoint(endpoints):
    """只取success=True返回终点；稳定排序只读取目标值，禁止真值参量。"""
    eligible=[e for e in endpoints if e['success']]
    return min(eligible,key=lambda e:e['loss']) if eligible else None


def stats(values):
    values=sorted(values)
    if not values: return dict(n=0,mean=None,median=None,p90=None,max=None)
    h=.9*(len(values)-1);lo=math.floor(h);hi=math.ceil(h)
    return dict(n=len(values),mean=statistics.fmean(values),median=statistics.median(values),
                p90=values[lo]+(values[hi]-values[lo])*(h-lo),max=max(values))


class MicroBudget:
    """微型精修最多8个起点、每个最多80次真实目标请求。"""
    def __init__(self): self.starts=0;self.current=0;self.total=0
    def start(self):
        if self.starts>=8: raise RuntimeError('D3 budget: ninth start forbidden')
        self.starts+=1;self.current=0
    def evaluate(self):
        if self.current>=80 or self.total>=640: raise RuntimeError('D3 budget exhausted')
        self.current+=1;self.total+=1


def diagnose(rows, thresholds):
    semantic=[];limited=[];unresolved=[]
    for r in rows:
        if r['strict_H5_certified']: continue
        near=(r.get('C1_status')=='AVAILABLE' and r['position_shift']<=thresholds['position_near_px']
              and abs(r['objective_regret'])<=thresholds['objective_abs_near'])
        corresponding=r.get('corresponding_successful_endpoint_distance')
        if (r['provenance']=='SUCCESSFUL_START_INTERMEDIATE' and near and corresponding is not None
                and corresponding<=thresholds['position_near_px']):
            semantic.append(r['observation_id'])
        elif r['C1_status']=='NO_CONVERGED_ENDPOINT' or (
            r['provenance']=='UNSUCCESSFUL_START_ONLY' and r['C1_status']=='AVAILABLE' and
            (r['position_shift']>thresholds['position_near_px'] or r['objective_regret']>thresholds['objective_abs_near'])):
            limited.append(r['observation_id'])
        else: unresolved.append(r['observation_id'])
    majority=len(semantic)>20
    label=('H5_DIAG_MIXED' if majority and limited else
           'H5_DIAG_SELECTION_SEMANTICS_DOMINANT' if majority else
           'H5_DIAG_CONVERGENCE_LIMITED' if limited else 'H5_DIAG_INCONCLUSIVE')
    return dict(label=label,semantic_close_cases=semantic,convergence_limited_cases=limited,
                unresolved_cases=unresolved,uncertified_denominator=40,
                D3_needed=label=='H5_DIAG_INCONCLUSIVE' or len(unresolved)>20,
                rule='多数未认证中间点接近成功终点且目标接近支持语义；无成功终点或failure-only点与成功终点有显著距离/目标差支持收敛限制。')
