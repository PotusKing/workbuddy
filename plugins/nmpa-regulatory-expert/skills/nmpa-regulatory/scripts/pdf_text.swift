// 用法: swift pdf_text.swift <输入PDF> <输出md> [--keep-footer]
// 用途: 文本型 PDF → Markdown。直接读 PDFKit 文本层，不做 OCR（比渲染识别快一个数量级）。
// 适用: FDA guidance、法规原文等有文本层的 PDF。
// 不适用: 扫描件（文本层为空）。若输出几乎为空，改用 ocr_pdf.swift。
import Foundation
import PDFKit

let args = CommandLine.arguments
guard args.count >= 3 else {
    print("用法: swift pdf_text.swift <输入PDF> <输出md> [--keep-footer]"); exit(1)
}
let inputPath = args[1]
let outputPath = args[2]
let keepFooter = args.count >= 4 && args[3] == "--keep-footer"

guard let pdf = PDFDocument(url: URL(fileURLWithPath: inputPath)) else {
    print("ERROR: cannot open PDF"); exit(1)
}
let total = pdf.pageCount
var out = ""
var emptyPages = 0

// FDA guidance 的常见页眉页脚，纯噪声
let noise: [String] = [
    "contains nonbinding recommendations",
    "contains non-binding recommendations",
    "draft - not for implementation",
    "draft guidance - not for implementation",
    "not for implementation",
]
// 页码行：单独的数字 / "12" / "Page 12" / "- 12 -"
func isPageNumber(_ s: String) -> Bool {
    let t = s.trimmingCharacters(in: .whitespaces)
    if t.isEmpty { return false }
    if t.range(of: #"^(page\s*)?-?\s*\d{1,4}\s*-?$"#, options: .regularExpression) != nil { return true }
    return false
}
func isNoise(_ s: String) -> Bool {
    let t = s.trimmingCharacters(in: .whitespaces).lowercased()
    if t.isEmpty { return true }
    for n in noise where t == n || (t.count < n.count + 24 && t.hasPrefix(n)) { return true }
    return false
}

for i in 0..<total {
    guard let page = pdf.page(at: i), let s = page.string else { emptyPages += 1; continue }
    var lines = s.components(separatedBy: "\n")
    if !keepFooter {
        lines = lines.filter { !isNoise($0) && !isPageNumber($0) }
    }
    let body = lines.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines)
    if body.isEmpty { continue }
    out += "\n<!-- p.\(i + 1) -->\n" + body + "\n"
    if (i + 1) % 20 == 0 { FileHandle.standardError.write("done \(i+1)/\(total)\n".data(using: .utf8)!) }
}

if out.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
    print("WARN: 文本层为空（疑似扫描件，共 \(total) 页，空页 \(emptyPages)）")
    exit(2)
}
try out.write(toFile: outputPath, atomically: true, encoding: .utf8)
print("OK \(total) 页, 空页 \(emptyPages), 输出 \(out.count) 字符")
