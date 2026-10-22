"""基础解析用例与真实归档数据的一致性门；由实验入口执行并落盘。"""
import ast
from types import SimpleNamespace
import numpy as np
import torch
from forward import render_multiband, render_one_hot, point_matrix, WAVELENGTHS, MODELS
from solvers import factorize, solve_nnls


def validate(root, kernels, weights, matrices, factors, indices):
    checks = []
    def check(name, passed, value=None):
        checks.append(dict(name=name, passed=bool(passed), value=value))
    rng = np.random.default_rng(20261020)
    check('按真实波长查31点响应索引', indices == list(range(2, 27, 3)), indices)
    check('B1全部波长固定540nm形状', all(np.array_equal(kernels[MODELS[1]][i], kernels[MODELS[2]][4]) for i in range(9)))
    check('B0统一delta位置与能量', np.all(kernels[MODELS[0]][:,256,256] == 1) and np.all(kernels[MODELS[0]].sum(axis=(1,2)) == 1))
    for name in MODELS:
        h, a = kernels[name], matrices[name]
        check(name+'数组非负有限归一', np.isfinite(a).all() and a.min() >= 0 and np.allclose(h.sum(axis=(1,2)),1,rtol=0,atol=1e-12))
        for band in range(9):
            err = float(np.max(abs(a[:,band]-render_one_hot(band,h,weights).ravel())))
            check(f'{name}独立单带{WAVELENGTHS[band]:g}', err < 1e-15, err)
        s = rng.random(9)
        y = render_multiband(s,h,weights).ravel(); ym = a@s
        ae = float(np.max(abs(y-ym))); re = float(np.linalg.norm(y-ym)/np.linalg.norm(y))
        check(name+'独立多带', re < 1e-14, dict(max_absolute=ae, relative=re))
        check(name+'零输入', np.count_nonzero(render_multiband(np.zeros(9),h,weights)) == 0)
        t = rng.random(9)
        linear = render_multiband(s+t,h,weights)-render_multiband(s,h,weights)-render_multiband(t,h,weights)
        check(name+'线性', np.max(abs(linear)) < 1e-14, float(np.max(abs(linear))))
        v = rng.normal(size=a.shape[0]); left = ym@v; right = s@(a.T@v)
        adj = float(abs(left-right)/max(1,abs(left),abs(right)))
        check(name+'伴随内积', adj < 1e-10, adj)
        u,b,sv,rank,tol = factors[name]
        check(name+'正交压缩重建A', np.linalg.norm(a-u@b)/np.linalg.norm(a) < 1e-12)
        # 在实际稠密观测上核验压缩目标等于原目标减去与解无关常数。
        yp = u.T@y; e,_ = solve_nnls(b,yp,sv[0])
        residual = np.linalg.norm(a@e-y)
        projected = np.sqrt(np.linalg.norm(b@e-yp)**2 + np.linalg.norm(y-u@yp)**2)
        check(name+'原矩阵与压缩残差一致', abs(residual-projected) < 1e-12, [float(residual),float(projected)])
        gradient = b.T@(b@e-yp)
        check(name+'NNLS_KKT', e.min() >= 0 and gradient.min() > -1e-12 and np.max(abs(e*gradient)) < 1e-12)
        # 用完整ROI真实加噪，独立核对正式批量实验采用的投影噪声及残差公式。
        sigma=1e-8; noisy=y+sigma*v; noisy_projected=u.T@noisy
        fitted,_=solve_nnls(b,noisy_projected,sv[0])
        direct=np.linalg.norm(a@fitted-noisy)
        zv=u.T@v
        formula=np.sqrt(np.linalg.norm(b@fitted-b@s-sigma*zv)**2 + sigma*sigma*(v@v-zv@zv))
        check(name+'完整加噪观测残差公式',abs(direct-formula)/max(direct,1e-300)<1e-10,
              dict(dense_residual=float(direct),projected_formula=float(formula)))
    check('B0_B1秩3', factors[MODELS[0]][3] == factors[MODELS[1]][3] == 3)
    truth = np.array([.2,.7,0.,.1]); est,status = solve_nnls(np.eye(4),truth,1)
    check('解析单位阵NNLS', np.max(abs(est-truth)) < 1e-8, float(np.max(abs(est-truth))))
    toy = np.array([[1.,1.,0.],[0.,0.,1.]])
    check('秩亏toy不误判唯一解', factorize(toy)[3] == 2 and np.array_equal(toy@np.array([1.,0.,1.]),toy@np.array([0.,1.,1.])))
    # 直接提取旧函数执行，核对实际RGB通道逻辑而非网络输入约定。
    path = root/'framework/DeepLensHSI/src/sensor/sensor.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='RGBSensor')
    fn = next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='response_curve')
    env={'torch':torch}; exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec'),env)
    probe=SimpleNamespace(wavelengths=[.45,.65],red_response=torch.tensor([0.,1.]),green_response=torch.zeros(2),blue_response=torch.tensor([1.,0.]))
    actual=env['response_curve'](probe,torch.tensor([[[[2.]],[[7.]]]])).flatten()
    check('原物理响应红蓝toy',torch.equal(actual,torch.tensor([7.,0.,2.])),actual.tolist())
    return checks
