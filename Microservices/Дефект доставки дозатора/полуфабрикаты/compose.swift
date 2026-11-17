// Сборка готовых кадров: общий вид с выноской, макро-фрагмент, кадры для ролика.
// swift compose.swift photo.jpg crack_points.json outdir
import AppKit
import Foundation

let a = CommandLine.arguments
guard a.count >= 4 else { print("usage: swift compose.swift photo.jpg crack_points.json outdir"); exit(1) }
let photoPath = a[1]
let jsonPath = a[2]
let outDir = URL(fileURLWithPath: a[3])
try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)

guard let photo = NSImage(contentsOfFile: photoPath) else { print("нет фото"); exit(1) }
let IW = 3072.0, IH = 4096.0

// --- точки трассировки ---
struct Pt { var x: Double; var y: Double }
var pts: [Pt] = []
if let d = try? Data(contentsOf: URL(fileURLWithPath: jsonPath)),
   let o = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
   let arr = o["points"] as? [[String: Any]] {
    pts = arr.compactMap { p in
        guard let x = p["x"] as? Double ?? (p["x"] as? Int).map(Double.init),
              let y = p["y"] as? Double ?? (p["y"] as? Int).map(Double.init) else { return nil }
        return Pt(x: x, y: y)
    }
}
if pts.isEmpty { pts = [Pt(x: 2865, y: 1816), Pt(x: 2842, y: 2317)] }

// область ядра (обводка) и область макро
let CORE = (x: 2780.0, y: 1780.0, w: 200.0, h: 590.0)
let MACRO = (x: 2680.0, y: 1690.0, w: 392.0, h: 523.0)

let NAVY = NSColor(calibratedRed: 0.106, green: 0.212, blue: 0.365, alpha: 1)
let RED = NSColor(calibratedRed: 0.93, green: 0.11, blue: 0.11, alpha: 1)

func makeCanvas(_ w: Int, _ h: Int) -> (NSBitmapImageRep, NSGraphicsContext) {
    let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: w, pixelsHigh: h,
                               bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                               colorSpaceName: .deviceRGB, bytesPerRow: w * 4, bitsPerPixel: 32)!
    let ctx = NSGraphicsContext(bitmapImageRep: rep)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = ctx
    return (rep, ctx)
}
func save(_ rep: NSBitmapImageRep, _ name: String) {
    NSGraphicsContext.restoreGraphicsState()
    let url = outDir.appendingPathComponent(name)
    try? rep.representation(using: .png, properties: [:])!.write(to: url)
    print("  " + url.lastPathComponent)
}
func text(_ s: String, x: CGFloat, top: CGFloat, size: CGFloat, bold: Bool = false,
          color: NSColor = .black, H: CGFloat) {
    let f = bold ? NSFont.boldSystemFont(ofSize: size) : NSFont.systemFont(ofSize: size)
    (s as NSString).draw(at: NSPoint(x: x, y: H - top - size * 1.3),
                         withAttributes: [.font: f, .foregroundColor: color])
}

