"""EXP2工程门，验证面积积分、坐标、独立前向、噪声及求解。"""
import ast
from types import SimpleNamespace
import numpy as np
import torch
from sampling import overlap_matrix,centered_grid,rebin,gaussian_overlap_matrix
from scipy.integrate import quad
from scipy.special import ndtr
from forward import render,matrix,Operator,MODELS,WAVES
from noise import protocol_p,protocol_q,gaussian_direction,realized_snr
from perturbations import perturb,detector_perturb


def validate(root,ops,cubes,weights,overlap,pitch,indices,scale):
    checks=[]
    def ck(name,condition,value=None):checks.append(dict(name=name,passed=bool(condition),value=value))
    rng=np.random.default_rng(20261025)
    for size,p in [(4,2),(7,1),(8,.5),(9,1.7)]:
        fine,det,w=centered_grid(size,p)
        image=np.ones((size,size))
        coarse=rebin(image,w)
        ck(f'常量面积_{size}_{p}',np.allclose(coarse,p*p,rtol=0,atol=1e-12))
        inside=float(coarse.sum());outside=float(image.sum()-inside)
        ck(f'守恒与部分视场_{size}_{p}',outside>=-1e-12 and abs(inside+outside-image.sum())<1e-12,
           dict(total=float(image.sum()),inside=inside,outside=outside))
    w=overlap_matrix([-1,0,1],[-.5,.5]);toy=rebin(np.ones((2,2)),w)
    ck('边界部分覆盖解析',abs(float(toy[0,0])-1)<1e-12)
    ck('全覆盖非负守恒',np.max(abs(np.asarray(overlap_matrix([-2,-1,0,1,2],[-2,0,2]).sum(axis=0))-1))<1e-12)
    # 小型非方阵的二维独立四循环，避免只与同一稀疏算子自洽。
    fx=np.array([-2.,-1.,0.,1.]);fy=np.array([-1.5,-.5,.5,1.5,2.5])
    dx=np.array([-1.7,-.2,1.3]);dy=np.array([-1.2,.4,2.])
    img=np.arange(12,dtype=float).reshape(4,3)
    slow=np.zeros((2,2))
    for v in range(2):
        for u in range(2):
            for j in range(4):
                for i in range(3):
                    ox=max(0,min(fx[i+1],dx[u+1])-max(fx[i],dx[u]))
                    oy=max(0,min(fy[j+1],dy[v+1])-max(fy[j],dy[v]))
                    slow[v,u]+=img[j,i]*ox*oy
    fast=rebin(img,overlap_matrix(fy,dy),overlap_matrix(fx,dx))
    ck('独立矩形重叠积分',np.max(abs(fast-slow))<1e-12,float(np.max(abs(fast-slow))))
    for sigma in [.274,1.37]:
        source=np.array([-1.,0.,1.]);dest=np.array([-2.1,-.1,.8,2.2])
        analytical=gaussian_overlap_matrix(source,dest,sigma).toarray()
        numerical=np.zeros_like(analytical)
        for j in range(3):
            for i in range(2):
                numerical[j,i]=quad(lambda x:ndtr((dest[j+1]-x)/sigma)-ndtr((dest[j]-x)/sigma),source[i],source[i+1],epsabs=1e-13)[0]
        ck(f'连续高斯双面积积分_{sigma}',np.max(abs(analytical-numerical))<1e-11,float(np.max(abs(analytical-numerical))))
    delta=np.zeros((1,512,512));delta[:,255:257,255:257]=.25
    rebinned=rebin(delta[0],overlap);m=len(rebinned)
    ck('光轴四格delta映射',np.allclose(rebinned[m//2-1:m//2+1,m//2-1:m//2+1],.25,rtol=0,atol=1e-12)
       and abs(rebinned.sum()-1)<1e-12)
    f_edges,d_edges,_=centered_grid(512,pitch)
    shifted_direct,_,_=detector_perturb(np.broadcast_to(delta,(9,512,512)),weights,dict(kind='common_shift_x',level=.1),pitch,f_edges,d_edges)
    ck('detector连续偏移质量',abs(shifted_direct[0].sum()-1)<1e-12 and shifted_direct[0][:,m//2:].sum()>.5)
    coord=np.arange(512)-255.5
    for axis in ['x','y']:
        for level in [-.1,.1]:
            moved,_,meta=perturb(np.broadcast_to(delta,(9,512,512)),weights,dict(kind='common_shift_'+axis,level=level),pitch)
            centroid=[float((moved[0].sum(axis=0)*coord).sum()),float((moved[0].sum(axis=1)*coord).sum())]
            expected=np.zeros(2);expected[0 if axis=='x' else 1]=level*pitch
            ck(f'非周期亚像元坐标_{axis}_{level}',np.max(abs(np.array(centroid)-expected))<1e-12,centroid)
    edge=np.zeros((9,512,512));edge[:,256,-1]=1
    shifted,_,_=perturb(edge,weights,dict(kind='common_shift_x',level=.5),pitch)
    ck('平移无环绕',np.count_nonzero(shifted[:,:,0])==0 and shifted.sum()<edge.sum())
    ck('精确RGB波长索引',indices==list(range(2,27,3)),indices)
    for key,op in ops.items():
        mode,name=key;cube=cubes[key];a=op.a;prefix=mode+'/'+name
        ck(prefix+'非负有限',np.isfinite(a).all() and a.min()>=0)
        for band in range(9):
            s=np.eye(9)[band];expected=render(s,cube,weights)
            ck(prefix+f'独立列_{band}',np.max(abs(a[:,band]-expected))<1e-14)
        s=rng.uniform(0,1,9);s/=s.sum();y=render(s,cube,weights)
        rel=float(np.linalg.norm(a@s-y)/np.linalg.norm(y))
        ck(prefix+'独立多带',rel<1e-10,rel)
        ck(prefix+'零输入',np.count_nonzero(render(np.zeros(9),cube,weights))==0)
        v=rng.normal(size=a.shape[0]);left=float((a@s)@v);right=float(s@(a.T@v))
        adj=abs(left-right)/max(1,abs(left),abs(right))
        ck(prefix+'伴随',adj<1e-10,adj)
        err=float(np.linalg.norm(a-op.u@op.b)/np.linalg.norm(a))
        ck(prefix+'SVD重构',err<1e-10,err)
        est,residual,kkt=op.solve(y)
        ck(prefix+'非负KKT',est.min()>=0 and kkt<1e-7,kkt)
        if name==MODELS[2]:ck(prefix+'无噪声谱恢复',np.linalg.norm(est-s)/np.linalg.norm(s)<1e-8)
        else:ck(prefix+'控制矩阵秩3',op.rank==3,op.rank)
        direction=gaussian_direction(20261021,2,len(y))
        noisy,amp=protocol_q(y,direction,30)
        snr=realized_snr(y,noisy)
        ck(prefix+'Q实际SNR',abs(snr-30)<.3,snr)
    s=np.ones(9)/9;clean=ops[('shape_only',MODELS[2])].a@s
    yp,meta=protocol_p(clean,1e4,scale,1.,20261021,2)
    yp2,meta2=protocol_p(clean,1e4,scale,1.,20261021,2)
    ck('P种子重复一致',np.array_equal(yp,yp2))
    ck('P有限非负rate',np.isfinite(yp).all() and meta['min_rate']>=0 and meta['expected_electrons']<=1e4*(1+1e-12))
    # 回归真实pilot暴露的欠定压缩问题；严格KKT核对，而非接受SciPy的零残差标记。
    for name in MODELS[:2]:
        op=ops[('shape_only',name)]
        for band,seed in [(6,20261022),(3,20261021)]:
            s=np.eye(9)[band];clean=op.a@s
            y,_=protocol_q(clean,gaussian_direction(seed,band,len(clean)),30)
            est,residual,kkt=op.solve(y)
            ck(f'欠定NNLS补零回归_{name}_{band}',kkt<1e-12,kkt)
    identity=Operator(np.eye(9));est,_,_=identity.solve(s)
    ck('解析NNLS单位阵',np.max(abs(est-s))<1e-8)
    # 核对实际旧响应函数，两个toy波长仅B和R响应。
    path=root/'framework/DeepLensHSI/src/sensor/sensor.py';tree=ast.parse(path.read_text(encoding='utf-8'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='RGBSensor')
    fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='response_curve')
    env={'torch':torch};exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec'),env)
    toy=SimpleNamespace(wavelengths=[.45,.65],red_response=torch.tensor([0.,1.]),green_response=torch.zeros(2),blue_response=torch.tensor([1.,0.]))
    got=env['response_curve'](toy,torch.tensor([[[[2.]],[[7.]]]])).flatten()
    ck('原RGB450B650R',torch.equal(got,torch.tensor([7.,0.,2.])),got.tolist())
    return checks
