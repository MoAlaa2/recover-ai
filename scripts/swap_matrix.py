"""Fabric swap test matrix: 3 rooms x 2 fabrics (plain + patterned).

Runs swap() end to end and saves results under results/swap_matrix/.
Prints a score table. Needs MODEL_API_KEY in .env (spends real API calls).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.swap import swap  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CASES = [
    ("sofa", "/tmp/room_sofa.jpg", "sofa", "FA-NL-02"),
    ("sofa", "/tmp/room_sofa.jpg", "sofa", "FA-NL-09"),
    ("chair", "/tmp/room_chair.jpg", "armchair", "FA-VL-01"),
    ("chair", "/tmp/room_chair.jpg", "armchair", "FA-VL-11"),
    ("curtains", "/tmp/room_curtains.jpg", "curtains", "FA-LA-01"),
    ("curtains", "/tmp/room_curtains.jpg", "curtains", "FA-LA-12"),
]


def main():
    out_dir = os.path.join(BASE, "results", "swap_matrix")
    os.makedirs(out_dir, exist_ok=True)
    print("%-9s %-8s scores attempts result" % ("room", "fabric"))
    for name, room, target, code in CASES:
        case_dir = os.path.join(out_dir, "%s_%s" % (name, code))
        os.makedirs(case_dir, exist_ok=True)
        try:
            res = swap(room, code, target, out_dir=case_dir)
            print("%-9s %-8s %s %d %s" % (
                name, code, res["scores"], res["attempts"],
                res["result_url"]))
        except Exception as exc:  # noqa: BLE001 - report and continue
            print("%-9s %-8s FAILED: %s" % (name, code, exc))


if __name__ == "__main__":
    main()
