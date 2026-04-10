"""
Cross-validate FetchPixelStats vs GPU Counters - Find data inconsistencies.

This script fetches both FetchPixelStats and raw GPU counters, then compares
them side-by-side to identify discrepancies that may indicate bugs.

Usage:
    python test_pixel_stats_vs_counters.py <rdc_file> [--output <json_path>]

Example:
    python test_pixel_stats_vs_counters.py ../TestRDC/GrassBuildTest_20250612.rdc
"""

import os
import sys
import json
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _rd_common import setup_renderdoc, open_capture, close_capture, get_drawcalls


def main():
    parser = argparse.ArgumentParser(
        description="Cross-validate FetchPixelStats vs GPU Counters")
    parser.add_argument("rdc_file", help="Path to the .rdc capture file")
    parser.add_argument("--output", "-o", default=None,
                        help="Output JSON file path (default: auto-generated)")
    parser.add_argument("--rd-dir", default=None,
                        help="Path to directory containing renderdoc.pyd")
    parser.add_argument("--tolerance", type=float, default=0.01,
                        help="Relative tolerance for float comparisons (default: 0.01)")
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
        drawcall_eids = set(a.eventId for a in drawcalls)
        print("[INFO] Total drawcalls: %d" % len(drawcalls))

        # --- Step 1: Fetch raw GPU counters ---
        print("\n=== Step 1: Fetching Raw GPU Counters ===")
        desired_counters = [
            rd.GPUCounter.EventGPUDuration,
            rd.GPUCounter.SamplesPassed,
            rd.GPUCounter.PSInvocations,
            rd.GPUCounter.RasterizedPrimitives,
        ]
        available = controller.EnumerateCounters()
        counters_to_fetch = [c for c in desired_counters if c in available]

        counter_descs = {}
        counter_names = {}
        for c in counters_to_fetch:
            desc = controller.DescribeCounter(c)
            counter_descs[int(c)] = desc
            counter_names[int(c)] = desc.name

        t1 = time.time()
        raw_results = controller.FetchCounters(counters_to_fetch)
        t1_elapsed = time.time() - t1
        print("[INFO] Raw GPU counters: %d entries in %.2fs" % (len(raw_results), t1_elapsed))

        # Organize raw counters by event
        raw_by_event = {}
        for r in raw_results:
            eid = r.eventId
            desc = counter_descs.get(r.counter)
            cname = counter_names.get(r.counter, str(r.counter))
            if desc:
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
            if eid not in raw_by_event:
                raw_by_event[eid] = {}
            raw_by_event[eid][cname] = val

        # --- Step 2: Fetch FetchPixelStats ---
        print("\n=== Step 2: Fetching FetchPixelStats ===")
        t2 = time.time()
        pixel_stats = controller.FetchPixelStats(0, 0, True)
        t2_elapsed = time.time() - t2
        print("[INFO] FetchPixelStats: %d entries in %.2fs" % (len(pixel_stats), t2_elapsed))

        ps_by_event = {}
        for s in pixel_stats:
            ps_by_event[s.eventId] = s

        # --- Step 3: Cross-validate ---
        print("\n=== Step 3: Cross-Validation ===")
        tolerance = args.tolerance
        comparisons = []
        mismatches = []

        # Find common drawcall events
        common_eids = sorted(drawcall_eids & set(raw_by_event.keys()) & set(ps_by_event.keys()))
        print("[INFO] Common drawcall events for comparison: %d" % len(common_eids))

        for eid in common_eids:
            raw = raw_by_event[eid]
            ps = ps_by_event[eid]

            comp = {"event_id": eid, "checks": [], "has_mismatch": False}

            # Compare SamplesPassed
            raw_sp = None
            for k in ("Samples Passed", "SamplesPassed"):
                if k in raw:
                    raw_sp = raw[k]
                    break
            if raw_sp is not None:
                check = {
                    "field": "samples_passed",
                    "raw_counter": int(raw_sp),
                    "pixel_stats": ps.samplesPassed,
                    "match": int(raw_sp) == ps.samplesPassed,
                }
                comp["checks"].append(check)
                if not check["match"]:
                    comp["has_mismatch"] = True

            # Compare PSInvocations
            raw_ps = None
            for k in ("PS Invocations", "PSInvocations", "Fragment Shader Invocations"):
                if k in raw:
                    raw_ps = raw[k]
                    break
            if raw_ps is not None:
                check = {
                    "field": "ps_invocations",
                    "raw_counter": int(raw_ps),
                    "pixel_stats": ps.psInvocations,
                    "match": int(raw_ps) == ps.psInvocations,
                }
                comp["checks"].append(check)
                if not check["match"]:
                    comp["has_mismatch"] = True

            # Compare RasterizedPrimitives
            raw_rp = None
            for k in ("Rasterized Primitives", "RasterizedPrimitives"):
                if k in raw:
                    raw_rp = raw[k]
                    break
            if raw_rp is not None:
                check = {
                    "field": "rasterized_primitives",
                    "raw_counter": int(raw_rp),
                    "pixel_stats": ps.rasterizedPrimitives,
                    "match": int(raw_rp) == ps.rasterizedPrimitives,
                }
                comp["checks"].append(check)
                if not check["match"]:
                    comp["has_mismatch"] = True

            # Compare GPU Duration (float, use tolerance)
            raw_dur = None
            for k in ("GPU Duration", "EventGPUDuration"):
                if k in raw:
                    raw_dur = raw[k]
                    break
            if raw_dur is not None:
                # Both should be in seconds
                diff = abs(raw_dur - ps.gpuDuration)
                max_val = max(abs(raw_dur), abs(ps.gpuDuration), 1e-12)
                rel_diff = diff / max_val
                check = {
                    "field": "gpu_duration",
                    "raw_counter": raw_dur,
                    "pixel_stats": ps.gpuDuration,
                    "abs_diff": diff,
                    "rel_diff": round(rel_diff, 6),
                    "match": rel_diff <= tolerance,
                }
                comp["checks"].append(check)
                if not check["match"]:
                    comp["has_mismatch"] = True

            # Additional: pixelTouched vs samplesPassed relationship
            if ps.pixelTouched > 0 and ps.samplesPassed > 0:
                # pixelTouched (overlay-based) should be <= samplesPassed (GPU counter)
                # because samplesPassed includes all instances
                check = {
                    "field": "pixelTouched_vs_samplesPassed",
                    "pixel_touched": ps.pixelTouched,
                    "samples_passed": ps.samplesPassed,
                    "ratio": round(ps.samplesPassed / ps.pixelTouched, 4),
                    "match": ps.pixelTouched <= ps.samplesPassed,
                    "note": "pixelTouched should be <= samplesPassed (overlay vs GPU counter)",
                }
                comp["checks"].append(check)
                if not check["match"]:
                    comp["has_mismatch"] = True

            comparisons.append(comp)
            if comp["has_mismatch"]:
                mismatches.append(comp)

        # Print results
        print("\n=== Results ===")
        print("Total comparisons: %d" % len(comparisons))
        print("Mismatches found:  %d" % len(mismatches))

        if mismatches:
            print("\n--- Mismatched Events ---")
            for m in mismatches[:30]:
                print("\n  Event %d:" % m["event_id"])
                for check in m["checks"]:
                    status = "OK" if check["match"] else "MISMATCH"
                    if check["field"] == "gpu_duration":
                        print("    [%s] %s: raw=%.6f, pixel_stats=%.6f (rel_diff=%.6f)" % (
                            status, check["field"],
                            check["raw_counter"], check["pixel_stats"],
                            check["rel_diff"]))
                    elif check["field"] == "pixelTouched_vs_samplesPassed":
                        print("    [%s] %s: touched=%d, passed=%d, ratio=%.4f" % (
                            status, check["field"],
                            check["pixel_touched"], check["samples_passed"],
                            check["ratio"]))
                    else:
                        print("    [%s] %s: raw=%s, pixel_stats=%s" % (
                            status, check["field"],
                            format(check["raw_counter"], ","),
                            format(check["pixel_stats"], ",")))
            if len(mismatches) > 30:
                print("\n  ... and %d more mismatches" % (len(mismatches) - 30))
        else:
            print("\n[OK] All values match between FetchPixelStats and raw GPU counters!")

        # Events only in one source
        only_raw = sorted(drawcall_eids & set(raw_by_event.keys()) - set(ps_by_event.keys()))
        only_ps = sorted(drawcall_eids & set(ps_by_event.keys()) - set(raw_by_event.keys()))
        if only_raw:
            print("\n[WARN] %d drawcall events have raw counters but no pixel stats" % len(only_raw))
            print("  Event IDs: %s" % str(only_raw[:20]))
        if only_ps:
            print("\n[WARN] %d drawcall events have pixel stats but no raw counters" % len(only_ps))
            print("  Event IDs: %s" % str(only_ps[:20]))

        # Build output
        output_data = {
            "rdc_file": rdc_file,
            "api": str(props.pipelineType),
            "total_drawcalls": len(drawcalls),
            "raw_counter_fetch_time": round(t1_elapsed, 3),
            "pixel_stats_fetch_time": round(t2_elapsed, 3),
            "tolerance": tolerance,
            "total_comparisons": len(comparisons),
            "total_mismatches": len(mismatches),
            "mismatches": mismatches,
            "events_only_in_raw_counters": only_raw,
            "events_only_in_pixel_stats": only_ps,
        }

        if args.output:
            output_path = os.path.abspath(args.output)
        else:
            from datetime import datetime
            basename = os.path.splitext(os.path.basename(rdc_file))[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, "%s_cross_validate_%s.json" % (basename, timestamp))

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
