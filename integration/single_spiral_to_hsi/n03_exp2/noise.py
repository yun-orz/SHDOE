"""两种公平性协议：等入射模拟电子预算P与匹配实现阵列SNR的Q。"""
import numpy as np


def gaussian_direction(seed,sample_id,size):
    return np.random.default_rng(np.random.SeedSequence([seed,sample_id,77])).normal(size=size)


def protocol_q(clean,direction,target_db):
    amplitude=np.linalg.norm(clean)*10**(-target_db/20)/np.linalg.norm(direction)
    noise=direction*amplitude
    return clean+noise,float(amplitude)


def protocol_p(clean,p_in,electron_scale,read_sigma,seed,sample_id):
    conversion=p_in*electron_scale
    mu=clean*conversion
    if not np.isfinite(mu).all() or mu.min()<0:raise ArithmeticError('负或非有限Poisson rate')
    # 三模型和两通量模式复用同一预定义生成方案、初始种子；率不同不宣称电子数逐像元相同。
    shot_rng=np.random.default_rng(np.random.SeedSequence([seed,sample_id,91]))
    read_rng=np.random.default_rng(np.random.SeedSequence([seed,sample_id,92]))
    counts=shot_rng.poisson(mu)
    read=read_rng.normal(size=len(mu))*read_sigma
    return (counts+read)/conversion,dict(expected_electrons=float(mu.sum()),
                 realized_poisson_electrons=int(counts.sum()),read_sigma_e=float(read_sigma),
                 electron_scale=electron_scale,conversion=conversion,min_rate=float(mu.min()),max_rate=float(mu.max()))


def realized_snr(clean,y):
    err=np.linalg.norm(y-clean)
    return float(20*np.log10(np.linalg.norm(clean)/err)) if err>0 else None
