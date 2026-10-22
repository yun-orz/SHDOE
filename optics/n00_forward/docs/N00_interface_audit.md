# N00 真实接口事实清单

核查日期：2026-10-09。参考仓库 `E:/DeepLensHSI` HEAD 为 `260aa949692e7321fd77b6afb613e6ed418c8710`，核查针对本机工作区（含既有改动），不是只读 HEAD 的推断。未运行旧库示例，不能声称本轮已验证旧示例跑通。

## 类、签名与数据约定

| 实际路径及行号（相对参考仓库） | 类/函数真实签名 | 输入与输出、单位、精度、依赖 |
|---|---|---|
| `src/hsi_camera.py:17` | `HSICamera.__init__(self,lens_file,sensor_file,device=None)` | JSON 路径→含 DiffractiveLens、RGBSensor 的对象；torch/scipy/matplotlib，N00 不复用 RGB 链路 |
| `src/hsi_camera.py:90` | `vis_psf(self,wvln_spectral,psf_ks=201,depth=float('inf'),save_dir='./results/vis',save_name=None)` | λ 输入 µm；逐波长调用 psf，`upsample_factor=2`；内部 `[C,ks,ks]` 精度随 torch 默认设置；仅图片文件输出、函数返回 None |
| `src/hsi_camera.py:163` | `render_lens(self,img_spectral,wvln_spectral,depth=float('inf'),psf_ks=201)` | `[B,C,H,W]`→同 shape；λ µm、depth mm；PSF 缓冲与图像 dtype 一致；render_psf |
| `src/hsi_camera.py:194` | `render(self,data_dict)` | dict 的 img `[B,C,H,W]` 与 wvln `[B,C]`；输出 RGB `[B,3,H,W]` 和输入光谱图；隐式采用 render_lens 默认无穷远 |
| `src/deeplens/diffraclens.py:32` | `DiffractiveLens.__init__(self,filename=None,sensor_size=(8.,8.),sensor_res=(2000,2000),device=None)` | 几何 mm，构造后 `self.double()`；并未修改全局默认 dtype |
| `src/deeplens/diffraclens.py:127` | `psf(self,depth=float('inf'),wvln=.589,ks=101,upsample_factor=1)` | depth mm、λ µm→`[ks,ks]` 实数 PSF；有限深度点源 vs 无穷远平面波；传播后双线性插值、裁剪、sum 归一化与翻转，返回 diff_float；不能从输出复核裁剪前能量 |
| `src/deeplens/diffraclens.py:216` | `psf_infinite(self,wvln=DEFAULT_WAVE,ks=101)` | 一进入便抛异常，已废弃，不使用 |
| `src/deeplens/diffractive_surface/base.py:16` | `DiffractiveSurface.__init__(self,d,res=(2000,2000),fab_ps=.001,design_ps=None,wvln0=.55,mat='fused_silica',device='cpu')` | d、fab_ps、design_ps 为 mm，λ 为 µm；依赖 Material、torch、torchvision |
| `src/deeplens/diffractive_surface/base.py:73` | `get_phase_map0(self)` | `_phase_map0()` 经 remainder(2π) 得 `[H,W]`，精度随 phase_map；不是原始实体高度 |
| `src/deeplens/diffractive_surface/base.py:83` | `get_phase_map(self,wvln=.55)` | 先包裹设计相位再乘 λ 与色散比；nearest 插值到 self.res；实际返回 `[H,W]`，docstring 所称 `[1,1,H,W]` 不符合代码 |
| `src/deeplens/diffractive_surface/base.py:113` | `forward(self,wave)` | ComplexWave `[B,1,H,W]`；prop_to、相位最近邻适配、裁剪或填充、乘 exp(iφ)；无显式圆孔径；保留原场 dtype |
| `src/deeplens/diffractive_surface/pixel2d.py:10,43,60` | `Pixel2D.__init__(self,d,phase_map_path=None,res=(2000,2000),mat='fused_silica',wvln0=.55,fab_ps=.001,device='cpu')`；`init_from_dict(cls,doe_dict)`；`_phase_map0(self)` | phase_map 形状 `[H,W]`；初始化默认 torch 随机实数，指定字符串通过 torch.load；`_phase_map0` 原样返回 phase_map |
| `src/deeplens/diffraclens.py:335,359–360` | `read_lens_json(self,filename)` | Pixel2D 初始化后明确 `np.load(doe_path)` 并赋给 phase_map；`planar_doe.npy` 因此是设计波长相位，不是制造高度 |
| `src/deeplens/wave.py:25` | `ComplexWave.__init__(self,u=None,wvln=.55,z=0.,phy_size=[4.,4.],res=[1000,1000],valid_phy_size=None)` | u `[H,W]` 或 `[B,C,H,W]`→内部 4D；λ µm，其余长度 mm；推荐 complex128，但未强制且实数会转 complex64；要求等间距 |
| `src/deeplens/wave.py:155,195` | `prop(self,prop_dist,n=1.)`；`prop_to(self,z,n=1)` | mm；小于 DELTA 不传播（负距离也进入该分支），其余调用 AngularSpectrumMethod；in-place 更新场；不适合作为本项目负距离参数检查 |
| `src/deeplens/wave.py:329` | `AngularSpectrumMethod(u,z,wvln,ps,n=1.,padding=True)` | 2D 或 4D 复数→同 shape；z、ps mm，λ µm；默认 2× 零填充后裁回原尺寸；频率用含端点 linspace，非 FFT 精确频点；未指定 meshgrid dtype；实数根号遇倏逝分量可 NaN；裁剪会损失能量；torch.fft |
| `src/deeplens/wave.py:388` | `ScalableASM(u,z,wvln,ps,n=1.,padding=True)` | 已发现定义，N00 未调用/未验证，不作可直接复用声明 |
| `src/deeplens/waveoptics_utils.py:67` | `plane_wave_field(phy_size,res,wvln=.589,z=0.,device='cpu',dtype=torch.float32)` | ones+0j→ComplexWave；尺寸 mm、λ µm；float64 得 complex128；torch/opencv |
| `src/deeplens/waveoptics_utils.py:73` | `point_source_field(point=[0.,0.,-1000.],phy_size=[2.,2.],res=[1024,1024],wvln=.589,z=0.,device='cpu',dtype=torch.float32)` | 点源 mm，λ µm；输出 ComplexWave；N00 不使用有限距离点源 |
| `src/deeplens/materials.py:73,77` | `Material.refractive_index(self,wvln)`；`ior(self,wvln)` | λ µm→标量 n；根据 materials_data.json 选 Sellmeier/Schott/Cauchy/interp；Sellmeier 的 torch.tensor(n2) 精度依赖默认 dtype |

