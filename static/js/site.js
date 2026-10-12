// Small touches of motion for the public café pages: fade sections in as they scroll into view,
// and give the header a shadow once the page has scrolled. Everything still shows without JavaScript.
(function () {
  "use strict";
  window.cafeMotion = true;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var revealables = document.querySelectorAll("[data-reveal]");

  if (reduceMotion || !("IntersectionObserver" in window)) {
    revealables.forEach(function (el) { el.classList.add("is-in"); });
  } else {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-in");
        observer.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    revealables.forEach(function (el) {
      if (el.dataset.reveal === "stagger") {
        Array.prototype.forEach.call(el.children, function (child, i) {
          child.style.setProperty("--i", Math.min(i, 8));
        });
      }
      observer.observe(el);
    });
  }

  var header = document.querySelector(".site-header");
  if (header) {
    var onScroll = function () { header.classList.toggle("is-scrolled", window.scrollY > 40); };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }
})();
