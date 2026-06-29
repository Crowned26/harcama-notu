(function () {
  var fisBtn = document.getElementById("fisBtn");
  var fisInput = document.getElementById("fisInput");
  var fisStatus = document.getElementById("fisStatus");
  if (!fisBtn || !fisInput) return;

  var msgs = {
    reading: document.body.dataset.fisReading || "Fiş okunuyor…",
    done: document.body.dataset.fisDone || "Fiş okundu — kontrol edip kaydedin.",
    partial: document.body.dataset.fisPartial || "Kısmen okundu — eksik alanları doldurun.",
    fail: document.body.dataset.fisFail || "Okunamadı — alanları elle doldurun.",
    noDate: document.body.dataset.fisNoDate || "Tarih bulunamadı",
    noAmount: document.body.dataset.fisNoAmount || "Tutar bulunamadı"
  };

  function setStatus(text, kind) {
    if (!fisStatus) return;
    fisStatus.textContent = text;
    fisStatus.hidden = !text;
    fisStatus.className = "fis-status" + (kind ? " fis-" + kind : "");
  }

  function ocrFix(s) {
    return String(s)
      .replace(/[OoоQ]/g, "0")
      .replace(/[Il|]/g, "1")
      .replace(/Ş/g, "S").replace(/ş/g, "s")
      .replace(/İ/g, "I").replace(/ı/g, "i")
      .replace(/ğ/g, "g").replace(/Ğ/g, "G");
  }

  function toGray(data, w, h) {
    var g = new Uint8Array(w * h);
    for (var i = 0, p = 0; i < data.length; i += 4, p++) {
      g[p] = Math.round(0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]);
    }
    return g;
  }

  function otsuThreshold(gray) {
    var hist = new Array(256).fill(0);
    for (var i = 0; i < gray.length; i++) hist[gray[i]]++;
    var total = gray.length, sum = 0;
    for (var t = 0; t < 256; t++) sum += t * hist[t];
    var sumB = 0, wB = 0, best = 0, th = 128;
    for (var k = 0; k < 256; k++) {
      wB += hist[k];
      if (!wB) continue;
      var wF = total - wB;
      if (!wF) break;
      sumB += k * hist[k];
      var mB = sumB / wB, mF = (sum - sumB) / wF;
      var v = wB * wF * (mB - mF) * (mB - mF);
      if (v > best) { best = v; th = k; }
    }
    return th;
  }

  function findReceiptCrop(gray, w, h) {
    var col = new Array(w).fill(0), row = new Array(h).fill(0);
    for (var y = 0; y < h; y++) {
      for (var x = 0; x < w; x++) {
        if (gray[y * w + x] > 165) { col[x]++; row[y]++; }
      }
    }
    var cTh = h * 0.08, rTh = w * 0.08;
    var x0 = 0, x1 = w - 1, y0 = 0, y1 = h - 1;
    for (var a = 0; a < w; a++) if (col[a] > cTh) { x0 = a; break; }
    for (var b = w - 1; b >= 0; b--) if (col[b] > cTh) { x1 = b; break; }
    for (var c = 0; c < h; c++) if (row[c] > rTh) { y0 = c; break; }
    for (var d = h - 1; d >= 0; d--) if (row[d] > rTh) { y1 = d; break; }
    var pad = Math.round(Math.min(w, h) * 0.01);
    x0 = Math.max(0, x0 - pad);
    y0 = Math.max(0, y0 - pad);
    x1 = Math.min(w - 1, x1 + pad);
    y1 = Math.min(h - 1, y1 + pad);
    if (x1 - x0 < w * 0.2 || y1 - y0 < h * 0.2) return { x: 0, y: 0, w: w, h: h };
    return { x: x0, y: y0, w: x1 - x0 + 1, h: y1 - y0 + 1 };
  }

  function putGray(ctx, gray, w, h, invert) {
    var id = ctx.createImageData(w, h);
    for (var i = 0, p = 0; p < gray.length; p++, i += 4) {
      var v = invert ? (gray[p] > 128 ? 0 : 255) : gray[p];
      id.data[i] = id.data[i + 1] = id.data[i + 2] = v;
      id.data[i + 3] = 255;
    }
    ctx.putImageData(id, 0, 0);
  }

  function buildVariants(img) {
    var scale = 1;
    var minW = 2200;
    if (img.width < minW) scale = minW / img.width;
    if (img.height < 2800 && img.height > img.width) scale = Math.max(scale, 2800 / img.height);
    var w = Math.round(img.width * scale), h = Math.round(img.height * scale);

    var base = document.createElement("canvas");
    base.width = w; base.height = h;
    var bctx = base.getContext("2d");
    bctx.fillStyle = "#fff";
    bctx.fillRect(0, 0, w, h);
    bctx.drawImage(img, 0, 0, w, h);

    var id = bctx.getImageData(0, 0, w, h);
    var gray = toGray(id.data, w, h);
    var crop = findReceiptCrop(gray, w, h);

    var cw = crop.w, ch = crop.h;
    var cropped = new Uint8Array(cw * ch);
    for (var y = 0; y < ch; y++) {
      for (var x = 0; x < cw; x++) {
        cropped[y * cw + x] = gray[(crop.y + y) * w + (crop.x + x)];
      }
    }

    for (var i = 0; i < cropped.length; i++) {
      var g = (cropped[i] - 128) * 1.5 + 128;
      cropped[i] = g < 0 ? 0 : g > 255 ? 255 : g;
    }

    var th = otsuThreshold(cropped);
    var otsu = new Uint8Array(cropped.length);
    for (var j = 0; j < cropped.length; j++) otsu[j] = cropped[j] < th ? 0 : 255;

    var sharp = new Uint8Array(cropped.length);
    for (var y = 1; y < ch - 1; y++) {
      for (var x = 1; x < cw - 1; x++) {
        var i = y * cw + x;
        var v = 5 * cropped[i] - cropped[i - 1] - cropped[i + 1] - cropped[i - cw] - cropped[i + cw];
        sharp[i] = v < 0 ? 0 : v > 255 ? 255 : v;
      }
    }

    var variants = [];

    function addVariant(grayBuf, invert) {
      var c = document.createElement("canvas");
      c.width = cw; c.height = ch;
      putGray(c.getContext("2d"), grayBuf, cw, ch, invert);
      variants.push(c.toDataURL("image/png"));
    }

    addVariant(cropped, false);
    addVariant(sharp, false);
    addVariant(otsu, true);
    return variants;
  }

  function parseTrAmount(raw) {
    var s = String(raw).replace(/[^\d.,]/g, "");
    if (!s) return NaN;
    if (s.indexOf(",") >= 0 && s.indexOf(".") >= 0) s = s.replace(/\./g, "").replace(",", ".");
    else if (s.indexOf(",") >= 0) s = s.replace(",", ".");
    return parseFloat(s);
  }

  function extractAmounts(line) {
    var norm = String(line).replace(/#/g, "*").replace(/(\d)\s+(\d)/g, "$1$2");
    var out = [];
    var re = /\*?\s*\d{1,3}(?:\.\d{3})*,\d{2}|\*?\s*\d+[.,]\d{2}/g;
    var m;
    while ((m = re.exec(norm))) {
      var v = parseTrAmount(m[0]);
      if (!isNaN(v) && v > 0 && v < 1000000) out.push(v);
    }
    return out;
  }

  function dateFromParts(d, mo, y) {
    if (y < 100) y += 2000;
    if (y > 2100 && y < 3000) y = 2000 + (y % 100);
    if (d < 1 || d > 31 || mo < 1 || mo > 12 || y < 2000 || y > 2100) return null;
    return y + "-" + String(mo).padStart(2, "0") + "-" + String(d).padStart(2, "0");
  }

  function isTarLine(line) {
    return /TAR\w{0,3}H|DATE/i.test(ocrFix(line));
  }

  function pickTarih(text, lines) {
    var candidates = [];
    function add(dt, score) {
      if (dt) candidates.push({ dt: dt, score: score });
    }

    for (var i = 0; i < lines.length; i++) {
      if (isTarLine(lines[i])) {
        add(parseDateFromLine(lines[i]), 40);
        if (i + 1 < lines.length) add(parseDateFromLine(lines[i + 1]), 35);
        if (i + 2 < lines.length) add(parseDateFromLine(lines[i + 2]), 30);
      }
    }

    var near = ocrFix(text).match(/TAR\w{0,3}H\s*:?\s*(\d{1,2})\s*[./\-]\s*(\d{1,2})\s*[./\-]\s*(\d{2,4})/i);
    if (near) add(dateFromParts(parseInt(near[1], 10), parseInt(near[2], 10), parseInt(near[3], 10)), 38);

    for (var j = 0; j < Math.min(lines.length, 22); j++) {
      var ln = lines[j].trim();
      if (ln.length <= 14 && /^\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}$/.test(ocrFix(ln).replace(/\s/g, ""))) {
        add(parseDateFromLine(ln), 25);
      }
    }

    var re = /(\d{1,2})\s*[./\-]\s*(\d{1,2})\s*[./\-]\s*(\d{2,4})/g;
    var m, fixed = ocrFix(text);
    while ((m = re.exec(fixed))) {
      var dt = dateFromParts(parseInt(m[1], 10), parseInt(m[2], 10), parseInt(m[3], 10));
      if (dt) {
        var y = parseInt(dt.slice(0, 4), 10);
        add(dt, y >= 2015 && y <= 2030 ? 12 : 3);
      }
    }

    if (!candidates.length) return null;
    candidates.sort(function (a, b) { return b.score - a.score; });
    return candidates[0].dt;
  }

  function parseDateFromLine(line) {
    var s = ocrFix(line);
    var m = s.match(/(\d{1,2})\s*[./\-]\s*(\d{1,2})\s*[./\-]\s*(\d{2,4})/);
    if (m) return dateFromParts(parseInt(m[1], 10), parseInt(m[2], 10), parseInt(m[3], 10));
    m = s.match(/(\d{1,2})\s+(\d{1,2})\s+(\d{4})/);
    if (m) return dateFromParts(parseInt(m[1], 10), parseInt(m[2], 10), parseInt(m[3], 10));
    return null;
  }

  function parseFisText(text) {
    var lines = text.split(/\r?\n/).map(function (l) { return l.trim(); }).filter(Boolean);
    var tarih = pickTarih(text, lines);

    var totalKeys = /GENEL\s*TOPLAM|^TOPLAM|ÖDENECEK|ODENECEK|NET\s*TUTAR|TAHS[Iİ]L|KRED[Iİ]|NAK[Iİ]T/i;
    var skipTotal = /TOPKDV|TOPKD[^A]|KDV\s*TOP|Kg\s*X|X\s*\d/i;
    var tutar = null;
    var candidates = [];
    for (var j = 0; j < lines.length; j++) {
      var line = ocrFix(lines[j]);
      if (skipTotal.test(line)) continue;
      if (totalKeys.test(line)) {
        var nums = extractAmounts(lines[j]);
        if (!nums.length && j + 1 < lines.length) nums = extractAmounts(lines[j + 1]);
        candidates = candidates.concat(nums);
      }
    }
    if (candidates.length) tutar = Math.max.apply(null, candidates);

    if (!tutar) {
      var all = [];
      lines.forEach(function (ln) {
        if (!skipTotal.test(ocrFix(ln))) all = all.concat(extractAmounts(ln));
      });
      if (all.length) {
        all.sort(function (a, b) { return b - a; });
        tutar = all[0];
      }
    }

    var aciklama = "";
    var storeRe = /MARKET|MIGROS|BIM|A101|ŞOK|SOK|CARREFOUR|TEKEL|ECZANE/i;
    for (var k = 0; k < lines.length; k++) {
      if (storeRe.test(lines[k])) {
        aciklama = lines[k].replace(/[^\w\sÇĞİÖŞÜçğıöşü&.-]/g, " ").trim().slice(0, 60);
        break;
      }
    }
    if (!aciklama) {
      for (var n = 0; n < Math.min(lines.length, 8); n++) {
        var ln2 = lines[n].replace(/[^\w\sÇĞİÖŞÜçğıöşü&.-]/g, " ").trim();
        if (ln2.length >= 3 && /[A-Za-zÇĞİÖŞÜ]/.test(ln2) && !/^\d+[.,]?\d*$/.test(ln2)) {
          aciklama = ln2.slice(0, 60);
          break;
        }
      }
    }
    if (!aciklama) aciklama = "Fiş";

    return { tarih: tarih, tutar: tutar, aciklama: aciklama };
  }

  function mergeTexts(texts) {
    var seen = {}, out = [];
    texts.forEach(function (t) {
      t.split(/\r?\n/).forEach(function (line) {
        line = line.trim();
        if (!line || line.length < 2) return;
        var key = ocrFix(line).replace(/\s+/g, " ").toUpperCase();
        if (!seen[key]) { seen[key] = true; out.push(line); }
      });
    });
    return out.join("\n");
  }

  function loadImage(file) {
    return new Promise(function (resolve, reject) {
      var img = new Image();
      var url = URL.createObjectURL(file);
      img.onload = function () { URL.revokeObjectURL(url); resolve(img); };
      img.onerror = reject;
      img.src = url;
    });
  }

  function recognizeAll(variants, onProgress) {
    var psms = ["4", "6"];
    var jobs = [];
    variants.forEach(function (v) { psms.forEach(function (p) { jobs.push({ img: v, psm: p }); }); });

    return Tesseract.createWorker("tur+eng", 1, {
      logger: function () {}
    }).then(function (worker) {
      var texts = [], step = 0;
      function next() {
        if (step >= jobs.length) {
          return worker.terminate().then(function () { return texts; });
        }
        var job = jobs[step++];
        if (onProgress) onProgress(step, jobs.length);
        return worker.setParameters({ tessedit_pageseg_mode: job.psm }).then(function () {
          return worker.recognize(job.img);
        }).then(function (res) {
          texts.push(res.data.text || "");
          return next();
        });
      }
      return next();
    });
  }

  function fillForm(data) {
    var aciklama = document.querySelector("[name=aciklama]");
    var tutar = document.querySelector("[name=tutar]");
    var tarih = document.getElementById("tarihInp");
    var tip = document.querySelector("[name=tip]");
    if (aciklama && data.aciklama) aciklama.value = data.aciklama;
    if (tutar && data.tutar) tutar.value = data.tutar.toFixed(2);
    if (tarih && data.tarih) tarih.value = data.tarih;
    if (tip) tip.value = "gider";
    if (tutar) tutar.dispatchEvent(new Event("input"));
    document.getElementById("add").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  fisBtn.onclick = function () { fisInput.click(); };

  fisInput.onchange = function () {
    var file = fisInput.files && fisInput.files[0];
    fisInput.value = "";
    if (!file || !window.Tesseract) {
      setStatus(msgs.fail, "warn");
      return;
    }
    fisBtn.disabled = true;
    setStatus(msgs.reading, "load");

    loadImage(file).then(function (img) {
      var variants = buildVariants(img);
      return recognizeAll(variants, function (cur, total) {
        setStatus(msgs.reading + " (" + cur + "/" + total + ")", "load");
      });
    }).then(function (texts) {
      var merged = mergeTexts(texts);
      var parsed = parseFisText(merged);
      fillForm(parsed);
      var notes = [];
      if (!parsed.tarih) notes.push(msgs.noDate);
      if (!parsed.tutar) notes.push(msgs.noAmount);
      if (parsed.tarih && parsed.tutar) setStatus(msgs.done, "ok");
      else if (parsed.tarih || parsed.tutar) setStatus(msgs.partial + (notes.length ? " (" + notes.join(", ") + ")" : ""), "warn");
      else setStatus(msgs.fail, "warn");
    }).catch(function () {
      setStatus(msgs.fail, "warn");
    }).finally(function () {
      fisBtn.disabled = false;
    });
  };

  if (typeof window !== "undefined") window.parseFisText = parseFisText;
})();
