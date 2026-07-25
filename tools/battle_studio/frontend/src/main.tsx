import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { getInitialBridgeUrl } from "./bridge-url";
import { DeckBuilder } from "./DeckBuilder";
import { initializeJapaneseUi } from "./locale";
import { installJapaneseNetworkErrors } from "./network";
import "./bridge-launch.css";
import "./mobile.css";
import "./layout-repair.css";
import "./deck-easy.css";
import "./simple-pocket.css";

initializeJapaneseUi();
getInitialBridgeUrl();
installJapaneseNetworkErrors();

const root = document.getElementById("root");
if (!root) throw new Error("#rootのアプリ表示領域がありません");

createRoot(root).render(
  <StrictMode>
    <App />
    <details className="app-shell deck-builder-shell deck-builder-drawer">
      <summary><strong>デッキ調整</strong><span>必要な時だけ開く</span></summary>
      <DeckBuilder importedDeck={null} />
    </details>
  </StrictMode>,
);

if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register("./sw.js");
  });
}
