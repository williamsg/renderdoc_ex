# RenderDoc Python API Reference

本文档列举了 RenderDoc 扩展版（renderdoc_ex）支持的 Python API 接口，包括签名、描述、使用方法和示例。

> **注意**：本文档基于 `IReplayController` 接口（通过 SWIG 暴露为 `renderdoc` Python 模块）。所有接口均可在 RenderDoc 的 Python Shell 或外部脚本中使用。

---

## 目录

- [快速开始](#快速开始)
- [数据结构](#数据结构)
  - [PixelEventStats](#pixeleventstats)
  - [OverdrawBucket](#overdrawbucket)
  - [CounterResult](#counterresult)
  - [PixelModification](#pixelmodification)
  - [ActionDescription](#actiondescription)
- [ReplayController 接口](#replaycontroller-接口)
  - [基础控制](#基础控制)
    - [GetAPIProperties](#getapiproperties)
    - [SetFrameEvent](#setframeevent)
    - [GetRootActions](#getrootactions)
    - [GetFrameInfo](#getframeinfo)
    - [Shutdown](#shutdown)
  - [Pipeline State 查询](#pipeline-state-查询)
    - [GetPipelineState](#getpipelinestate)
    - [GetD3D11PipelineState](#getd3d11pipelinestate)
    - [GetD3D12PipelineState](#getd3d12pipelinestate)
    - [GetGLPipelineState](#getglpipelinestate)
    - [GetVulkanPipelineState](#getvulkanpipelinestate)
  - [资源查询](#资源查询)
    - [GetResources](#getresources)
    - [GetTextures](#gettextures)
    - [GetBuffers](#getbuffers)
    - [GetUsage](#getusage)
  - [数据获取](#数据获取)
    - [GetBufferData](#getbufferdata)
    - [GetTextureData](#gettexturedata)
    - [SaveTexture](#savetexture)
  - [像素与纹理分析](#像素与纹理分析)
    - [PickPixel](#pickpixel)
    - [GetMinMax](#getminmax)
    - [GetHistogram](#gethistogram)
    - [PixelHistory](#pixelhistory)
    - [**FetchPixelStats (新增)**](#fetchpixelstats-新增)
  - [GPU 计数器](#gpu-计数器)
    - [EnumerateCounters](#enumeratecounters)
    - [DescribeCounter](#describecounter)
    - [FetchCounters](#fetchcounters)
  - [Shader 调试](#shader-调试)
    - [DebugVertex](#debugvertex)
    - [DebugPixel](#debugpixel)
    - [DebugThread](#debugthread)
    - [GetShaderEntryPoints](#getshaderentrypoints)
    - [GetShader](#getshader)
    - [DisassembleShader](#disassembleshader)
  - [Shader 编译与替换](#shader-编译与替换)
    - [BuildCustomShader](#buildcustomshader)
    - [BuildTargetShader](#buildtargetshader)
    - [ReplaceResource](#replaceresource)
    - [RemoveReplacement](#removereplacement)
  - [Mesh 数据](#mesh-数据)
    - [GetPostVSData](#getpostvsdata)
  - [其他](#其他)
    - [GetDebugMessages](#getdebugmessages)
    - [GetStructuredFile](#getstructuredfile)
    - [GetDescriptors](#getdescriptors)
    - [GetCBufferVariableContents](#getcbuffervariablecontents)
- [全局函数](#全局函数)
  - [OpenCaptureFile](#opencapturefile)
  - [InitialiseReplay / ShutdownReplay](#initialisereplay--shutdownreplay)
  - [ExecuteAndInject](#executeandinject)

---

## 快速开始

### 在 RenderDoc Python Shell 中使用

```python
import renderdoc as rd

# 在 RenderDoc GUI 的 Python Shell 中，controller 已经可用
# 通过 pyrenderdoc 对象获取
controller = pyrenderdoc.Replay().GetController()
```

### 在外部脚本中使用

```python
import renderdoc as rd

# 打开 capture 文件
cap = rd.OpenCaptureFile()
result = cap.OpenFile("my_capture.rdc", "", None)

if result != rd.ResultCode.Succeeded:
    print(f"Failed to open capture: {result}")
    exit(1)

# 检查本地是否支持回放
if cap.LocalReplaySupport() != rd.ReplaySupport.Supported:
    print("Capture cannot be replayed locally")
    exit(1)

# 创建 ReplayController
result, controller = cap.OpenCapture(rd.ReplayOptions(), None)

if result != rd.ResultCode.Succeeded:
    print(f"Failed to open replay: {result}")
    exit(1)

# --- 使用 controller 进行分析 ---

# 获取所有 drawcall
actions = controller.GetRootActions()

# 设置到某个事件
controller.SetFrameEvent(actions[-1].eventId, True)

# 获取 pipeline state
state = controller.GetPipelineState()

# 完成后关闭
controller.Shutdown()
cap.Shutdown()
```

---

## 数据结构

### PixelEventStats

> **新增** - 每个事件的像素统计信息，通过 GPU 硬件计数器收集。

| 字段 | 类型 | 描述 |
|------|------|------|
| `eventId` | `int` | 事件 ID |
| `samplesPassed` | `int` | 通过深度/模板测试的样本数 |
| `psInvocations` | `int` | Pixel Shader 调用次数（包含 early-Z 前的所有光栅化像素） |
| `rasterizedPrimitives` | `int` | 光栅化的图元数量 |
| `gpuDuration` | `float` | GPU 执行时间（秒） |
| `pixelTouched` | `int` | 被此 drawcall 覆盖的像素数（等同于 `samplesPassed`） |
| `overdrawEstimate` | `float` | 估算的平均 overdraw 比率（`psInvocations / samplesPassed`），1.0 表示无 overdraw |
| `overdrawDistribution` | `List[OverdrawBucket]` | Overdraw 分布（仅当 `overdrawDistribution=True` 时可用） |

### OverdrawBucket

> **新增** - Overdraw 分布桶，描述有多少像素具有特定的 overdraw 次数。

| 字段 | 类型 | 描述 |
|------|------|------|
| `overdrawCount` | `int` | Overdraw 次数（1 = 无 overdraw，2 = 绘制了 2 次，以此类推） |
| `pixelCount` | `int` | 具有该 overdraw 次数的像素数量 |

### CounterResult

GPU 计数器查询结果。

| 字段 | 类型 | 描述 |
|------|------|------|
| `eventId` | `int` | 事件 ID |
| `counter` | `GPUCounter` | 计数器类型 |
| `value` | `CounterValue` | 计数器值（联合体，包含 `.u32`, `.u64`, `.f`, `.d` 等） |

### PixelModification

像素历史中的单次修改记录。

| 字段 | 类型 | 描述 |
|------|------|------|
| `eventId` | `int` | 事件 ID |
| `directShaderWrite` | `bool` | 是否为直接 shader 写入 |
| `preMod` / `postMod` | `ModificationValue` | 修改前/后的像素值 |
| `shaderOut` | `ModificationValue` | Shader 输出值 |
| `backfaceCulled` | `bool` | 是否被背面剔除 |
| `depthTestFailed` | `bool` | 是否深度测试失败 |
| `stencilTestFailed` | `bool` | 是否模板测试失败 |

### ActionDescription

Drawcall / Action 描述。

| 字段 | 类型 | 描述 |
|------|------|------|
| `eventId` | `int` | 事件 ID |
| `actionId` | `int` | Action ID |
| `customName` | `str` | 自定义名称 |
| `flags` | `ActionFlags` | Action 标志位 |
| `children` | `List[ActionDescription]` | 子 Action 列表 |
| `outputs` | `List[ResourceId]` | 输出的 Render Target |
| `depthOut` | `ResourceId` | 深度输出 |

---

## ReplayController 接口

### 基础控制

#### GetAPIProperties

```python
props = controller.GetAPIProperties()
# props.pipelineType  -> GraphicsAPI (e.g. rd.GraphicsAPI.D3D11)
# props.degraded      -> bool
```

**描述**：获取当前 capture 的 API 属性信息。

**返回值**：`APIProperties`

---

#### SetFrameEvent

```python
controller.SetFrameEvent(eventId, force)
```

**描述**：将回放状态移动到指定事件 ID **之后**的状态。这是大多数查询操作的前置步骤。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `eventId` | `int` | 目标事件 ID |
| `force` | `bool` | 即使已在该事件，是否强制刷新 |

**示例**：
```python
# 移动到第 100 个事件
controller.SetFrameEvent(100, True)

# 获取该事件的 pipeline state
state = controller.GetPipelineState()
```

---

#### GetRootActions

```python
actions = controller.GetRootActions()
```

**描述**：获取 capture 中所有根级别的 Action（drawcall）列表。Action 以树形结构组织，可通过 `children` 属性递归遍历。

**返回值**：`List[ActionDescription]`

**示例**：
```python
def iterate_actions(actions, depth=0):
    for action in actions:
        print("  " * depth + f"EID {action.eventId}: {action.customName}")
        iterate_actions(action.children, depth + 1)

actions = controller.GetRootActions()
iterate_actions(actions)
```

---

#### GetFrameInfo

```python
frame_info = controller.GetFrameInfo()
```

**描述**：获取 capture 中帧的描述信息。

**返回值**：`FrameDescription`

---

#### Shutdown

```python
controller.Shutdown()
```

**描述**：关闭并销毁当前接口及所有已创建的输出。

---

### Pipeline State 查询

#### GetPipelineState

```python
state = controller.GetPipelineState()
```

**描述**：获取当前的抽象 Pipeline State，适用于所有 API。

**返回值**：`PipeState`

**示例**：
```python
controller.SetFrameEvent(eventId, True)
state = controller.GetPipelineState()

# 获取当前绑定的 render target
targets = state.GetOutputTargets()
for t in targets:
    print(f"RT: {t.resource}")
```

---

#### GetD3D11PipelineState

```python
d3d11_state = controller.GetD3D11PipelineState()
```

**描述**：获取当前 D3D11 Pipeline State。如果 capture 不是 D3D11 API，返回 `None`。

**返回值**：`D3D11State` 或 `None`

---

#### GetD3D12PipelineState

```python
d3d12_state = controller.GetD3D12PipelineState()
```

**描述**：获取当前 D3D12 Pipeline State。如果 capture 不是 D3D12 API，返回 `None`。

**返回值**：`D3D12State` 或 `None`

---

#### GetGLPipelineState

```python
gl_state = controller.GetGLPipelineState()
```

**描述**：获取当前 OpenGL Pipeline State。如果 capture 不是 OpenGL API，返回 `None`。

**返回值**：`GLState` 或 `None`

---

#### GetVulkanPipelineState

```python
vk_state = controller.GetVulkanPipelineState()
```

**描述**：获取当前 Vulkan Pipeline State。如果 capture 不是 Vulkan API，返回 `None`。

**返回值**：`VKState` 或 `None`

---

### 资源查询

#### GetResources

```python
resources = controller.GetResources()
```

**描述**：获取 capture 中所有资源的列表，包括所有分配了 `ResourceId` 的对象。

**返回值**：`List[ResourceDescription]`

---

#### GetTextures

```python
textures = controller.GetTextures()
```

**描述**：获取 capture 中所有存活纹理的列表。

**返回值**：`List[TextureDescription]`

**示例**：
```python
textures = controller.GetTextures()
for tex in textures:
    print(f"Texture {tex.resourceId}: {tex.width}x{tex.height} {tex.format.Name()}")
```

---

#### GetBuffers

```python
buffers = controller.GetBuffers()
```

**描述**：获取 capture 中所有存活 buffer 的列表。

**返回值**：`List[BufferDescription]`

---

#### GetUsage

```python
usages = controller.GetUsage(resourceId)
```

**描述**：获取指定资源在 capture 中的所有使用记录。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `resourceId` | `ResourceId` | 要查询的资源 ID |

**返回值**：`List[EventUsage]`

---

### 数据获取

#### GetBufferData

```python
data = controller.GetBufferData(bufferId, offset, length)
```

**描述**：获取 buffer 中指定范围的原始数据。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `bufferId` | `ResourceId` | Buffer 的资源 ID |
| `offset` | `int` | 起始字节偏移 |
| `length` | `int` | 读取长度（0 = 读取剩余全部） |

**返回值**：`bytes`

**示例**：
```python
# 读取整个 buffer
data = controller.GetBufferData(bufferId, 0, 0)

# 使用 struct 解析
import struct
values = struct.unpack(f'{len(data)//4}f', data)
```

---

#### GetTextureData

```python
data = controller.GetTextureData(textureId, subresource)
```

**描述**：获取纹理指定子资源的原始数据。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `textureId` | `ResourceId` | 纹理的资源 ID |
| `subresource` | `Subresource` | 子资源（mip level, array slice 等） |

**返回值**：`bytes`

---

#### SaveTexture

```python
result = controller.SaveTexture(saveData, path)
```

**描述**：将纹理保存到磁盘文件。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `saveData` | `TextureSave` | 保存配置 |
| `path` | `str` | 保存路径 |

**返回值**：`ResultDetails`

**示例**：
```python
save = rd.TextureSave()
save.resourceId = textureId
save.destType = rd.FileType.PNG
save.mip = 0
save.slice.sliceIndex = 0

result = controller.SaveTexture(save, "output.png")
```

---

### 像素与纹理分析

#### PickPixel

```python
pixel = controller.PickPixel(textureId, x, y, subresource, typeCast)
```

**描述**：获取纹理中指定像素的内容。坐标始终为左上角原点。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `textureId` | `ResourceId` | 纹理 ID |
| `x` | `int` | X 坐标 |
| `y` | `int` | Y 坐标 |
| `subresource` | `Subresource` | 子资源 |
| `typeCast` | `CompType` | 类型转换（`CompType.Typeless` 表示不转换） |

**返回值**：`PixelValue`

**示例**：
```python
sub = rd.Subresource()
pixel = controller.PickPixel(texId, 100, 200, sub, rd.CompType.Typeless)
print(f"RGBA: {pixel.floatValue}")
```

---

#### GetMinMax

```python
minVal, maxVal = controller.GetMinMax(textureId, subresource, typeCast)
```

**描述**：获取纹理中的最小值和最大值。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `textureId` | `ResourceId` | 纹理 ID |
| `subresource` | `Subresource` | 子资源 |
| `typeCast` | `CompType` | 类型转换 |

**返回值**：`Tuple[PixelValue, PixelValue]`

---

#### GetHistogram

```python
buckets = controller.GetHistogram(textureId, subresource, typeCast, minval, maxval, channels)
```

**描述**：获取纹理的直方图数据。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `textureId` | `ResourceId` | 纹理 ID |
| `subresource` | `Subresource` | 子资源 |
| `typeCast` | `CompType` | 类型转换 |
| `minval` | `float` | 最小桶值 |
| `maxval` | `float` | 最大桶值 |
| `channels` | `Tuple[bool,bool,bool,bool]` | RGBA 通道开关 |

**返回值**：`List[int]`

---

#### PixelHistory

```python
modifications = controller.PixelHistory(textureId, x, y, subresource, typeCast)
```

**描述**：获取指定像素的完整修改历史。这会回放每个事件并记录该像素在每次 drawcall 前后的精确值。

> ⚠️ **性能注意**：此方法较慢（约 58.7 px/s），因为需要逐事件回放。如果只需要统计信息，请使用 `FetchPixelStats`。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `textureId` | `ResourceId` | 纹理 ID |
| `x` | `int` | X 坐标（左上角原点） |
| `y` | `int` | Y 坐标（左上角原点） |
| `subresource` | `Subresource` | 子资源 |
| `typeCast` | `CompType` | 类型转换 |

**返回值**：`List[PixelModification]`

**示例**：
```python
sub = rd.Subresource()
history = controller.PixelHistory(texId, 512, 384, sub, rd.CompType.Typeless)

for mod in history:
    print(f"Event {mod.eventId}:")
    print(f"  Pre:  {mod.preMod.col.floatValue}")
    print(f"  Post: {mod.postMod.col.floatValue}")
    if mod.depthTestFailed:
        print("  (depth test failed)")
```

---

#### FetchPixelStats (新增)

```python
stats = controller.FetchPixelStats(eventStart, eventEnd, overdrawDistribution)
```

**描述**：获取每个 drawcall 事件的像素统计信息。采用**混合方案**：

1. **GPU 硬件计数器**（`SamplesPassed`、`PSInvocations`、`RasterizedPrimitives`、`EventGPUDuration`）一次性收集所有事件的基础统计数据
2. **Drawcall Overlay 纹理读回**：对每个 drawcall 渲染 `DebugOverlay::Drawcall` overlay，读回纹理统计覆盖像素数，得到**精确的 `pixelTouched`**（不受 Instance Count 影响）
3. **QuadOverdrawDraw Overlay 纹理读回**（可选）：渲染 `DebugOverlay::QuadOverdrawDraw` overlay，读回纹理获取**精确的逐像素 overdraw 分布**

> ⚠️ **Instance Count 修正**：GPU 硬件计数器的 `SamplesPassed` 和 `PSInvocations` 会将所有实例的结果累加。例如 `DrawIndexedInstanced(108, 2)` 中 2 个完全重叠的实例，`SamplesPassed` 会报告 2 倍的实际像素数。通过 Overlay 方式，`pixelTouched` 统计的是**唯一覆盖像素数**，不受实例数影响。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `eventStart` | `int` | 起始事件 ID（0 = 从头开始） |
| `eventEnd` | `int` | 结束事件 ID（0 = 到末尾） |
| `overdrawDistribution` | `bool` | 是否计算精确的逐像素 overdraw 分布（较慢，需要额外的 overlay 渲染和纹理读回） |

**返回值**：`List[PixelEventStats]`

**字段说明**：

| 字段 | 含义 | 数据来源 |
|------|------|----------|
| `pixelTouched` | 此 drawcall 覆盖的**唯一像素数量**（不受 Instance Count 影响） | Drawcall Overlay 纹理读回 |
| `samplesPassed` | GPU 硬件计数器报告的通过深度/模板测试的样本数（含所有实例） | GPU Counter |
| `psInvocations` | Pixel Shader 调用次数（含所有实例） | GPU Counter |
| `rasterizedPrimitives` | 光栅化的图元数量 | GPU Counter |
| `gpuDuration` | GPU 执行时间（秒） | GPU Counter |
| `overdrawEstimate` | 平均 overdraw 比率 = `psInvocations / pixelTouched` | 计算值 |
| `overdrawDistribution` | 精确的逐像素 overdraw 分布 | QuadOverdrawDraw Overlay 纹理读回 |

**Overdraw 分布说明**：

当 `overdrawDistribution=True` 时，使用 RenderDoc 内置的 **QuadOverdrawDraw Overlay** 机制获取精确的逐像素 overdraw 分布：
- 每个 `OverdrawBucket` 包含 `overdrawCount`（overdraw 次数）和 `pixelCount`（像素数量）
- 例如：`overdrawCount=1` 表示无 overdraw（只画了 1 次），`overdrawCount=2` 表示该像素被画了 2 次
- 对于 `DrawIndexedInstanced(108, 2)` 中 2 个完全重叠的实例，分布会正确显示 `{2: N}` 而非 `{1: 2N}`
- 该方式使用 `InterlockedAdd` 在 UAV 上累加每个 2x2 quad 的绘制次数，然后 resolve 到 overlay 纹理

**性能说明**：
- 基础统计（无 overdraw 分布）：每个 drawcall 需要 1 次 overlay 渲染 + 1 次纹理读回
- 含 overdraw 分布：每个 drawcall 需要 2 次 overlay 渲染 + 2 次纹理读回
- 对于 1444×784 分辨率，每次纹理读回约 9MB（`R16G16B16A16_FLOAT` 格式）

**示例**：

```python
import renderdoc as rd

# 获取所有事件的像素统计（含精确 overdraw 分布）
stats = controller.FetchPixelStats(0, 0, True)

print(f"Total events with pixel stats: {len(stats)}")
print()

# 找出像素覆盖最多的 Top 10 drawcall
sorted_stats = sorted(stats, key=lambda s: s.pixelTouched, reverse=True)

print("=== Top 10 Drawcalls by Pixel Coverage ===")
for s in sorted_stats[:10]:
    if s.pixelTouched > 0:
        print(f"Event {s.eventId}:")
        print(f"  Pixels touched (unique): {s.pixelTouched:,}")
        print(f"  Samples passed (GPU):    {s.samplesPassed:,}")
        print(f"  PS Invocations:          {s.psInvocations:,}")
        print(f"  Rasterized prims:        {s.rasterizedPrimitives:,}")
        print(f"  GPU Duration:            {s.gpuDuration*1000:.3f} ms")
        print(f"  Overdraw estimate:       {s.overdrawEstimate:.2f}x")
        
        if s.overdrawDistribution:
            print(f"  Overdraw distribution:")
            for bucket in s.overdrawDistribution:
                print(f"    {bucket.overdrawCount}x: {bucket.pixelCount:,} pixels")
        print()

# 统计总体 overdraw 情况
total_pixels = sum(s.pixelTouched for s in stats)
total_ps = sum(s.psInvocations for s in stats)
if total_pixels > 0:
    print(f"=== Overall Statistics ===")
    print(f"Total unique pixels touched: {total_pixels:,}")
    print(f"Total PS invocations:        {total_ps:,}")
    print(f"Average overdraw:            {total_ps/total_pixels:.2f}x")
```

**与 PixelHistory 的对比**：

| 特性 | PixelHistory | FetchPixelStats |
|------|-------------|-----------------|
| 速度 | ~58.7 px/s（慢） | 每 drawcall 约数十 ms（快） |
| 单像素精确颜色值 | ✅ 支持 | ❌ 不支持 |
| 每像素独立值 | ✅ 支持 | ❌ 不支持 |
| 精确唯一像素覆盖数 | ❌ 不直接支持 | ✅ 支持（Overlay 方式） |
| 精确 Overdraw 分布 | ❌ 不直接支持 | ✅ 支持（QuadOverdraw Overlay） |
| Instance Count 修正 | 部分支持 | ✅ 自动正确 |
| 深度/模板测试通过率 | 部分支持 | ✅ 可计算 |

**推荐用法**：先用 `FetchPixelStats` 快速定位关键事件，再对特定事件使用 `PixelHistory` 深入分析。

---

### GPU 计数器

#### EnumerateCounters

```python
counters = controller.EnumerateCounters()
```

**描述**：获取当前 capture 分析实现中可用的 GPU 计数器列表。

**返回值**：`List[GPUCounter]`

**示例**：
```python
counters = controller.EnumerateCounters()
for c in counters:
    desc = controller.DescribeCounter(c)
    print(f"{desc.name}: {desc.description}")
```

---

#### DescribeCounter

```python
desc = controller.DescribeCounter(counter)
```

**描述**：获取指定计数器的详细描述信息。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `counter` | `GPUCounter` | 要查询的计数器 |

**返回值**：`CounterDescription`

---

#### FetchCounters

```python
results = controller.FetchCounters(counters)
```

**描述**：获取指定 GPU 计数器的查询结果。每个结果包含事件 ID、计数器类型和值。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `counters` | `List[GPUCounter]` | 要查询的计数器列表 |

**返回值**：`List[CounterResult]`

**示例**：
```python
# 查询 GPU 时间和像素通过数
results = controller.FetchCounters([
    rd.GPUCounter.EventGPUDuration,
    rd.GPUCounter.SamplesPassed
])

for r in results:
    if r.counter == rd.GPUCounter.EventGPUDuration:
        print(f"Event {r.eventId}: GPU time = {r.value.d*1000:.3f} ms")
    elif r.counter == rd.GPUCounter.SamplesPassed:
        print(f"Event {r.eventId}: Samples passed = {r.value.u64}")
```

**常用 GPU 计数器**：

| 计数器 | 描述 |
|--------|------|
| `GPUCounter.EventGPUDuration` | 事件 GPU 执行时间 |
| `GPUCounter.SamplesPassed` | 通过深度/模板测试的样本数 |
| `GPUCounter.PSInvocations` | Pixel Shader 调用次数 |
| `GPUCounter.VSInvocations` | Vertex Shader 调用次数 |
| `GPUCounter.CSInvocations` | Compute Shader 调用次数 |
| `GPUCounter.RasterizedPrimitives` | 光栅化的图元数 |
| `GPUCounter.InputVerticesRead` | 读取的输入顶点数 |

---

### Shader 调试

#### DebugVertex

```python
trace = controller.DebugVertex(vertid, instid, idx, view)
```

**描述**：调试指定顶点的 Vertex Shader 执行。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `vertid` | `int` | 顶点 ID（0-based） |
| `instid` | `int` | 实例 ID（0-based） |
| `idx` | `int` | 实际索引值（已应用 drawcall 偏移） |
| `view` | `int` | Multiview 视口索引（不使用时为 0） |

**返回值**：`ShaderDebugTrace`

> 使用完毕后需调用 `controller.FreeTrace(trace)` 释放。

---

#### DebugPixel

```python
trace = controller.DebugPixel(x, y, inputs)
```

**描述**：调试指定像素的 Pixel Shader 执行。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `x` | `int` | X 坐标（左上角原点） |
| `y` | `int` | Y 坐标（左上角原点） |
| `inputs` | `DebugPixelInputs` | 调试输入参数（sample, primitive, view） |

**返回值**：`ShaderDebugTrace`

---

#### DebugThread

```python
trace = controller.DebugThread(groupid, threadid)
```

**描述**：调试指定 Compute Shader 线程的执行。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `groupid` | `Tuple[int,int,int]` | 3D 工作组索引 |
| `threadid` | `Tuple[int,int,int]` | 工作组内的 3D 线程索引 |

**返回值**：`ShaderDebugTrace`

---

#### GetShaderEntryPoints

```python
entries = controller.GetShaderEntryPoints(shaderId)
```

**描述**：获取指定 shader 的入口点列表。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `shaderId` | `ResourceId` | Shader 资源 ID |

**返回值**：`List[ShaderEntryPoint]`

---

#### GetShader

```python
refl = controller.GetShader(pipelineId, shaderId, entry)
```

**描述**：获取指定 shader 的反射信息。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `pipelineId` | `ResourceId` | Pipeline State Object ID |
| `shaderId` | `ResourceId` | Shader 资源 ID |
| `entry` | `ShaderEntryPoint` | Shader 入口点 |

**返回值**：`ShaderReflection`

---

#### DisassembleShader

```python
disasm = controller.DisassembleShader(pipelineId, refl, target)
```

**描述**：获取指定 shader 的反汇编文本。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `pipelineId` | `ResourceId` | Pipeline State Object ID |
| `refl` | `ShaderReflection` | Shader 反射信息 |
| `target` | `str` | 反汇编目标（空字符串使用默认） |

**返回值**：`str`

---

### Shader 编译与替换

#### BuildCustomShader

```python
shaderId, errors = controller.BuildCustomShader(entry, encoding, source, flags, stage)
```

**描述**：编译自定义 shader，用于本地回放实例。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `entry` | `str` | 入口点名称 |
| `encoding` | `ShaderEncoding` | 源码编码格式 |
| `source` | `bytes` | 源码数据 |
| `flags` | `ShaderCompileFlags` | 编译标志 |
| `stage` | `ShaderStage` | Shader 阶段 |

**返回值**：`Tuple[ResourceId, str]`

---

#### BuildTargetShader

```python
shaderId, errors = controller.BuildTargetShader(entry, encoding, source, flags, stage)
```

**描述**：编译适用于 capture API 的替换 shader。

**参数**：同 `BuildCustomShader`

**返回值**：`Tuple[ResourceId, str]`

---

#### ReplaceResource

```python
controller.ReplaceResource(originalId, replacementId)
```

**描述**：用新资源替换原始资源，用于后续回放和分析。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `originalId` | `ResourceId` | 原始资源 ID |
| `replacementId` | `ResourceId` | 替换资源 ID |

---

#### RemoveReplacement

```python
controller.RemoveReplacement(resourceId)
```

**描述**：移除之前设置的资源替换。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `resourceId` | `ResourceId` | 之前被替换的资源 ID |

---

### Mesh 数据

#### GetPostVSData

```python
meshData = controller.GetPostVSData(instance, view, stage)
```

**描述**：获取几何处理阶段的输出数据。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `instance` | `int` | 实例索引（非实例化绘制为 0） |
| `view` | `int` | Multiview 视口索引（不使用时为 0） |
| `stage` | `MeshDataStage` | 几何处理阶段 |

**返回值**：`MeshFormat`

---

### 其他

#### GetDebugMessages

```python
messages = controller.GetDebugMessages()
```

**描述**：获取新生成的调试消息。每次调用后，已返回的消息不会再次返回。

**返回值**：`List[DebugMessage]`

---

#### GetStructuredFile

```python
sdfile = controller.GetStructuredFile()
```

**描述**：获取 capture 的结构化数据表示。

**返回值**：`SDFile`

---

#### GetDescriptors

```python
descriptors = controller.GetDescriptors(descriptorStore, ranges)
```

**描述**：获取描述符存储中指定范围的描述符内容。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `descriptorStore` | `ResourceId` | 描述符存储 ID |
| `ranges` | `List[DescriptorRange]` | 要查询的描述符范围 |

**返回值**：`List[Descriptor]`

---

#### GetCBufferVariableContents

```python
variables = controller.GetCBufferVariableContents(pipelineId, shaderId, stage, entryPoint, cbufslot, bufferId, offset, length)
```

**描述**：获取常量缓冲区的变量内容。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `pipelineId` | `ResourceId` | Pipeline State Object ID |
| `shaderId` | `ResourceId` | Shader 资源 ID |
| `stage` | `ShaderStage` | Shader 阶段 |
| `entryPoint` | `str` | 入口点名称 |
| `cbufslot` | `int` | 常量缓冲区槽位索引 |
| `bufferId` | `ResourceId` | Buffer 资源 ID |
| `offset` | `int` | 起始字节偏移 |
| `length` | `int` | 读取长度（0 = 读取剩余全部） |

**返回值**：`List[ShaderVariable]`

---

## 全局函数

### OpenCaptureFile

```python
cap = rd.OpenCaptureFile()
```

**描述**：创建一个 capture 文件句柄，用于打开和处理 `.rdc` 文件。

**返回值**：`CaptureFile`

**示例**：
```python
cap = rd.OpenCaptureFile()
result = cap.OpenFile("capture.rdc", "", None)

if result == rd.ResultCode.Succeeded:
    # 打开回放
    result, controller = cap.OpenCapture(rd.ReplayOptions(), None)
    
    if result == rd.ResultCode.Succeeded:
        # 使用 controller...
        controller.Shutdown()
    
    cap.Shutdown()
```

---

### InitialiseReplay / ShutdownReplay

```python
rd.InitialiseReplay(globalEnv, args)
# ... 使用 replay API ...
rd.ShutdownReplay()
```

**描述**：初始化/关闭 RenderDoc 回放环境。在调用任何回放 API 之前必须先初始化，程序退出前必须关闭。

---

### ExecuteAndInject

```python
result = rd.ExecuteAndInject(app, workingDir, cmdLine, env, captureFile, opts, waitForExit)
```

**描述**：启动应用程序并注入 RenderDoc 以进行捕获。

**参数**：
| 参数 | 类型 | 描述 |
|------|------|------|
| `app` | `str` | 应用程序路径 |
| `workingDir` | `str` | 工作目录（空字符串使用应用程序所在目录） |
| `cmdLine` | `str` | 命令行参数 |
| `env` | `List[EnvironmentModification]` | 环境变量修改 |
| `captureFile` | `str` | Capture 文件路径模板（空字符串使用默认位置） |
| `opts` | `CaptureOptions` | 捕获选项 |
| `waitForExit` | `bool` | 是否等待进程退出 |

**返回值**：`ExecuteResult`

---

## 完整示例：性能分析工作流

```python
import renderdoc as rd

def analyze_capture(rdc_path):
    """完整的 capture 分析工作流示例"""
    
    # 1. 打开 capture
    cap = rd.OpenCaptureFile()
    result = cap.OpenFile(rdc_path, "", None)
    assert result == rd.ResultCode.Succeeded, f"Failed to open: {result}"
    
    result, controller = cap.OpenCapture(rd.ReplayOptions(), None)
    assert result == rd.ResultCode.Succeeded, f"Failed to replay: {result}"
    
    try:
        # 2. 获取基本信息
        props = controller.GetAPIProperties()
        print(f"API: {props.pipelineType}")
        
        frame = controller.GetFrameInfo()
        print(f"Frame drawcalls: {frame.stats.draws}")
        
        # 3. 快速获取所有事件的像素统计（新增 API）
        stats = controller.FetchPixelStats(0, 0, True)
        
        # 4. 找出最耗时的 drawcall
        sorted_by_time = sorted(stats, key=lambda s: s.gpuDuration, reverse=True)
        print("\n=== Top 5 Slowest Drawcalls ===")
        for s in sorted_by_time[:5]:
            print(f"  Event {s.eventId}: {s.gpuDuration*1000:.3f}ms, "
                  f"{s.pixelTouched:,} pixels, "
                  f"overdraw {s.overdrawEstimate:.1f}x")
        
        # 5. 找出 overdraw 最严重的 drawcall
        sorted_by_overdraw = sorted(
            [s for s in stats if s.pixelTouched > 100],
            key=lambda s: s.overdrawEstimate, reverse=True
        )
        print("\n=== Top 5 Highest Overdraw ===")
        for s in sorted_by_overdraw[:5]:
            print(f"  Event {s.eventId}: overdraw {s.overdrawEstimate:.2f}x, "
                  f"{s.pixelTouched:,} pixels")
            for bucket in s.overdrawDistribution:
                print(f"    {bucket.overdrawCount}x: {bucket.pixelCount:,} pixels")
        
        # 6. 对最耗时的 drawcall 做精确像素分析
        if sorted_by_time:
            worst_event = sorted_by_time[0]
            controller.SetFrameEvent(worst_event.eventId, True)
            
            state = controller.GetPipelineState()
            targets = state.GetOutputTargets()
            
            if targets:
                texId = targets[0].resource
                textures = controller.GetTextures()
                tex = next((t for t in textures if t.resourceId == texId), None)
                
                if tex:
                    # 对中心像素做精确历史分析
                    cx, cy = tex.width // 2, tex.height // 2
                    sub = rd.Subresource()
                    history = controller.PixelHistory(texId, cx, cy, sub, rd.CompType.Typeless)
                    
                    print(f"\n=== Pixel History at ({cx}, {cy}) ===")
                    for mod in history:
                        print(f"  Event {mod.eventId}: "
                              f"{'PASS' if not mod.depthTestFailed else 'DEPTH_FAIL'}")
    
    finally:
        controller.Shutdown()
        cap.Shutdown()

# 使用示例
# analyze_capture("my_capture.rdc")
```
