// Поиск тёмных тонких линий (трещин/щелей) внутри светлого пластика: black-hat + компоненты.
// Запуск:  swift crack_detect.swift <фото.jpg> [out_overlay.png]
import AppKit
import Foundation

let args = CommandLine.arguments
guard args.count > 1 else { print("usage: swift crack_detect.swift photo.jpg [overlay.png]"); exit(1) }
let srcPath = args[1]
let overlayPath = args.count > 2 ? args[2] : ""

guard let src = NSImage(contentsOfFile: srcPath) else { print("нет файла"); exit(1) }

let DW = 1536, DH = 2048                    // рабочее разрешение (фактор 2 к оригиналу)
let scale = 2.0

let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: DW, pixelsHigh: DH,
                           bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                           colorSpaceName: .deviceRGB, bytesPerRow: DW * 4, bitsPerPixel: 32)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
NSColor.white.setFill()
NSRect(x: 0, y: 0, width: DW, height: DH).fill()
src.draw(in: NSRect(x: 0, y: 0, width: DW, height: DH), from: .zero, operation: .sourceOver, fraction: 1)
NSGraphicsContext.restoreGraphicsState()

let px = rep.bitmapData!
let rowBytes = rep.bytesPerRow

var gray = [UInt8](repeating: 0, count: DW * DH)
for y in 0..<DH {
    for x in 0..<DW {
        let o = y * rowBytes + x * 4
        let r = Double(px[o]), g = Double(px[o+1]), b = Double(px[o+2])
        gray[y * DW + x] = UInt8(max(0, min(255, 0.299*r + 0.587*g + 0.114*b)))
    }
}

// --- морфология (квадрат 9x9, разделяемая) ---
func morph(_ src: [UInt8], _ r: Int, _ isMax: Bool) -> [UInt8] {
    var tmp = [UInt8](repeating: 0, count: DW * DH)
    var dst = [UInt8](repeating: 0, count: DW * DH)
    for y in 0..<DH {
        for x in 0..<DW {
            var v = isMax ? UInt8(0) : UInt8(255)
            let lo = max(0, x - r), hi = min(DW - 1, x + r)
            for k in lo...hi {
                let s = src[y * DW + k]
                if isMax { if s > v { v = s } } else { if s < v { v = s } }
            }
            tmp[y * DW + x] = v
        }
    }
    for y in 0..<DH {
        let lo = max(0, y - r), hi = min(DH - 1, y + r)
        for x in 0..<DW {
            var v = isMax ? UInt8(0) : UInt8(255)
            for k in lo...hi {
                let s = tmp[k * DW + x]
                if isMax { if s > v { v = s } } else { if s < v { v = s } }
            }
            dst[y * DW + x] = v
        }
    }
    return dst
}

let R = 4
let dil = morph(gray, R, true)
let clo = morph(dil, R, false)

// black-hat: насколько пиксель темнее локального окружения
var bh = [UInt8](repeating: 0, count: DW * DH)
for i in 0..<(DW * DH) {
    bh[i] = clo[i] > gray[i] ? clo[i] &- gray[i] : 0
}

// статистика по светлым участкам (пластик)
var vals: [UInt8] = []
vals.reserveCapacity(DW * DH / 4)
for i in 0..<(DW * DH) where gray[i] > 85 { vals.append(bh[i]) }
vals.sort()
let p995 = vals.isEmpty ? 40 : Int(vals[Int(Double(vals.count) * 0.995)])
let thr = UInt8(max(18, min(90, p995)))
print("порог black-hat: \(thr) (99.5-й перцентиль светлых участков)")

var mask = [Bool](repeating: false, count: DW * DH)
for i in 0..<(DW * DH) {
    if gray[i] > 85 && bh[i] >= thr { mask[i] = true }
}

