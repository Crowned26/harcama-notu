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
      .replace(/[Ooо]/g, "0")
      .replace(/[Il|]/g, "1")
      .replace(/Ş/g, "S").replace(/ş/g, "s")
      .replace(/İ/g, "I").replace(/ı/g, "i");
  }

  function parseTrAmount(raw) {
    var s = String(raw).replace(/[^\d.,]/g, "");
    if (!s) return NaN;
    if (s.indexOf(",") >= 0 && s.indexOf(".") >= 0) s = s.replace(/\./g, "").replace(",", ".");
    else if (s.indexOf(",") >= 0) s = s.replace(",", ".");
    return parseFloat(s);
  }

  function extractAmounts(line) {
    var out = [];
    var re = /\*?\s*\d{1,3}(?:\.\d{3})*,\d{2}|\*?\s*\d+[.,]\d{2}/g;
    var m;
    while ((m = re.exec(line))) {
      var v = parseTrAmount(m[0]);
      if (!isNaN(v) && v > 0 && v < 1000000) out.push(v);
    }
    return out;
  }

  function dateFromParts(d, mo, y) {
    if (y < 100) y += 2000;
    if (d < 1 || d > 31 || mo < 1 || mo > 12 || y < 2000 || y > 2100) return null;
    return y + "-" + String(mo).padStart(2, "0") + "-" + String(d).padStart(2, "0");
  }

  function parseDateFromLine(line) {
    var s = ocrFix(line);
    var patterns = [
      /(\d{1,2})\s*[./\-]\s*(\d{1,2})\s*[./\-]\s*(\d{2,4})/,
      /(\d{1,2})\s+(\d{1,2})\s+(\d{4})/
    ];
    for (var i = 0; i < patterns.length; i++) {
      var m = s.match(patterns[i]);
      if (m) {
        var dt = dateFromParts(parseInt(m[1], 10), parseInt(m[2], 10), parseInt(m[3], 10));
        if (dt) return dt;
      }
    }
    return null;
  }

  function findAllDates(text) {
    var dates = [];
    var s = ocrFix(text);
    var re = /(\d{1,2})\s*[./\-]\s*(\d{1,2})\s*[./\-]\s*(\d{2,4})/g;
    var m;
    while ((m = re.exec(s))) {
      var dt = dateFromParts(parseInt(m[1], 10), parseInt(m[2], 10), parseInt(m[3], 10));
      if (dt) dates.push(dt);
    }
    return dates;
  }

  function parseFisText(text) {
    var lines = text.split(/\r?\n/).map(function (l) { return l.trim(); }).filter(Boolean);
    var fixed = ocrFix(text);
    var tarih = null;

    for (var i = 0; i < lines.length; i++) {
      var ln = ocrFix(lines[i]);
      if (/TAR[Iİ1L]H|DATE/i.test(ln)) {
        tarih = parseDateFromLine(lines[i]);
        if (!tarih && i + 1 < lines.length) tarih = parseDateFromLine(lines[i + 1]);
        if (tarih) break;
      }
    }

    if (!tarih) {
      var near = fixed.match(/TAR[Iİ1L]H\s*:?\s*(\d{1,2})\s*[./\-]\s*(\d{1,2})\s*[./\-]\s*(\d{2,4})/i);
      if (near) tarih = dateFromParts(parseInt(near[1], 10), parseInt(near[2], 10), parseInt(near[3], 10));
    }

    if (!tarih) {
      var all = findAllDates(text);
      if (all.length) tarih = all[0];
    }

    var totalKeys = /GENEL\s*TOPLAM|^TOPLAM|ÖDENECEK|ODENECEK|NET\s*TUTAR|TAHS[Iİ]L/i;
    var skipTotal = /TOPKDV|KDV\s*TOP/i;
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

  function preprocessCanvas(img) {
    var w = img.width, h = img.height;
    var scale = 1;
    if (w < 1400) scale = Math.max(scale, 1400 / w);
    if (h < 2000 && h > w) scale = Math.max(scale, 2000 / h);
    if (scale > 1) { w = Math.round(w * scale); h = Math.round(h * scale); }

    var c = document.createElement("canvas");
    c.width = w; c.height = h;
    var ctx = c.getContext("2d");
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, w, h);
    ctx.drawImage(img, 0, 0, w, h);

    var id = ctx.getImageData(0, 0, w, h);
    var d = id.data;
    for (var i = 0; i < d.length; i += 4) {
      var g = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
      g = (g - 128) * 1.35 + 128;
      g = g < 0 ? 0 : g > 255 ? 255 : g;
      d[i] = d[i + 1] = d[i + 2] = g;
    }
    ctx.putImageData(id, 0, 0);
    return c.toDataURL("image/png");
  }

  function preprocessImage(file) {
    return new Promise(function (resolve, reject) {
      var img = new Image();
      var url = URL.createObjectURL(file);
      img.onload = function () {
        URL.revokeObjectURL(url);
        resolve(preprocessCanvas(img));
      };
      img.onerror = reject;
      img.src = url;
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
    preprocessImage(file).then(function (dataUrl) {
      return Tesseract.recognize(dataUrl, "tur+eng", {
        tessedit_pageseg_mode: "6",
        logger: function (m) {
          if (m.status === "recognizing text" && fisStatus) {
            setStatus(msgs.reading + " " + Math.round((m.progress || 0) * 100) + "%", "load");
          }
        }
      });
    }).then(function (res) {
      var parsed = parseFisText(res.data.text || "");
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
