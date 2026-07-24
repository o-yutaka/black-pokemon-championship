import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { getInitialBridgeUrl } from "./bridge-url";
import { DeckBuilder } from "./DeckBuilder";
import "./mobile.css";

getInitialBridgeUrl();

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root application mount");

createRoot(root).render(
  <StrictMode>
    <App />
    <div className="app-shell deck-builder-shell">
      <DeckBuilder importedDeck={null} />
    </div>
  </StrictMode>,
);

if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register("./sw.js");
  });
}
