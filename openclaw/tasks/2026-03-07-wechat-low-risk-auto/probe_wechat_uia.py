from __future__ import annotations

import json
import time
from pathlib import Path

from pywinauto import Desktop

OUT = Path(__file__).with_name("probe-output.json")


def main() -> None:
    desktop = Desktop(backend="uia")
    windows = [w for w in desktop.windows() if "微信" in (w.window_text() or "")]
    if not windows:
        windows = [w for w in desktop.windows() if (w.class_name() or "").lower().find("weixin") >= 0]

    payload: dict = {"found": bool(windows), "windows": []}

    for window in windows[:2]:
        try:
            window.set_focus()
        except Exception:
            pass
        time.sleep(0.2)

        children = []
        for ctrl in window.descendants(depth=3):
            try:
                children.append(
                    {
                        "name": ctrl.window_text(),
                        "control_type": ctrl.element_info.control_type,
                        "class_name": ctrl.class_name(),
                        "automation_id": getattr(ctrl.element_info, "automation_id", ""),
                    }
                )
            except Exception:
                continue

        payload["windows"].append(
            {
                "title": window.window_text(),
                "class_name": window.class_name(),
                "child_count": len(children),
                "sample_children": children[:120],
            }
        )

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(OUT))


if __name__ == "__main__":
    main()
