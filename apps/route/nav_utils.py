def split_points(s):
    pts = [
        list(map(float, p.split(",")))
        for p in s.strip("()").split(";")
        if p.strip()
    ]

    if not pts:
        return {"start": None, "end": None, "vias": []}

    start = pts[0]
    end = pts[-1] if len(pts) > 1 else None
    vias = pts[1:-1] if len(pts) > 2 else []

    return {"start": start, "end": end, "vias": vias}