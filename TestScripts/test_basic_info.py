"""
Test Basic Capture Info - Verify basic RenderDoc API functionality.

Extracts actions, textures, buffers, pipeline state, and basic frame info.

Usage:
    python test_basic_info.py <rdc_file> [--output <json_path>]

Example:
    python test_basic_info.py ../TestRDC/GrassBuildTest_20250612.rdc
"""

import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _rd_common import setup_renderdoc, open_capture, close_capture, flatten_actions, get_drawcalls


def main():
    parser = argparse.ArgumentParser(description="Test Basic Capture Info APIs")
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
        # --- API Properties ---
        props = controller.GetAPIProperties()
        api_info = {
            "pipeline_type": str(props.pipelineType),
            "degraded": props.degraded,
        }
        print("[INFO] API: %s, degraded: %s" % (api_info["pipeline_type"], api_info["degraded"]))

        # --- Frame Info ---
        frame = controller.GetFrameInfo()
        frame_info = {}
        if hasattr(frame, "stats"):
            frame_info["draws"] = frame.stats.draws
            frame_info["dispatches"] = frame.stats.dispatches
        print("[INFO] Frame info: %s" % json.dumps(frame_info))

        # --- Actions (drawcall tree) ---
        root_actions = controller.GetRootActions()
        structured_file = controller.GetStructuredFile()

        all_actions = flatten_actions(root_actions)
        drawcalls = get_drawcalls(root_actions)
        print("[INFO] Total actions (leaf): %d, drawcalls: %d" % (len(all_actions), len(drawcalls)))

        # Build action list
        action_list = []
        for a in drawcalls[:50]:  # Limit to first 50 for brevity
            entry = {
                "event_id": a.eventId,
                "action_id": a.actionId,
                "flags": str(a.flags),
                "num_indices": a.numIndices,
                "num_instances": a.numInstances if a.numInstances > 0 else 1,
            }
            try:
                entry["name"] = a.GetName(structured_file)
            except Exception:
                entry["name"] = a.customName or ""
            action_list.append(entry)

        # --- Textures ---
        textures = controller.GetTextures()
        print("[INFO] Textures: %d" % len(textures))

        tex_list = []
        for t in textures[:30]:  # Limit
            tex_list.append({
                "resource_id": str(t.resourceId),
                "width": t.width,
                "height": t.height,
                "depth": t.depth,
                "mips": t.mips,
                "array_size": t.arraysize,
                "format": t.format.Name() if hasattr(t.format, "Name") else str(t.format),
                "byte_size": t.byteSize,
                "type": str(t.type),
            })

        # --- Buffers ---
        buffers = controller.GetBuffers()
        print("[INFO] Buffers: %d" % len(buffers))

        buf_list = []
        for b in buffers[:30]:  # Limit
            buf_list.append({
                "resource_id": str(b.resourceId),
                "length": b.length,
            })

        # --- Pipeline State for first drawcall ---
        pipe_info = None
        if drawcalls:
            first_dc = drawcalls[0]
            controller.SetFrameEvent(first_dc.eventId, True)
            pipe = controller.GetPipelineState()

            pipe_info = {
                "event_id": first_dc.eventId,
            }

            # Output targets
            try:
                targets = pipe.GetOutputTargets()
                pipe_info["output_targets"] = []
                for t in targets:
                    try:
                        res_id = t.resource
                    except AttributeError:
                        res_id = getattr(t, "resourceId", None)
                    if res_id:
                        pipe_info["output_targets"].append(str(res_id))
            except Exception as e:
                pipe_info["output_targets_error"] = str(e)

            # Depth target
            try:
                depth = pipe.GetDepthTarget()
                if depth:
                    try:
                        pipe_info["depth_target"] = str(depth.resource)
                    except AttributeError:
                        pipe_info["depth_target"] = str(getattr(depth, "resourceId", ""))
            except Exception as e:
                pipe_info["depth_target_error"] = str(e)

            # Topology
            try:
                topo = pipe.GetPrimitiveTopology()
                pipe_info["topology"] = str(topo)
            except Exception:
                pass

            # Shader reflection
            try:
                ps_refl = pipe.GetShaderReflection(rd.ShaderStage.Fragment)
                if ps_refl:
                    pipe_info["ps_entry_point"] = ps_refl.entryPoint
                    if hasattr(ps_refl, "stats"):
                        pipe_info["ps_alu_instructions"] = ps_refl.stats.aluInstructions
                        pipe_info["ps_tex_instructions"] = ps_refl.stats.texInstructions
            except Exception:
                pass

            try:
                vs_refl = pipe.GetShaderReflection(rd.ShaderStage.Vertex)
                if vs_refl:
                    pipe_info["vs_entry_point"] = vs_refl.entryPoint
            except Exception:
                pass

            print("[INFO] Pipeline state sampled for event %d" % first_dc.eventId)

        # --- Build output ---
        output_data = {
            "rdc_file": rdc_file,
            "api_properties": api_info,
            "frame_info": frame_info,
            "total_actions_leaf": len(all_actions),
            "total_drawcalls": len(drawcalls),
            "total_textures": len(textures),
            "total_buffers": len(buffers),
            "drawcalls_sample": action_list,
            "textures_sample": tex_list,
            "buffers_sample": buf_list,
            "pipeline_state_sample": pipe_info,
        }

        if args.output:
            output_path = os.path.abspath(args.output)
        else:
            from datetime import datetime
            basename = os.path.splitext(os.path.basename(rdc_file))[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, "%s_basic_info_%s.json" % (basename, timestamp))

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