// ------------------------------------------------------------------
// 1. Общий вид с выноской (1600 px по ширине)
// ------------------------------------------------------------------
do {
    let W = 1600, H = Int(1600.0 * IH / IW)
    let (rep, _) = makeCanvas(W, H)
    let k = CGFloat(W) / CGFloat(IW)
    let hh = CGFloat(H)
    photo.draw(in: NSRect(x: 0, y: 0, width: CGFloat(W), height: hh),
               from: .zero, operation: .copy, fraction: 1)

    // затемнение неинформативной части под врезку
    NSColor(calibratedWhite: 1, alpha: 0.82).setFill()
    NSRect(x: 0, y: hh - 1180, width: 660, height: 1180).fill()

    // обводка ядра
    RED.setStroke()
    let core = NSRect(x: CGFloat(CORE.x) * k, y: hh - CGFloat(CORE.y + CORE.h) * k,
                      width: CGFloat(CORE.w) * k, height: CGFloat(CORE.h) * k)
    let box = NSBezierPath(roundedRect: core.insetBy(dx: -6, dy: -6), xRadius: 10, yRadius: 10)
    box.lineWidth = 4
    box.stroke()

    // линия трассировки
    let trace = NSBezierPath()
    for (i, p) in pts.enumerated() {
        let q = NSPoint(x: CGFloat(p.x) * k, y: hh - CGFloat(p.y) * k)
        i == 0 ? trace.move(to: q) : trace.line(to: q)
    }
    trace.lineWidth = 3
    RED.setStroke()
    trace.stroke()

    // врезка
    let insW: CGFloat = 600
    let insH = insW * CGFloat(MACRO.h / MACRO.w) * 0.98
    let ins = NSRect(x: 30, y: hh - 30 - insH, width: insW, height: insH)
    photo.draw(in: ins, from: NSRect(x: CGFloat(MACRO.x), y: CGFloat(IH) - CGFloat(MACRO.y + MACRO.h),
                                     width: CGFloat(MACRO.w), height: CGFloat(MACRO.h)),
               operation: .copy, fraction: 1)
    // повтор трассировки внутри врезки
    let mk = insW / CGFloat(MACRO.w)
    let trace2 = NSBezierPath()
    for (i, p) in pts.enumerated() {
        let q = NSPoint(x: ins.minX + CGFloat(p.x - MACRO.x) * mk,
                        y: ins.maxY - CGFloat(p.y - MACRO.y) * mk)
        i == 0 ? trace2.move(to: q) : trace2.line(to: q)
    }
    trace2.lineWidth = 2.5
    RED.setStroke()
    trace2.stroke()

    NAVY.setStroke()
    let frame = NSBezierPath(rect: ins)
    frame.lineWidth = 4
    frame.stroke()

    // выноска
    let leader = NSBezierPath()
    leader.move(to: NSPoint(x: core.minX, y: core.maxY))
    leader.line(to: NSPoint(x: ins.maxX, y: ins.maxY - 40))
    leader.lineWidth = 2
    NSColor(calibratedRed: 0.93, green: 0.11, blue: 0.11, alpha: 0.85).setStroke()
    leader.stroke()

    let capTop = 30 + insH + 12
    text("Увеличено ×1,5 · фрагмент 392×523 px", x: 36, top: capTop, size: 19, color: .darkGray, H: hh)
    text("Трещина и щель по краю верхней крышки", x: 36, top: capTop + 30, size: 24,
         bold: true, color: RED, H: hh)
    text("линия обведена по фактическому изображению", x: 36, top: capTop + 66, size: 17,
         color: .darkGray, H: hh)

    // шапка
    NSColor(calibratedRed: 0.106, green: 0.212, blue: 0.365, alpha: 0.88).setFill()
    NSRect(x: 0, y: 0, width: CGFloat(W), height: 74).fill()
    text("Дозатор · ТН № 025510684 · трещина по краю крышки · фото 1794635603887",
         x: 22, top: 22, size: 22, bold: true, color: .white, H: hh)
    save(rep, "01_трещина_на_кадре_с_выноской.png")
}

// ------------------------------------------------------------------
// 2. Макро ×4 (для печати) и кадр ×2,75 (для ролика)
// ------------------------------------------------------------------
func macroCanvas(_ W: Int, _ H: Int, _ name: String, caption: String, drawTrace: Bool) {
    let (rep, _) = makeCanvas(W, H)
    let hh = CGFloat(H)
    let k = CGFloat(W) / CGFloat(MACRO.w)
    photo.draw(in: NSRect(x: 0, y: 0, width: CGFloat(W), height: hh),
               from: NSRect(x: CGFloat(MACRO.x), y: CGFloat(IH) - CGFloat(MACRO.y + MACRO.h),
                            width: CGFloat(MACRO.w), height: CGFloat(MACRO.h)),
               operation: .copy, fraction: 1)
    if drawTrace {
        let t = NSBezierPath()
        for (i, p) in pts.enumerated() {
            let q = NSPoint(x: CGFloat(p.x - MACRO.x) * k,
                            y: hh - CGFloat(p.y - MACRO.y) * k)
            i == 0 ? t.move(to: q) : t.line(to: q)
        }
        t.lineWidth = max(2, CGFloat(W) / 380)
        RED.setStroke()
        t.stroke()
        // уголки-засечки
        let c: CGFloat = CGFloat(W) * 0.06
        let m: CGFloat = CGFloat(W) * 0.02
        let corners: [(CGFloat, CGFloat, CGFloat, CGFloat)] = [
            (m, m, 1, 1), (CGFloat(W) - m, m, -1, 1),
            (m, hh - m, 1, -1), (CGFloat(W) - m, hh - m, -1, -1)
        ]
        NAVY.setStroke()
        for (cx, cy, sx, sy) in corners {
            let p = NSBezierPath()
            p.move(to: NSPoint(x: cx + c * sx, y: cy))
            p.line(to: NSPoint(x: cx, y: cy))
            p.line(to: NSPoint(x: cx, y: cy + c * sy))
            p.lineWidth = max(3, CGFloat(W) / 300)
            p.stroke()
        }
    }
    // подпись снизу
    NSColor(calibratedWhite: 1, alpha: 0.85).setFill()
    NSRect(x: 0, y: 0, width: CGFloat(W), height: CGFloat(W) * 0.115).fill()
    text(caption, x: CGFloat(W) * 0.03, top: hh - CGFloat(W) * 0.098,
         size: CGFloat(W) * 0.032, bold: true, color: NAVY, H: hh)
    text("Разметка выполнена по фактическому изображению, без дорисовки деталей",
         x: CGFloat(W) * 0.03, top: hh - CGFloat(W) * 0.058,
         size: CGFloat(W) * 0.024, color: .darkGray, H: hh)
    save(rep, name)
}

