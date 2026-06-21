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
