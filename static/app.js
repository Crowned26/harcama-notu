(function () {
  var html = document.documentElement;
  var dark = localStorage.getItem("theme") === "dark" || html.dataset.dark === "1";
  html.classList.toggle("dark", dark);

  var btn = document.getElementById("themeBtn");
  if (btn) btn.onclick = function () {
    dark = !html.classList.contains("dark");
    html.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
    fetch("/theme", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dark: dark }) });
    document.getElementById("themeIcon").textContent = dark ? "☀" : "☾";
  };

  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/static/sw.js").catch(function () {});

  var vbtn = document.getElementById("voiceBtn");
  if (vbtn && (window.SpeechRecognition || window.webkitSpeechRecognition)) {
    var R = window.SpeechRecognition || window.webkitSpeechRecognition;
    vbtn.onclick = function () {
      var r = new R();
      r.lang = document.documentElement.lang === "en" ? "en-US" : "tr-TR";
      r.onresult = function (e) {
        var t = e.results[0][0].transcript;
        var parts = t.trim().split(/\s+/);
        var amount = parseFloat(parts[parts.length - 1].replace(",", "."));
        if (!isNaN(amount)) {
          document.querySelector("[name=aciklama]").value = parts.slice(0, -1).join(" ") || t;
          document.querySelector("[name=tutar]").value = amount;
        } else document.querySelector("[name=aciklama]").value = t;
      };
      r.start();
    };
  } else if (vbtn) vbtn.style.display = "none";

  var kurlar = { usd: parseFloat(document.body.dataset.usd || "0"), eur: parseFloat(document.body.dataset.eur || "0") };
  var dovizSel = document.getElementById("dovizSel");
  var tutarInp = document.querySelector("[name=tutar]");
  var kurBox = document.getElementById("kurOnizleme");
  var kurMetin = document.getElementById("kurMetin");
  var approxTpl = document.body.dataset.approxTry || "≈ {amount} TL";

  function kurGuncelle() {
    fetch("/api/kurlar").then(function (r) { return r.json(); }).then(function (d) {
      kurlar.usd = d.usd;
      kurlar.eur = d.eur;
      kurOnizle();
    }).catch(function () {});
  }

  function kurOnizle() {
    if (!dovizSel || !tutarInp || !kurBox) return;
    var dv = dovizSel.value;
    var amt = parseFloat(String(tutarInp.value).replace(",", "."));
    if (dv === "TRY" || isNaN(amt) || amt <= 0) {
      kurBox.hidden = true;
      return;
    }
    var kur = dv === "USD" ? kurlar.usd : kurlar.eur;
    if (!kur) {
      kurGuncelle();
      return;
    }
    kurMetin.textContent = approxTpl.replace("{amount}", (amt * kur).toFixed(2));
    kurBox.hidden = false;
  }

  if (dovizSel) {
    dovizSel.addEventListener("change", kurOnizle);
    tutarInp.addEventListener("input", kurOnizle);
    kurOnizle();
    kurGuncelle();
  }

  var h = parseInt(document.body.dataset.reminder || "0", 10);
  if (h > 0 && "Notification" in window) {
    Notification.requestPermission().then(function (p) {
      if (p === "granted") setInterval(function () {
        var n = new Date();
        if (n.getHours() === h && n.getMinutes() < 2) new Notification("Harcama Notu", { body: "Bugün harcama girdin mi?" });
      }, 60000);
    });
  }
})();
