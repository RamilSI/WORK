// Сборка PDF из набора PNG (по одной странице A4 на файл, с сохранением пропорций).
// swift pdf.swift out.pdf page1.png [page2.png ...]
import AppKit
import Foundation
import CoreGraphics

let a = CommandLine.arguments
guard a.count >= 3 else { print("usage: swift pdf.swift out.pdf img1.png [img2.png ...]"); exit(1) }
let outURL = URL(fileURLWithPath: a[1])

let pageW: CGFloat = 595, pageH: CGFloat = 842   // A4, pt
var media = CGRect(x: 0, y: 0, width: pageW, height: pageH)
guard let ctx = CGContext(outURL as CFURL, mediaBox: &media, nil) else { print("не создан PDF"); exit(1) }

for path in a.dropFirst(2) {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        print("пропуск: \(path)"); continue
    }
    let iw = CGFloat(cg.width), ih = CGFloat(cg.height)
    let m: CGFloat = 24
    let s = min((pageW - 2*m) / iw, (pageH - 2*m) / ih)
    let w = iw * s, h = ih * s
    ctx.beginPDFPage(nil)
    ctx.saveGState()
    ctx.translateBy(x: 0, y: pageH)
    ctx.scaleBy(x: 1, y: -1)
    ctx.draw(cg, in: CGRect(x: (pageW - w)/2, y: (pageH - h)/2, width: w, height: h))
    ctx.restoreGState()
    ctx.endPDFPage()
    print("  страница: \(URL(fileURLWithPath: path).lastPathComponent)")
}
ctx.closePDF()
print("PDF: \(outURL.path)")
