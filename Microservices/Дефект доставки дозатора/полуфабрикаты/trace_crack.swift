// Трассировка трещины в заданной области: black-hat → порог → компоненты → осевая линия.
// Печатает JSON с точками в координатах оригинала и пишет маску для контроля.
// swift trace_crack.swift photo.jpg x0 y0 w h out.json [mask.png]
import AppKit
import Foundation

let a = CommandLine.arguments
guard a.count >= 7 else {
    print("usage: swift trace_crack.swift photo.jpg x0 y0 w h out.json [mask.png]"); exit(1)
}
let srcPath = a[1]
let X0 = Int(a[2])!, Y0 = Int(a[3])!, W = Int(a[4])!, H = Int(a[5])!
let jsonPath = a[6]
let maskPath = a.count > 7 ? a[7] : ""

guard let src = NSImage(contentsOfFile: srcPath) else { print("нет файла"); exit(1) }

// рисуем только нужную область, 1:1
let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: W, pixelsHigh: H,
                           bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                           colorSpaceName: .deviceRGB, bytesPerRow: W * 4, bitsPerPixel: 32)!
let srcH: CGFloat = src.size.height
let srcW: CGFloat = src.size.width
let dx: CGFloat = CGFloat(-X0)
let dy: CGFloat = -(srcH - CGFloat(Y0) - CGFloat(H))
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
src.draw(in: NSRect(x: dx, y: dy, width: srcW, height: srcH),
         from: .zero, operation: .copy, fraction: 1)
NSGraphicsContext.restoreGraphicsState()

let px = rep.bitmapData!
let rb = rep.bytesPerRow
var gray = [UInt8](repeating: 0, count: W * H)
for y in 0..<H {
    for x in 0..<W {
        let o = y * rb + x * 4
        let r: Double = Double(px[o])
        let g: Double = Double(px[o+1])
        let b: Double = Double(px[o+2])
        let luma: Double = 0.299 * r + 0.587 * g + 0.114 * b
        let v: Int = Int(luma.rounded())
        gray[y * W + x] = UInt8(max(0, min(255, v)))
    }
}

func morph(_ s: [UInt8], _ r: Int, _ isMax: Bool) -> [UInt8] {
    var t = [UInt8](repeating: 0, count: W * H)
    var d = [UInt8](repeating: 0, count: W * H)
    for y in 0..<H {
        for x in 0..<W {
            var v = isMax ? UInt8(0) : UInt8(255)
            for k in max(0, x-r)...min(W-1, x+r) {
                let s2 = s[y*W+k]
                if isMax { if s2 > v { v = s2 } } else { if s2 < v { v = s2 } }
            }
            t[y*W+x] = v
        }
    }
    for y in 0..<H {
        for x in 0..<W {
            var v = isMax ? UInt8(0) : UInt8(255)
            for k in max(0, y-r)...min(H-1, y+r) {
                let s2 = t[k*W+x]
                if isMax { if s2 > v { v = s2 } } else { if s2 < v { v = s2 } }
            }
            d[y*W+x] = v
        }
    }
    return d
}

let R = 6
let closed = morph(morph(gray, R, true), R, false)
var bh = [UInt8](repeating: 0, count: W * H)
for i in 0..<(W*H) { bh[i] = closed[i] > gray[i] ? closed[i] &- gray[i] : 0 }

var vals: [UInt8] = []
for i in 0..<(W*H) where gray[i] > 80 { vals.append(bh[i]) }
vals.sort()
let thr = vals.isEmpty ? 30 : max(20, Int(vals[min(vals.count-1, Int(Double(vals.count) * 0.985))]))
print("порог: \(thr)")

var mask = [Bool](repeating: false, count: W * H)
for i in 0..<(W*H) where gray[i] > 80 && bh[i] >= UInt8(thr) { mask[i] = true }

// компоненты
var label = [Int](repeating: -1, count: W * H)
struct B { var n = 0; var x0 = W; var y0 = H; var x1 = 0; var y1 = 0 }
var blobs: [B] = []
var st = [Int]()
for i in 0..<(W*H) where mask[i] && label[i] == -1 {
    let id = blobs.count
    var b = B()
    st.removeAll(keepingCapacity: true); st.append(i); label[i] = id
    while let c = st.popLast() {
        let x = c % W, y = c / W
        b.n += 1
        if x < b.x0 { b.x0 = x }; if x > b.x1 { b.x1 = x }
        if y < b.y0 { b.y0 = y }; if y > b.y1 { b.y1 = y }
        for (dx, dy) in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1),(1,-1),(-1,1)] {
            let nx = x+dx, ny = y+dy
            if nx < 0 || ny < 0 || nx >= W || ny >= H { continue }
            let ni = ny*W+nx
            if mask[ni] && label[ni] == -1 { label[ni] = id; st.append(ni) }
        }
    }
    blobs.append(b)
}

// берём все значимые компоненты и строим осевую линию по строкам
var keep = Set<Int>()
for (i, b) in blobs.enumerated() where b.n >= 50 { keep.insert(i) }
print("компонент всего: \(blobs.count), значимых: \(keep.count)")

var pts: [(Double, Double)] = []
var y = 0
while y < H {
    var sx = 0.0, cnt = 0.0
    for x in 0..<W {
        let l = label[y*W+x]
        if l >= 0 && keep.contains(l) { sx += Double(x); cnt += 1 }
    }
    if cnt >= 2 { pts.append((sx / cnt, Double(y))) }
    y += 8
}
// сглаживание и прореживание
var smooth: [(Double, Double)] = []
for i in 0..<pts.count {
    let lo = max(0, i-2), hi = min(pts.count-1, i+2)
    var sx = 0.0, sy = 0.0, n = 0.0
    for k in lo...hi { sx += pts[k].0; sy += pts[k].1; n += 1 }
    smooth.append((sx/n, sy/n))
}
var out: [(Int, Int)] = []
for (i, p) in smooth.enumerated() where i % 3 == 0 {
    out.append((Int(p.0.rounded()) + X0, Int(p.1.rounded()) + Y0))
}
print("точек осевой линии: \(out.count)")

let json = "{\n  \"region\": {\"x\": \(X0), \"y\": \(Y0), \"w\": \(W), \"h\": \(H)},\n  \"points\": [" +
    out.map { "{\"x\": \($0.0), \"y\": \($0.1)}" }.joined(separator: ", ") + "]\n}\n"
try! json.write(toFile: jsonPath, atomically: true, encoding: .utf8)
print("JSON: \(jsonPath)")

if !maskPath.isEmpty {
    let mrep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: W, pixelsHigh: H,
                                bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                                colorSpaceName: .deviceRGB, bytesPerRow: W * 4, bitsPerPixel: 32)!
    for yy in 0..<H {
        for xx in 0..<W {
            let o = yy * mrep.bytesPerRow + xx * 4
            let l = label[yy*W+xx]
            let on = l >= 0 && keep.contains(l)
            mrep.bitmapData![o]   = on ? 255 : gray[yy*W+xx]
            mrep.bitmapData![o+1] = on ? 40  : gray[yy*W+xx]
            mrep.bitmapData![o+2] = on ? 40  : gray[yy*W+xx]
            mrep.bitmapData![o+3] = 255
        }
    }
    try? mrep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: maskPath))
    print("маска: \(maskPath)")
}
