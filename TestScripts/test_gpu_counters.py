"""
Test GPU Counters API - Verify GPU counter data for drawcalls.

Usage:
    python test_gpu_counters.py <rdc_file> [--output <json_path>]

Example:
    python test_gpu_counters.py ../TestRDC/GrassBuildTest_20250612.rdc
"""

import os
import sys
import json
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _rd_common import setup_renderdoc, open_capture, close_capture, get_drawcalls


def main():
    parser = argparse.ArgumentParser(description="Test GPU Counters API")
    parser.add_argument("rdc_file", help="Path to the .rdc capture file")
    parser.add_argument("--output", "-o", default=None,
                        help="Output JSON file path (default: auto-generated)")
    parser.add_argument("--rd-dir", default=None,
                        help="Path to directory containing renderdoc.pyd")
    args = parser.parse_args()

    rdc_file = os.path.abspath(args.rdc_file)
    if not os.path.isfile(rdc_file):
        print("[ERROR] RDC file not found: %s" % rdc_file)
        sys.exit(1)

    if not setup_renderdoc(args.rd_dir):
        sys.exit(1)

    import renderdoc as rd

    cap, controller = open_capture(rdc_file)
    if controller is None:
        sys.exit(1)

    try:
        props = controller.GetAPIProperties()
        print("[INFO] API: %s" % str(props.pipelineType))

        root_actions = controller.GetRootActions()
        drawcalls = get_drawcalls(root_actions)
        print("[INFO] Total drawcalls: %d" % len(drawcalls))

        # Enumerate available counters
        print("\n=== Enumerating GPU Counters ===")
        available = controller.EnumerateCounters()
        print("[INFO] Available counters: %d" % len(available))

        counter_info = []
        for c in available:
            desc = controller.DescribeCounter(c)
            info = {
                "counter": str(c),
                "name": desc.name,
                "description": desc.description,
                "result_type": str(desc.resultType),
                "result_byte_width": desc.resultByteWidth,
            }
            counter_info.append(info)
            print("  %s: %s" % (desc.name, desc.description))

        # Fetch key counters
        desired_counters = [
            rd.GPUCounter.EventGPUDuration,
            rd.GPUCounter.SamplesPassed,
            rd.GPUCounter.PSInvocations,
            rd.GPUCounter.VSInvocations,
            rd.GPUCounter.RasterizedPrimitives,
            rd.GPUCounter.InputVerticesRead,
        ]

        counters_to_fetch = [c for c in desired_counters if c in available]
        print("\n=== Fetching %d Counters ===" % len(counters_to_fetch))

        # Build descriptions lookup
        counter_descs = {}
        counter_names = {}
        for c in counters_to_fetch:
            desc = controller.DescribeCounter(c)
            counter_descs[int(c)] = desc
            counter_names[int(c)] = desc.name

        t_start = time.time()
        results = controller.FetchCounters(counters_to_fetch)
        t_elapsed = time.time() - t_start
        print("[INFO] FetchCounters returned %d entries in %.2fs" % (len(results), t_elapsed))

        # Organize by event
        event_data = {}  # eventId -> { counter_name: value }
        for r in results:
            eid = r.eventId
            cid = r.counter
            desc = counter_descs.get(cid)
            cname = counter_names.get(cid, "counter_%d" % cid)

            if desc is not None:
                bw = desc.resultByteWidth
                rt = desc.resultType
                if rt == rd.CompType.Float:
                    val = r.value.f if bw == 4 else r.value.d
                elif rt == rd.CompType.UInt:
                    val = r.value.u32 if bw == 4 else r.value.u64
                else:
                    val = r.value.d
            else:
                val = r.value.u64

            if eid not in event_data:
                event_data[eid] = {}
            event_data[eid][cname] = val

        # Print summary for drawcall events
        drawcall_eids = set(a.eventId for a in drawcalls)
        dc_counter_data = {eid: data for eid, data in event_data.items() if eid in drawcall_eids}

        print("\n=== Counter Summary (drawcalls only) ===")
        print("Drawcalls with counter data: %d / %d" % (len(dc_counter_data), len(drawcalls)))

        if dc_counter_data:
            # Aggregate stats
            for cname in sorted(set(k for d in dc_counter_data.values() for k in d)):
                values = [d[cname] for d in dc_counter_data.values() if cname in d]
                if values:
                    print("\n  %s:" % cname)
                    print("    Count:  %d" % len(values))
                    print("    Min:    %s" % format(min(values), ","))
                    print("    Max:    %s" % format(max(values), ","))
                    print("    Sum:    %s" % format(sum(values), ","))
                    if len(values) > 0:
                        print("    Avg:    %.2f" % (sum(values) / len(values)))

        # Build output
        output_events = []
        for eid in sorted(event_data.keys()):
            entry = {"event_id": eid}
            entry["counters"] = event_data[eid]
            entry["is_drawcall"] = eid in drawcall_eids
            output_events.append(entry)

        output_data = {
            "rdc_file": rdc_file,
            "api": str(props.pipelineType),
            "total_drawcalls": len(drawcalls),
            "fetch_time_seconds": round(t_elapsed, 3),
            "available_counters": counter_info,
            "fetched_counters": [counter_names.get(int(c), str(c)) for c in counters_to_fetch],
            "events": output_events,
        }

        if args.output:
            output_path = os.path.abspath(args.output)
        else:
            from datetime import datetime
            basename = os.path.splitext(os.path.basename(rdc_file))[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, "%s_gpu_counters_%s.json" % (basename, timestamp))

        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)

        print("\n[INFO] Results saved to: %s" % output_path)

    finally:
        close_capture(cap, controller)


if __name__ == "__main__":
    main()
