"""GPU compute support (optional).

Everything here is optional and import-guarded: the core toolkit and its test suite
must keep working on a machine with no GPU and no OpenCL runtime.

Why this package exists: openEMS is CPU-only, so the only way to use a GPU for the
*simulation* is to run a different FDTD kernel.  This package builds that kernel in
OpenCL, starting with a deliberately small scope (a validated 2-D TMz solver) so the
physics can be checked against an analytic answer before anything is built on top.

Hard expectation, stated once and measurable with ``scripts/gpu_benchmark.py``: FDTD is
memory-bandwidth bound.  An integrated GPU shares the system memory bus with the CPU
(here: ~6 GB of shared DDR4), so an iGPU of this class is *not* expected to beat a
16-thread Ryzen.  A cheap discrete GPU with dedicated VRAM has several times the
bandwidth and is where this path pays off.  The code is written so the same kernel
scales to one without changes.
"""

from __future__ import annotations

from typing import List, Optional

__all__ = ["opencl_devices", "gpu_available"]


def gpu_available() -> bool:
    """True when pyopencl is importable and at least one OpenCL device exists."""
    return bool(opencl_devices())


def opencl_devices() -> List[dict]:
    """Describe the OpenCL devices available, or return an empty list.

    Never raises: a missing pyopencl, a missing runtime or a driver error all come
    back as "no devices", because callers use this to decide whether to skip.
    """
    try:
        import pyopencl as cl  # imported lazily: optional dependency
    except Exception:
        return []

    devices: List[dict] = []
    try:
        for platform in cl.get_platforms():
            for device in platform.get_devices():
                devices.append(
                    {
                        "platform": platform.name,
                        "platform_version": platform.version,
                        "name": device.name,
                        "type": cl.device_type.to_string(device.type),
                        "compute_units": device.max_compute_units,
                        "clock_mhz": device.max_clock_frequency,
                        "global_mem_mb": round(device.global_mem_size / 1048576),
                        "local_mem_kb": round(device.local_mem_size / 1024),
                        "max_work_group": device.max_work_group_size,
                        "fp64": bool(device.double_fp_config),
                    }
                )
    except Exception:
        return devices
    return devices


def first_device_index() -> Optional[int]:
    """Index into :func:`opencl_devices` of the first GPU, else the first device."""
    devices = opencl_devices()
    for index, device in enumerate(devices):
        if "GPU" in device["type"]:
            return index
    return 0 if devices else None
