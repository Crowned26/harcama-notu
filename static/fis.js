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

  function parseTrAmount(raw) {
    var s = String(raw).replace(/[^\d.,]/g, "");
    if (!s) return NaN;
    if (s.indexOf(",") >= 0 && s.indexOf(".") >= 0) s = s.replace(/\./g, "").replace(",", ".");
    else if (s.indexOf(",") >= 0) s = s.replace(",", ".");
    return parseFloat(s);
  }

  function extractAmounts(line) {
    var out = [];
    var re = /\d{1,3}(?:\.\d{3})*,\d{2}|\d+[.,]\d{2}|\d+/g;
    var m;
    while ((m = re.exec(line))) {
      var v = parseTrAmount(m[0]);
      if (!isNaN(v) && v > 0 && v < 1000000) out.push(v);
    }
    return out;
  }

  function parseFisText(text) {
    var lines = text.split(/\r?\n/).map(function (l) { return l.trim(); }).filter(Boolean);
    var joined = lines.join("\n");
    var dateRe = /\b(\d{1,2})[./](\d{1,2})[./](\d{2,4})\b/g;
    var dates = [];
    var dm;
    while ((dm = dateRe.exec(joined))) {
      var d = parseInt(dm[1], 10), mo = parseInt(dm[2], 10), y = parseInt(dm[3], 10);
      if (y < 100) y += 2000;
      if (d >= 1 && d <= 31 && mo >= 1 && mo <= 12) {
        dates.push(y + "-" + String(mo).padStart(2, "0") + "-" + String(d).padStart(2, "0"));
      }
    }
    var tarih = null;
    for (var i = 0; i < lines.length; i++) {
      if (/TAR[Iİ]H|DATE/i.test(lines[i]) && dates.length) {
        tarih = dates[0];
        break;
      }
    }
    if (!tarih && dates.length) tarih = dates[dates.length - 1];

    var totalKeys = /GENEL\s*TOPLAM|TOPLAM|ÖDENECEK|ODENECEK|NET\s*TUTAR|TAHS[Iİ]L/i;
    var tutar = null;
    var candidates = [];
    for (var j = 0; j < lines.length; j++) {
      if (totalKeys.test(lines[j])) {
        var nums = extractAmounts(lines[j]);
        if (!nums.length && j + 1 < lines.length) nums = extractAmounts(lines[j + 1]);
        candidates = candidates.concat(nums);
      }
    }
    if (candidates.length) tutar = Math.max.apply(null, candidates);
    if (!tutar) {
      var all = [];
      lines.forEach(function (ln) { all = all.concat(extractAmounts(ln)); });
      if (all.length) tutar = Math.max.apply(null, all);
    }

    var aciklama = "";
    for (var k = 0; k < Math.min(lines.length, 5); k++) {
      var ln = lines[k].replace(/[^\w\sÇĞİÖŞÜçğıöşü&.-]/g, " ").trim();
      if (ln.length >= 3 && /[A-Za-zÇĞİÖŞÜ]/.test(ln) && !/^\d+[.,]?\d*$/.test(ln)) {
        aciklama = ln.slice(0, 60);
        break;
      }
    }
    if (!aciklama) aciklama = "Fiş";

    return { tarih: tarih, tutar: tutar, aciklama: aciklama };
  }

  function resizeImage(file) {
    return new Promise(function (resolve, reject) {
      var img = new Image();
      var url = URL.createObjectURL(file);
      img.onload = function () {
        var w = img.width, h = img.height, max = 1600;
        if (w > max) { h = Math.round(h * max / w); w = max; }
        var c = document.createElement("canvas");
        c.width = w; c.height = h;
        c.getContext("2d").drawImage(img, 0, 0, w, h);
        URL.revokeObjectURL(url);
        resolve(c.toDataURL("image/jpeg", 0.85));
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
    resizeImage(file).then(function (dataUrl) {
      return Tesseract.recognize(dataUrl, "tur+eng", {
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
})();
