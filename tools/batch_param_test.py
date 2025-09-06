# tools/batch_param_test.py
import asyncio
import itertools
import os
import re
import sys

SCRIPT_PATH = "module/sub/c_rosvot_to_midi.py"

# 試すパラメータのリスト
MIN_NOTE_S_LIST = [0.07, 0.05, 0.04, 0.03, 0.02, 0.015, 0.01]
ROSVOT_THR_LIST = [0.85, 0.8, 0.75, 0.7, 0.68, 0.65, 0.6, 0.55, 0.5]
MERGE_GAP_S_LIST = [0.02, 0.015, 0.01, 0.005, 0.003, 0.001]
BRIDGE_GAP_MS_LIST = [40, 20, 10, 5, 3, 2, 1, 0]

async def run_case(min_note_s, rosvot_thr, merge_gap_s, bridge_gap_ms):
    env = os.environ.copy()
    env["MIN_NOTE_S"] = str(min_note_s)
    env["ROSVOT_THR"] = str(rosvot_thr)
    env["MERGE_GAP_S"] = str(merge_gap_s)
    env["BRIDGE_GAP_MS"] = str(bridge_gap_ms)

    proc = await asyncio.create_subprocess_exec(
        sys.executable, SCRIPT_PATH,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env
    )
    stdout, stderr = await proc.communicate()
    output = stdout.decode(errors="ignore") + stderr.decode(errors="ignore")

    # 🎵 音符情報: 以降を抽出
    match = re.search(r"(🎵 音符情報:[\s\S]+?)(?=\n\S|$)", output)
    note_info = match.group(1).strip() if match else "(音符情報なし)"

    return {
        "params": (min_note_s, rosvot_thr, merge_gap_s, bridge_gap_ms),
        "note_info": note_info
    }

async def main():
    all_params = list(itertools.product(
        MIN_NOTE_S_LIST, ROSVOT_THR_LIST, MERGE_GAP_S_LIST, BRIDGE_GAP_MS_LIST
    ))
    BATCH_SIZE = 5
    for i in range(0, len(all_params), BATCH_SIZE):
        batch_params = all_params[i:i+BATCH_SIZE]
        tasks = [
            run_case(min_note_s, rosvot_thr, merge_gap_s, bridge_gap_ms)
            for min_note_s, rosvot_thr, merge_gap_s, bridge_gap_ms in batch_params
        ]
        results = await asyncio.gather(*tasks)
        for res in results:
            min_note_s, rosvot_thr, merge_gap_s, bridge_gap_ms = res["params"]
            print("="*80)
            print(f"MIN_NOTE_S={min_note_s}, ROSVOT_THR={rosvot_thr}, MERGE_GAP_S={merge_gap_s}, BRIDGE_GAP_MS={bridge_gap_ms}")
            print(res["note_info"])
            print()

if __name__ == "__main__":
    asyncio.run(main())
