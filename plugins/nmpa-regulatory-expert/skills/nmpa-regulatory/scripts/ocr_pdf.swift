// 用法: swift ocr_pdf.swift <输入PDF路径> <输出md路径> [识别语言，默认 zh-Hans]
// 用途: 扫描版 PDF → 文本（macOS 原生 PDFKit 渲染 + Vision OCR，无需安装依赖）
import Foundation
import PDFKit
import Vision

let args = CommandLine.arguments
guard args.count >= 3 else {
    print("用法: swift ocr_pdf.swift <输入PDF> <输出md> [语言，默认zh-Hans]"); exit(1)
}
let inputPath = args[1]
let outputPath = args[2]
let lang = args.count >= 4 ? args[3] : "zh-Hans"

guard let pdf = PDFDocument(url: URL(fileURLWithPath: inputPath)) else {
    print("ERROR: cannot open PDF"); exit(1)
}
let total = pdf.pageCount
var out = "> 来源：\(inputPath)，经 macOS Vision OCR 识别（\(total) 页，语言：\(lang)）。\n"
out += "> 注意：OCR 识别可能存在少量字符错误，条款引用前请留意。\n\n"

for i in 0..<total {
    guard let page = pdf.page(at: i) else { continue }
    let scale: CGFloat = 300.0 / 72.0
    let bounds = page.bounds(for: .mediaBox)
    let size = CGSize(width: bounds.width * scale, height: bounds.height * scale)
    let img = page.thumbnail(of: size, for: .mediaBox)
    guard let tiff = img.tiffRepresentation, let bitmap = NSBitmapImageRep(data: tiff),
          let cgImage = bitmap.cgImage else { continue }
    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = [lang]
    request.usesLanguageCorrection = true
    do { try handler.perform([request]) } catch { print("page \(i+1) OCR error: \(error)") }
    let lines = (request.results ?? []).compactMap { $0 as? VNRecognizedTextObservation }
        .flatMap { $0.topCandidates(1) }.map { $0.string }
    out += "【第 \(i+1) 页】\n" + lines.joined(separator: "\n") + "\n\n"
    if (i+1) % 5 == 0 { print("done \(i+1)/\(total)") }
}
try? out.write(toFile: outputPath, atomically: true, encoding: .utf8)
print("OCR complete → \(outputPath)")
