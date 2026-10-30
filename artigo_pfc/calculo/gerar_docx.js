// Gera o artigo em .docx (A4, IEEE duas colunas) e a versao em texto, a partir de conteudo.js.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType,
  AlignmentType, SectionType, TabStopType, Tab, BorderStyle, ShadingType, VerticalAlign,
  Math: OMath, MathRun, MathFraction, MathSubScript, MathSuperScript, MathSubSuperScript,
  MathIntegral, MathSum, MathRoundBrackets,
} = require("docx");

const DIR = __dirname;
const OUT = process.argv[2] || path.join(DIR, "artigo.docx");
const OUT_TXT = process.argv[3] || path.join(DIR, "artigo.txt");
const C = require("./conteudo.js");
const FONT = "Times New Roman";
const COLW = 5040;                       // largura da coluna, twips (3,5 in = 88,9 mm)

// ------------------------------------------------------------- marcacao inline
function parseInline(s, base = {}) {
  const out = [];
  let i = 0, buf = "";
  const flush = () => { if (buf) { out.push({ ...base, text: buf }); buf = ""; } };
  while (i < s.length) {
    if (s.startsWith("**", i)) {
      const j = s.indexOf("**", i + 2); flush();
      out.push(...parseInline(s.slice(i + 2, j), { ...base, bold: true })); i = j + 2; continue;
    }
    const c = s[i];
    if (c === "*" || c === "$") {
      const j = s.indexOf(c, i + 1); flush();
      out.push(...parseInline(s.slice(i + 1, j), { ...base, italics: c === "$" ? true : !base.italics }));
      i = j + 1; continue;
    }
    if ((c === "_" || c === "^") && s[i + 1] === "{") {
      let depth = 0, j = i + 1;
      for (; j < s.length; j++) { if (s[j] === "{") depth++; else if (s[j] === "}") { depth--; if (depth === 0) break; } }
      flush();
      const k = c === "_" ? "subScript" : "superScript";
      out.push(...parseInline(s.slice(i + 2, j), { ...base, [k]: true, italics: false }));
      i = j + 1; continue;
    }
    buf += c; i++;
  }
  flush();
  return out;
}

function runs(s, o = {}) {
  return parseInline(s).map(r => new TextRun({
    text: r.text, font: FONT, size: o.size || 20,
    italics: o.italics ? !r.italics : !!r.italics,
    bold: !!(r.bold || o.bold), subScript: !!r.subScript, superScript: !!r.superScript,
    smallCaps: !!o.smallCaps,
  }));
}

