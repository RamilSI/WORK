import Quartz

windows = Quartz.CGWindowListCopyWindowInfo(
    Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID
)
for w in windows:
    owner = w.get("kCGWindowOwnerName") or ""
    low = owner.lower()
    if "assist" in low or "Ассист" in owner:
        b = w.get("kCGWindowBounds") or {}
        print(
            w.get("kCGWindowNumber"),
            owner,
            repr(w.get("kCGWindowName")),
            "layer",
            w.get("kCGWindowLayer"),
            dict(b),
        )
