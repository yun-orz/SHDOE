"""分片常数像元能量的几何重叠积分，无插值缩放或外插。"""
import numpy as np
from scipy.sparse import csr_matrix
from scipy.special import ndtr


def overlap_matrix(fine_edges, detector_edges):
    fine_edges=np.asarray(fine_edges,dtype=float)
    detector_edges=np.asarray(detector_edges,dtype=float)
    widths=np.diff(fine_edges)
    assert np.all(widths>0) and np.all(np.diff(detector_edges)>0)
    overlap=np.maximum(0,np.minimum(detector_edges[1:,None],fine_edges[None,1:])-
                       np.maximum(detector_edges[:-1,None],fine_edges[None,:-1]))
    return csr_matrix(overlap/widths[None,:])


def centered_grid(size,pitch):
    count=int(np.floor(size/pitch))
    fine_edges=np.arange(size+1,dtype=float)-size/2
    detector_edges=(np.arange(count+1,dtype=float)-count/2)*pitch
    return fine_edges,detector_edges,overlap_matrix(fine_edges,detector_edges)


def rebin(image,wy,wx=None):
    if wx is None:wx=wy
    return (wx@(wy@image).T).T


def rebin_cube(cube,weights):
    return np.stack([rebin(h,weights) for h in cube])


def gaussian_overlap_matrix(fine_edges,detector_edges,sigma_um):
    """对源像元内常量强度、连续高斯、接收像元面积做解析双重积分。"""
    fine=np.asarray(fine_edges,dtype=float);det=np.asarray(detector_edges,dtype=float)
    def primitive(x):
        z=x/sigma_um
        return x*ndtr(z)+sigma_um/np.sqrt(2*np.pi)*np.exp(-.5*z*z)
    a,b=det[:-1,None],det[1:,None];c,d=fine[None,:-1],fine[None,1:]
    values=(primitive(b-c)-primitive(a-c)-primitive(b-d)+primitive(a-d))/np.diff(fine)[None,:]
    if values.min() < -1e-10:raise ArithmeticError('高斯面积积分出现显著负值')
    # 远尾双差的浮点抵消量级约1e-14，不将它当作空间编码。
    values=np.maximum(values,0);values[values<5e-14]=0
    return csr_matrix(values)