名为 `Wave` 的类在核查模块中**未发现**；实际类名是 `ComplexWave`。直接接收任意未包裹固定高度并导出原始能量的标准接口**未发现**。

## 配置事实与适配边界

`lenses/paraxiallens/doelens_hsi.json`：传感器距离 50 mm，size 12.34×12.34 mm，res 4504×4504；DOE 1024×1024、pitch .004 mm、wvln0 .700 µm、mat SK1300、d_next 50 mm。该配置仅为历史参考。本次 N00 对照明确独立指定 D=128 µm、f=1 mm、设计 λ=550 nm；没有将旧库硬件几何缩小后冒充其收敛验证。

选择独立适配的理由：现有相位包裹流程无法表示任意未包裹实体高度，现有 PSF 会丢弃原始能量；现有 ASM 的频点与裁剪方式不满足本阶段可独立审计要求。新代码不复制旧库源码，按数学定义独立实现，复用已核实的调用思想/torch FFT 依赖，而不是调用上述有风险的算子。其正确性由 T01–T06 验证，不由旧项目跑通推出。

材料采用 [Malitson 原始论文](https://opg.optica.org/josa/abstract.cfm?uri=josa-55-10-1205) 的熔融石英 Sellmeier 参数，λ µm、20 °C，适用 .21–3.71 µm；N00 的 .4–.7 µm 位于范围内。

## 新接口

`src/spiral_hsi/optics/psf.py` 的 `compute_psf(height_um,wavelength_nm,aperture_mask,material_model=fused_silica,sampling_pitch_um=1.,propagation_distance_mm=1.,incident_condition='plane_wave',axis='on_axis',padding=4,crop=512,sensor_sampling='native',device='cuda')`。

输入 height 与振幅 aperture `[H,W]`，pitch 标量或 `(dy,dx)` µm；z mm、λ列表 nm。输出 dict：`PSF_cube [C,crop,crop] float64`、`raw_intensity [C,H*padding,W*padding] float64`、`raw_energy_stats`、严格同序波长与 metadata。所有光场为 complex128，材料/相位 numpy float64。采用原生传感器网格，不插值；填充频域采用 torch.fft.fftfreq；周期 FFT 域，倏逝分量正向指数衰减。原始能量积分权重 dy×dx。

归一化仅发生在最终裁剪之后。NPZ 同时保存高度、光瞳、物理坐标、全填充域原始强度；metadata 记录实体高度哈希、环境折射率、材料来源、版本及资源。宽谱物理应非相干强度求和，本阶段不实现跨波長复振幅相加。
