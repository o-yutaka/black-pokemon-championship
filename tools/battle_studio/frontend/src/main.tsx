import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { getInitialBridgeUrl } from "./bridge-url";
import { DeckBuilder } from "./DeckBuilder";
import { initializeJapaneseUi } from "./locale";
import { installJapaneseNetworkErrors } from "./network";
import "./bridge-launch.css";
import "./mobile.css";

initializeJapaneseUi();
getInitialBridgeUrl();
installJapaneseNetworkErrors();

const root = document.getElementById("root");
if (!root) throw new Error("#rootのアプリ表示領域がありません");

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