const SUP = { "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "−": "⁻", "+": "⁺" };
function plain(s) {
  const rs = parseInline(s);
  let out = "", sup = "";
  const flushSup = () => {
    if (!sup) return;
    if ([...sup].every(ch => SUP[ch])) out += [...sup].map(ch => SUP[ch]).join("");
    else if (/^[0-9,]+$/.test(sup) || sup.length === 1) out += "^" + sup;
    else out += "^(" + sup + ")";
    sup = "";
  };
  for (const r of rs) { if (r.superScript) sup += r.text; else { flushSup(); out += r.text; } }
  flushSup();
  return out;
}

// ------------------------------------------------------------- equacoes (OMML)
const r = t => new MathRun(t);
const sb = (b, s) => new MathSubScript({ children: b, subScript: s });
const sp = (b, s) => new MathSuperScript({ children: b, superScript: s });
const ss = (b, s, p) => new MathSubSuperScript({ children: b, subScript: s, superScript: p });
const fr = (n, d) => new MathFraction({ numerator: n, denominator: d });
const it = (lo, hi, body) => new MathIntegral({ children: body, subScript: lo, superScript: hi });
const sm = (lo, hi, body) => new MathSum({ children: body, subScript: lo, superScript: hi });
const mu = s => sb([r("μ")], [r(s)]);
const abs = c => new MathRoundBrackets({ children: [r("§ABS§"), ...c] });
const EQ = {
  1: () => [fr([mu("inc"), r("(H)")], [mu("i")]), r("="),
            fr([r("1")], [r("1+"), sp([new MathRoundBrackets({ children: [fr([r("H")], [sb([r("H")], [r("0")])])] })], [r("n")])])],
  2: () => [r("B(H)="), mu("0"), mu("i"), it([r("0")], [r("H")], [fr([mu("inc"), r("(h)")], [mu("i")]), r("dh")])],
  3: () => [r("ΔB="), fr([sb([r("v")], [r("in")]), r("D"), sb([r("T")], [r("s")])], [r("N"), sb([r("A")], [r("e")])])],
  4: () => [sb([r("P")], [r("v")]), r("="), fr([r("1")], [sb([r("T")], [r("s")])]),
            it([r("0")], [sb([r("T")], [r("s")])], [sb([r("k")], [r("i")]),
              sp([abs([fr([r("dB")], [r("dt")])])], [r("α")]), sp([r("ΔB")], [r("β−α")]), r("dt")])],
  5: () => [sb([r("k")], [r("i")]), r("="),
            fr([r("k")], [sp([r("(2π)")], [r("α−1")]),
              it([r("0")], [r("2π")], [sp([abs([r("§COS§")])], [r("α")]), sp([r("2")], [r("β−α")]), r("dθ")])])],
  6: () => [sb([r("P")], [r("Cu")]), r("="), sb([r("R")], [r("CC")]), ss([r("I")], [r("ef")], [r("2")]), r("+"),
            sm([r("n=1")], [r("60")], [sb([r("R")], [r("CC")]), sb([r("F")], [r("R")]),
              r("(n"), sb([r("f")], [r("s")]), r(")"), fr([ss([r("I")], [r("n")], [r("2")])], [r("2")])])],
};

// ------------------------------------------------------------- utilitarios
function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
const P = (children, o = {}) => new Paragraph({ children, ...o });
const thin = { style: BorderStyle.SINGLE, size: 4, color: "000000" };
const ROMAN = { I: "I", II: "II", III: "III" };

function cellPar(text, size, align, bold, keep) {
  return P(runs(text, { size, bold }), { alignment: align, keepNext: !!keep, keepLines: true, spacing: { before: 0, after: 0 } });
}

function makeTable(tb) {
  const size = tb.size || 15;
  const W = tb.widths;
  const mk = (txt, idx, header, span = 1, rowSpan = 1, keep = true) => {
    const w = W.slice(idx, idx + span).reduce((a, b) => a + b, 0);
    const align = idx === 0 && !header ? AlignmentType.LEFT : AlignmentType.CENTER;
    return new TableCell({
      width: { size: w, type: WidthType.DXA }, columnSpan: span, rowSpan,
      verticalAlign: VerticalAlign.CENTER,
      margins: { top: 15, bottom: 15, left: 45, right: 45 },
      shading: header ? { type: ShadingType.CLEAR, fill: "D9D9D9", color: "auto" } : undefined,
      children: [cellPar(txt, size, align, header, keep)],
    });
  };
  const rows = [];
  tb.header.forEach((hr, hi) => {
    const cells = []; let idx = 0;
    if (hi > 0 && tb.header[0].some(c => typeof c === "object" && c.rowSpan > 1)) {
      // pula colunas ocupadas por rowSpan da linha anterior
      tb.header[0].forEach(c => { if (typeof c === "object" && c.rowSpan > 1) idx += (c.colSpan || 1); else return; });
    }
    hr.forEach(c => {
      const o = typeof c === "object" ? c : { text: c };
      cells.push(mk(o.text, idx, true, o.colSpan || 1, o.rowSpan || 1));
      idx += o.colSpan || 1;
    });
    rows.push(new TableRow({ children: cells, tableHeader: true }));
  });
  tb.rows.forEach((rw, ri) => rows.push(new TableRow({ children: rw.map((c, k) => mk(c, k, false, 1, 1, ri < tb.rows.length - 1)), cantSplit: true })));
  return new Table({
    width: { size: W.reduce((a, b) => a + b, 0), type: WidthType.DXA }, columnWidths: W, rows,
    borders: { top: thin, bottom: thin, left: thin, right: thin, insideHorizontal: thin, insideVertical: thin },
  });
}

// ------------------------------------------------------------- montagem
const head = [], body = [], txt = [];
for (const b of C) {
  switch (b.t) {
    case "title":
      head.push(P(runs(b.text, { size: 48 }), { alignment: AlignmentType.CENTER, spacing: { before: 0, after: 160 } }));
      txt.push(plain(b.text), ""); break;
    case "author":
      head.push(P(runs(b.text, { size: 22 }), { alignment: AlignmentType.CENTER, spacing: { after: 20 } }));
      txt.push(plain(b.text)); break;
    case "affil":
      head.push(P(runs(b.text, { size: 18, italics: true }), { alignment: AlignmentType.CENTER, spacing: { after: 240 } }));
      txt.push(plain(b.text), ""); break;
    case "abstract": case "keywords":
      body.push(P([...runs(b.label + " ", { size: 18, bold: true, italics: true }), ...runs(b.text, { size: 18, bold: true })],
        { alignment: AlignmentType.JUSTIFIED, indent: { firstLine: 202 }, spacing: { after: b.t === "keywords" ? 120 : 60 } }));
      txt.push(b.label + " " + plain(b.text), ""); break;
    case "h1":
      body.push(P(runs(b.text, { size: 20, smallCaps: true }), { alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 200, after: 100 } }));
      txt.push(plain(b.text).toUpperCase(), ""); break;
    case "h2":
      body.push(P(runs(b.text, { size: 20, italics: true }), { keepNext: true, spacing: { before: 100, after: 60 } }));
      txt.push(plain(b.text), ""); break;
    case "p":
      body.push(P(runs(b.text), { alignment: AlignmentType.JUSTIFIED, indent: { firstLine: b.noindent ? 0 : 202 }, spacing: { before: 0, after: 0 } }));
      txt.push(plain(b.text), ""); break;
    case "eq":
      body.push(new Paragraph({
        tabStops: [{ type: TabStopType.CENTER, position: COLW / 2 }, { type: TabStopType.RIGHT, position: COLW }],
        spacing: { before: 80, after: 80 },
        children: [new TextRun({ children: [new Tab()] }), new OMath({ children: EQ[b.n]() }),
                   new TextRun({ children: [new Tab(), `(${b.n})`], font: FONT, size: 20 })],
      }));
      txt.push(`    ${b.plain}    (${b.n})`, ""); break;
    case "fig": {
      const file = path.join(DIR, "fig", b.file), s = pngSize(file);
      const w = 336, h = Math.round(w * s.h / s.w);
      body.push(P([new ImageRun({ type: "png", data: fs.readFileSync(file), transformation: { width: w, height: h },
        altText: { title: `Fig. ${b.n}`, description: plain(b.caption), name: `fig${b.n}` } })],
        { alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 40 } }));
      body.push(P([new TextRun({ text: `Fig. ${b.n}. `, font: FONT, size: 16 }), ...runs(b.caption, { size: 16 })],
        { alignment: AlignmentType.JUSTIFIED, spacing: { after: 160 } }));
      txt.push(`[Figura ${b.n}: fig${b.n}.png]`, `Fig. ${b.n}. ${plain(b.caption)}`, ""); break;
    }
    case "table": {
      body.push(P(runs(`Tabela ${b.n}`, { size: 16, smallCaps: true }), { alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 160, after: 0 } }));
      body.push(P(runs(b.caption, { size: 16, smallCaps: true }), { alignment: AlignmentType.CENTER, keepNext: true, spacing: { after: 60 } }));
      body.push(makeTable(b));
      body.push(P([new TextRun({ text: "", size: 8 })], { spacing: { after: 120 } }));
      // texto
      const hdr = b.header.length === 1 ? b.header[0].map(c => plain(typeof c === "object" ? c.text : c))
        : ["Vac (V)", "Carga (%)", "Núcleo ref.", "Núcleo nano", "Δ núcleo (%)", "Cobre ref.", "Cobre nano", "Δ cobre (%)", "Total ref.", "Total nano", "Δ total (%)"];
      txt.push(`TABELA ${b.n}. ${plain(b.caption).toUpperCase()}`, "");
      txt.push(hdr.join(" | "));
      b.rows.forEach(rw => txt.push(rw.map(plain).join(" | ")));
      txt.push(""); break;
    }
    case "refs":
      b.items.forEach((it2, k) => {
        body.push(new Paragraph({
          tabStops: [{ type: TabStopType.LEFT, position: 360 }],
          indent: { left: 360, hanging: 360 }, alignment: AlignmentType.JUSTIFIED, spacing: { after: 20 },
          children: [new TextRun({ text: `[${k + 1}]`, font: FONT, size: 16 }), new TextRun({ children: [new Tab()], size: 16 }), ...runs(it2, { size: 16 })],
        }));
        txt.push(`[${k + 1}] ${plain(it2)}`);
      });
      break;
  }
}

const page = { size: { width: 11906, height: 16838 }, margin: { top: 1077, bottom: 2438, left: 794, right: 794, header: 709, footer: 709 } };
const doc = new Document({
  creator: "Andre Denzel", title: plain(C[0].text), language: "pt-BR",
  styles: { default: { document: { run: { font: FONT, size: 20 } } } },
  sections: [
    { properties: { page }, children: head },
    { properties: { type: SectionType.CONTINUOUS, page, column: { count: 2, space: 238, equalWidth: true } }, children: body },
  ],
});
Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  fs.writeFileSync(OUT_TXT, txt.join("\n"));
  console.log("ok", OUT, buf.length);
});