// --- компоненты связности ---
var label = [Int](repeating: -1, count: DW * DH)
struct Blob { var n = 0; var x0 = 0; var y0 = 0; var x1 = 0; var y1 = 0; var sum = 0.0; var maxv = 0 }
var blobs: [Blob] = []
var stack = [Int]()
for i in 0..<(DW * DH) where mask[i] && label[i] == -1 {
    let id = blobs.count
    var b = Blob(x0: DW, y0: DH, x1: 0, y1: 0)
    stack.removeAll(keepingCapacity: true)
    stack.append(i)
    label[i] = id
    while let cur = stack.popLast() {
        let x = cur % DW, y = cur / DW
        b.n += 1
        b.sum += Double(bh[cur])
        if bh[cur] > b.maxv { b.maxv = Int(bh[cur]) }
        if x < b.x0 { b.x0 = x }; if x > b.x1 { b.x1 = x }
        if y < b.y0 { b.y0 = y }; if y > b.y1 { b.y1 = y }
        for (dx, dy) in [(1,0),(-1,0),(0,1),(0,-1)] {
            let nx = x + dx, ny = y + dy
            if nx < 0 || ny < 0 || nx >= DW || ny >= DH { continue }
            let ni = ny * DW + nx
            if mask[ni] && label[ni] == -1 { label[ni] = id; stack.append(ni) }
        }
    }
    blobs.append(b)
}

struct Cand { var score: Double; var cx: Int; var cy: Int; var w: Int; var h: Int; var n: Int }
var cands: [Cand] = []
for b in blobs {
    let w = b.x1 - b.x0 + 1, h = b.y1 - b.y0 + 1
    let elong = Double(max(w, h)) / Double(max(1, min(w, h)))
    let dens = Double(b.n) / Double(w * h)
    guard b.n >= 40, b.n <= 6000, elong >= 1.8, dens < 0.65 else { continue }
    let score = (b.sum / Double(b.n)) * sqrt(Double(b.n)) * min(elong, 8.0)
    cands.append(Cand(score: score,
                      cx: Int(Double(b.x0 + b.x1) / 2 * scale),
                      cy: Int(Double(b.y0 + b.y1) / 2 * scale),
                      w: Int(Double(w) * scale), h: Int(Double(h) * scale), n: b.n))
}
cands.sort { $0.score > $1.score }
print("\nкандидаты (координаты центра в пикселях оригинала 3072x4096):")
for (i, c) in cands.prefix(10).enumerated() {
    print(String(format: "%2d) x=%4d y=%4d  %4dx%-4d px  score=%7.1f",
                 i + 1, c.cx, c.cy, c.w, c.h, c.score))
}

if !overlayPath.isEmpty, let big = NSImage(contentsOfFile: srcPath) {
    let W = 1536, H = 2048
    let orep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: W, pixelsHigh: H,
                                bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                                colorSpaceName: .deviceRGB, bytesPerRow: W * 4, bitsPerPixel: 32)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: orep)
    big.draw(in: NSRect(x: 0, y: 0, width: W, height: H), from: .zero, operation: .copy, fraction: 1)
    for (i, c) in cands.prefix(10).enumerated() {
        let x = Double(c.cx) / 2, y = Double(c.cy) / 2
        let w = Double(c.w) / 2, h = Double(c.h) / 2
        NSColor(calibratedRed: 1, green: 0.1, blue: 0.1, alpha: 0.9).setStroke()
        let r = NSRect(x: x - w/2 - 6, y: Double(H) - y - h/2 - 6, width: w + 12, height: h + 12)
        NSBezierPath(rect: r).stroke()
        let t = "\(i+1)" as NSString
        t.draw(at: NSPoint(x: r.minX + 2, y: r.maxY - 16),
               withAttributes: [.font: NSFont.boldSystemFont(ofSize: 16),
                                .foregroundColor: NSColor.red])
    }
    NSGraphicsContext.restoreGraphicsState()
    try? orep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: overlayPath))
    print("\nоверлей: \(overlayPath)")
}
