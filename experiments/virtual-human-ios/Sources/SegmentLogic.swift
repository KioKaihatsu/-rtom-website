import CoreLocation

extension Segment {
    func position(at minute: Double) -> CLLocationCoordinate2D {
        if wp.count == 1 || mode == "stay" {
            return CLLocationCoordinate2D(latitude: wp[0][0], longitude: wp[0][1])
        }
        let f = max(0, min(1, (minute - Double(s)) / Double(duration)))
        let n = wp.count - 1
        let idx = min(Int(f * Double(n)), n - 1)
        let segF = f * Double(n) - Double(idx)
        let a = wp[idx], b = wp[idx + 1]
        return CLLocationCoordinate2D(
            latitude:  a[0] + (b[0] - a[0]) * segF,
            longitude: a[1] + (b[1] - a[1]) * segF
        )
    }

    /// Progress within this segment in [0, 1]. Useful for the "32% 到着まで" hint.
    func progress(at minute: Double) -> Double {
        max(0, min(1, (minute - Double(s)) / Double(duration)))
    }
}

extension PersonaData {
    func segment(at minute: Double, segments: [Segment]) -> Segment {
        for (i, seg) in segments.enumerated() {
            if Double(seg.e) > minute {
                return Double(seg.s) <= minute ? seg : segments[max(0, i - 1)]
            }
        }
        return segments.last ?? segments[0]
    }

    func position(at minute: Double, segments: [Segment]) -> CLLocationCoordinate2D {
        segment(at: minute, segments: segments).position(at: minute)
    }

    /// Earned and spent so far today, with linear accumulation within the
    /// current segment.
    func cumulative(at minute: Double, segments: [Segment]) -> (earned: Int, spent: Int) {
        var e = 0.0
        var sp = 0.0
        for seg in segments {
            if Double(seg.e) <= minute {
                e += Double(seg.wage)
                sp += Double(seg.cost)
            } else if Double(seg.s) <= minute {
                let f = (minute - Double(seg.s)) / Double(seg.duration)
                e += Double(seg.wage) * f
                sp += Double(seg.cost) * f
            }
        }
        return (Int(e.rounded()), Int(sp.rounded()))
    }

    /// 30-minute trailing positions sampled every 2 minutes.
    func trail(endingAt minute: Double, segments: [Segment]) -> [CLLocationCoordinate2D] {
        let lookback = 30
        let step = 2
        var out: [CLLocationCoordinate2D] = []
        let start = max(0, Int(minute) - lookback)
        var t = start
        while Double(t) <= minute {
            out.append(position(at: Double(t), segments: segments))
            t += step
        }
        return out
    }
}
