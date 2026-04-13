# TestScripts 使用说明

## 概述

本目录包含一组 Python 测试脚本，用于通过 RenderDoc Python API 打开 `.rdc` 抓帧文件，提取 **Pixel Stats**、**GPU Counters**、**基础帧信息** 等数据，并导出为 JSON 格式，方便排查 Pixel Stats 导出异常等问题。

---

## 快速开始（推荐）

运行 `setup_venv` 脚本即可自动创建匹配 `renderdoc.pyd` 所需 Python 版本的虚拟环境：

```powershell
# PowerShell
.\TestScripts\setup_venv.ps1

# cmd.exe
TestScripts\setup_venv.bat
```

脚本会自动：
1. 从 `x64/Release/pythonXY.dll` 检测所需 Python 版本
2. 通过 `py` launcher 或常见安装路径查找对应的 Python 解释器
3. 验证 Python 版本和 64-bit 兼容性
4. 在 `TestScripts/.venv` 创建虚拟环境

创建完成后，激活 venv 再运行测试脚本：

```powershell
# 激活 (PowerShell)
TestScripts\.venv\Scripts\Activate.ps1

# 激活 (cmd.exe)
TestScripts\.venv\Scripts\activate.bat

# 运行测试
python TestScripts\test_pixel_stats.py path\to\your_capture.rdc
```

> **提示**：如果 venv 已存在，脚本会跳过创建。使用 `-Force`（PowerShell）或 `--force`（bat）强制重建。

---

## 前置条件

1. **Python 版本**：必须与编译 `renderdoc.pyd` 时使用的 Python 版本一致（通常为 **Python 3.6**）。推荐使用 `setup_venv` 脚本自动处理。
2. **renderdoc.pyd**：默认从项目根目录的 `x64/Release/` 加载。如果你的构建输出在其他位置，可通过 `--rd-dir` 参数指定。
3. **RDC 文件**：需要一个有效的 `.rdc` 抓帧文件作为输入。

---

## 文件说明

| 文件 | 说明 |
|------|------|
| `setup_venv.ps1` | **环境配置脚本（PowerShell）**。自动检测所需 Python 版本并创建匹配的 venv |
| `setup_venv.bat` | **环境配置脚本（cmd.exe）**。功能同上，适用于 cmd 环境 |
| `_rd_common.py` | 公共模块。处理 `renderdoc.pyd` 加载、Python 版本检测、Capture 打开/关闭、Action 树遍历等 |
| `test_pixel_stats.py` | 测试 `FetchPixelStats` API，输出像素覆盖、overdraw 分布、GPU 耗时等统计，并进行异常检测 |
| `test_gpu_counters.py` | 测试 GPU 计数器枚举与获取，输出 `SamplesPassed`、`PSInvocations`、`EventGPUDuration` 等 |
| `test_basic_info.py` | 测试基础 API，提取 Actions 树、Textures、Buffers、Pipeline State 等信息 |
| `test_pixel_stats_vs_counters.py` | **交叉验证**：对比 `FetchPixelStats` 与原始 GPU Counters 数据，找出不一致的地方 |

---

## 通用参数

所有测试脚本都支持以下参数：

| 参数 | 说明 |
|------|------|
| `<rdc_file>` | （必填）`.rdc` 抓帧文件路径 |
| `--output` / `-o` | （可选）指定输出 JSON 文件路径。不指定则自动生成到 `TestScripts/output/` 目录 |
| `--rd-dir` | （可选）指定 `renderdoc.pyd` 所在目录。默认为 `<项目根目录>/x64/Release/` |

---

## 使用示例

> 以下示例假设在项目根目录 (`renderdoc_ex/`) 下执行，Python 3.6 安装在默认路径。
> 请根据实际情况替换 Python 路径和 RDC 文件路径。

### 1. 测试 Pixel Stats（最常用）

```powershell
# 基本用法
python TestScripts/test_pixel_stats.py path/to/your_capture.rdc

# 指定输出路径
python TestScripts/test_pixel_stats.py path/to/your_capture.rdc -o result_pixel_stats.json
```

**输出内容**：
- 每个事件的 `pixels_touched`、`samples_passed`、`ps_invocations`、`rasterized_primitives`、`gpu_duration`、`overdraw_estimate`
- 每个事件的逐像素 overdraw 分布（`overdraw_distribution`），仅统计通过 Depth Test 的像素（与 RenderDoc 的 Quad Overdraw overlay 行为一致）
- Top 10 排行（按像素覆盖、overdraw、GPU 耗时）
- **异常检测**（Sanity Checks）：自动标记可疑数据，例如：
  - `pixels_touched > ps_invocations`
  - `overdraw_estimate < 1.0`（当两个值都 > 0 时）
  - `samples_passed == 0` 但 `pixels_touched > 0`
  - 负数 GPU 耗时

### 2. 交叉验证 PixelStats vs GPU Counters（排查数据不一致）

