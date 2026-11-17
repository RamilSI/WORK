// Сборка листа визуализации дефекта (без сторонних зависимостей, только AppKit).
// Запуск:  swift сборка_листа.swift
import AppKit
import Foundation

let base = URL(fileURLWithPath: CommandLine.arguments[0]).deletingLastPathComponent()
func path(_ n: String) -> String { base.appendingPathComponent(n).path }

func load(_ n: String) -> NSImage {
    guard let im = NSImage(contentsOfFile: path(n)) else {
        FileHandle.standardError.write(("Нет файла: " + n + "\n").data(using: .utf8)!)
        exit(1)
    }
    return im
}

let original = load("05_обзор_1400.png")          // полный кадр
let filmOff  = load("03_снятие_плёнки_подавление_блика.png")
let edges    = load("02_краевая_карта.png")
let macro    = load("04_зона_кандидат_верх_справа.png")

let W: CGFloat = 2400
let M: CGFloat = 60
let headerH: CGFloat = 210
let panelW: CGFloat = (W - M * 4) / 3
let panelH: CGFloat = panelW * 4096.0 / 3072.0
let capH: CGFloat = 86
let macroW: CGFloat = 1160
let macroH: CGFloat = macroW
let H: CGFloat = headerH + panelH + capH + 70 + macroH + M

let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(W), pixelsHigh: Int(H),
                           bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                           colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)

// фон
NSColor(calibratedWhite: 1.0, alpha: 1).setFill()
NSRect(x: 0, y: 0, width: W, height: H).fill()

func rect(top: CGFloat, height h: CGFloat, x: CGFloat, width w: CGFloat) -> NSRect {
    NSRect(x: x, y: H - top - h, width: w, height: h)
}

func text(_ s: String, top: CGFloat, x: CGFloat, size: CGFloat, bold: Bool = false,
          color: NSColor = NSColor(calibratedWhite: 0.15, alpha: 1)) {
    let font = bold ? NSFont.boldSystemFont(ofSize: size) : NSFont.systemFont(ofSize: size)
    let attrs: [NSAttributedString.Key: Any] = [.font: font, .foregroundColor: color]
    (s as NSString).draw(at: NSPoint(x: x, y: H - top - size * 1.25), withAttributes: attrs)
}

func wrap(_ s: String, top: CGFloat, x: CGFloat, width: CGFloat, size: CGFloat, line: CGFloat) -> CGFloat {
    var y = top
    for raw in s.components(separatedBy: "\n") {
        var cur = ""
        for word in raw.components(separatedBy: " ") {
            let t = cur.isEmpty ? word : cur + " " + word
            let w = (t as NSString).size(withAttributes: [.font: NSFont.systemFont(ofSize: size)]).width
            if w > width && !cur.isEmpty {
                text(cur, top: y, x: x, size: size)
                y += line
                cur = word
            } else { cur = t }
        }
        if !cur.isEmpty { text(cur, top: y, x: x, size: size); y += line }
        y += 6
    }
    return y
}

// шапка
NSColor(calibratedRed: 0.106, green: 0.212, blue: 0.365, alpha: 1).setFill()
rect(top: 0, height: headerH, x: 0, width: W).fill()
text("ДЕФЕКТ ДОСТАВКИ ДОЗАТОРА · ВИЗУАЛЬНЫЙ РАЗБОР ТРЕЩИНЫ", top: 46, x: M, size: 46, bold: true,
     color: .white)
text("ТН № 025510684 · склад Самара, 12.11.2026 · фото 1794635603887.jpg (3072×4096)",
     top: 112, x: M, size: 26, color: NSColor(calibratedWhite: 0.82, alpha: 1))
text("ООО «ТОНАЛЬ» · техническое приложение к претензии", top: 154, x: M, size: 24,
     color: NSColor(calibratedWhite: 0.7, alpha: 1))

// три панели
let panels: [(NSImage, String, String)] = [
    (original, "1. Оригинал", "Фото как есть: корпус в стрейч-плёнке, блики плёнки маскируют рельеф"),
    (filmOff,  "2. Виртуальное снятие плёнки", "Блик и отражения подавлены, рельеф корпуса проявлен"),
    (edges,    "3. Краевая карта", "Линии излома и царапины выделены как контуры")
]

var px = M
for (img, title, sub) in panels {
    NSColor(calibratedWhite: 0.93, alpha: 1).setFill()
    rect(top: headerH + 30, height: panelH, x: px, width: panelW).fill()
    img.draw(in: rect(top: headerH + 30, height: panelH, x: px, width: panelW),
             from: .zero, operation: .copy, fraction: 1)
    NSColor(calibratedWhite: 0.75, alpha: 1).setStroke()
    let r = rect(top: headerH + 30, height: panelH, x: px, width: panelW)
    NSBezierPath(rect: r.insetBy(dx: 0.5, dy: 0.5)).stroke()
    text(title, top: headerH + 30 + panelH + 14, x: px, size: 26, bold: true)
    _ = wrap(sub, top: headerH + 30 + panelH + 48, x: px, width: panelW, size: 18, line: 22)
    px += panelW + M
}

// макро-врезка
let macroTop = headerH + 30 + panelH + capH + 60
macro.draw(in: rect(top: macroTop, height: macroH, x: M, width: macroW),
           from: .zero, operation: .copy, fraction: 1)
NSColor(calibratedRed: 0.106, green: 0.212, blue: 0.365, alpha: 1).setStroke()
NSBezierPath(rect: rect(top: macroTop, height: macroH, x: M, width: macroW)).stroke()
text("4. Зона контроля в увеличении", top: macroTop + 14, x: M + 24, size: 28, bold: true,
     color: NSColor(calibratedRed: 1, green: 0.42, blue: 0.42, alpha: 1))

let tx = M + macroW + 60
let tw = W - tx - M
_ = wrap("""
Что сделано
• Плёнка «снята» программно: гомоморфное подавление блика убирает зеркальные отражения стрейч-плёнки, при этом геометрия и цвет корпуса не меняются.
• Рельеф усилен (локальный контраст + unsharp): линия излома, побеление кромок пластика (stress whitening) и микросколы читаются отчётливее.
• Краевая карта показывает те же линии как контуры — удобно для сверки, что это не блик.

Что искать на кадре
• Трещина верхней пластиковой крышки — идёт по линии гиба крышки.
• Царапины и трещина боковой пластиковой панели.
• Щель и выпуклость пластика по краю аппарата (фиксировались ещё сквозь плёнку при приходе).

Как получить точную трассировку
1. Открыть «Открыть_визуализатор.command».
2. Включить слой «Снятие плёнки», навести линзу ×4–×6 на линию трещины.
3. Поставить 2–4 метки: начало → излом → конец.
4. «Скачать PNG-аннотацию» — лист с обводкой и макро-врезкой ×4.

Важно: это визуализация для претензии, а не измерение. Контуры трещины не дорисовываются — разметка ставится по фактическому изображению.
""", top: macroTop + 8, x: tx, width: tw, size: 21, line: 27)

NSGraphicsContext.restoreGraphicsState()

let out = base.appendingPathComponent("06_лист_дефекта.png")
try! rep.representation(using: .png, properties: [:])!.write(to: out)
print("Готово: " + out.path)
