(async function () {
  "use strict";
  const form = document.getElementById("archive-search");
  if (!form) return;
  const phrase = document.getElementById("phrase");
  const author = document.getElementById("author");
  const status = document.getElementById("results-status");
  const results = document.getElementById("search-results");
  let messages;
  function search() {
    const query = phrase.value.trim().toLocaleLowerCase();
    const matches = messages.filter(message =>
      (!author.value || message.author === author.value) &&
      (!query || message.text.toLocaleLowerCase().includes(query))
    );
    results.replaceChildren();
    const shown = matches.slice(0, 12);
    status.textContent = matches.length
      ? matches.length + " matching " + (matches.length === 1 ? "message" : "messages") + (matches.length > shown.length ? "; showing the first " + shown.length : "")
      : "No matches. Try another phrase or choose Everyone.";
    for (const message of shown) {
      const item = document.createElement("li");
      const metadata = document.createElement("div");
      metadata.className = "message-meta";
      const name = document.createElement("strong");
      name.textContent = message.author;
      metadata.append(name, document.createTextNode(message.date + " " + message.time));
      const text = document.createElement("p");
      text.textContent = message.text;
      item.append(metadata, text);
      results.append(item);
    }
  }
  try {
    const response = await fetch("assets/sample-archive.json");
    if (!response.ok) throw new Error("Sample unavailable");
    messages = await response.json();
    search();
    form.addEventListener("submit", event => { event.preventDefault(); search(); });
    author.addEventListener("change", search);
    phrase.addEventListener("search", search);
  } catch (_) {
    status.textContent = "The sample could not load. Reload this page or read the command walkthrough below.";
    form.querySelector("button").disabled = true;
  }
})();
