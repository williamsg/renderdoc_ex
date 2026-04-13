"""
Test FetchPixelStats API - Verify pixel statistics for drawcalls.

Usage:
    python test_pixel_stats.py <rdc_file> [--output <json_path>]

Example:
    python test_pixel_stats.py ../TestRDC/GrassBuildTest_20250612.rdc
    python test_pixel_stats.py ../TestRDC/GrassBuildTest_20250612.rdc --output result.json
"""

import os
import sys
import json
import time
import argparse

# Add script directory to path for _rd_common import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _rd_common import setup_renderdoc, open_capture, close_capture, get_drawcalls, flatten_actions

def main():
    parser = argparse.ArgumentParser(description="Test FetchPixelStats API")
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

    # Setup renderdoc
    if not setup_renderdoc(args.rd_dir):
        sys.exit(1)

    import renderdoc as rd

    # Open capture
    cap, controller = open_capture(rdc_file)
    if controller is None:
        sys.exit(1)

    try:
        # Get basic info
        props = controller.GetAPIProperties()
        print("[INFO] API: %s" % str(props.pipelineType))

        root_actions = controller.GetRootActions()
        drawcalls = get_drawcalls(root_actions)
        print("[INFO] Total drawcalls: %d" % len(drawcalls))

        # Build eventId -> action name mapping (from all actions, not just drawcalls)
        structured_file = controller.GetStructuredFile()
        all_actions = flatten_actions(root_actions)
        event_name_map = {}
        for action in all_actions:
            name = action.GetName(structured_file)
            if name:
                event_name_map[action.eventId] = name

        # Fetch pixel stats (always with overdraw distribution)
        print("\n=== Fetching Pixel Stats ===")

        t_start = time.time()
        stats = controller.FetchPixelStats(0, 0, True)
        t_elapsed = time.time() - t_start

        print("[INFO] FetchPixelStats returned %d entries in %.2fs" % (len(stats), t_elapsed))

        # Build result data
        results = []
        for s in stats:
            entry = {
                "event_id": s.eventId,
                "event_name": event_name_map.get(s.eventId, ""),
                "pixels_touched": s.pixelTouched,
                "samples_passed": s.samplesPassed,
                "ps_invocations": s.psInvocations,
                "rasterized_primitives": s.rasterizedPrimitives,
                "gpu_duration_ms": round(s.gpuDuration * 1000, 4),
                "overdraw_estimate": round(s.overdrawEstimate, 4) if s.overdrawEstimate is not None else 0.0,
            }

            # Overdraw distribution
            # NOTE: overdraw_distribution only counts pixels that passed the Depth Test,
            # consistent with RenderDoc's Quad Overdraw overlay (which uses [earlydepthstencil]).
            # This means sum(overdraw_distribution values) may be less than pixels_touched,
            # because pixels_touched is counted with Depth Test disabled.
            if s.overdrawDistribution:
                dist = {}
                for bucket in s.overdrawDistribution:
                    dist[str(bucket.overdrawCount)] = bucket.pixelCount
                entry["overdraw_distribution"] = dist

            results.append(entry)

        # Print summary
        print("\n=== Pixel Stats Summary ===")
        print("Events with stats: %d" % len(results))

        non_zero = [r for r in results if r["pixels_touched"] > 0]
        print("Events with pixels > 0: %d" % len(non_zero))

        if non_zero:
            total_pixels = sum(r["pixels_touched"] for r in non_zero)
            total_ps = sum(r["ps_invocations"] for r in non_zero)
            total_gpu_ms = sum(r["gpu_duration_ms"] for r in non_zero)

            print("Total unique pixels touched: %s" % format(total_pixels, ","))
            print("Total PS invocations:        %s" % format(total_ps, ","))
            print("Total GPU time:              %.3f ms" % total_gpu_ms)
            if total_pixels > 0 and total_ps > 0:
                avg_overdraw = total_ps / total_pixels
                print("Average overdraw:            %.2fx" % avg_overdraw)

            # Top 10 by pixel coverage
            sorted_by_pixels = sorted(non_zero, key=lambda r: r["pixels_touched"], reverse=True)
            print("\n--- Top 10 by Pixel Coverage ---")
            for r in sorted_by_pixels[:10]:
                print("  Event %d [%s]: pixels=%s, ps_inv=%s, overdraw=%.2fx, gpu=%.3fms" % (
                    r["event_id"],
                    r["event_name"],
                    format(r["pixels_touched"], ","),
                    format(r["ps_invocations"], ","),
                    r["overdraw_estimate"],
                    r["gpu_duration_ms"],
                ))
                if "overdraw_distribution" in r:
                    for k, v in sorted(r["overdraw_distribution"].items(), key=lambda x: int(x[0])):
                        print("    %sx: %s pixels" % (k, format(v, ",")))

            # Top 10 by overdraw
            high_overdraw = [r for r in non_zero if r["overdraw_estimate"] > 1.0]
            if high_overdraw:
                sorted_by_od = sorted(high_overdraw, key=lambda r: r["overdraw_estimate"], reverse=True)
                print("\n--- Top 10 by Overdraw ---")
                for r in sorted_by_od[:10]:
                    print("  Event %d [%s]: overdraw=%.2fx, pixels=%s, ps_inv=%s" % (
                        r["event_id"],
                        r["event_name"],
                        r["overdraw_estimate"],
                        format(r["pixels_touched"], ","),
                        format(r["ps_invocations"], ","),
                    ))

            # Top 10 by GPU time
            sorted_by_time = sorted(non_zero, key=lambda r: r["gpu_duration_ms"], reverse=True)
            print("\n--- Top 10 by GPU Time ---")
            for r in sorted_by_time[:10]:
                print("  Event %d [%s]: gpu=%.3fms, pixels=%s, overdraw=%.2fx" % (
                    r["event_id"],
                    r["event_name"],
                    r["gpu_duration_ms"],
                    format(r["pixels_touched"], ","),
                    r["overdraw_estimate"],
                ))

        # Sanity checks
        print("\n=== Sanity Checks ===")
        anomalies = []

        # Detect if SamplesPassed/PSInvocations counters are unavailable (e.g. GLES replay)
        # In that case, all samples_passed and ps_invocations will be 0 - this is expected
        has_any_samples = any(r["samples_passed"] > 0 for r in results)
        has_any_ps_inv = any(r["ps_invocations"] > 0 for r in results)
        counters_unavailable = not has_any_samples and not has_any_ps_inv and len(results) > 0

        for r in results:
            issues = []
            # Check: pixels_touched should not exceed ps_invocations (in most cases)
            if r["pixels_touched"] > 0 and r["ps_invocations"] > 0:
                if r["pixels_touched"] > r["ps_invocations"]:
                    issues.append("pixels_touched(%d) > ps_invocations(%d)" % (
                        r["pixels_touched"], r["ps_invocations"]))

            # Check: overdraw_estimate should be >= 1.0 when both values are positive
            if r["pixels_touched"] > 0 and r["ps_invocations"] > 0:
                if r["overdraw_estimate"] < 1.0:
                    issues.append("overdraw_estimate(%.4f) < 1.0" % r["overdraw_estimate"])

            # Check: samples_passed should be > 0 if pixels_touched > 0
            # Skip this check when counters are unavailable (GLES replay)
            if not counters_unavailable:
                if r["pixels_touched"] > 0 and r["samples_passed"] == 0:
                    issues.append("pixels_touched(%d) > 0 but samples_passed == 0" % r["pixels_touched"])

            # Check: gpu_duration should be non-negative
            if r["gpu_duration_ms"] < 0:
                issues.append("negative gpu_duration: %.4f ms" % r["gpu_duration_ms"])

            if issues:
                anomalies.append({"event_id": r["event_id"], "issues": issues})

        if anomalies:
            print("[WARN] Found %d events with anomalies:" % len(anomalies))
            for a in anomalies[:20]:
                print("  Event %d:" % a["event_id"])
                for issue in a["issues"]:
                    print("    - %s" % issue)
            if len(anomalies) > 20:
                print("  ... and %d more" % (len(anomalies) - 20))
        else:
            print("[OK] No anomalies detected.")

        # Save JSON output
        output_data = {
            "rdc_file": rdc_file,
            "api": str(props.pipelineType),
            "total_drawcalls": len(drawcalls),
            "fetch_time_seconds": round(t_elapsed, 3),
            "overdraw_distribution_enabled": True,
            "pixel_stats": results,
            "anomalies": anomalies,
        }

        if args.output:
            output_path = os.path.abspath(args.output)
        else:
            from datetime import datetime
            basename = os.path.splitext(os.path.basename(rdc_file))[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, "%s_pixel_stats_%s.json" % (basename, timestamp))

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