```powershell
# 基本用法
python TestScripts/test_pixel_stats_vs_counters.py path/to/your_capture.rdc

# 调整浮点比较容差（默认 0.01 即 1%）
python TestScripts/test_pixel_stats_vs_counters.py path/to/your_capture.rdc --tolerance 0.05
```

**输出内容**：
- 逐事件对比 `FetchPixelStats` 返回值与 `FetchCounters` 原始 GPU 计数器
- 标记所有不匹配的字段（`samples_passed`、`ps_invocations`、`rasterized_primitives`、`gpu_duration`）
- 检查 `pixelTouched <= samplesPassed` 关系是否成立

### 3. 测试 GPU Counters

```powershell
python TestScripts/test_gpu_counters.py path/to/your_capture.rdc
```

**输出内容**：
- 枚举所有可用 GPU 计数器及其描述
- 获取关键计数器数据并按事件组织
- 聚合统计（Min / Max / Sum / Avg）

### 4. 测试基础帧信息

```powershell
python TestScripts/test_basic_info.py path/to/your_capture.rdc
```

**输出内容**：
- API 类型、帧统计
- Drawcall 列表（前 50 个）
- Texture 列表（前 30 个，含尺寸、格式、字节大小）
- Buffer 列表（前 30 个）
- 第一个 Drawcall 的 Pipeline State（输出目标、深度目标、拓扑、Shader 入口点等）

---

## 输出说明

- 默认输出到 `TestScripts/output/` 目录，文件名格式为 `<rdc文件名>_<测试类型>_<时间戳>.json`
- 可通过 `-o` 参数指定自定义输出路径
- 所有输出均为格式化的 JSON（`indent=2`），方便阅读和后续处理

### 字段说明

| 字段 | 说明 |
|------|------|
| `pixels_touched` | 该 drawcall 光栅化覆盖的**所有**唯一像素数（禁用 Depth Test 统计） |
| `overdraw_distribution` | 逐像素 overdraw 分布，仅统计**通过 Depth Test** 的像素。与 RenderDoc 的 Quad Overdraw overlay 行为一致，使用 `[earlydepthstencil]` 属性进行 early-Z 剔除 |
| `overdraw_estimate` | overdraw 估算值 = `samples_passed / pixels_touched` |
| `samples_passed` | 通过 Depth/Stencil Test 的采样数（来自 GPU Counter） |
| `ps_invocations` | Pixel Shader 调用次数（来自 GPU Counter） |

> **注意**：`pixels_touched` 可能大于 `overdraw_distribution` 中所有像素数的累加值。这是因为 `pixels_touched` 统计时禁用了 Depth Test（统计所有光栅化像素），而 `overdraw_distribution` 仅统计通过 Depth Test 的像素（与 RenderDoc 的 Quad Overdraw overlay 保持一致）。

### 输出 JSON 示例（test_pixel_stats.py）

```json
{
  "rdc_file": "D:/captures/my_capture.rdc",
  "api": "GraphicsAPI.D3D11",
  "total_drawcalls": 256,
  "fetch_time_seconds": 1.234,
  "overdraw_distribution_enabled": true,
  "pixel_stats": [
    {
      "event_id": 42,
      "pixels_touched": 921600,
      "samples_passed": 1843200,
      "ps_invocations": 1843200,
      "rasterized_primitives": 5000,
      "gpu_duration_ms": 0.1234,
      "overdraw_estimate": 2.0,
      "overdraw_distribution": {
        "1": 460800,
        "2": 230400
      }
    }
  ],
  "anomalies": []
}
```

---

## 指定 Python 版本

**推荐方式**：使用 `setup_venv.ps1` / `setup_venv.bat` 自动创建 venv（见「快速开始」章节）。

如果不想使用 venv，也可以手动指定 Python 路径：

```powershell
# Windows - 使用特定版本的 Python
& "C:\Python36\python.exe" TestScripts/test_pixel_stats.py path/to/capture.rdc

# 或者使用 py launcher
py -3.6 TestScripts/test_pixel_stats.py path/to/capture.rdc
```

## 指定自定义 renderdoc 目录

```powershell
python TestScripts/test_pixel_stats.py path/to/capture.rdc --rd-dir "D:/custom_build/x64/Release"
```

---

## 常见问题

### Q: 提示 "Python version mismatch"
**A**: `renderdoc.pyd` 编译时绑定了特定 Python 版本。请检查 `x64/Release/` 下的 `pythonXY.dll` 文件名来确认所需版本，然后使用对应版本的 Python 运行脚本。

### Q: 提示 "Failed to import renderdoc"
**A**: 确认 `x64/Release/` 目录下存在 `renderdoc.pyd` 和相关 DLL。如果构建输出在其他位置，使用 `--rd-dir` 指定。

### Q: 提示 "Capture cannot be replayed on this machine"
**A**: 该 RDC 文件可能是在不同 GPU/驱动环境下抓取的，无法在当前机器上回放。

### Q: 交叉验证发现大量 mismatch
**A**: 这可能正是 Pixel Stats 异常的表现。检查 JSON 输出中的 `mismatches` 字段，关注 `samples_passed` 和 `ps_invocations` 的差异，这些通常是问题的关键线索。