macroCanvas(1568, Int(1568.0 * MACRO.h / MACRO.w), "02_макро_трещина_x4.png",
            caption: "×4 · фрагмент 392×523 px · линия трещины обведена", drawTrace: true)

macroCanvas(1080, 1440, "03_кадр_макро_1080.png",
            caption: "×2,75 · трещина по краю крышки", drawTrace: true)

// ------------------------------------------------------------------
// 3. Кадр 1080×1440 с выноской (первый план ролика)
// ------------------------------------------------------------------
do {
    let W = 1080, H = 1440
    let (rep, _) = makeCanvas(W, H)
    let hh = CGFloat(H)
    let k = CGFloat(W) / CGFloat(IW)
    photo.draw(in: NSRect(x: 0, y: 0, width: CGFloat(W), height: hh),
               from: .zero, operation: .copy, fraction: 1)

    let core = NSRect(x: CGFloat(CORE.x) * k, y: hh - CGFloat(CORE.y + CORE.h) * k,
                      width: CGFloat(CORE.w) * k, height: CGFloat(CORE.h) * k)
    RED.setStroke()
    let b = NSBezierPath(roundedRect: core.insetBy(dx: -4, dy: -4), xRadius: 8, yRadius: 8)
    b.lineWidth = 3
    b.stroke()

    // врезка справа-снизу
    let insW: CGFloat = 300
    let insH = insW * CGFloat(MACRO.h / MACRO.w)
    let ins = NSRect(x: CGFloat(W) - insW - 28, y: 120, width: insW, height: insH)
    photo.draw(in: ins, from: NSRect(x: CGFloat(MACRO.x), y: CGFloat(IH) - CGFloat(MACRO.y + MACRO.h),
                                     width: CGFloat(MACRO.w), height: CGFloat(MACRO.h)),
               operation: .copy, fraction: 1)
    let mk = insW / CGFloat(MACRO.w)
    let t2 = NSBezierPath()
    for (i, p) in pts.enumerated() {
        let q = NSPoint(x: ins.minX + CGFloat(p.x - MACRO.x) * mk,
                        y: ins.maxY - CGFloat(p.y - MACRO.y) * mk)
        i == 0 ? t2.move(to: q) : t2.line(to: q)
    }
    t2.lineWidth = 2
    RED.setStroke(); t2.stroke()
    NAVY.setStroke()
    let fr = NSBezierPath(rect: ins); fr.lineWidth = 3; fr.stroke()

    let leader = NSBezierPath()
    leader.move(to: NSPoint(x: core.maxX, y: core.minY))
    leader.line(to: NSPoint(x: ins.maxX, y: ins.maxY))
    leader.lineWidth = 2
    RED.setStroke(); leader.stroke()

    text("Трещина по краю крышки", x: 28, top: 96, size: 30, bold: true, color: .white, H: hh)
    text("увеличено ×2,75 →", x: 28, top: 136, size: 20, color: NSColor(calibratedWhite: 0.9, alpha: 1), H: hh)
    save(rep, "04_кадр_с_выноской_1080.png")
}

print("готово")
